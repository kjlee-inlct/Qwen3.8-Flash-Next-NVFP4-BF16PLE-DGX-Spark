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
