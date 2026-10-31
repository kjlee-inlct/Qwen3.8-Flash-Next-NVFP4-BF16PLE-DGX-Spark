"""Offline P1 integrated API client guard tests. No network/GPU."""
import unittest
from unittest.mock import patch

from src import p1_integrated_api_check as candidate


class Tests(unittest.TestCase):
    H = "a"*40
    ID = "b"*64

    def test_only_fixed_loopback_paths(self):
        with self.assertRaisesRegex(candidate.Blocked, "ALLOWLISTED"):
            candidate.request("/admin", {})

    def test_running_original_blocks_any_client_probes(self):
        with patch.object(candidate.release, "_legacy_state_for_release",
                          return_value=({"id": self.ID},
                                        {"Id": self.ID}, {}, "running")), \
             patch.object(candidate.runtime, "verify_image") as check:
            with self.assertRaisesRegex(candidate.Blocked, "MUST_BE_EXITED"):
                candidate.verify_live(self.H, self.ID)
            check.assert_not_called()

    def test_api_smoke_success_cannot_promote_final(self):
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate, "tool_smoke"), \
             patch.object(candidate, "responses_smoke"):
            result = candidate.api_smoke(self.H, self.ID)
        self.assertEqual(result["status"], "API_SMOKE_PASS")
        self.assertFalse(result["p1_final_pass"])

    def test_api_smoke_error_is_structured(self):
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate, "tool_smoke",
                          side_effect=candidate.Blocked("TOOL_FAILED")), \
             patch.object(candidate, "responses_smoke"):
            result = candidate.api_smoke(self.H, self.ID)
        self.assertEqual(result["checks"]["tool_chat"], "TOOL_FAILED")
        self.assertEqual(result["status"], "API_SMOKE_INCOMPLETE")

    def test_old_strict_drift_still_fails(self):
        report = {"status": "INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE",
                  "cache_hit_observed": True, "mtp_acceptance_observed": True,
                  "max_token_logprob_abs_delta": 0.0003418332780711353}
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate.oracle, "run_oracle", return_value=report):
            result = candidate.prefix_oracle(self.H, self.ID)
        self.assertFalse(result["strict_numeric_pass"])
        self.assertFalse(result["p1_final_pass"])
        self.assertEqual(result["strict_abs_tolerance"], 1e-4)

    def test_cold_hit_strict_without_verified_controls_not_final_numeric(self):
        report = {"status": "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS",
                  "cache_hit_observed": True, "mtp_acceptance_observed": True,
                  "all_repeats_token_ids_equal": True,
                  "max_token_logprob_abs_delta": 0.00008}
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate.oracle, "run_oracle", return_value=report):
            result = candidate.prefix_oracle(self.H, self.ID)
        self.assertTrue(result["cold_hit_strict_pass"])
        self.assertFalse(result["strict_numeric_pass"])
        self.assertFalse(result["p1_final_pass"])

    def test_full_numeric_requires_both_independent_controls(self):
        report = {"status": "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS",
                  "cache_hit_observed": True, "mtp_acceptance_observed": True,
                  "all_repeats_token_ids_equal": True,
                  "max_token_logprob_abs_delta": 0.00008,
                  "same_input_cold_controls": {
                      "status": "CONTROL_NO_PREFIX_HIT_OBSERVED_NUMERIC_PARITY_MEASURED",
                      "all_controls_no_prefix_hit_observed": True,
                      "all_controls_token_ids_match_reference": True,
                      "cold_reference_to_control_max_abs_delta": 0.00005},
                  "no_hit_strict_numeric_baseline": {
                      "status": "NO_HIT_BASELINE_WITHIN_STRICT_GATE",
                      "no_hit_numeric_reproducibility_at_strict_gate": True}}
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate.oracle, "run_oracle", return_value=report):
            result = candidate.prefix_oracle(self.H, self.ID)
        self.assertTrue(result["strict_numeric_pass"])
        self.assertFalse(result["p1_final_pass"])
        self.assertFalse(result["full_state_reuse_verified"])

    def test_original_cold_reference_drift_blocks_numeric(self):
        report = {"status": "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS",
                  "cache_hit_observed": True, "mtp_acceptance_observed": True,
                  "all_repeats_token_ids_equal": True,
                  "max_token_logprob_abs_delta": 0.00008,
                  "same_input_cold_controls": {
                      "status": "CONTROL_NO_PREFIX_HIT_OBSERVED_NUMERIC_PARITY_MEASURED",
                      "all_controls_no_prefix_hit_observed": True,
                      "all_controls_token_ids_match_reference": True,
                      "cold_reference_to_control_max_abs_delta": 0.0002452},
                  "no_hit_strict_numeric_baseline": {
                      "status": "NO_HIT_BASELINE_WITHIN_STRICT_GATE",
                      "no_hit_numeric_reproducibility_at_strict_gate": True}}
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate.oracle, "run_oracle", return_value=report):
            result = candidate.prefix_oracle(self.H, self.ID)
        self.assertTrue(result["cold_hit_strict_pass"])
        self.assertFalse(result["cold_reference_to_no_hit_strict_pass"])
        self.assertFalse(result["strict_numeric_pass"])

    def test_tool_roundtrip_requires_valid_call_id_and_followup(self):
        first = {"choices": [{"finish_reason": "tool_calls",
            "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_abc123", "type": "function",
                    "function": {"name": "weather", "arguments": '{"city":"Seoul"}'}}]}}]}
        second = {"choices": [{"finish_reason": "stop",
            "message": {"role": "assistant", "content": "Clear."}}]}
        with patch.object(candidate, "request", side_effect=[first, second]) as send:
            candidate.tool_smoke("model")
        self.assertEqual(send.call_count, 2)
        second_payload = send.call_args_list[1].args[1]
        self.assertEqual(second_payload["messages"][-1]["tool_call_id"], "call_abc123")
        self.assertEqual(second_payload["messages"][-1]["role"], "tool")


if __name__ == "__main__":
    unittest.main()
