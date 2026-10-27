"""Phase6 A→B performance-freeze stdlib-only validation, no benchmark loads."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/phase6_ab_benchmark_plan.py"
SPEC = importlib.util.spec_from_file_location("phase6_ab_benchmark_plan", PATH)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def synthetic():
    return {
        "model": mod.MODEL_ID, "latency_mode": "generation", "max_concurrency": 1,
        "benchmarks": [
            {"prompt_size": pp, "response_size": tg, "context_size": dp,
             "is_context_prefill_phase": False, "concurrency": 1,
             **{k: {"values": [1.0, 2.0, 3.0], "mean": 2.0}
                for k in mod.MEASURES}}
            for pp, tg, dp in sorted(mod.MATRIX)
        ],
    }


class Phase6PreBBenchmarkContractTests(unittest.TestCase):
    def test_real_original_baseline_artifact_hash_and_matrix(self):
        actual = mod.verify_immutable_baseline()
        self.assertEqual(actual["status"], "SOURCE_BASELINE_MATRIX_VALIDATED")
        self.assertEqual(actual["measured_runs"], 36)
        self.assertTrue(actual["original_sha256_match"])

    def test_synthetic_complete_matrix(self):
        self.assertEqual(mod.verify_matrix(synthetic())["measured_runs"], 36)

    def test_missing_row_is_blocked(self):
        doc = synthetic()
        doc["benchmarks"].pop()
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_duplicate_combination_is_blocked(self):
        doc = synthetic()
        doc["benchmarks"][1] = copy.deepcopy(doc["benchmarks"][0])
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_wrong_repeats_is_blocked(self):
        doc = synthetic()
        doc["benchmarks"][0]["tg_throughput"]["values"] = [1.0, 2.0]
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_wrong_mean_is_blocked(self):
        doc = synthetic()
        doc["benchmarks"][0]["pp_throughput"]["mean"] = 100.0
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_nonfinite_is_blocked(self):
        doc = synthetic()
        doc["benchmarks"][0]["tg_throughput"]["values"] = [float("nan"), 2.0, 3.0]
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_bool_concurrency_blocked(self):
        doc = synthetic()
        doc["benchmarks"][0]["concurrency"] = True
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_different_model_blocked(self):
        doc = synthetic()
        doc["model"] = "different-model"
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_inconsistent_latency_blocked(self):
        doc = synthetic()
        doc["latency_mode"] = "end-to-end"
        self.assertEqual(mod.verify_matrix(doc)["status"], "BLOCKED")

    def test_symlink_baseline_file_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            original = ROOT / mod.BASELINE_REL
            pointer = Path(folder) / "link.json"
            pointer.symlink_to(original)
            self.assertIsNone(mod.bounded_bytes(pointer))

    def test_checkpoint_plan_never_claims_runtime_pass_or_authorization(self):
        p = mod.plan()
        self.assertEqual(p["status"], "PLAN_READY_NOT_EXECUTED")
        self.assertEqual(p["actual_p6_a_runtime_abi"], "BLOCKED")
        self.assertEqual(p["pre_b_checkpoint_run"], "NOT_RUN")
        self.assertFalse(p["performance_benchmark_authorized"])
        self.assertFalse(p["production_service_benchmark_permitted"])

    def test_shell_plan_has_no_execute_or_external_benchmark_invocation(self):
        script = (ROOT / "scripts/phase6-ab-benchmark-plan.sh").read_text()
        self.assertIn("source-state.py", script)
        self.assertIn("phase6_ab_benchmark_plan.py", script)
        for op in ("docker run", "docker exec", "curl ", "nvidia-smi ", "llama-benchy ",
                   "python3 -m llama_benchy", "--base-url", "--gpus"):
            # We deliberately keep the script's comment documenting prohibited
            # actions; prohibit actual *shell command invocation*, not prose.
            for line in script.splitlines():
                if not line.strip().startswith("#"):
                    self.assertNotIn(op, line)


if __name__ == "__main__":
    unittest.main()
