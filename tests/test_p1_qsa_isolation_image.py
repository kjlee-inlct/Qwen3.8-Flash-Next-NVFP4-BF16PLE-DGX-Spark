"""QSA-only image controlled experiment CPU-only guard tests."""
import unittest
from unittest.mock import patch

from src import p1_qsa_isolation_image as i


class Tests(unittest.TestCase):
    H = "a"*40

    def test_dockerfile_original_base_only_one_qsa_copy(self):
        df=i.dockerfile()
        self.assertIn("FROM "+i.legacy.IMAGE_TAG,df)
        self.assertNotIn("kjlee-qwen38-p1-prefix",df)
        self.assertEqual(df.count("\nCOPY "),1)
        self.assertIn("qsa.py ",df)
        self.assertIn("ENV VLLM_QSA_EXACT_TOPK=1",df)
        self.assertNotIn("\nRUN ",df)
        self.assertNotIn("scheduler.py",df)
        self.assertNotIn("mamba_hybrid.py",df)

    def test_ancestry_requires_exact_one_layer_and_label_env(self):
        base={"RootFS":{"Layers":["a","b"]}}
        d=i.labels(self.H,"f"*64)
        child={"RootFS":{"Layers":["a","b","c"]},
               "Config":{"Labels":d,"Env":["VLLM_QSA_EXACT_TOPK=1"]}}
        i.check_image(child,base,self.H,"f"*64)
        with self.assertRaisesRegex(i.qsa.Blocked,"ANCESTRY"):
            i.check_image({**child,"RootFS":{"Layers":["x","b","c"]}},
                          base,self.H,"f"*64)
        with self.assertRaisesRegex(i.qsa.Blocked,"LABEL_DRIFT"):
            i.check_image({**child,"Config":{"Labels":{},"Env":["VLLM_QSA_EXACT_TOPK=1"]}},
                          base,self.H,"f"*64)

    def test_pinned_qsa_activation_requires_one_switch(self):
        base={"RootFS":{"Layers":["a","b"]}}
        child={"RootFS":{"Layers":["a","b","c"]},
               "Config":{"Labels":i.labels(self.H,"f"*64),
                         "Env":["VLLM_QSA_EXACT_TOPK=1"]}}
        for env in ([],["VLLM_QSA_EXACT_TOPK=0"],
                    ["VLLM_QSA_EXACT_TOPK=1"]*2):
            with self.assertRaisesRegex(i.qsa.Blocked,"FLAG_DRIFT"):
                i.check_image({**child,"Config":{**child["Config"],"Env":env}},
                              base,self.H,"f"*64)

    def test_original_exited_blocks_before_image_build(self):
        receipt={"id":"b"*64}
        original={"Id":"b"*64}
        base={"Id":i.ORIGINAL_IMAGE_ID}
        with patch.object(i.release,"_legacy_state_for_release",
                          return_value=(receipt,original,base,"exited")), \
             patch.object(i.qsa,"read_qsa") as copied:
            with self.assertRaisesRegex(i.qsa.Blocked,"ORIGINAL_DRIFT"):
                i.build(self.H)
            copied.assert_not_called()

    def test_only_legacy_original_image_is_allowed(self):
        receipt={"id":"b"*64}
        original={"Id":"b"*64}
        base={"Id":"sha256:"+"f"*64}
        with patch.object(i.release,"_legacy_state_for_release",
                          return_value=(receipt,original,base,"running")), \
             patch.object(i.qsa,"read_qsa") as copied:
            with self.assertRaisesRegex(i.qsa.Blocked,"ORIGINAL_DRIFT"):
                i.build(self.H)
            copied.assert_not_called()


if __name__ == "__main__":
    unittest.main()
