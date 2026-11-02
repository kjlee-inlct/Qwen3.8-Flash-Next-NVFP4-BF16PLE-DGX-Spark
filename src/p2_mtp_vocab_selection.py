"""Deterministic P2 MTP draft-ID selection from sanitized token frequencies.

Consumes token counts only (no prompts, files, tokenizer loading or network).
The resulting map is a CPU contract, not a published vocabulary or approval
to change the installed model. Special/added/byte fallback tokens are kept.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from src.p2_mtp_draft_vocab import (
    DraftVocab, DraftVocabError, FULL_VOCAB_SIZE, PROPOSED_DRAFT_SIZE,
)


def select_draft_vocab(
    token_counts: Mapping[int, int], *,
    special_ids: Iterable[int],
    added_ids: Iterable[int],
    full_size: int = FULL_VOCAB_SIZE,
    draft_size: int = PROPOSED_DRAFT_SIZE,
    byte_fallback_count: int = 256,
) -> DraftVocab:
    if (type(full_size) is not int or not 1 <= full_size <= 500_000
            or type(draft_size) is not int or not 1 <= draft_size < full_size
            or type(byte_fallback_count) is not int
            or not 0 <= byte_fallback_count <= draft_size):
        raise DraftVocabError("DRAFT_VOCAB_SELECTION_DIMENSIONS_INVALID")
    if not isinstance(token_counts, Mapping) or len(token_counts) > full_size:
        raise DraftVocabError("TOKEN_COUNT_SOURCE_INVALID")
    if any(type(k) is not int or not 0 <= k < full_size
           or type(v) is not int or v < 0
           for k, v in token_counts.items()):
        raise DraftVocabError("INVALID_TOKEN_FREQUENCY")
    required = tuple(set(special_ids) | set(added_ids) | set(range(byte_fallback_count)))
    if any(type(k) is not int or not 0 <= k < full_size for k in required):
        raise DraftVocabError("INVALID_REQUIRED_TOKEN_ID")
    selected = set(required)
    if len(selected) > draft_size:
        raise DraftVocabError("REQUIRED_TOKEN_COUNT_EXCEEDS_DRAFT_SIZE")
    # Reserve the mandatory IDs first, then fit domain token frequencies.
    # Ties resolve by ascending original tokenizer ID for deterministic builds.
    for tid, count in sorted(token_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if len(selected) >= draft_size:
            break
        if count:
            selected.add(tid)
    for tid in range(full_size):
        if len(selected) >= draft_size:
            break
        selected.add(tid)
    if len(selected) != draft_size:
        raise DraftVocabError("DRAFT_VOCAB_SELECTION_INCOMPLETE")
    return DraftVocab.validate(
        sorted(selected), target_size=full_size, draft_size=draft_size,
        required_token_ids=required,
    )


def coverage(token_counts: Mapping[int, int], vocab: DraftVocab) -> float | None:
    if (not isinstance(vocab, DraftVocab) or not isinstance(token_counts, Mapping)
            or any(type(tid) is not int or not 0 <= tid < vocab.target_size
                   or type(count) is not int or count < 0
                   for tid, count in token_counts.items())):
        raise DraftVocabError("TOKEN_COVERAGE_INPUT_INVALID")
    total = sum(token_counts.values())
    if total == 0:
        return None
    ids = set(vocab.draft_to_full)
    return sum(count for tid, count in token_counts.items() if tid in ids) / total
