"""Safety and numeric contract for the approved one-shot P1 window; CPU mocks only."""
import unittest
from unittest.mock import patch
from src import p1_qsa_window_bundle as w


class Tests(unittest.TestCase):
    H = "a" * 40
    O = w.ORIGINAL_ID
    C = "c" * 64

    @staticmethod
    def run_data(delta=0, token_offset=0):
        return [{"token_ids": list(range(token_offset, token_offset+150)),
                 "logprobs": [-0.15 + delta] * 150,
                 "finish_reason": "stop"}]

    def test_same_payload_arm_reproducibility_and_cross_arm_diagnostic(self):
        a = [self.run_data(delta)[0] for delta in (0, 0.0003, 0, 0)]
        b = [self.run_data(delta)[0] for delta in (0, 0.00005, 0, 0)]
        result = w.summarize(a, b)
        self.assertEqual(result["status"], "AB_MEASURED")
        self.assertEqual(result["A"]["status"],
                         "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
        self.assertTrue(result["B"]["numeric_reproducible_at_strict"])
        self.assertEqual(result["strict_abs_tolerance"], 1e-4)
        self.assertTrue(result["cross_arm_same_index_token_ids"])
        self.assertEqual(result["causal_qsa_conclusion"], "NOT_PROVEN")
        self.assertFalse(result["p1_final_pass"])

    def test_cross_arm_token_mismatch_forbids_logprob_parity(self):
        a = self.run_data()[0]
        b = self.run_data(token_offset=10)[0]
        result = w.summarize([a]*4, [b]*4)
        self.assertFalse(result["cross_arm_same_index_token_ids"])
        self.assertIsNone(result["cross_arm_max_abs_logprob_delta"])

    def test_restore_b_after_exited_cleans_owned_then_original(self):
        receipt = {"id": self.O, "cache": "/cache", "views": "/views"}
        with patch.object(w.b, "original_state", return_value=(
                 receipt, {}, {}, "exited")), \
             patch.object(w.b, "candidate_ids",
                          side_effect=[[self.C], []]), \
             patch.object(w.b, "cleanup_owned") as clean, \
             patch.object(w.b, "restore_original") as start, \
             patch.object(w, "check_original_running"):
            w.restore_b(self.H, self.O, "m")
        clean.assert_called_once_with(self.H, self.C, receipt)
        start.assert_called_once_with(self.H, self.O, "m")

    def test_restore_b_when_running_does_not_call_start(self):
        with patch.object(w.b, "original_state", return_value=(
                 {"id": self.O}, {}, {}, "running")), \
             patch.object(w.b, "candidate_ids", return_value=[]), \
             patch.object(w.b, "restore_original") as start, \
             patch.object(w, "check_original_running"):
            w.restore_b(self.H, self.O, "m")
        start.assert_not_called()

    def test_foreign_candidate_blocks_restore_start(self):
        with patch.object(w.b, "original_state", return_value=(
                 {"id": self.O}, {}, {}, "exited")), \
             patch.object(w.b, "candidate_ids", return_value=[self.C]), \
             patch.object(w.b, "cleanup_owned",
                          side_effect=w.qsa.Blocked("FOREIGN")), \
             patch.object(w.b, "restore_original") as start:
            with self.assertRaisesRegex(w.qsa.Blocked, "FOREIGN"):
                w.restore_b(self.H, self.O, "m")
        start.assert_not_called()

    def test_stop_uses_only_pinned_legacy_script(self):
        with patch.object(w.release, "_run") as call, \
             patch.object(w.b, "original_state", return_value=(
                 {}, {}, {}, "exited")) as state:
            w.stop_original(self.H, self.O)
        argv = call.call_args.args[0]
        self.assertEqual(argv[:2], ["bash", str(w.qsa.ROOT / "scripts/stop.sh")])
        self.assertIn("--confirm-id", argv)
        self.assertEqual(argv[-1], "--execute")
        state.assert_called_once_with("exited")

    def test_failed_b_numeric_still_attempts_restoration(self):
        with patch.object(w.qsa, "preflight"), \
             patch.object(w.b, "original_state", return_value=(
                 {"id": self.O}, {"Id": self.O}, {}, "running")), \
             patch.object(w.b, "preflight"), \
             patch.object(w, "check_original_running"), \
             patch.object(w.baseline, "precheck", return_value=("m", self.O)), \
             patch.object(w.oracle, "build_payload", return_value={
                 "messages": [{"role": "user", "content": "synthetic"}]}), \
             patch.object(w, "collect", side_effect=[
                 [self.run_data()[0]]*4, w.Blocked("B_INFERENCE_FAILED")]), \
             patch.object(w, "stop_original"), \
             patch.object(w.b, "launch", return_value={"candidate_id": self.C}), \
             patch.object(w, "restore_b") as restored:
            with self.assertRaisesRegex(w.Blocked, "B_INFERENCE_FAILED"):
                w.run(self.H, self.O, include_integrated=False)
        restored.assert_called_once_with(self.H, self.O, "m")

    def test_a_inconclusive_never_stops_original(self):
        bad = self.run_data()[0].copy()
        bad["token_ids"] = [1, 2]
        with patch.object(w.qsa, "preflight"), \
             patch.object(w.b, "original_state", return_value=(
                 {"id": self.O}, {"Id": self.O}, {}, "running")), \
             patch.object(w.b, "preflight"), \
             patch.object(w, "check_original_running"), \
             patch.object(w.baseline, "precheck", return_value=("m", self.O)), \
             patch.object(w.oracle, "build_payload", return_value={
                 "messages": [{"role": "user", "content": "synthetic"}]}), \
             patch.object(w, "collect", return_value=[bad]*4), \
             patch.object(w, "stop_original") as stop:
            with self.assertRaisesRegex(w.Blocked, "A_MEASUREMENT_INCONCLUSIVE"):
                w.run(self.H, self.O, include_integrated=False)
        stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
