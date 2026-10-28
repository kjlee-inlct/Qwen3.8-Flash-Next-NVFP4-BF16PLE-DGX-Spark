"""P1: minimal falsifiable tests of strict Preview prefix patch staging.

These test synthetic *source shapes* only. The installed-source SHA-specific
staging executes in an explicit disposable CPU-only container, never here.
"""
import ast
import hashlib
import tempfile
import unittest
from pathlib import Path

from src import preview_p1_prefix_candidate as candidate


WORKER = """
class MambaHybridModelState:
    def add_request(self, req_index, new_req_data):
        if self._align_mode:
            self._mamba_state_idx_gpu[req_index].fill_(
                (new_req_data.num_computed_tokens - 1)
                // self.cache_config.block_size
            )
"""
SCHEDULER = """
class Scheduler:
    def _mamba_block_aligned_split(self, request, n, computed, external):
        block_size = self.cache_config.block_size
        return (n // block_size) * block_size
"""


def digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


class PreviewPrefixCandidateTests(unittest.TestCase):
    def test_two_exact_only_expression_changes(self):
        for label, original, before, after in (
            ("mamba", WORKER, candidate.OLD_WORKER, candidate.NEW_WORKER),
            ("scheduler", SCHEDULER, candidate.OLD_SCHED, candidate.NEW_SCHED),
        ):
            with self.subTest(label=label):
                result = candidate.patch_source(
                    label, original.encode(), digest(original))
                self.assertEqual(result, original.encode().replace(before, after))
                ast.parse(result)
                self.assertEqual(result.count(after), 1)
                self.assertEqual(result.count(before), 0)

    def test_source_sha_drift_is_fail_closed(self):
        with self.assertRaises(candidate.Blocked) as cm:
            candidate.patch_source("mamba", WORKER.encode(), "0" * 64)
        self.assertEqual(cm.exception.code, "PREVIEW_SOURCE_SHA_DRIFT")

    def test_worker_requires_align_seed_call_not_unrelated_division(self):
        tampered = WORKER.replace(
            "self._mamba_state_idx_gpu[req_index].fill_",
            "other_data[req_index].fill_")
        with self.assertRaises(candidate.Blocked) as cm:
            candidate.patch_source("mamba", tampered.encode(), digest(tampered))
        self.assertEqual(cm.exception.code, "MAMBA_SEED_CALL_DRIFT")
        tampered = WORKER.replace("if self._align_mode:", "if self.enable_cache:")
        with self.assertRaises(candidate.Blocked) as cm:
            candidate.patch_source("mamba", tampered.encode(), digest(tampered))
        self.assertEqual(cm.exception.code, "MAMBA_ALIGN_BRANCH_DRIFT")

    def test_scheduler_multiple_writes_are_rejected(self):
        tampered = SCHEDULER.replace(
            "return (n // block_size) * block_size",
            "block_size = self.other_block\n        return block_size")
        with self.assertRaises(candidate.Blocked) as cm:
            candidate.patch_source(
                "scheduler", tampered.encode(), digest(tampered))
        self.assertEqual(cm.exception.code, "SCHEDULER_BLOCK_VARIABLE_DRIFT")

    def test_installed_entry_is_explicit_and_does_not_write_package(self):
        self.assertEqual(candidate.main([]), 2)
        source = Path(candidate.__file__).read_text()
        self.assertIn("PREVIEW_SOURCE_SHA_DRIFT", source)
        self.assertIn("TemporaryDirectory(", source)
        self.assertIn("installed_package_modified", source)
        for forbidden in (
            "torch.cuda", "docker exec", "docker stop", "requests.post",
            "subprocess.run", "import vllm", "CUDA_VISIBLE_DEVICES=0",
        ):
            self.assertNotIn(forbidden, source)
        self.assertTrue(all(len(h) == 64 for _, h in candidate.SPECS.values()))


if __name__ == "__main__":
    unittest.main()
