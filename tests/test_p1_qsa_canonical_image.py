"""Canonical QSA B2 image source contracts. Standard-library only."""
import unittest
from unittest.mock import patch

from src import p1_qsa_canonical_image as b2


class Tests(unittest.TestCase):
    HEAD = "a" * 40

    def test_canonical_diff_is_exactly_one_sort_operation(self):
        base = b"def placeholder():\n    indices = torch.topk(safe, k=k, dim=1, sorted=False).indices\n"
        # Stand-in transformer output must parse and contain the stock fallback.
        patched = (base + b"    torch.ops._C.persistent_topk\n")
        with patch.object(b2.qsa, "transform", return_value=patched):
            out = b2.canonical_transform(b"original bytes")
        self.assertEqual(out, patched.replace(b2.UNSORTED, b2.CANONICAL))
        self.assertIn(b".indices.sort(dim=1).values", out)
        self.assertNotIn(b2.UNSORTED, out)

    def test_duplicate_anchor_fails_closed(self):
        patched = (b"def example():\n" + b2.UNSORTED*2 +
                   b"    torch.ops._C.persistent_topk\n")
        with patch.object(b2.qsa, "transform", return_value=patched):
            with self.assertRaisesRegex(b2.qsa.Blocked, "ANCHOR_INVALID"):
                b2.canonical_transform(b"source")

    def test_original_base_exactly_one_copy_and_one_opt_in(self):
        df = b2.dockerfile()
        self.assertIn("FROM " + b2.legacy.IMAGE_TAG, df)
        self.assertEqual(df.count("\nCOPY "), 1)
        self.assertEqual(df.count("ENV VLLM_QSA_EXACT_TOPK=1"), 1)
        self.assertNotIn("scheduler.py", df)
        self.assertNotIn("mamba_hybrid.py", df)
        self.assertNotIn("\nRUN ", df)

    def test_image_layers_labels_and_default_settings(self):
        base = {"RootFS":{"Layers":["x","y"]},
                "Config":{"Entrypoint":["serve"], "Cmd":["--no-enable-prefix-caching"],
                          "Env":["base=1"],"User":"","WorkingDir":"/"}}
        c = {"RootFS":{"Layers":["x","y","z"]},
             "Config":{**base["Config"],"Env":["base=1","VLLM_QSA_EXACT_TOPK=1"],
                       "Labels":b2.labels(self.HEAD, "f"*64)}}
        b2.check_image(c,base,self.HEAD,"f"*64)
        bad = {**c, "RootFS":{"Layers":["z","x","y"]}}
        with self.assertRaisesRegex(b2.qsa.Blocked, "LAYER_DRIFT"):
            b2.check_image(bad,base,self.HEAD,"f"*64)
        bad = {**c, "Config":{**c["Config"], "Cmd":["--enable-prefix-caching"]}}
        with self.assertRaisesRegex(b2.qsa.Blocked, "RUNTIME_DEFAULT_DRIFT"):
            b2.check_image(bad,base,self.HEAD,"f"*64)

    def test_original_not_running_never_reads_qsa_or_builds(self):
        receipt={"id":"b"*64}
        original={"Id":receipt["id"]}
        base={"Id":b2.legacy.IMAGE_ID}
        with patch.object(b2.release,"_legacy_state_for_release",
                          return_value=(receipt,original,base,"exited")), \
             patch.object(b2.qsa,"read_qsa") as read, \
             patch.object(b2.qsa,"command") as command:
            with self.assertRaisesRegex(b2.qsa.Blocked, "B2_ORIGINAL_ID_OR_STATE"):
                b2.build(self.HEAD)
            read.assert_not_called()
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
