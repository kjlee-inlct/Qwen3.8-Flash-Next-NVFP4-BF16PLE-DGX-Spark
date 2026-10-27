"""Offline Phase6 evaluator regressions; no DGX/GPU dependencies."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase6_gate", ROOT / "src/phase6_gate.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def sample():
    return {"source_sha": "test", "image_digest": "test", "scheduler_class": "Scheduler",
            "cache_block_size": 16, "scheduler_block_size": 32, "hash_block_size": 16,
            "groups": [{"block_size": 32, "block_table": {
                "rows": 1, "columns": 2, "row_stride_elements": 4, "physical_ids": [[0, 1]]},
                "states": [{"allocated_bytes": 128, "block_stride_bytes": 64,
                            "payload_bytes": 32, "physical_blocks": 2}]}]}

class Phase6GateTests(unittest.TestCase):
    def test_fixture_pass_is_not_runtime_certification(self):
        result = mod.evaluate_a(sample())
        self.assertEqual(result["status"], "PASS")
        self.assertIn("not active DGX", result["scope"])

    def test_missing_group_blocked(self):
        data = sample()
        del data["groups"]
        self.assertEqual(mod.evaluate_a(data)["status"], "BLOCKED")

    def test_missing_physical_ids_blocked(self):
        data = sample()
        del data["groups"][0]["block_table"]["physical_ids"]
        self.assertEqual(mod.evaluate_a(data)["status"], "BLOCKED")

    def test_out_of_bounds_fail(self):
        data = sample()
        data["groups"][0]["block_table"]["physical_ids"][0][1] = 2
        self.assertEqual(mod.evaluate_a(data)["status"], "FAIL")

    def test_stride_underflow_fail(self):
        data = sample()
        data["groups"][0]["block_table"]["row_stride_elements"] = 1
        self.assertEqual(mod.evaluate_a(data)["status"], "FAIL")

    def test_mismatched_blocks_not_automatically_fail(self):
        data = sample()
        data["cache_block_size"] = 16
        data["groups"][0]["block_size"] = 32
        self.assertEqual(mod.evaluate_a(data)["status"], "PASS")

    def test_payload_larger_than_stride_fail(self):
        data = sample()
        data["groups"][0]["states"][0]["payload_bytes"] = 65
        self.assertEqual(mod.evaluate_a(data)["status"], "FAIL")

if __name__ == "__main__":
    unittest.main()
