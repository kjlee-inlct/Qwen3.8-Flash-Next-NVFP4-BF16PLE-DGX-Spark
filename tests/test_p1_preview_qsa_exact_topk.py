"""P1 opt-in exact top-k source patch: zero GPU/HTTP side effects."""
import ast
import hashlib
import unittest
from unittest.mock import patch

from src import p1_preview_qsa_exact_topk as mod


def fixture():
    return ("import torch\n\n"
            "def select(logits, visible_blocks, blocks, topk_workspace, "
            "block_topk, columns, use_cooperative_topk):\n"
            + "    if True:\n" + mod.ANCHOR + "    return blocks\n").encode()


class Tests(unittest.TestCase):
    def test_default_keeps_original_kernel_selection(self):
        raw = fixture()
        patched = mod.transform(raw, expected_sha=hashlib.sha256(raw).hexdigest())
        ast.parse(patched.decode())
        self.assertIn(b'if _P1_EXACT_TOPK:', patched)
        self.assertIn(b'else:\n            topk_op = (', patched)
        self.assertIn(b'torch.ops._C.persistent_topk', patched)
        self.assertIn(b'torch.ops._C.cooperative_topk', patched)

    def test_pinned_sha_refuses_other_qsa(self):
        with self.assertRaisesRegex(mod.Blocked, "QSA_SHA_DRIFT"):
            mod.transform(fixture())

    def test_missing_or_duplicate_anchor_fail_closed(self):
        for raw in (b"import torch\n", fixture() + fixture()):
            with self.assertRaises(mod.Blocked):
                mod.transform(raw, expected_sha=hashlib.sha256(raw).hexdigest())

    def test_double_patch_blocked(self):
        raw = fixture()
        patched = mod.transform(raw, expected_sha=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(mod.Blocked):
            mod.transform(patched, expected_sha=hashlib.sha256(patched).hexdigest())

    def test_invisible_columns_masked(self):
        self.assertIn('logits.masked_fill(invalid, float("-inf"))', mod.HELPER)
        self.assertIn("visible_blocks[:, None]", mod.HELPER)
        self.assertIn("torch.topk(safe, k=k", mod.HELPER)

    def test_dockerfile_only_copy_and_env_no_run(self):
        d = mod.dockerfile()
        self.assertEqual(d.count("\nCOPY "), 1)
        self.assertNotIn("\nRUN ", d)
        self.assertIn("FROM kjlee-qwen38-p1-prefix:c0160408ab22", d)
        self.assertIn("ENV VLLM_QSA_EXACT_TOPK=1", d)

    def test_ancestry_and_env_fail_closed(self):
        head = "a"*40
        parent = {"RootFS": {"Layers": ["a", "b"]}}
        labels = mod.labels(head, "f"*64)
        child = {"RootFS": {"Layers": ["a", "b", "c"]},
                 "Config": {"Labels": labels, "Env": ["VLLM_QSA_EXACT_TOPK=1"]}}
        mod.check_child(child, parent, head, "f"*64)
        with self.assertRaises(mod.Blocked):
            mod.check_child({**child, "RootFS": {"Layers": ["z"]}},
                            parent, head, "f"*64)
        with self.assertRaises(mod.Blocked):
            mod.check_child({**child, "Config": {"Labels": labels, "Env": []}},
                            parent, head, "f"*64)

    def test_exited_original_blocks_build_before_docker(self):
        with patch.object(mod.release, "_legacy_state_for_release",
                          return_value=({"id": "a"*64}, {"Id": "a"*64}, {}, "exited")), \
             patch.object(mod.release, "_release_image") as parent:
            with self.assertRaisesRegex(mod.Blocked, "ORIGINAL_NOT_RUNNING"):
                mod.build("a"*40)
            parent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
