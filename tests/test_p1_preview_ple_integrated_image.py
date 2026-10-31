"""Pinned CPU-only P1 PLE image build constraints, not GPU behavioral tests."""
import ast
import unittest
from unittest.mock import patch

from src import p1_preview_ple_integrated_image as ple


class Tests(unittest.TestCase):
    def test_dockerfile_adds_only_ple_module(self):
        df = ple.dockerfile()
        self.assertEqual(df.count("\nCOPY "), 1)
        self.assertIn("FROM kjlee-qwen38-p1-tool-qsa:b89641b4fb52", df)
        self.assertIn("vllm_ple_mmap.py", df)
        self.assertNotIn("\nRUN ", df)
        self.assertNotIn("ENV VLLM_PLE_PHASE_STATS=1", df)
        self.assertNotIn("ENV VLLM_PLE_FAST_GATHER=1", df)

    def test_actual_checked_module_source_is_valid_and_includes_opt_in(self):
        source = ple.checked_ple_source()
        ast.parse(source)
        self.assertEqual(ple.digest(source), ple.NEW_PLE_SHA)
        self.assertIn(b"VLLM_PLE_PHASE_STATS", source)
        self.assertIn(b"VLLM_PLE_FAST_GATHER", source)

    def test_parent_layer_and_labels_fail_closed(self):
        head = "a"*40
        p = {"RootFS": {"Layers": ["a", "b"]}}
        correct = {"RootFS": {"Layers": ["a", "b", "c"]},
                   "Config": {"Labels": ple.labels(head), "Env": []}}
        ple.check_child(correct, p, head)
        with self.assertRaisesRegex(ple.qsa.Blocked, "ANCESTRY"):
            ple.check_child({**correct, "RootFS": {"Layers": ["a", "x", "c"]}},
                            p, head)
        with self.assertRaisesRegex(ple.qsa.Blocked, "LABELS"):
            ple.check_child({**correct, "Config": {"Labels": {}, "Env": []}}, p, head)
        with self.assertRaisesRegex(ple.qsa.Blocked, "ENV"):
            ple.check_child({**correct, "Config": {
                "Labels": ple.labels(head), "Env": ["VLLM_PLE_PHASE_STATS=1"]}}, p, head)

    def test_running_legacy_required_before_build(self):
        with patch.object(ple.release, "_legacy_state_for_release",
                          return_value=({"id": "b"*64}, {"Id": "b"*64}, {}, "exited")), \
             patch.object(ple.release, "_inspect_image") as inspect:
            with self.assertRaisesRegex(ple.qsa.Blocked, "ORIGINAL_NOT_RUNNING"):
                ple.build("a"*40)
            inspect.assert_not_called()

    def test_known_running_original_sha_guard(self):
        with patch.object(ple.tool, "docker_copy", return_value=b"unexpected"):
            with self.assertRaisesRegex(ple.qsa.Blocked, "ORIGINAL_PLE_SHA_DRIFT"):
                ple.verify_installed_ple()

    def test_ple_source_guard_missing_abi_fails_closed(self):
        with patch.object(ple.qsa.Path, "read_bytes", return_value=b"import sys\n"):
            with self.assertRaisesRegex(ple.qsa.Blocked, "REPOSITORY_PLE_SHA_DRIFT"):
                ple.checked_ple_source()


if __name__ == "__main__":
    unittest.main()
