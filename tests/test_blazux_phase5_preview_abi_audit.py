"""Read-only, stdlib-only fixture tests for Phase 5 preview ABI triage.

These tests simulate Python source trees. They do NOT import installed vLLM
and cannot certify or test actual prefix hits, tools, MTP, GPU or model loading.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import phase5_preview_abi_audit as audit


def write(root: Path, relative: str, data: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data, encoding="utf-8")
    return target


class PreviewReadOnlyAuditTests(unittest.TestCase):
    def test_empty_directory_is_not_mistaken_for_compatible_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.audit_tree(Path(tmp))
            self.assertEqual(
                result["components"]["mamba"]["state"],
                "ABSENT_OR_OUTSIDE_ROOT",
            )
            self.assertEqual(result["model_search"]["state"], "SCANNED_READ_ONLY")
            self.assertEqual(result["model_search"]["candidates"], [])
            self.assertIn("NOT_ABI_CERTIFIED", result["package"])

    def test_mamba_legacy_versus_dedicated_block_size_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = (
                "class MambaHybridModelState:\n"
                " def add_request(self, new_req_data):\n"
                "  x = (new_req_data.num_computed_tokens - 1) // self.cache_config.block_size\n"
                " def preprocess_state(self): pass\n"
                " def postprocess_state(self): pass\n"
            )
            path = write(root, audit.COMPONENTS["mamba"], legacy)
            result = audit.audit_tree(root)["components"]["mamba"]
            self.assertTrue(result["blazux_mamba_anchor_hints"]["legacy_small_block_expression"])
            self.assertFalse(result["blazux_mamba_anchor_hints"]["direct_mamba_block_expression"])
            self.assertFalse(result["matches_previous_dgx_sha"])
            self.assertEqual(result["target_method_signatures"]["add_request"]["args"],
                             ["self", "new_req_data"])
            path.write_text(legacy.replace("self.cache_config.block_size",
                                           "self.cache_config.mamba_block_size"),
                            encoding="utf-8")
            revised = audit.audit_tree(root)["components"]["mamba"]
            self.assertTrue(revised["blazux_mamba_anchor_hints"]["direct_mamba_block_expression"])
            self.assertFalse(revised["blazux_mamba_anchor_hints"]["legacy_small_block_expression"])

    def test_scheduler_and_parser_methods_are_heuristics_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, audit.COMPONENTS["scheduler"], (
                "class Scheduler:\n"
                " def _mamba_block_aligned_split(self):\n"
                "  block_size = self.cache_config.block_size\n"
                " def _get_local_prefix_cache_hit(self): pass\n"
            ))
            write(root, audit.COMPONENTS["parser_engine"], (
                "class ParserEngine:\n"
                " def _handle_tool_end(self, event, deltas): pass\n"
            ))
            write(root, audit.COMPONENTS["responses_serving"], (
                "class OpenAIServingResponses:\n"
                " async def _process_simple_streaming_events(self): pass\n"
            ))
            comp = audit.audit_tree(root)["components"]
            self.assertTrue(comp["scheduler"]["blazux_scheduler_anchor_hints"][
                "legacy_cache_block_assignment"])
            self.assertIn("_normalize_tool_arguments", comp["parser_engine"][
                "missing_target_methods"])
            self.assertFalse(comp["parser_engine"]["blazux_tool_schema_anchor_hints"][
                "_normalize_tool_arguments"])
            self.assertIsNone(comp["responses_serving"]["target_method_signatures"][
                "_make_failed_response_event"])
            self.assertEqual(comp["responses_serving"]["state"], "PRESENT_SOURCE_PARSEABLE")

    def test_model_search_prioritizes_qwen4_exp_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "model_executor/models/qwen3_8_flash_next/nvidia/mtp.py",
                  "class OtherMTP:\n def compute_logits(self, x): pass\n")
            write(root, "model_executor/models/qwen4_exp/nvidia/mtp.py",
                  "class Qwen4ExpMTP:\n def compute_logits(self, hidden_states, spec_step_idx=0): pass\n")
            write(root, "model_executor/models/qwen4_exp/nvidia/ple_layer.py",
                  "class PLELayer: pass\n")
            write(root, "model_executor/models/qwen2/__init__.py", "# ignored\n")
            result = audit.audit_tree(root)["model_search"]
            self.assertEqual(result["state"], "SCANNED_READ_ONLY")
            self.assertEqual(result["matched_file_count"], 3)
            paths = [c["relative_path"] for c in result["candidates"]]
            self.assertIn("model_executor/models/qwen4_exp/nvidia/mtp.py", paths)
            self.assertIn("model_executor/models/qwen4_exp/nvidia/ple_layer.py", paths)
            self.assertTrue(paths[0].startswith("model_executor/models/qwen4_exp"))
            source = next(c for c in result["candidates"] if c["relative_path"].endswith(
                "qwen4_exp/nvidia/mtp.py"))
            self.assertEqual(source["state"], "PRESENT_SOURCE_PARSEABLE")
            self.assertIn("Qwen4ExpMTP", source["classes"])
            self.assertEqual(source["mtp_ple_candidate_methods"]["Qwen4ExpMTP"]
                             ["compute_logits"],
                             ["self", "hidden_states", "spec_step_idx"])

    def test_candidate_overflow_is_reported_not_silently_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "models/qwen4_exp/mtp.py", "class Qwen4ExpMTP: pass\n")
            write(root, "models/qwen3_8/mtp.py", "class Qwen38MTP: pass\n")
            with patch.object(audit, "MAX_MODEL_CANDIDATES", 1):
                result = audit.audit_tree(root)["model_search"]
            self.assertEqual(result["state"], "CANDIDATE_LIMIT_REACHED")
            self.assertEqual(result["matched_file_count"], 2)
            self.assertEqual(len(result["candidates"]), 1)
            self.assertIn("qwen4_exp", result["candidates"][0]["relative_path"])

    def test_symlink_and_oversized_source_are_never_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vllm"
            root.mkdir()
            outside = write(Path(tmp), "private/secret.py", "class Secret: pass\n")
            link = root / audit.COMPONENTS["parser_qwen3"]
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
            self.assertEqual(audit.audit_tree(root)["components"]["parser_qwen3"][
                "state"], "SYMLINK_IGNORED")
            path = write(root, audit.COMPONENTS["parser_engine"], "class ParserEngine: pass\n")
            with patch.object(audit, "MAX_FILE_BYTES", 4):
                record = audit.audit_tree(root)["components"]["parser_engine"]
            self.assertEqual(record["state"], "TOO_LARGE_FOR_AUDIT")

    def test_source_sha_is_bytes_exact_and_syntax_error_is_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = "class Qwen3Parser:\n def extract_reasoning(self, text): pass\n"
            write(root, audit.COMPONENTS["parser_qwen3"], valid)
            record = audit.audit_tree(root)["components"]["parser_qwen3"]
            self.assertEqual(record["sha256"], hashlib.sha256(valid.encode()).hexdigest())
            self.assertEqual(record["state"], "PRESENT_SOURCE_PARSEABLE")
            write(root, audit.COMPONENTS["parser_qwen3"], "class Qwen3Parser(\n")
            self.assertEqual(audit.audit_tree(root)["components"]["parser_qwen3"][
                "state"], "UNPARSEABLE")


if __name__ == "__main__":
    unittest.main()
