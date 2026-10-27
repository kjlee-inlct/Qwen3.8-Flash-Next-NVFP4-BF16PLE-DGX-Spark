"""No-vLLM-import synthetic tests for Scheduler ctor provenance triage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import phase5_scheduler_provenance as audit


def put(root: Path, relative: str, source: str) -> Path:
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return p


class Phase5SchedulerProvenanceTests(unittest.TestCase):
    def test_empty_package_cannot_approve(self):
        with tempfile.TemporaryDirectory() as td:
            result = audit.inspect(Path(td))
        self.assertFalse(result["patch_approved"])
        self.assertEqual(result["scan"]["state"], "COMPLETE_IN_SCANNED_SCOPE")
        self.assertEqual(result["scheduler_constructor_candidates"]["sites"], [])
        self.assertEqual(result["core_method_traces"]["mamba"]["state"],
                         "ABSENT_OR_OUTSIDE_ROOT")

    def test_scheduler_keyword_ctor_reports_exact_candidate_expression(self):
        with tempfile.TemporaryDirectory() as td:
            put(Path(td), "v1/core/engine.py", (
                "def make(vcfg, kv, mgr):\n"
                "  return Scheduler(vcfg, kv, mgr, block_size=cfg.lcm_block_size,\n"
                "                   hash_block_size=cfg.hash_block_size)\n"
            ))
            rec = audit.inspect(Path(td))["scheduler_constructor_candidates"]
        self.assertEqual(rec["direct_name_matches"], 1)
        self.assertEqual(rec["dynamic_unresolved"], 0)
        site = rec["sites"][0]
        self.assertEqual(site["scope"], "make")
        self.assertEqual(site["block_size_expr_candidate"], "cfg.lcm_block_size")
        self.assertEqual(site["hash_block_size_expr_candidate"],
                         "cfg.hash_block_size")
        self.assertIn("NOT_RESOLVED", site["kind"])

    def test_scheduler_positional_ctor_uses_observed_arg_position_only_as_hint(self):
        with tempfile.TemporaryDirectory() as td:
            put(Path(td), "v1/engine/core.py", (
                "def create(a, b, c, d, e):\n"
                "  return Scheduler(a, b, c, d, e)\n"
            ))
            row = audit.inspect(Path(td))[
                "scheduler_constructor_candidates"]["sites"][0]
        self.assertEqual(row["block_size_expr_candidate"], "d")
        self.assertEqual(row["hash_block_size_expr_candidate"], "e")

    def test_dynamic_scheduler_cls_ctor_is_unresolved_not_direct(self):
        with tempfile.TemporaryDirectory() as td:
            put(Path(td), "v1/engine/core.py", (
                "def make(config, requested):\n"
                "  scheduler_cls = resolve_obj_by_qualname(config.scheduler_cls)\n"
                "  return scheduler_cls(config, block_size=requested)\n"
            ))
            rec = audit.inspect(Path(td))["scheduler_constructor_candidates"]
        self.assertEqual(rec["direct_name_matches"], 0)
        self.assertEqual(rec["dynamic_unresolved"], 1)
        self.assertEqual(rec["sites"][0]["kind"], "DYNAMIC_CTOR_UNRESOLVED")
        self.assertEqual(rec["sites"][0]["block_size_expr_candidate"], "requested")

    def test_lcm_expression_is_a_static_assignment_hint(self):
        with tempfile.TemporaryDirectory() as td:
            put(Path(td), "v1/core/core.py", (
                "def make(cfg):\n"
                "  block_size = math.lcm(cfg.mamba_block_size, cfg.block_size)\n"
                "  return Scheduler(cfg, cfg.kv, cfg.som, block_size, cfg.hash)\n"
            ))
            out = audit.inspect(Path(td))
        sites = out["block_assignments"]
        self.assertEqual(len(sites), 1)
        self.assertTrue(sites[0]["lcmlike_call"])
        self.assertIn("math.lcm", sites[0]["expression_shape"])

    def test_config_field_store_and_load_remain_only_ast_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            put(Path(td), "config/cache.py", (
                "class CacheConfig:\n"
                " def __init__(self):\n"
                "  self.mamba_block_size = 1600\n"
                " def get(self):\n"
                "  return self.mamba_block_size\n"
            ))
            out = audit.inspect(Path(td))
        fields = [(x["kind"], x["reference"])
                  for x in out["mamba_field_references"]]
        self.assertEqual(fields, [
            ("STORE", "self.mamba_block_size"),
            ("LOAD", "self.mamba_block_size"),
        ])
        self.assertFalse(out["patch_approved"])

    def test_core_mamba_scheduler_method_traces(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, audit.PATHS["mamba"], (
                "class MambaHybridModelState:\n"
                " def add_request(self, idx, req):\n"
                "  return (req.num_computed_tokens - 1) // self.cache_config.block_size\n"
            ))
            put(root, audit.PATHS["scheduler"], (
                "class Scheduler:\n"
                " def __init__(self, block_size):\n"
                "  self.block_size = block_size\n"
                " def _mamba_block_aligned_split(self, request):\n"
                "  return request.num_tokens % self.cache_config.block_size\n"
            ))
            out = audit.inspect(root)["core_method_traces"]
        self.assertEqual(out["mamba"]["state"], "PARSEABLE_ONLY")
        self.assertIn("cache_config.block_size", out["mamba"]["methods"][
            "add_request"]["floor_div_or_mod"][0]["right"])
        self.assertEqual(out["scheduler"]["methods"]["__init__"][
            "watched_assignments"][0]["value_shape"], "block_size")

    def test_file_limit_sets_partial_status_and_no_approval(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, "config/a.py", "x = 1\n")
            put(root, "v1/b.py", "y = 2\n")
            with patch.object(audit, "MAX_FILES", 1):
                out = audit.inspect(root)
        self.assertEqual(out["scan"]["state"], "PARTIAL")
        self.assertIn("FILE_LIMIT", out["scan"]["limits"])
        self.assertFalse(out["patch_approved"])

    def test_byte_limit_sets_partial_status_without_false_completion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, "config/scheduler.py", "return_value = Scheduler(block_size=x)\n")
            with patch.object(audit, "MAX_BYTES", 8):
                out = audit.inspect(root)
        self.assertEqual(out["scan"]["state"], "PARTIAL")
        self.assertIn("BYTE_LIMIT", out["scan"]["limits"])
        self.assertEqual(out["scan"]["visited"], 0)

    def test_symlink_never_follows_external_source_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            root.mkdir()
            external = put(Path(td), "secret.py", "Scheduler(private, block_size=999)\n")
            link = root / "v1" / "symlink.py"
            link.parent.mkdir()
            link.symlink_to(external)
            out = audit.inspect(root)
        self.assertEqual(out["scan"]["state"], "PARTIAL")
        self.assertGreaterEqual(out["scan"]["unreadable_or_unparseable"], 1)
        self.assertEqual(out["scheduler_constructor_candidates"]["sites"], [])

    def test_sensitive_literals_redacted_and_dynamic_cannot_get_positional_hint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, "v1/core/scheduler_factory.py", (
                "def make(cls):\n"
                "  scheduler_cls = cls\n"
                "  return scheduler_cls('secret-test-token', 12345)\n"
            ))
            out = audit.inspect(root)
        site = out["scheduler_constructor_candidates"]["sites"][0]
        self.assertIsNone(site["block_size_expr_candidate"])
        self.assertNotIn("secret-test-token", str(out))
        self.assertNotIn("12345", str(out))
        self.assertFalse(out["patch_approved"])


if __name__ == "__main__":
    unittest.main()
