"""Source-pinned candidate MTP hook and token selection tests (stdlib only)."""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import p2_mtp_candidate_overlay as overlay
from src.p2_mtp_vocab_selection import select_draft_vocab, coverage
from src.p2_mtp_draft_vocab import DraftVocabError


FAKE_MTP = b'''class Qwen3_8FlashNextMTP:
    def compute_logits(self, hidden_states, spec_step_idx=0):
        return self.logits_processor(self.lm_head, hidden_states)
'''


def method_sha(data: bytes) -> str:
    tree = ast.parse(data)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef))
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef))
    return hashlib.sha256(ast.dump(fn, include_attributes=False).encode()).hexdigest()


class ReducedDraftCandidateTests(unittest.TestCase):
    def transform_fixture(self):
        return overlay.transform(
            FAKE_MTP, expected_sha=hashlib.sha256(FAKE_MTP).hexdigest(),
            method_sha=method_sha(FAKE_MTP),
        )

    def test_exact_pinned_source_transform_and_default_off(self):
        out = self.transform_fixture()
        ast.parse(out.decode())
        self.assertEqual(out.count(overlay.MARKER.encode()), 1)
        self.assertIn(b'if _P2_DV_PATH:', out)
        self.assertIn(b'Qwen3_8FlashNextMTP.compute_logits =', out)
        self.assertIn(b'float("-inf")', out)
        self.assertIn(b'full.index_copy_(1, ids, reduced)', out)
        self.assertIn(b'head.weight', out) if b'head.weight' in out else self.assertIn(b'getattr(head, "weight"', out)
        self.assertNotIn(b'docker run', out)
        self.assertNotIn(b'checkpoint.save', out)

    def test_hook_is_inert_without_runtime_opt_in(self):
        with patch.dict(os.environ, {overlay.ENV_NAME: "",
                                    overlay.HASH_ENV_NAME: ""}):
            scope = {"__name__": "synthetic_mtp"}
            exec(compile(self.transform_fixture(), "<synthetic pinned MTP>",
                         "exec"), scope)
            self.assertNotIn("_p2dv_state", scope["Qwen3_8FlashNextMTP"].__dict__)
            self.assertIsNot(
                scope["Qwen3_8FlashNextMTP"].compute_logits,
                scope["_p2dv_compute_logits"],
            )

    def test_wrong_source_or_method_sha_fails_closed(self):
        with self.assertRaisesRegex(overlay.Blocked, "SOURCE_SHA_DRIFT"):
            overlay.transform(FAKE_MTP)
        with self.assertRaisesRegex(overlay.Blocked, "COMPUTE_AST_DRIFT"):
            overlay.transform(FAKE_MTP,
                              expected_sha=hashlib.sha256(FAKE_MTP).hexdigest(),
                              method_sha="0" * 64)

    def test_reapply_and_missing_mtp_anchors_block(self):
        patched = self.transform_fixture()
        with self.assertRaisesRegex(overlay.Blocked, "ALREADY_PATCHED"):
            overlay.transform(patched, expected_sha=hashlib.sha256(patched).hexdigest(),
                              method_sha=method_sha(FAKE_MTP))
        fake = FAKE_MTP.replace(b"self.logits_processor", b"self.passthrough")
        with self.assertRaisesRegex(overlay.Blocked, "LOGITS_ANCHOR_MISSING"):
            overlay.transform(fake, expected_sha=hashlib.sha256(fake).hexdigest(),
                              method_sha=method_sha(fake))

    def test_candidate_receipt_is_not_runtime_certificate(self):
        result = overlay.candidate_receipt()
        self.assertFalse(result["original_target_head_mutated"])
        self.assertFalse(result["candidate_gpu_or_api_executed"])
        self.assertEqual(result["out_of_subset_fill"], "-inf")
        self.assertEqual(result["draft_weight_rows"], 65536)


class DraftSelectionTests(unittest.TestCase):
    def test_preserve_special_added_bytes_and_domain_frequency(self):
        mapping = select_draft_vocab(
            {10: 9, 11: 30, 12: 3, 13: 3, 14: 1},
            special_ids=(30,), added_ids=(31,), full_size=40,
            draft_size=8, byte_fallback_count=2)
        self.assertEqual(mapping.draft_to_full, (0, 1, 10, 11, 12, 13, 30, 31))
        self.assertEqual(mapping.draft_indices([30, 31]), (6, 7))
        self.assertEqual(coverage({11: 7, 39: 3}, mapping), 0.7)

    def test_empty_counts_fallback_lowest_ids(self):
        mapping = select_draft_vocab(
            {}, special_ids=(), added_ids=(), full_size=8,
            draft_size=4, byte_fallback_count=2)
        self.assertEqual(mapping.draft_to_full, (0, 1, 2, 3))
        self.assertIsNone(coverage({}, mapping))

    def test_bad_special_counts_and_shape_block(self):
        with self.assertRaisesRegex(DraftVocabError, "EXCEEDS"):
            select_draft_vocab({}, special_ids=(4, 5, 6), added_ids=(),
                               full_size=8, draft_size=2, byte_fallback_count=1)
        with self.assertRaisesRegex(DraftVocabError, "INVALID_TOKEN_FREQUENCY"):
            select_draft_vocab({1: -1}, special_ids=(), added_ids=(),
                               full_size=8, draft_size=4, byte_fallback_count=1)
        with self.assertRaisesRegex(DraftVocabError, "DIMENSIONS_INVALID"):
            select_draft_vocab({}, special_ids=(), added_ids=(),
                               full_size=8, draft_size=8, byte_fallback_count=1)

    def test_full_vocab_65536_deterministic_no_corpus(self):
        a = select_draft_vocab({}, special_ids=(248319,),
                               added_ids=(248318,))
        b = select_draft_vocab({}, special_ids=(248318,),
                               added_ids=(248319,))
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertEqual(len(a.draft_to_full), 65536)
        self.assertEqual(a.draft_to_full[:256], tuple(range(256)))
        self.assertEqual(a.draft_to_full[-2:], (248318, 248319))


if __name__ == "__main__":
    unittest.main()
