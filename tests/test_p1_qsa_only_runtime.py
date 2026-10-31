"""QSA-only B runtime safety contracts; no Docker, GPU or HTTP."""
import unittest
from unittest.mock import patch
from src import p1_qsa_only_runtime as r

class Tests(unittest.TestCase):
    H = "a" * 40
    ORIGINAL = "b" * 64
    CANDIDATE = "c" * 64

    def test_pins_are_exact_operator_b_image(self):
        self.assertEqual(r.PIN_TAG, "kjlee-qwen38-p1-qsa-isolation:c3d31b7f3ab3")
        self.assertEqual(r.PORT, 18080)
        self.assertEqual(r.PIN_IMAGE_ID,
                         "sha256:3d1c21c8fea3ed57dafad2f97c4cd8af1c3bce1f3cb22897cd87901b021b9fe7")

    def test_original_cmd_preserves_prefix_off(self):
        cmd = ["--no-enable-prefix-caching", "--speculative-config",
               '{"method":"mtp","num_speculative_tokens":2}', "--port", "8000"]
        with patch.object(r.gpu, "candidate_cmd", return_value=(
                ["--enable-prefix-caching"], "m")) as probe:
            result, model = r.original_command(cmd)
        self.assertEqual(result, cmd)
        self.assertIsNot(result, cmd)
        self.assertEqual(model, "m")
        probe.assert_called_once_with(cmd)

    def test_prefix_on_rejected_even_if_validation_misbehaves(self):
        with patch.object(r.gpu, "candidate_cmd", return_value=([], "m")):
            with self.assertRaisesRegex(r.qsa.Blocked, "PREFIX_NOT_OFF"):
                r.original_command(["--enable-prefix-caching"])

    def test_running_original_blocks_launch_before_mutation(self):
        with patch.object(r, "original_state", side_effect=r.qsa.Blocked(
                "ORIGINAL_MUST_BE_EXITED")), patch.object(r.release, "_run") as run:
            with self.assertRaises(r.qsa.Blocked):
                r.launch(self.H, self.ORIGINAL)
            run.assert_not_called()

    def test_launch_mismatched_id_blocks_without_mutation(self):
        with patch.object(r, "original_state", return_value=(
                {"id": self.ORIGINAL}, {}, {}, "exited")), \
             patch.object(r.release, "_run") as run:
            with self.assertRaisesRegex(r.qsa.Blocked, "ORIGINAL_CONFIRM_ID"):
                r.launch(self.H, "e"*64)
            run.assert_not_called()

    def test_candidate_missing_or_foreign_labels_blocks_cleanup(self):
        with patch.object(r.legacy, "inspect", return_value={
                "Id": self.CANDIDATE, "Name": "/" + r.NAME, "Image": r.PIN_IMAGE_ID,
                "Config": {"Labels": {}}, "HostConfig": {}}), \
             patch.object(r.release, "_run") as run:
            with self.assertRaisesRegex(r.qsa.Blocked, "OWNERSHIP"):
                r.cleanup_owned(self.H, self.CANDIDATE,
                                {"cache": "/cache", "views": "/views"})
            run.assert_not_called()

    def test_mounts_strictly_read_only(self):
        mounts = [{"Source": "/cache", "Destination": "/recipe/hf-cache",
                   "Type": "bind", "RW": False},
                  {"Source": "/views", "Destination": "/recipe/recipe-views",
                   "Type": "bind", "RW": False}]
        receipt = {"cache": "/cache", "views": "/views"}
        r.verify_mounts({"Mounts": mounts}, receipt)
        mounts[1]["RW"] = True
        with self.assertRaisesRegex(r.qsa.Blocked, "MOUNTS_DRIFT"):
            r.verify_mounts({"Mounts": mounts}, receipt)

    def test_numeric_cannot_touch_gpu_if_original_running(self):
        with patch.object(r, "original_state", side_effect=r.qsa.Blocked(
                "ORIGINAL_MUST_BE_EXITED")), \
             patch.object(r.oracle, "request_json") as request:
            with self.assertRaises(r.qsa.Blocked):
                r.numeric(self.H, self.ORIGINAL, self.CANDIDATE)
            request.assert_not_called()

    def test_restore_requires_original_exited(self):
        with patch.object(r, "original_state", side_effect=r.qsa.Blocked(
                "ORIGINAL_MUST_BE_EXITED")), \
             patch.object(r.release, "_run") as run:
            with self.assertRaises(r.qsa.Blocked):
                r.restore(self.H, self.ORIGINAL, self.CANDIDATE)
            run.assert_not_called()

    def test_numeric_reuses_exact_baseline_metric_without_claiming_p1_pass(self):
        result = {"status": "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT",
                  "original_qsa": "stock", "original_prefix_caching": "OFF",
                  "original_mtp_speculative_tokens": 2,
                  "original_reproducible_at_strict": False,
                  "strict_abs_tolerance": 0.0001}
        with patch.object(r, "original_state", return_value=(
                {"id": self.ORIGINAL}, {"Config": {"Cmd": []}}, {}, "exited")), \
             patch.object(r, "verify_image"), \
             patch.object(r, "owned", return_value={
                "Id": self.CANDIDATE, "State": {"Status": "running"}}), \
             patch.object(r, "verify_mounts"), \
             patch.object(r, "original_command", return_value=([], "model")), \
             patch.object(r.oracle, "build_payload", return_value={
                "messages": [{"role": "user", "content": "synthetic"}]}), \
             patch.object(r.oracle, "request_json", return_value={}) as request, \
             patch.object(r.oracle, "extract", return_value={}), \
             patch.object(r.oracle, "validate_chat_output"), \
             patch.object(r.baseline, "compare", return_value=result):
            output = r.numeric(self.H, self.ORIGINAL, self.CANDIDATE)
        self.assertEqual(request.call_count, 4)
        self.assertEqual(output["status"], "QSA_ONLY_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
        self.assertEqual(output["strict_abs_tolerance"], 1e-4)
        self.assertFalse(output["p1_final_pass"])
        self.assertNotIn("original_qsa", output)

if __name__ == "__main__":
    unittest.main()
