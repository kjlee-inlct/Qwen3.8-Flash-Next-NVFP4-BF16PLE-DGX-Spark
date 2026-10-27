"""Phase 5 exact-file preflight (source-only; zero engine imports or patches)."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from src.phase5_patch_readiness import (
    PATHS, PIN, classify_patch_preflight, inspect_source_tree,
)


def write(root: Path, label: str, source: str) -> None:
    path = root / PATHS[label]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


MAMBA = (
    "class MambaHybridModelState:\n"
    " def add_request(self, req_index, new_req_data):\n"
    "  return (new_req_data.num_computed_tokens - 1) // self.cache_config.block_size\n"
)
SCHED = (
    "class Scheduler:\n"
    " def _mamba_block_aligned_split(self, request):\n"
    "  block_size = self.cache_config.block_size\n"
    "  # The last block-aligned position whose state can be cached.\n"
    "  return block_size\n"
)
MTP = (
    "class Qwen3_8FlashNextMTP:\n"
    " def compute_logits(self, hidden_states, spec_step_idx=0):\n"
    "  return self.lm_head.weight\n"
    " def load_weights(self, weights): pass\n"
)


class Phase5PatchReadinessTests(unittest.TestCase):
    def test_missing_source_never_certifies_or_approves_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_source_tree(Path(tmp))
            self.assertEqual(result["pinned_blazux"], PIN)
            self.assertEqual(result["status"], "SOURCE_ONLY_NOT_PATCH_OR_ABI_CERTIFIED")
            self.assertEqual(result["preflight"]["mamba_scheduler"]["status"],
                             "SOURCE_MISSING_OR_UNPARSEABLE")
            self.assertEqual(
                result["preflight"]["mtp_reduced_draft_vocabulary"]["status"],
                "MTP_SOURCE_MISSING_OR_UNPARSEABLE")
            for value in result["preflight"].values():
                self.assertNotIn("APPROVED", value["status"])

    def test_legacy_mamba_and_scheduler_remain_unsafe_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "mamba", MAMBA)
            write(root, "scheduler", SCHED)
            result = inspect_source_tree(root)
            mamba = result["preflight"]["mamba_scheduler"]
            self.assertEqual(mamba["status"], "SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY")
            self.assertEqual(result["components"]["mamba"]["anchor_counts"][
                "self.cache_config.block_size"], 1)
            self.assertIn("cache_config creation", mamba["requires"])
            fingerprint = result["components"]["mamba"]["method_fingerprints"][0]
            self.assertEqual(fingerprint["method"], "add_request")
            self.assertEqual(fingerprint["signature"], ["self", "req_index", "new_req_data"])
            self.assertEqual(len(fingerprint["ast_sha256"]), 64)

    def test_native_code_without_legacy_preimage_is_not_directly_patchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "mamba", MAMBA.replace(
                "self.cache_config.block_size", "self.cache_config.mamba_block_size"))
            write(root, "scheduler", SCHED)
            output = inspect_source_tree(root)["preflight"]["mamba_scheduler"]
            self.assertEqual(output["status"], "PREIMAGE_MISMATCH_OR_NATIVE_REVIEW")

    def test_parser_and_responses_need_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label in (
                "parser_engine", "qwen3", "adapters", "abstract_parser",
                "responses_serving", "responses_protocol", "stream", "config",
            ):
                write(root, label, "class Dummy: pass\n")
            output = inspect_source_tree(root)["preflight"]
            self.assertEqual(output["tool_argument_schema"]["status"],
                             "MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED")
            self.assertEqual(output["tool_literal_marker"]["status"],
                             "MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED")
            self.assertEqual(output["responses_terminal"]["status"],
                             "PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED")
            for label in ("tool_argument_schema", "tool_literal_marker",
                          "responses_terminal"):
                self.assertNotIn("APPROVED", output[label]["status"])

    def test_mtp_compute_logits_signature_is_candidate_not_engine_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "mtp_nvidia", MTP)
            result = inspect_source_tree(root)
            records = result["components"]["mtp_nvidia"]["method_fingerprints"]
            self.assertEqual(
                {r["method"] for r in records}, {"compute_logits", "load_weights"})
            self.assertEqual(
                result["preflight"]["mtp_reduced_draft_vocabulary"]["status"],
                "MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED")
            self.assertEqual(records[0]["signature"],
                             ["self", "hidden_states", "spec_step_idx"])

    def test_source_sha_is_exact_bytes_and_unparseable_is_no_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "mtp_nvidia", MTP)
            result = inspect_source_tree(root)
            expected = hashlib.sha256(MTP.encode()).hexdigest()
            self.assertEqual(result["components"]["mtp_nvidia"]["sha256"], expected)
            write(root, "mtp_nvidia", "class Qwen3_8FlashNextMTP(\n")
            result = inspect_source_tree(root)
            self.assertEqual(result["components"]["mtp_nvidia"]["state"], "UNPARSEABLE")
            self.assertEqual(result["preflight"]["mtp_reduced_draft_vocabulary"]["status"],
                             "MTP_SOURCE_MISSING_OR_UNPARSEABLE")

    def test_symlink_source_is_skipped_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vllm"
            root.mkdir()
            outside = Path(tmp) / "outside.py"
            outside.write_text(MTP, encoding="utf-8")
            path = root / PATHS["mtp_nvidia"]
            path.parent.mkdir(parents=True)
            path.symlink_to(outside)
            result = inspect_source_tree(root)
            self.assertEqual(result["components"]["mtp_nvidia"]["state"],
                             "SYMLINK_IGNORED")

    def test_helper_classification_never_uses_apply_approved(self):
        samples = {
            "mtp_nvidia": {
                "state": "PARSEABLE_ONLY", "anchor_counts": {},
                "method_fingerprints": [{"method": "compute_logits"},
                                        {"method": "load_weights"}],
            }
        }
        result = classify_patch_preflight(samples)
        self.assertEqual(len(result), 5)
        for item in result.values():
            self.assertNotEqual(item["status"], "APPLY_APPROVED")
            self.assertTrue(item["requires"])


if __name__ == "__main__":
    unittest.main()
