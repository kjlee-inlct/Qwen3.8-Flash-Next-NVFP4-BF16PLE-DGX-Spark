"""P2 CPU BF16 reduced head, not native engine or checkpoint integration."""
import unittest

try:
    import torch
except ImportError:
    torch = None

from src.p2_mtp_draft_vocab import DraftVocab, DraftVocabError
from src.p2_mtp_head_cpu import (reduce_bf16_head, compare_selected_logits,
                                 remap_draft_indices_cpu, implementation_receipt)


@unittest.skipIf(torch is None, "CPU torch missing: does not count as PASS")
class HeadCpuTests(unittest.TestCase):
    def setUp(self):
        self.map = DraftVocab.validate([5, 1, 7, 0], target_size=8, draft_size=4,
                                       required_token_ids=(0, 7))
        self.full = torch.arange(32, dtype=torch.float32).reshape(8, 4).to(torch.bfloat16)

    def test_selected_rows_and_independent_storage(self):
        original = self.full.clone()
        draft = reduce_bf16_head(self.full, self.map)
        self.assertEqual(tuple(draft.shape), (4, 4))
        self.assertEqual(draft.dtype, torch.bfloat16)
        self.assertTrue(torch.equal(draft, self.full[[5, 1, 7, 0]]))
        self.assertNotEqual(self.full.data_ptr(), draft.data_ptr())
        draft[0, 0] = -999
        self.assertTrue(torch.equal(self.full, original))

    def test_cpu_selected_target_logits_match_reduced(self):
        draft = reduce_bf16_head(self.full, self.map)
        hidden = torch.tensor([[1, 0, -1, 2], [0, 2, 0, -3]],
                              dtype=torch.bfloat16)
        self.assertTrue(compare_selected_logits(hidden, self.full, draft, self.map))

    def test_wrong_head_shape_and_dtype_blocked(self):
        for bad in (self.full[1:], self.full.float(),
                    self.full[:, :0], self.full.unsqueeze(0)):
            with self.subTest(shape=tuple(bad.shape), dtype=str(bad.dtype)), \
                 self.assertRaisesRegex(DraftVocabError, "SHAPE_REQUIRED"):
                reduce_bf16_head(bad, self.map)

    def test_training_weight_and_invalid_mapping_blocked(self):
        t = self.full.clone().requires_grad_(True)
        with self.assertRaisesRegex(DraftVocabError, "TRAINABLE"):
            reduce_bf16_head(t, self.map)
        forged = DraftVocab((0, 0, 1, 2), target_size=8, required_token_ids=())
        with self.assertRaisesRegex(DraftVocabError, "ROW_MAPPING"):
            reduce_bf16_head(self.full, forged)

    def test_real_dimension_memory_bounded_synthetic(self):
        # Only 248320 x 2 BF16: ~1 MB. No real 31-tensor model or checkpoint.
        mapping = DraftVocab.validate(list(range(65536)), required_token_ids=(0,))
        weight = torch.arange(496640, dtype=torch.float32).reshape(248320, 2).to(torch.bfloat16)
        result = reduce_bf16_head(weight, mapping)
        self.assertEqual(tuple(result.shape), (65536, 2))
        self.assertTrue(torch.equal(result[0], weight[0]))
        self.assertTrue(torch.equal(result[-1], weight[65535]))
        self.assertNotEqual(result.data_ptr(), weight.data_ptr())

    def test_draft_indices_remap_to_full_tokens(self):
        proposal = torch.tensor([[0, 2], [3, 1]], dtype=torch.int64)
        remapped = remap_draft_indices_cpu(proposal, self.map)
        self.assertEqual(remapped.tolist(), [[5, 7], [0, 1]])
        self.assertEqual(remapped.dtype, torch.int64)
        self.assertTrue(torch.equal(proposal, torch.tensor([[0, 2], [3, 1]])))
        for invalid in (torch.tensor([-1]), torch.tensor([4])):
            with self.assertRaisesRegex(DraftVocabError, "OUT_OF_RANGE"):
                remap_draft_indices_cpu(invalid, self.map)
        forged = DraftVocab((0, 0, 1, 2), target_size=8, required_token_ids=())
        with self.assertRaisesRegex(DraftVocabError, "ROW_MAPPING"):
            remap_draft_indices_cpu(torch.tensor([0]), forged)

    def test_receipt_never_claims_runtime(self):
        d = implementation_receipt(self.map)
        self.assertFalse(d["writes_to_checkpoint"])
        self.assertFalse(d["modifies_target_head"])
        self.assertFalse(d["installed_preview_loader_bound"])
        self.assertFalse(d["candidate_gpu_or_api_tested"])


if __name__ == "__main__":
    unittest.main()
