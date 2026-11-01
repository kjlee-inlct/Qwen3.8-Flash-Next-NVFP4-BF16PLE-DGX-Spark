"""Offline tests: never access Docker, vLLM, model, CUDA or API."""
from __future__ import annotations

import io
import tarfile
import unittest
from unittest.mock import patch

from src import p1_numeric_source_trace as trace


class NumericSourceTraceTests(unittest.TestCase):
    def test_allowlist_blocks_traversal(self):
        for path in ("../../etc/passwd", "/etc/passwd", "vllm/random.py"):
            with self.assertRaises(trace.Blocked):
                trace.safe_source_path(path)
        self.assertTrue(trace.safe_source_path(trace.SOURCES["runner"]).endswith(
            "vllm/v1/worker/gpu_model_runner.py"))

    def test_locator_is_source_only(self):
        source = (
            b"class Runner:\n"
            b"    def execute_model(self):\n"
            b"        logits = self.model.compute_logits(hidden)\n"
            b"        return torch.log_softmax(logits, dim=-1)\n"
        )
        result = trace.locate_symbols(source)
        names = {(p["kind"], p["name"]) for p in result["locations"]}
        self.assertIn(("call", "self.model.compute_logits"), names)
        self.assertIn(("call", "torch.log_softmax"), names)
        self.assertIn(("def", "execute_model"), names)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertFalse(result["locations_truncated"])

    def test_python_tar_in_memory(self):
        body = b"def compute_logits(self):\n    return 1\n"
        bio = io.BytesIO()
        with tarfile.open(fileobj=bio, mode="w:") as archive:
            item = tarfile.TarInfo("gpu_model_runner.py")
            item.size = len(body)
            archive.addfile(item, io.BytesIO(body))
        self.assertEqual(trace.extract_python_tar(bio.getvalue()), body)

    def test_reject_tar_without_python(self):
        bio = io.BytesIO()
        with tarfile.open(fileobj=bio, mode="w:") as archive:
            item = tarfile.TarInfo("checkpoint.safetensors")
            item.size = 1
            archive.addfile(item, io.BytesIO(b"x"))
        with self.assertRaises(trace.Blocked):
            trace.extract_python_tar(bio.getvalue())

    def test_no_original_inspection_without_matching_explicit_id(self):
        with patch.object(trace.qsa, "preflight") as preflight, \
             patch.object(trace, "inspect_original") as inspected:
            result = trace.main([
                "--expected-head", "a" * 40,
                "--confirm-original-id", "wrong",
                "--inspect-original",
            ])
        self.assertEqual(result, 2)
        preflight.assert_not_called()
        inspected.assert_not_called()


if __name__ == "__main__":
    unittest.main()
