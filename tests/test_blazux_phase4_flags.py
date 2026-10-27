"""Phase 4 default-OFF feature flags and isolated source contract tests.

Uses the actual _env_flag/_env_int function bodies from the production AST,
so the repository-wide unittest suite needs no NumPy, PyTorch or vLLM.
"""

from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "vllm_ple_mmap.py"


def env_functions():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_env_flag", "_env_int"}
    definitions = [
        x for x in tree.body
        if isinstance(x, ast.FunctionDef) and x.name in names
    ]
    if {x.name for x in definitions} != names:
        raise AssertionError("production feature flag helper drift")
    namespace = {"os": os}
    exec(compile(
        ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[])),
        str(SOURCE), "exec",
    ), namespace)
    return namespace


class Phase4FeatureFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.env = env_functions()
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_both_flags_are_default_off(self):
        with patch.dict(os.environ, {}, clear=True):
            for key in ("VLLM_PLE_FAST_GATHER", "VLLM_PLE_PHASE_STATS"):
                self.assertFalse(self.env["_env_flag"](key))

    def test_only_explicit_true_opt_in(self):
        for value in ("1", "true", "YES", " True "):
            with self.subTest(value=value), patch.dict(
                os.environ, {"VLLM_PLE_FAST_GATHER": value},
            ):
                self.assertTrue(self.env["_env_flag"]("VLLM_PLE_FAST_GATHER"))
        for value in ("0", "false", "OFF", "garbage", "", "2"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"VLLM_PLE_FAST_GATHER": value},
            ):
                self.assertFalse(self.env["_env_flag"]("VLLM_PLE_FAST_GATHER"))

    def test_threshold_parse_preserves_default_and_fails_off(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.env["_env_int"]("VLLM_PLE_FAST_GATHER_ROWS", 512), 512)
        with patch.dict(os.environ, {"VLLM_PLE_FAST_GATHER_ROWS": "invalid"}):
            self.assertEqual(self.env["_env_int"]("VLLM_PLE_FAST_GATHER_ROWS", 512), 512)

    def test_independent_stats_and_fast_gather_api_contracts(self):
        source = self.source
        for literal in (
            'if _env_flag("VLLM_PLE_FAST_GATHER") else 0',
            'self.phase_stats_enabled = _env_flag("VLLM_PLE_PHASE_STATS")',
            "def stats_snapshot(self)",
            "def _gather_rows(self, ids: np.ndarray)",
            "if not self.phase_stats_enabled:",
            "if ids.size <= self.fast_gather_rows:",
        ):
            with self.subTest(literal=literal):
                self.assertIn(literal, source)
        self.assertIn("logical_bytes", source)
        self.assertIn("PLE duplicate shard index", source)

    def test_phase4_cpu_matrix_has_all_four_modes_and_no_real_weights(self):
        path = ROOT / "src" / "test_ple_phase4_cpu.py"
        source = path.read_text(encoding="utf-8")
        self.assertIn(
            "((False, False), (True, False), (False, True), (True, True))",
            source,
        )
        self.assertIn("PHASE4_CPU_MATRIX_ALL_OK", source)
        self.assertIn('CUDA_VISIBLE_DEVICES") != "-1"', source)
        self.assertIn("make_bf16_fixture", source)


if __name__ == "__main__":
    unittest.main()
