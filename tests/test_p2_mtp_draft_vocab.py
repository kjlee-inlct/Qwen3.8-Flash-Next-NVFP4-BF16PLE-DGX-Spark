"""CPU-only reduced draft vocabulary ABI contract tests; no weights/model."""
import unittest

from src.p2_mtp_draft_vocab import DraftVocab, DraftVocabError


def mapping():
    return DraftVocab.validate([5, 1, 7, 0], target_size=8, draft_size=4,
                               required_token_ids=(0, 7))


class DraftVocabTests(unittest.TestCase):
    def test_forward_and_reverse_exact(self):
        m = mapping()
        self.assertEqual(m.full_ids([0, 3, 2]), (5, 0, 7))
        self.assertEqual(m.draft_indices([7, 0, 4, 5]), (2, 3, None, 0))

    def test_invalid_duplicate_or_out_of_range(self):
        for ids in ([1, 2, 2, 3], [1, 2, 3, 8], [-1, 2, 3, 4],
                    [True, 2, 3, 4]):
            with self.subTest(ids=ids), self.assertRaises(DraftVocabError):
                DraftVocab.validate(ids, target_size=8, draft_size=4)

    def test_missing_special_tokens_fails(self):
        with self.assertRaisesRegex(DraftVocabError, "REQUIRED_SPECIAL"):
            DraftVocab.validate([1, 2, 3, 4], target_size=8, draft_size=4,
                                required_token_ids=(0,))

    def test_wrong_vocab_sizes_fail(self):
        with self.assertRaises(DraftVocabError):
            DraftVocab.validate([1, 2, 3], target_size=8, draft_size=4)

    def test_unrepresentable_tokens_not_aliased(self):
        m = mapping()
        self.assertEqual(m.draft_indices([3]), (None,))
        with self.assertRaisesRegex(DraftVocabError, "FULL_TOKEN_OUT"):
            m.draft_indices([8])
        with self.assertRaisesRegex(DraftVocabError, "DRAFT_INDEX_OUT"):
            m.full_ids([4])

    def test_reduced_head_size_must_match(self):
        m = mapping()
        m.validate_head_rows(4)
        with self.assertRaisesRegex(DraftVocabError, "NOT_REDUCED"):
            m.validate_head_rows(8)

    def test_pinned_production_dims_no_weights_changed(self):
        m = DraftVocab.validate(list(range(65536)), required_token_ids=(0, 10))
        report = m.plan()
        self.assertEqual(report["draft_vocab_size"], 65536)
        self.assertEqual(report["target_vocab_size"], 248320)
        self.assertEqual(len(report["draft_index_mapping_sha256"]), 64)
        self.assertFalse(report["weights_sliced"])
        self.assertFalse(report["target_head_modified"])
        self.assertFalse(report["draft_head_loader_abi_verified"])


if __name__ == "__main__":
    unittest.main()
