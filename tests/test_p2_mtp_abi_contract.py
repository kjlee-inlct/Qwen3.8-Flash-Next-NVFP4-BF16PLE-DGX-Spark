"""P2 pinned MTP source structure audit, stdlib only, zero Docker operations."""
import hashlib
import unittest
from unittest.mock import patch

from src import p2_mtp_abi_contract as abi


MTP = b"""class Qwen3_8FlashNextMultiTokenPredictor:
    def __init__(self, config):
        self.draft = None
    def forward(self, hidden):
        return self.draft(hidden)
    def load_weights(self, weights):
        self.draft.load_weights(weights)

class Qwen3_8FlashNextMTP:
    def __init__(self, config):
        self.lm_head = None
        self.logits_processor = None
    def compute_logits(self, hidden):
        return self.logits_processor(self.lm_head, hidden)
    def forward(self, hidden):
        return self.mtp(hidden)
    def load_weights(self, weights):
        self.lm_head.load_weights(weights)
"""


class MtpAbiTests(unittest.TestCase):
    def test_head_and_logits_ast_hints_from_exact_class(self):
        r = abi.source_surface(MTP)
        self.assertEqual(r["sha256"], hashlib.sha256(MTP).hexdigest())
        c = r["classes"]["Qwen3_8FlashNextMTP"]
        self.assertIn("self.lm_head", c["compute_logits"]["referenced_self_attributes"]["names"])
        self.assertIn("self.logits_processor",
                      c["compute_logits"]["referenced_self_attributes"]["names"])
        self.assertIn("self.lm_head", c["__init__"]["assigned_self_attributes"]["names"])
        self.assertFalse(r["head_ownership_proven"])

    def test_three_exact_sha_and_class_abi_guard(self):
        expected = hashlib.sha256(MTP).hexdigest()
        with patch.dict(abi.MTPS, {
            "vllm/models/qwen3_8_flash_next/nvidia/mtp.py": expected,
            "vllm/models/qwen3_8_flash_next/nvidia/model.py": expected,
            "vllm/v1/spec_decode/eagle.py": expected,
        }, clear=True):
            result = abi.check_pinned_sources(
                reader=lambda p: None if p == abi.OPTIONAL_UNVERIFIED else MTP)
        self.assertEqual(result["pinned_source_files"], 3)
        self.assertFalse(result["reduced_head_wired"])
        self.assertFalse(result["runtime_candidate_or_gpu_executed"])
        self.assertFalse(result["source_surfaces"][abi.OPTIONAL_UNVERIFIED]["found"])

    def test_unpinned_source_rejected(self):
        with self.assertRaisesRegex(abi.Blocked, "SOURCE_DRIFT"):
            abi.check_pinned_sources(reader=lambda p: MTP)

    def test_missing_core_class_rejected_even_if_sha_valid(self):
        missing = b"class Dummy:\n    pass\n"
        digest = hashlib.sha256(missing).hexdigest()
        with patch.dict(abi.MTPS, {k: digest for k in abi.MTPS}, clear=True):
            with self.assertRaisesRegex(abi.Blocked, "METHOD_ABI_DRIFT"):
                abi.check_pinned_sources(reader=lambda p: missing)

    def test_exact_original_id_blocks_before_read(self):
        with patch.object(abi.qsa, "preflight"), \
             patch.object(abi.trace, "original_identity") as identity, \
             patch.object(abi, "check_pinned_sources") as read:
            self.assertEqual(abi.main(["--expected-head", "a"*40,
                                       "--confirm-original-id", "wrong",
                                       "--read-installed"]), 2)
            identity.assert_not_called()
            read.assert_not_called()

    def test_invalid_ast_rejected(self):
        with self.assertRaisesRegex(abi.Blocked, "INVALID_AST"):
            abi.source_surface(b"class Bad:\n  def foo(:")


if __name__ == "__main__":
    unittest.main()
