"""P1 B2 canonical-runtime isolation and two-arm numeric window CPU tests."""
import unittest
from unittest.mock import patch

from src import p1_qsa_canonical_runtime as b2
from src import p1_qsa_canonical_window as w


class Tests(unittest.TestCase):
    H = "a"*40
    O = w.window.ORIGINAL_ID
    C = "c"*64

    @staticmethod
    def first(token=100, lp=-0.23, reason="length"):
        return {"token_ids":[token], "logprobs":[lp],
                "finish_reason": reason}

    @staticmethod
    def long(token=0, lp=-0.2):
        return {"token_ids":list(range(token,token+150)),
                "logprobs":[lp]*150, "finish_reason":"stop"}

    def test_pins_actual_b2_operator_image_and_source(self):
        self.assertEqual(b2.PIN_BUILD_HEAD,
                         "6aa092842c354ef2b6ce63a58fc42d2edd3b806d")
        self.assertEqual(b2.PIN_IMAGE_ID,
                         "sha256:fc74fa28ffc3bee18f630ee5dd54441ba93d21b73698700d19859a6829b9693b")
        self.assertEqual(b2.PIN_PATCH_SHA,
                         "7a76dad0c02e7cd29ce399b2c23f5fd7977334802f1a50574b8ad023f579a278")
        self.assertEqual(b2.PIN_TAG, b2.image_builder.tag(b2.PIN_BUILD_HEAD))
        self.assertNotEqual(b2.PIN_TAG, "kjlee-qwen38-p1-qsa-canonical:wrong")
        self.assertIn("p1-qsa-only-candidate", b2.OTHER_NAMES)

    def test_b2_checks_image_lineage_and_patch_sha(self):
        with patch.object(b2.release,"_inspect_image",
                          side_effect=[{"Id":b2.legacy.IMAGE_ID,"Config":{}},
                                       {"Id":b2.PIN_IMAGE_ID,"Config":{}}]), \
             patch.object(b2.image_builder, "check_image") as image:
            b2.verify_image()
        image.assert_called_once()
        self.assertEqual(image.call_args.args[2:],
                         (b2.PIN_BUILD_HEAD,b2.PIN_PATCH_SHA))

    def test_single_token_comparator_strict_exact(self):
        good=[self.first(lp=x) for x in (-0.2,-0.20004,-0.2,-0.2)]
        r=w.compare_first(good)
        self.assertTrue(r["strict_pass"])
        self.assertEqual(r["tokens_each"],[1]*4)
        bad=[self.first(lp=x) for x in (-0.2,-0.20014,-0.2,-0.2)]
        r=w.compare_first(bad)
        self.assertEqual(r["status"],"SINGLE_TOKEN_NUMERIC_ABOVE_STRICT")
        self.assertFalse(r["strict_pass"])
        self.assertEqual(r["strict_abs_tolerance"],1e-4)

    def test_first_token_ids_mismatch_forbids_numeric_comparison(self):
        items=[self.first(token=x) for x in (1,2,1,1)]
        r=w.compare_first(items)
        self.assertEqual(r["status"],"SINGLE_TOKEN_ID_OR_FINISH_INCONCLUSIVE")
        self.assertIsNone(r["all_pairs_max_abs_delta"])

    def test_cross_arm_first_token_does_not_claim_causation(self):
        a=[self.first()]*4
        b=[self.first(lp=-0.21)]*4
        r=w.cross_first(a,b)
        self.assertEqual(r["causal_qsa_conclusion"],"NOT_PROVEN")
        self.assertTrue(r["same_request_index_token_ids_and_finish"])
        c=[self.first(token=101)]*4
        self.assertIsNone(w.cross_first(a,c)["max_abs_delta"])

    def test_first_token_fails_closed_before_any_request_if_wrong_payload(self):
        with patch.object(w.oracle, "request_json") as api:
            with self.assertRaisesRegex(w.Blocked, "PAYLOAD_DRIFT"):
                w.collect_first(8000,{"max_tokens":10,"seed":42},lambda:None)
        api.assert_not_called()

    def test_first_token_allows_empty_text_but_requires_numeric_proof(self):
        payload={"max_tokens":1,"seed":42}
        raw={"choices":[{"message":{"content":""},
                         "logprobs":{"content":[{"token":"t","logprob":-0.25}]},
                         "token_ids":[33],"finish_reason":"length"}]}
        with patch.object(w.oracle,"request_json",return_value=raw), \
             patch.object(w.oracle,"extract",return_value=self.first()):
            ret=w.collect_first(18080,payload,lambda:None)
        self.assertEqual(len(ret),4)

    def test_recovery_only_owned_candidate_before_original_start(self):
        r={"id":self.O,"cache":"/cache","views":"/views"}
        with patch.object(b2,"original_state",
                          return_value=(r,{},{},"exited")), \
             patch.object(b2,"candidate_ids",side_effect=[[self.C],[],[]]), \
             patch.object(b2,"cleanup_owned") as cleanup, \
             patch.object(b2,"restore_original") as restore, \
             patch.object(w.window,"check_original_running"):
            w.restore_b2(self.H,self.O,"m")
        cleanup.assert_called_once_with(self.H,self.C,r)
        restore.assert_called_once_with(self.H,self.O,"m")

    def test_foreign_candidate_blocks_restoration_to_avoid_two_gpu_models(self):
        r={"id":self.O}
        with patch.object(b2,"original_state",
                          return_value=(r,{},{},"exited")), \
             patch.object(b2,"candidate_ids",return_value=[self.C]), \
             patch.object(b2,"cleanup_owned",side_effect=b2.qsa.Blocked("FOREIGN")), \
             patch.object(b2,"restore_original") as restore:
            with self.assertRaisesRegex(b2.qsa.Blocked,"FOREIGN"):
                w.restore_b2(self.H,self.O,"m")
        restore.assert_not_called()

    def test_a_first_inconclusive_does_not_stop_production(self):
        bad=[self.first(token=x) for x in (1,2,1,1)]
        a_long=[self.long()]*4
        with patch.object(w,"preflight",return_value={}), \
             patch.object(w.baseline,"precheck",return_value=("m",self.O)), \
             patch.object(w.oracle,"build_payload",
                          return_value={"model":"m","messages":[],
                                        "max_tokens":256,"seed":42}), \
             patch.object(w.window,"collect",return_value=a_long), \
             patch.object(w,"collect_first",return_value=bad), \
             patch.object(w.window,"stop_original") as stop:
            with self.assertRaisesRegex(w.Blocked,"A_FIRST_INCONCLUSIVE"):
                w.execute(self.H,self.O)
        stop.assert_not_called()

    def test_b2_request_error_still_calls_restore(self):
        a_first=[self.first()]*4
        a_long=[self.long()]*4
        with patch.object(w,"preflight",return_value={}), \
             patch.object(w.baseline,"precheck",return_value=("m",self.O)), \
             patch.object(w.oracle,"build_payload",
                          return_value={"model":"m","messages":[],
                                        "max_tokens":256,"seed":42}), \
             patch.object(w.window,"collect",
                          side_effect=[a_long, w.Blocked("B2_REQUEST_ERROR")]), \
             patch.object(w,"collect_first",return_value=a_first), \
             patch.object(w.window,"check_original_running"), \
             patch.object(w.window,"stop_original"), \
             patch.object(w.b2,"launch",return_value={"candidate_id":self.C}), \
             patch.object(w,"restore_b2") as restore:
            with self.assertRaisesRegex(w.Blocked,"B2_REQUEST_ERROR"):
                w.execute(self.H,self.O)
        restore.assert_called_once_with(self.H,self.O,"m")


if __name__=="__main__":
    unittest.main()
