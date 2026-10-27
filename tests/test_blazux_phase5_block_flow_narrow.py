"""Only synthetic AST fixtures; no real vLLM import, weights, GPU or patches."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import phase5_block_flow_narrow as audit


KV = (
    "import math\n"
    "def resolve_kv_cache_block_sizes(groups, requested=None):\n"
    "  group_block_sizes = [g.kv_cache_spec.block_size for g in groups]\n"
    "  hashing_sizes = [g.kv_cache_spec.hash_block_size for g in groups]\n"
    "  scheduler_block_size = math.lcm(*group_block_sizes)\n"
    "  hash_block_size = (requested if requested is not None\n"
    "                     else math.gcd(*hashing_sizes))\n"
    "  return scheduler_block_size, hash_block_size\n"
)
ENGINE = (
    "from vllm.v1.core.kv_cache_utils import resolve_kv_cache_block_sizes\n"
    "from vllm.v1.core.sched.scheduler import Scheduler\n"
    "class EngineCore:\n"
    " def __init__(self, config):\n"
    "  scheduler_block_size, hash_block_size = (\n"
    "      resolve_kv_cache_block_sizes(config.groups))\n"
    "  self.scheduler = Scheduler(config, block_size=scheduler_block_size,\n"
    "                             hash_block_size=hash_block_size)\n"
)
MAMBA = (
    "class MambaHybridModelState:\n"
    " def add_request(self, index, req):\n"
    "  return (req.num_computed_tokens - 1) // self.cache_config.block_size\n"
    " def preprocess_state(self):\n"
    "  return self.mamba_spec.block_size\n"
    " def postprocess_state(self): pass\n"
)
SCHEDULER = (
    "class Scheduler:\n"
    " def __init__(self, config, block_size=None):\n"
    "  self.block_size = block_size\n"
    " def _mamba_block_aligned_split(self, request):\n"
    "  return request.num_tokens % self.cache_config.block_size\n"
)


def write(root: Path, label: str, content: str) -> Path:
    path = root / audit.PATHS[label]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def fixture(root: Path) -> None:
    write(root, "kv_utils", KV)
    write(root, "engine_core", ENGINE)
    write(root, "mamba_worker", MAMBA)
    write(root, "scheduler", SCHEDULER)


class Phase5NarrowBlockFlowTests(unittest.TestCase):
    def test_full_synthetic_ast_chain_is_only_a_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            out = audit.inspect(root)
        chain = out["static_chain"]
        self.assertEqual(out["status"],
                         "NARROW_SOURCE_AST_ONLY_NOT_ABI_OR_CACHE_CERTIFIED")
        self.assertEqual(chain["status"],
                         "STATIC_CHAIN_CANDIDATE_NOT_RUNTIME_CERTIFIED")
        self.assertTrue(all(chain["checks"].values()))
        self.assertFalse(chain["runtime_flow_proven"])
        self.assertFalse(out["patch_approved"])

    def test_engine_import_binding_is_captured_but_not_runtime_proven(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            engine = audit.inspect(root)["files"]["engine_core"]
        self.assertIn("Scheduler", engine["imports_of_interest"])
        self.assertTrue(engine["imports_of_interest"]["Scheduler"].endswith(
            "v1.core.sched.scheduler.Scheduler"))
        self.assertIn("resolve_kv_cache_block_sizes",
                      engine["imports_of_interest"])
        ct = engine["methods"]["__init__"]
        self.assertEqual(ct["assignments"][0]["targets"],
                         ["scheduler_block_size", "hash_block_size"])
        self.assertIn("Scheduler", [c["callee"] for c in ct["calls"]])
        self.assertEqual(ct["returns"], [])

    def test_lcm_group_list_and_separate_hash_gcd_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            rec = audit.inspect(root)["files"]["kv_utils"]["function"]
        assignments = {name: x for x in rec["assignments"]
                       for name in x["targets"]}
        self.assertIn("math.lcm", assignments["scheduler_block_size"][
            "value_shape"])
        self.assertIn("group_block_sizes", assignments[
            "scheduler_block_size"]["value_shape"])
        self.assertIn("math.gcd", assignments["hash_block_size"]["value_shape"])
        self.assertEqual(rec["returns"][0]["names"],
                         ["scheduler_block_size", "hash_block_size"])

    def test_core_mamba_consumer_preserves_legacy_config_block_size(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            out = audit.inspect(root)
        mamba = out["files"]["mamba_worker"]["method_traces"]["add_request"]
        aligned = out["files"]["scheduler"]["method_traces"][
            "_mamba_block_aligned_split"]
        self.assertIn("cache_config.block_size",
                      mamba["floor_div_or_mod"][0]["right"])
        self.assertIn("cache_config.block_size",
                      aligned["floor_div_or_mod"][0]["right"])

    def test_missing_engine_source_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, "kv_utils", KV)
            out = audit.inspect(root)
        self.assertEqual(out["static_chain"]["status"], "INSUFFICIENT_SOURCE")
        self.assertFalse(out["static_chain"]["runtime_flow_proven"])
        self.assertIn("ENGINE_CORE_UNAVAILABLE", out["static_chain"]["missing"])

    def test_wrong_scheduler_import_prevents_static_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            write(root, "engine_core", ENGINE.replace(
                "vllm.v1.core.sched.scheduler import Scheduler",
                "vllm.fake.other import Scheduler"))
            out = audit.inspect(root)
        self.assertEqual(out["static_chain"]["status"],
                         "UNRESOLVED_OR_PARTIAL_STATIC_CHAIN")
        self.assertFalse(out["static_chain"]["checks"][
            "engine_static_imports_scheduler"])

    def test_missing_kv_tuple_return_prevents_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            write(root, "kv_utils", KV.replace(
                "return scheduler_block_size, hash_block_size",
                "return scheduler_block_size"))
            out = audit.inspect(root)
        self.assertFalse(out["static_chain"]["checks"][
            "kv_function_returns_both_sizes"])
        self.assertEqual(out["static_chain"]["status"],
                         "UNRESOLVED_OR_PARTIAL_STATIC_CHAIN")

    def test_no_engine_resolver_assignment_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            write(root, "engine_core", ENGINE.replace(
                "resolve_kv_cache_block_sizes(config.groups)",
                "read_cache_sizes(config.groups)"))
            out = audit.inspect(root)
        self.assertFalse(out["static_chain"]["checks"][
            "engine_assigns_scheduler_size_from_resolver"])

    def test_non_scheduler_lcm_assignment_does_not_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            write(root, "kv_utils", KV.replace(
                "scheduler_block_size = math.lcm(*group_block_sizes)",
                "scheduler_block_size = group_block_sizes[0]"))
            out = audit.inspect(root)
        self.assertFalse(out["static_chain"]["checks"][
            "kv_scheduler_size_lcm_assignment"])

    def test_changed_kv_source_hash_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            p = root / audit.PATHS["kv_utils"]
            first = audit.inspect(root)["files"]["kv_utils"]["sha256"]
            p.write_text(KV + "\n# only syntactic edit\n", encoding="utf-8")
            second = audit.inspect(root)["files"]["kv_utils"]["sha256"]
        self.assertNotEqual(first, second)

    def test_symlinked_critical_source_is_not_read(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            root.mkdir()
            write(root, "kv_utils", KV)
            out = Path(td) / "engine_private.py"
            out.write_text(ENGINE, encoding="utf-8")
            link = root / audit.PATHS["engine_core"]
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(out)
            result = audit.inspect(root)
        self.assertEqual(result["files"]["engine_core"]["state"],
                         "SYMLINK_IGNORED")
        self.assertEqual(result["static_chain"]["status"],
                         "INSUFFICIENT_SOURCE")

    def test_invalid_syntax_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            write(root, "engine_core", "class EngineCore(\n")
            result = audit.inspect(root)
        self.assertEqual(result["files"]["engine_core"]["state"], "UNPARSEABLE")
        self.assertEqual(result["static_chain"]["status"], "INSUFFICIENT_SOURCE")

    def test_bounded_assignment_cap_does_not_report_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            with patch.object(audit, "MAX_RECORDS", 1):
                result = audit.inspect(root)
        self.assertTrue(result["static_chain"]["bounded_output_truncated"])
        self.assertEqual(result["static_chain"]["status"],
                         "UNRESOLVED_OR_PARTIAL_STATIC_CHAIN")

    def test_source_shape_redacts_string_and_number_constants(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            write(root, "kv_utils", KV.replace(
                "math.lcm(*group_block_sizes)",
                "math.lcm(*group_block_sizes) + secret('credential-marker', 882739)"))
            result = audit.inspect(root)
        rendered = str(result)
        self.assertNotIn("credential-marker", rendered)
        self.assertNotIn("882739", rendered)

    def test_not_a_vllm_package_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "missing"
            result = audit.inspect(root)
        self.assertEqual(result["status"], "INVALID_ROOT")
        self.assertFalse(result["patch_approved"])


if __name__ == "__main__":
    unittest.main()
