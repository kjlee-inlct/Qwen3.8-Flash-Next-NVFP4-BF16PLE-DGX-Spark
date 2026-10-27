"""A3b-0 strictly synthetic CPU and pinned AST source contract tests."""
from __future__ import annotations
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "src/phase6_a3b_cpu_config.py"
spec = importlib.util.spec_from_file_location("phase6_a3b_cpu_config", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fixture = json.loads((HERE / "tests/fixtures/phase6_a3b_synthetic.json").read_text(encoding="utf-8"))


class A3bCPUPreparationTests(unittest.TestCase):
    def test_fixture_is_synthetic_never_active(self):
        result = mod.fixture_projection(fixture)
        self.assertEqual(result["status"], "SYNTHETIC_GEOMETRY_ONLY_NOT_RUNTIME")
        self.assertEqual(result["p6_a_runtime_status"], "BLOCKED")
        self.assertFalse(result["actual_scheduler_class_observed"])
        self.assertFalse(result["physical_block_tables_or_tensors_observed"])

    def test_naive_lcm_gcd_are_diagnostics_only(self):
        result = mod.fixture_projection(fixture)
        self.assertEqual(result["candidate_group_lcm_not_resolved_scheduler"], 32)
        self.assertEqual(result["candidate_group_gcd_not_resolved_hash"], 16)
        self.assertTrue(result["declared_scheduler_block_matches_naive_lcm"])

    def test_unequal_mamba_does_not_assert_bug(self):
        result = mod.fixture_projection(fixture)
        self.assertTrue(result["synthetic_mamba_cache_block_difference"])
        self.assertTrue(result["conditional_index_divergence_not_a_bug"])
        self.assertEqual(result["status"], "SYNTHETIC_GEOMETRY_ONLY_NOT_RUNTIME")

    def test_equal_size_stays_synthetic(self):
        obj = dict(fixture)
        obj["groups"] = [{"kind": "mamba", "block_size": 16}]
        result = mod.fixture_projection(obj)
        self.assertFalse(result["synthetic_mamba_cache_block_difference"])
        self.assertEqual(result["p6_a_runtime_status"], "BLOCKED")

    def test_attention_dcp_multiplication_candidate_only(self):
        obj = dict(fixture)
        obj["dcp_size"] = 2
        result = mod.fixture_projection(obj)
        self.assertEqual(result["candidate_group_lcm_not_resolved_scheduler"], 32)
        self.assertIn("ignores", result["note"])

    def test_missing_fields_blocked(self):
        self.assertEqual(mod.fixture_projection({"groups": []})["status"], "BLOCKED")

    def test_unknown_fields_blocked(self):
        obj = dict(fixture)
        obj["api_key"] = "do-not-show"
        result = mod.fixture_projection(obj)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("do-not-show", str(result))

    def test_actual_origin_claim_blocked(self):
        obj = dict(fixture)
        obj["source_kind"] = "ACTIVE_GPU_RUNTIME"
        self.assertEqual(mod.fixture_projection(obj)["status"], "BLOCKED")

    def test_bool_is_not_integer(self):
        obj = dict(fixture)
        obj["cache_block_size"] = True
        self.assertEqual(mod.fixture_projection(obj)["status"], "BLOCKED")

    def test_invalid_group_blocked(self):
        obj = dict(fixture)
        obj["groups"] = [{"kind": "mamba", "block_size": 0}]
        self.assertEqual(mod.fixture_projection(obj)["status"], "BLOCKED")

    def test_unbounded_group_count_blocked(self):
        obj = dict(fixture)
        obj["groups"] = [{"kind": "mamba", "block_size": 16}] * 17
        self.assertEqual(mod.fixture_projection(obj)["status"], "BLOCKED")

    def test_synthetic_only_no_custom_group_identifiers(self):
        obj = dict(fixture)
        obj["groups"] = [{"kind": "mamba", "block_size": 16, "name": "/private"}]
        self.assertEqual(mod.fixture_projection(obj)["status"], "BLOCKED")

    def test_isolation_guard_blocks_without_exact_flags(self):
        self.assertFalse(mod.isolated_environment_guard({}))
        good = {
            "PHASE6_A3B_CPU_INSPECTION_ONLY": "1", "CUDA_VISIBLE_DEVICES": "-1",
            "NVIDIA_VISIBLE_DEVICES": "void", "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.assertTrue(mod.isolated_environment_guard(good))
        good["NVIDIA_VISIBLE_DEVICES"] = "all"
        self.assertFalse(mod.isolated_environment_guard(good))

    def test_read_fixture_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            target = home / "data.json"
            target.write_text(json.dumps(fixture), encoding="utf-8")
            link = home / "alias.json"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                mod.read_fixture(link)

    def test_source_contract_missing_root_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(mod.source_contract(Path(td))["status"], "BLOCKED")

    def test_source_contract_recognizes_ast_anchor_but_requires_pin(self):
        tree = ast.parse("class SchedulerConfig:\n  def get_scheduler_cls(self): return None\n")
        self.assertTrue(mod._has_method(tree, "SchedulerConfig", "get_scheduler_cls"))
        self.assertFalse(mod._has_method(tree, "SchedulerConfig", "other"))
        self.assertTrue(mod._has_function(ast.parse("def resolve_kv_cache_block_sizes(): pass\n"),
                                          "resolve_kv_cache_block_sizes"))

    def test_cli_fixture_end_to_end_only(self):
        self.assertEqual(mod.main(["--fixture", str(HERE / "tests/fixtures/phase6_a3b_synthetic.json")]), 0)


if __name__ == "__main__":
    unittest.main()
