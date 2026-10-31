"""No GPU/Docker: ensure P1 window always attempts safe same-ID recovery."""
import unittest
from unittest.mock import patch

from src import p1_integrated_window as window


class WindowTests(unittest.TestCase):
    H = "a" * 40
    ID = "b" * 64
    C = "c" * 64

    def _pre(self):
        return {"original_state": "running", "original_id": self.ID}

    def test_no_approval_exits_before_any_preflight(self):
        with patch.object(window.qsa, "preflight") as guarded:
            self.assertEqual(window.main([
                "--expected-head", self.H, "--confirm-original-id", self.ID,
            ]), 2)
            guarded.assert_not_called()

    def test_wrong_original_state_blocks_before_stop(self):
        with patch.object(window.runtime, "preflight",
                          return_value={"original_state": "exited",
                                        "original_id": self.ID}), \
             patch.object(window.release, "_run") as stopped:
            with self.assertRaisesRegex(window.WindowBlocked, "PREFLIGHT_ORIGINAL_DRIFT"):
                window.execute_window(self.H, self.ID)
            stopped.assert_not_called()

    def test_success_still_not_full_state_p1_pass(self):
        with patch.object(window.runtime, "preflight", return_value=self._pre()), \
             patch.object(window, "assert_original_running", return_value="model"), \
             patch.object(window.oracle, "probe_before_stop",
                          return_value={"status":"PASS_ORIGINAL_CHAT_PROTOCOL"}), \
             patch.object(window.release, "_run"), \
             patch.object(window.release, "_legacy_state_for_release",
                          return_value=({"id":self.ID},{"Id":self.ID},{},"exited")), \
             patch.object(window.runtime, "launch", return_value={"candidate_id":self.C}), \
             patch.object(window.api, "api_smoke", return_value={"status":"API_SMOKE_PASS"}), \
             patch.object(window.api, "prefix_oracle",
                          return_value={"strict_numeric_pass":True}), \
             patch.object(window, "safe_restore_after_window",
                          return_value={"same_id_http_verified":True}) as restore:
            result = window.execute_window(self.H, self.ID)
        restore.assert_called_once_with(self.H, self.ID, self.C, "model")
        self.assertFalse(result["p1_final_pass"])
        self.assertFalse(result["full_GDN_PLE_layer_reuse_verified"])

    def test_api_exception_still_runs_prefix_and_restores(self):
        with patch.object(window.runtime, "preflight", return_value=self._pre()), \
             patch.object(window, "assert_original_running", return_value="model"), \
             patch.object(window.oracle, "probe_before_stop",
                          return_value={"status":"PASS_ORIGINAL_CHAT_PROTOCOL"}), \
             patch.object(window.release, "_run"), \
             patch.object(window.release, "_legacy_state_for_release",
                          return_value=({"id":self.ID},{"Id":self.ID},{},"exited")), \
             patch.object(window.runtime, "launch", return_value={"candidate_id":self.C}), \
             patch.object(window.api, "api_smoke", side_effect=RuntimeError("hidden")), \
             patch.object(window.api, "prefix_oracle",
                          return_value={"strict_numeric_pass":False}) as numeric, \
             patch.object(window, "safe_restore_after_window",
                          return_value={"same_id_http_verified":True}) as restore:
            result = window.execute_window(self.H, self.ID)
        self.assertEqual(result["status"], "P1_INTEGRATED_GPU_VALIDATION_INCOMPLETE")
        numeric.assert_called_once()
        restore.assert_called_once()

    def test_stop_failure_still_checks_and_restores_original(self):
        with patch.object(window.runtime, "preflight", return_value=self._pre()), \
             patch.object(window, "assert_original_running", return_value="model"), \
             patch.object(window.oracle, "probe_before_stop",
                          return_value={"status":"PASS_ORIGINAL_CHAT_PROTOCOL"}), \
             patch.object(window.release, "_run",
                          side_effect=window.release.ReleaseBlocked("COMMAND_FAILED")), \
             patch.object(window, "safe_restore_after_window",
                          return_value={"same_id_http_verified":True}) as restore:
            result = window.execute_window(self.H, self.ID)
        self.assertEqual(result["status"], "P1_INTEGRATED_GPU_VALIDATION_INCOMPLETE")
        restore.assert_called_once_with(self.H, self.ID, None, "model")

    def test_recovery_uncertainty_never_claims_success(self):
        with patch.object(window.runtime, "preflight", return_value=self._pre()), \
             patch.object(window, "assert_original_running", return_value="model"), \
             patch.object(window.oracle, "probe_before_stop",
                          return_value={"status":"PASS_ORIGINAL_CHAT_PROTOCOL"}), \
             patch.object(window.release, "_run",
                          side_effect=window.release.ReleaseBlocked("COMMAND_FAILED")), \
             patch.object(window, "safe_restore_after_window",
                          side_effect=window.WindowBlocked("unsafe")):
            with self.assertRaisesRegex(
                    window.WindowBlocked, "RECOVERY_NOT_CONFIRMED"):
                window.execute_window(self.H, self.ID)

    def test_no_candidate_id_and_exited_recovery_no_simultaneous_gpu(self):
        with patch.object(window.release, "_legacy_state_for_release",
                          return_value=({"id":self.ID},{"Id":self.ID},{},"exited")), \
             patch.object(window.runtime, "no_other_candidates") as absence, \
             patch.object(window.runtime, "restore_original") as start:
            out = window.safe_restore_after_window(self.H, self.ID, None, "model")
        absence.assert_called_once()
        start.assert_called_once_with(self.H, self.ID, "model")
        self.assertTrue(out["same_id_http_verified"])

    def test_candidate_recovery_calls_exact_id_restore(self):
        with patch.object(window.runtime, "restore",
                          return_value={"original_id":self.ID}) as restore:
            out = window.safe_restore_after_window(
                self.H, self.ID, self.C, "model")
        restore.assert_called_once_with(self.H, self.ID, self.C)
        self.assertTrue(out["same_id_http_verified"])


if __name__ == "__main__":
    unittest.main()
