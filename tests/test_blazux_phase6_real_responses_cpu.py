"""Source-only checks for P1 actual Preview Responses Serving CPU integration."""
import ast
import unittest
from pathlib import Path

from src import preview_p1_real_responses_cpu as r


class RealResponsesCPUPlanTests(unittest.TestCase):
    def test_syntax_and_explicit_opt_in(self):
        ast.parse(Path(r.__file__).read_bytes())
        self.assertEqual(r.main([]), 2)

    def test_reuses_pinned_existing_three_patches(self):
        source = Path(r.__file__).read_text()
        self.assertIn("from src.preview_p1_real_parser_cpu import (", source)
        self.assertIn("_stage(find_installed_preview(), overlay)", source)
        self.assertIn("sys.meta_path.insert(0, Overlay())", source)

    def test_no_service_model_gpu_or_network_changes(self):
        source = Path(r.__file__).read_text()
        for unsafe in ("docker stop", "docker exec", "torch.cuda.",
                       "requests.post(", "urllib.request.urlopen("):
            self.assertNotIn(unsafe, source)
        self.assertIn('"actual_http_request": False', source)
        self.assertIn('"actual_model_or_gpu_executed": False', source)

    def test_stream_fixture_uses_shared_preview_context_and_final_items(self):
        source = Path(r.__file__).read_text()
        self.assertIn("serving.SimpleContext(response_parser=parser_instance)", source)
        self.assertIn("typed_request, sampling, contexts(), context,", source)
        self.assertIn('ev.type == "response.output_item.done"', source)
        self.assertIn('stored_items = getattr(context, "streamed_output_items", None)', source)
        self.assertIn('a.model_dump(mode="json") != b.model_dump(mode="json")', source)
        self.assertIn("REAL_RESPONSES_STREAM_PROCESSOR_DONE_ITEMS_MISSING", source)
        self.assertIn("REAL_RESPONSES_STREAM_PROCESSOR_ITEMS_CONFLICT", source)
        self.assertIn('P1_DIAG_CONTEXT_ITEMS=', source)
        self.assertIn('P1_DIAG_TERMINAL_ENTERED=', source)
        self.assertIn('REAL_PARSER_TO_RESPONSES_STREAM_FINAL_TOOL_WRONG', source)

    def test_validation_diagnostics_never_emit_raw_errors(self):
        source = Path(r.__file__).read_text()
        self.assertIn("include_input=False", source)
        self.assertIn("include_context=False", source)
        self.assertIn("P1_DIAG_VALIDATION_FIELD=", source)
        self.assertIn("STREAM_VALID_GENERATOR", source)
        self.assertIn("STREAM_VALID_WIRE", source)
        self.assertIn("P1_DIAG_EVENT_KIND=", source)
        self.assertIn("P1_DIAG_ATTR=", source)
        self.assertIn("P1_DIAG_ATTR_FRAME=", source)
        self.assertIn("P1_DIAG_BLOCKED_CODE=", source)
        self.assertIn('blocked_codes.get(str(exc), "OTHER")', source)
        self.assertIn('attr_names.get(getattr(exc, "name", None), "OTHER")', source)
        self.assertNotIn("print(str(exc)", source)

    def test_typed_events_and_roundtrip_required(self):
        source = Path(r.__file__).read_text()
        for name in ("serving.OpenAIServingResponses",
                     "protocol.ResponseCompletedEvent",
                     "protocol.ResponseIncompleteEvent",
                     "protocol.ResponseFailedEvent",
                     "adapter.validate_json"):
            self.assertIn(name, source)


if __name__ == "__main__":
    unittest.main()
