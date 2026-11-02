"""P2 reduced draft-vocabulary mapping contract (CPU-only, no checkpoint edit).

This is the model-side contract required BEFORE replacing an MTP draft head:
draft row i predicts full tokenizer token id draft_to_full[i]. Native MTP
acceptance and target head stay on full vocabulary. Actual Preview ABI binding
and tensor slicing are deliberately blocked until installed-source evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import Iterable, Sequence

FULL_VOCAB_SIZE = 248320
PROPOSED_DRAFT_SIZE = 65536


class DraftVocabError(ValueError):
    pass


@dataclass(frozen=True)
class DraftVocab:
    draft_to_full: tuple[int, ...]
    target_size: int
    required_token_ids: tuple[int, ...]

    @classmethod
    def validate(
        cls, draft_to_full: Sequence[int], *, target_size: int = FULL_VOCAB_SIZE,
        draft_size: int = PROPOSED_DRAFT_SIZE,
        required_token_ids: Iterable[int] = (),
    ) -> "DraftVocab":
        if (type(target_size) is not int or target_size < 1
                or type(draft_size) is not int or draft_size < 1
                or draft_size > target_size):
            raise DraftVocabError("INVALID_VOCAB_SIZES")
        if len(draft_to_full) != draft_size:
            raise DraftVocabError("DRAFT_SIZE_MISMATCH")
        ids = tuple(draft_to_full)
        if (any(type(v) is not int or v < 0 or v >= target_size for v in ids)
                or len(set(ids)) != len(ids)):
            raise DraftVocabError("INVALID_OR_DUPLICATE_FULL_ID")
        required = tuple(required_token_ids)
        if any(type(v) is not int or v < 0 or v >= target_size for v in required):
            raise DraftVocabError("INVALID_REQUIRED_TOKEN_ID")
        if not set(required).issubset(ids):
            raise DraftVocabError("REQUIRED_SPECIAL_TOKEN_ABSENT")
        return cls(ids, target_size, required)

    @property
    def fingerprint(self) -> str:
        payload = struct.pack("<II", self.target_size, len(self.draft_to_full))
        payload += struct.pack("<" + "I" * len(self.draft_to_full),
                               *self.draft_to_full)
        return hashlib.sha256(payload).hexdigest()

    def full_ids(self, draft_indices: Sequence[int]) -> tuple[int, ...]:
        """Convert sampler proposal indices to full tokenizer IDs; fail closed."""
        output = []
        for idx in draft_indices:
            if type(idx) is not int or not 0 <= idx < len(self.draft_to_full):
                raise DraftVocabError("DRAFT_INDEX_OUT_OF_RANGE")
            output.append(self.draft_to_full[idx])
        return tuple(output)

    def draft_indices(self, token_ids: Sequence[int]) -> tuple[int | None, ...]:
        """Return None for tokens not representable by the reduced draft."""
        lookup = {full: draft for draft, full in enumerate(self.draft_to_full)}
        output = []
        for token in token_ids:
            if type(token) is not int or not 0 <= token < self.target_size:
                raise DraftVocabError("FULL_TOKEN_OUT_OF_RANGE")
            output.append(lookup.get(token))
        return tuple(output)

    def validate_head_rows(self, rows: int) -> None:
        """A shared 248320-row target head is NOT a 65536-row draft head."""
        if type(rows) is not int or rows != len(self.draft_to_full):
            raise DraftVocabError("DRAFT_HEAD_ROWS_NOT_REDUCED")

    def plan(self) -> dict:
        return {
            "status": "P2_REDUCED_DRAFT_ABI_NOT_BOUND",
            "target_vocab_size": self.target_size,
            "draft_vocab_size": len(self.draft_to_full),
            "required_tokens_verified": True,
            "draft_index_mapping_sha256": self.fingerprint,
            "weights_sliced": False,
            "target_head_modified": False,
            "gpu_candidate_executed": False,
            "draft_head_loader_abi_verified": False,
        }
