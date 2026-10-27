"""Synthetic Phase5 dependency-trace tests. Never import or patch vLLM."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import phase5_dependency_trace as tr


def put(root: Path, relative: str, source: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


MAMBA = (
    "class MambaHybridModelState:\n"
    " def add_request(self, req_index, new_req_data):\n"
    "  value = (new_req_data.num_computed_tokens - 1) // self.cache_config.block_size\n"
    "  return value\n"
)
SCHEDULER = (
    "class Scheduler:\n"
    " def __init__(self, cache_config):\n"
    "  self.block_size = lcm(cache_config.block_size, 1600)\n"
    " def _mamba_block_aligned_split(self, request, num_new_tokens):\n"
    "  block_size = self.cache_config.block_size\n"
    "  return num_new_tokens % block_size\n"
    " def _get_local_prefix_cache_hit(self, request):\n"
    "  return self._mamba_block_aligned_split(request, 5)\n"
)
MTP = (
    "class Qwen3_8FlashNextMTP:\n"
    " def __init__(self):\n"
    "  self.lm_head = SharedHead(25)\n"
    "  self.logits_processor = LogitsProcessor()\n"
    " def compute_logits(self, hidden_states, spec_step_idx):\n"
    "  return self.logits_processor(self.lm_head, hidden_states)\n"
    " def forward(self, input_ids, positions):\n"
    "  return self.compute_logits(input_ids, 0)\n"
    " def load_weights(self, weights):\n"
    "  return weights\n"
)


class Phase5DependencyTraceTests(unittest.TestCase):
    def test_empty_tree_reports_absence_and_never_approval(self):
        with tempfile.TemporaryDirectory() as td:
            result = tr.inspect(Path(td))
            self.assertTrue(result["not_patch_approved"])
            self.assertEqual(
                result["components"]["mamba"]["state"], "ABSENT_OR_OUTSIDE_ROOT"
            )
            self.assertEqual(
                result["mamba_field_scan"]["state"], "SCANNED_READ_ONLY"
            )
            self.assertEqual(result["components"]["mtp_nvidia"]["state"],
                             "ABSENT_OR_OUTSIDE_ROOT")

    def test_mamba_floor_division_reports_block_size_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, tr.PATHS["mamba"], MAMBA)
            rec = tr.inspect(root)["components"]["mamba"]["methods"]["add_request"]
            self.assertEqual(rec["signature"], ["self", "req_index", "new_req_data"])
            self.assertEqual(len(rec["floor_div_or_mod"]), 1)
            self.assertEqual(rec["floor_div_or_mod"][0]["kind"], "floor_div")
            self.assertIn("cache_config.block_size",
                          rec["floor_div_or_mod"][0]["right"])
            self.assertIn("new_req_data.num_computed_tokens",
                          rec["floor_div_or_mod"][0]["left"])

    def test_scheduler_lcm_assignment_and_prefix_calls(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, tr.PATHS["scheduler"], SCHEDULER)
            methods = tr.inspect(root)["components"]["scheduler"]["methods"]
            self.assertEqual(methods["__init__"]["watched_assignments"][0]["target"],
                             "self.block_size")
            self.assertIn("lcm(", methods["__init__"][
                "watched_assignments"][0]["value_shape"])
            self.assertEqual(methods["_mamba_block_aligned_split"][
                "floor_div_or_mod"][0]["kind"], "mod")
            self.assertIn("self._mamba_block_aligned_split",
                          methods["_get_local_prefix_cache_hit"]["calls"])

    def test_mtp_head_owner_assignments_and_processor_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, tr.PATHS["mtp_nvidia"], MTP)
            methods = tr.inspect(root)["components"]["mtp_nvidia"]["methods"]
            owner = [item["target"] for item in methods["__init__"][
                "watched_assignments"]]
            self.assertEqual(owner, ["self.lm_head", "self.logits_processor"])
            self.assertIn("self.logits_processor",
                          methods["compute_logits"]["calls"])
            self.assertEqual(
                methods["load_weights"]["signature"], ["self", "weights"]
            )

    def test_parser_and_responses_call_edges_not_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, tr.PATHS["parser_engine"], (
                "class ParserEngine:\n"
                " def _handle_tool_end(self, event, deltas):\n"
                "  return self._compute_arg_delta(event, deltas)\n"
                " def _compute_arg_delta(self, idx, raw_delta):\n"
                "  return json.loads(raw_delta)\n"
            ))
            put(root, tr.PATHS["responses_serving"], (
                "class OpenAIServingResponses:\n"
                " async def _process_simple_streaming_events(self, request):\n"
                "  return self._send_failed_response(request)\n"
            ))
            rec = tr.inspect(root)["components"]
            self.assertIn("self._compute_arg_delta", rec["parser_engine"][
                "methods"]["_handle_tool_end"]["calls"])
            self.assertIn("self._send_failed_response", rec["responses_serving"][
                "methods"]["_process_simple_streaming_events"]["calls"])

    def test_scan_finds_store_and_load_but_does_not_certify_provider(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, "config/cache.py", (
                "class CacheConfig:\n"
                " def __init__(self):\n"
                "  self.mamba_block_size = 1600\n"
                " def size(self):\n"
                "  return self.mamba_block_size\n"
            ))
            records = tr.scan_mamba_field(root)
            self.assertEqual(records["state"], "SCANNED_READ_ONLY")
            self.assertEqual(
                [(r["kind"], r["target"]) for r in records["sites"]],
                [("STORE", "self.mamba_block_size"),
                 ("LOAD", "self.mamba_block_size")],
            )

    def test_file_scan_limit_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, "config/a.py", "a=1\n")
            put(root, "v1/b.py", "b=2\n")
            with patch.object(tr, "MAX_SCAN_FILES", 1):
                records = tr.scan_mamba_field(root)
            self.assertEqual(records["state"], "FILE_LIMIT_EXCEEDED")
            self.assertEqual(records["files_matched"], 2)
            self.assertEqual(records["sites"], [])

    def test_byte_scan_limit_is_explicit_not_false_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            put(root, "config/cache.py", "mamba_block_size=1600\n")
            with patch.object(tr, "MAX_SCAN_BYTES", 5):
                records = tr.scan_mamba_field(root)
            self.assertEqual(records["state"], "BYTE_LIMIT_EXCEEDED")

    def test_symlink_source_refused_even_when_target_valid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            root.mkdir()
            outside = put(Path(td), "outside.py", MAMBA)
            link = root / tr.PATHS["mamba"]
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
            result = tr.inspect(root)
            self.assertEqual(result["components"]["mamba"]["state"],
                             "SYMLINK_IGNORED")

    def test_expression_shapes_redact_sensitive_constants(self):
        expr = ast.parse(
            "self.lm_head = Hidden('secret-placeholder-value', 314159)"
        ).body[0].value
        shown = tr._shape(expr)
        self.assertNotIn("secret-placeholder-value", shown)
        self.assertNotIn("314159", shown)
        self.assertIn("<redacted>", shown)
        self.assertIn("<number>", shown)


if __name__ == "__main__":
    unittest.main()
