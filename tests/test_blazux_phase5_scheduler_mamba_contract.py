"""Synthetic AST/CPU-only tests; never import installed vLLM or execute GPU."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import phase5_scheduler_mamba_contract as audit

CFG = (
    "class SchedulerConfig:\n"
    " def get_scheduler_cls(self):\n"
    "  if self.scheduler_cls is not None:\n"
    "   return self.scheduler_cls\n"
    "  return DefaultScheduler\n"
)
ENGINE = (
    "class EngineCore:\n"
    " def __init__(self, vllm_config):\n"
    "  Scheduler = vllm_config.scheduler_config.get_scheduler_cls()\n"
    "  scheduler_block_size = 32\n"
    "  self.scheduler = Scheduler(block_size=scheduler_block_size)\n"
)
WORKER = (
    "class MambaHybridModelState:\n"
    " def add_request(self, req):\n"
    "  return (req.num_computed_tokens - 1) // self.cache_config.block_size\n"
    " def _get_mamba_group_info(self, groups, mamba_spec):\n"
    "  assert all(spec.block_size == mamba_spec.block_size for spec in groups)\n"
    " def _ensure_align_ctx(self, groups):\n"
    "  return self._mamba_ctx\n"
    " def preprocess_state(self, mamba_spec):\n"
    "  preprocess_mamba_align_fused_kernel[grid](MAMBA_BLOCK_SIZE=mamba_spec.block_size)\n"
    " def postprocess_state(self):\n"
    "  self._mamba_ctx.run_fused_postprocess_align(1)\n"
)
SCHED = (
    "class Scheduler:\n"
    " def __init__(self, block_size):\n"
    "  self.block_size = block_size\n"
    " def _mamba_block_aligned_split(self):\n"
    "  block_size = self.cache_config.block_size\n"
    "  return block_size\n"
)
BACK = (
    "class BaseMambaAttentionMetadataBuilder:\n"
    " def _compute_common_metadata(self):\n"
    "  mamba_block_size = self.kv_cache_spec.block_size\n"
    "  return mamba_block_size\n"
)


def put(root: Path, label: str, data: str) -> Path:
    path = root / audit.FILES[label]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return path


def fixture(root: Path) -> None:
    for label, code in [
        ("scheduler_config", CFG), ("engine_core", ENGINE),
        ("mamba_worker", WORKER), ("scheduler", SCHED),
        ("mamba_backend", BACK),
        ("cache_config", "class CacheConfig:\n pass\n"),
    ]:
        put(root, label, code)


class Phase5SchedulerMambaContractTests(unittest.TestCase):
    def test_complete_synthetic_source_remains_not_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            out = audit.inspect(root)
        self.assertEqual(out["status"], "SOURCE_FACTORY_AND_SLOT_EVIDENCE_ONLY")
        self.assertTrue(all(out["source_checks"].values()))
        self.assertEqual(out["missing_source_checks"], [])
        self.assertFalse(out["patch_approved"])
        self.assertFalse(out["active_scheduler_class_verified"])
        self.assertFalse(out["actual_config_block_equality_verified"])
        self.assertFalse(out["state_slot_correctness_verified"])

    def test_config_factory_method_missing_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "scheduler_config", CFG.replace(
                "get_scheduler_cls", "choose_dynamically"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"]["scheduler_config_factory_declared"])

    def test_engine_binding_requires_actual_factory_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "engine_core", ENGINE.replace(
                "vllm_config.scheduler_config.get_scheduler_cls()",
                "load_unrelated_class()"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "engine_assigns_scheduler_from_config_factory"])

    def test_engine_constructor_needs_block_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "engine_core", ENGINE.replace(
                "block_size=scheduler_block_size", "size=scheduler_block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "engine_calls_factory_result_scheduler"])

    def test_seed_divisor_legacy_field_detected_and_drift_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "mamba_worker", WORKER.replace(
                "req.num_computed_tokens - 1) // self.cache_config.block_size",
                "req.num_computed_tokens - 1) // self.cache_config.mamba_block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "mamba_seed_uses_cache_config_block"])

    def test_group_assertion_must_compare_spec_block_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "mamba_worker", WORKER.replace(
                "spec.block_size == mamba_spec.block_size",
                "spec.block_size == self.cache_config.block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "mamba_group_checks_spec_block"])

    def test_preprocess_requires_mamba_spec_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "mamba_worker", WORKER.replace(
                "MAMBA_BLOCK_SIZE=mamba_spec.block_size",
                "MAMBA_BLOCK_SIZE=self.cache_config.block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "mamba_preprocess_uses_group_spec_block"])

    def test_missing_align_context_helper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "mamba_worker", WORKER.replace(
                "_ensure_align_ctx", "_unrelated_ctx"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "mamba_align_context_helper_declared"])

    def test_postprocess_requires_fused_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "mamba_worker", WORKER.replace(
                "run_fused_postprocess_align", "different_hook"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "mamba_postprocess_fused_hook"])

    def test_scheduler_uses_legacy_cache_config_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "scheduler", SCHED.replace(
                "block_size = self.cache_config.block_size",
                "block_size = self.block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "scheduler_align_uses_cache_config_block"])

    def test_backend_kv_cache_spec_field_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "mamba_backend", BACK.replace(
                "self.kv_cache_spec.block_size", "self.cache_config.block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["source_checks"][
            "backend_reads_spec_block"])

    def test_equal_synthetic_blocks_have_equal_indices(self):
        out = audit.synthetic_seed_oracle(16, 16)
        self.assertEqual(out["different_index_positions"], [])
        self.assertTrue(out["not_runtime_or_kernel_certification"])

    def test_different_synthetic_blocks_expose_sensitive_boundary(self):
        out = audit.synthetic_seed_oracle(16, 32)
        differences = out["different_index_positions"]
        self.assertEqual(differences[0]["tokens"], 17)
        self.assertEqual(differences[0]["config_seed_index"], 1)
        self.assertEqual(differences[0]["spec_reference_index"], 0)

    def test_oracle_rejects_invalid_values_and_scope(self):
        for a, b, positions in [
            (0, 16, (1,)), (16, -1, (1,)), (True, 16, (1,)),
            (16, 32, (0,)), (16, 32, tuple(range(1, 70))),
        ]:
            with self.subTest(a=a, b=b, n=len(positions)):
                with self.assertRaises(ValueError):
                    audit.synthetic_seed_oracle(a, b, positions)

    def test_missing_or_symlink_source_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pkg"
            root.mkdir()
            fixture(root)
            file = root / audit.FILES["scheduler_config"]
            file.unlink()
            outside = Path(tmp) / "external.py"
            outside.write_text(CFG, encoding="utf-8")
            file.symlink_to(outside)
            out = audit.inspect(root)
        self.assertEqual(
            out["file_evidence"]["scheduler_config"]["state"],
            "SYMLINK_IGNORED")
        self.assertFalse(out["source_checks"][
            "scheduler_config_factory_declared"])

    def test_source_constants_are_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            put(root, "scheduler_config", CFG.replace(
                "return DefaultScheduler",
                "return resolve_obj_by_qualname('my-secret-token', 199999)"))
            out = audit.inspect(root)
        self.assertNotIn("my-secret-token", str(out))
        self.assertNotIn("199999", str(out))

    def test_missing_package_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = audit.inspect(Path(tmp) / "absent")
        self.assertEqual(out["status"], "INVALID_ROOT")
        self.assertFalse(out["patch_approved"])


if __name__ == "__main__":
    unittest.main()
