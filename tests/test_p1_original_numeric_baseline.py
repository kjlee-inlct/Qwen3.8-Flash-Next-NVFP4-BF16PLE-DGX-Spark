"""Offline original Prefix-OFF numeric baseline; no Docker/GPU/network."""
import unittest
from unittest.mock import patch

from src import p1_original_numeric_baseline as b


def run(ids, logs, *, finish="stop"):
    return {"token_ids": ids, "logprobs": logs, "finish_reason": finish}


class Tests(unittest.TestCase):
    def test_exact_four_requests_required(self):
        with self.assertRaisesRegex(b.Blocked, "REQUEST_COUNT_INVALID"):
            b.compare([])

    def test_identical_logprobs_under_tolerance(self):
        ids=list(range(150))
        runs=[run(ids,[0.01]*150) for _ in range(4)]
        out=b.compare(runs)
        self.assertEqual(out["status"], "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT")
        self.assertTrue(out["original_reproducible_at_strict"])
        self.assertFalse(out["p1_final_pass"])

    def test_no_hit_numeric_drift_does_not_pass_strict(self):
        ids=list(range(150))
        runs=[run(ids,[0.01]*150) for _ in range(4)]
        runs[1]["logprobs"][0]+=0.0001794818672351539
        out=b.compare(runs)
        self.assertEqual(out["status"], "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
        self.assertFalse(out["original_reproducible_at_strict"])
        self.assertEqual(out["strict_exceed_positions_0_based_first16"],[0])

    def test_token_id_change_blocks_numerical_attribution(self):
        ids=list(range(150))
        runs=[run(ids.copy(),[0.01]*150) for _ in range(4)]
        runs[2]["token_ids"][5]=700
        out=b.compare(runs)
        self.assertEqual(out["status"], "INCONCLUSIVE_TOKEN_IDS_DIFFER")
        self.assertIsNone(out["all_pairs_max_abs_delta"])

    def test_short_generation_cannot_claim_reproducible(self):
        runs=[run(list(range(32)),[0.01]*32) for _ in range(4)]
        self.assertEqual(b.compare(runs)["status"], "INCONCLUSIVE_TOO_FEW_TOKENS")

    def test_baseline_enforces_original_off_before_any_request(self):
        with patch.object(b.release, "_legacy_state_for_release",
                          return_value=({"id":"x"*64},{"Id":"x"*64,
                               "Config":{"Cmd":[]}},{},"exited")), \
             patch.object(b.oracle, "request_json") as request:
            with self.assertRaisesRegex(b.Blocked,"ORIGINAL_NOT_RUNNING"):
                b.precheck()
            request.assert_not_called()

    def test_baseline_uses_exact_four_real_synthetic_requests(self):
        ids=list(range(150))
        r=run(ids,[0.01]*150)
        with patch.object(b.oracle,"build_payload",return_value={
                "messages":[{"role":"user","content":"synthetic"}]}), \
             patch.object(b.oracle,"request_json",return_value={"mock":True}) as request, \
             patch.object(b.oracle,"extract",return_value=r), \
             patch.object(b.oracle,"validate_chat_output"), \
             patch.object(b,"precheck",return_value=("model","x"*64)):
            out=b.baseline("model","x"*64)
        self.assertEqual(request.call_count,4)
        self.assertEqual(out["request_count"],4)
        self.assertFalse(out["p1_candidate_numeric_pass"])


if __name__ == "__main__":
    unittest.main()
