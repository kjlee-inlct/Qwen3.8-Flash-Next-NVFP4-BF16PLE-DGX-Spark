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

    def test_even_strict_pass_is_not_full_state_proof(self):
        report = {"status": "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS",
                  "cache_hit_observed": True, "mtp_acceptance_observed": True,
                  "max_token_logprob_abs_delta": 0.00008}
        with patch.object(candidate, "verify_live", return_value="model"), \
             patch.object(candidate.oracle, "run_oracle", return_value=report):
            result = candidate.prefix_oracle(self.H, self.ID)
        self.assertTrue(result["strict_numeric_pass"])
        self.assertFalse(result["p1_final_pass"])
        self.assertFalse(result["full_state_reuse_verified"])


if __name__ == "__main__":
    unittest.main()
