"""P1 source-only Tool/Responses overlay builder tests."""
import unittest
from unittest.mock import patch

from src import p1_preview_tool_qsa_image as candidate


class Tests(unittest.TestCase):
    def test_no_runtime_entrypoint_or_cuda_run(self):
        df = candidate.dockerfile()
        self.assertIn("FROM kjlee-qwen38-p1-qsa-exact:3852995a19f4", df)
        self.assertEqual(df.count("\nCOPY "), 1)
        self.assertNotIn("\nRUN ", df)
        self.assertNotIn("--chmod=0644 vllm/", df)
        self.assertNotIn("docker run", df)
        self.assertNotIn("docker exec", df)
        self.assertNotIn("VLLM_PLE_PHASE_STATS=1", df)

    def test_selected_files_only(self):
        with self.assertRaisesRegex(candidate.qsa.Blocked, "NOT_ALLOWLISTED"):
            candidate.docker_copy("../etc/passwd")
        self.assertIn(candidate.stage.NEW_FILE, candidate.stage.ALLOWED_FILES)
        self.assertEqual(candidate.native.NEW_MODULE, candidate.stage.NEW_FILE)
        self.assertTrue(candidate.native.TARGETS <= candidate.stage.ALLOWED_FILES)

    def test_native_patches_not_v032_bundle(self):
        import inspect
        source = inspect.getsource(candidate.prepare_overlay)
        self.assertIn("native._stage(original, context)", source)
        self.assertNotIn("stage.read_patch_bundle(", source)
        self.assertIn("native.SOURCE_PINS.get", source)
        self.assertIn("STAGED_FILES_NOT_EXACT_ALLOWLIST", source)

    def test_ple_report_read_only_and_non_promoting(self):
        with patch.object(candidate, "docker_copy", return_value=b"other"), \
             patch.object(candidate.qsa.Path, "read_bytes", return_value=b"source"):
            result = candidate.inspect_ple()
            self.assertEqual(result["status"], "DIFFERENT")
            self.assertFalse(result["ple_runtime_modified"])
            self.assertFalse(result["ple_phase_stats_activated"])

    def test_child_requires_parent_layer_prefix_and_labels(self):
        head = "a"*40
        hashes = {"vllm/parser/qwen3.py": "x"*64}
        expected = candidate.labels(head, hashes)
        parent = {"RootFS": {"Layers": ["a", "b"]}}
        child = {"RootFS": {"Layers": ["a", "b", "c"]},
                 "Config": {"Labels": expected}}
        candidate.verify_child(child, parent, expected)
        for mutated in [
            {"RootFS": {"Layers": ["x"]}, "Config": {"Labels": expected}},
            {"RootFS": {"Layers": ["a", "b", "c"]}, "Config": {"Labels": {}}},
        ]:
            with self.assertRaises(candidate.qsa.Blocked):
                candidate.verify_child(mutated, parent, expected)

    def test_original_must_be_running_before_image_ops(self):
        with patch.object(candidate.release, "_legacy_state_for_release",
                          return_value=({"id": "a"*64}, {"Id": "a"*64}, {}, "exited")), \
             patch.object(candidate.release, "_inspect_image") as inspect:
            with self.assertRaisesRegex(candidate.qsa.Blocked, "ORIGINAL_NOT_RUNNING"):
                candidate.build("a"*40)
            inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
