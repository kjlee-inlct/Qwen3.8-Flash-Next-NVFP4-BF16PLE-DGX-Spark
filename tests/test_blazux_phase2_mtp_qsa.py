"""Phase 2 MTP name/dtype guard regression + independent QSA CPU oracle.

No vLLM/CUDA runtime is imported. The QSA reference specifies offline
fixture expectations only, not kernel equivalence or speculative acceptance.
"""

from __future__ import annotations

import unittest

from phase2_ple_fixtures import qsa_topk_oracle
from recipe.mtp import MTP_TENSOR_NAMES
from src.patch_qwen4_exp_mtp_load_guard import (
    PATCH_MTP_TENSOR_NAMES,
    validate_observed,
)


class Phase2MtpGuardTests(unittest.TestCase):
    def test_exact_31_bf16_names_are_preserved(self):
        self.assertEqual(len(MTP_TENSOR_NAMES), 31)
        self.assertEqual(len(set(MTP_TENSOR_NAMES)), 31)
        self.assertEqual(MTP_TENSOR_NAMES, PATCH_MTP_TENSOR_NAMES)
        validate_observed({name: "torch.bfloat16" for name in MTP_TENSOR_NAMES})

    def test_missing_extra_or_non_bf16_fail_closed(self):
        good = {name: "torch.bfloat16" for name in MTP_TENSOR_NAMES}
        variants = (
            ("missing", {k: v for k, v in good.items() if k != MTP_TENSOR_NAMES[-1]}),
            ("unexpected", {**good, "mtp.unexpected.tensor": "torch.bfloat16"}),
            ("dtype", {**good, MTP_TENSOR_NAMES[0]: "torch.float16"}),
        )
        for label, case in variants:
            with self.subTest(label=label), self.assertRaisesRegex(RuntimeError, label):
                validate_observed(case)


class Phase2QsaCpuOracleTests(unittest.TestCase):
    def test_invisible_columns_cannot_win(self):
        scores = (1000.0, 0.5, 2000.0, 0.75, 0.25)
        self.assertEqual(qsa_topk_oracle(scores, (1, 3, 4), 2), (3, 1))

    def test_k_zero_all_visible_and_tie_rule(self):
        scores = (1.0, 1.0, -2.0, 1.0)
        self.assertEqual(qsa_topk_oracle(scores, (3, 1, 0, 2), 0), ())
        self.assertEqual(qsa_topk_oracle(scores, (3, 1, 0, 2), 4), (0, 1, 3, 2))

    def test_invalid_visible_set_or_nonfinite_score_fails_closed(self):
        for visible, k in (((1, 1), 1), ((5,), 1), ((-1,), 1), ((0,), 2)):
            with self.subTest(visible=visible, k=k), self.assertRaises(ValueError):
                qsa_topk_oracle((0.1, 0.2), visible, k)
        for score in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score), self.assertRaisesRegex(ValueError, "non-finite"):
                qsa_topk_oracle((0.0, score), (0, 1), 1)

    def test_invalid_k_fails_closed(self):
        for k in (-1, 3, 0.1):
            with self.subTest(k=k), self.assertRaises(ValueError):
                qsa_topk_oracle((1.0, 2.0), (0, 1), k)


if __name__ == "__main__":
    unittest.main()
