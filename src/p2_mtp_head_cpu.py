"""P2 CPU-only BF16 draft head materialization, not an installed vLLM patch.

The source target head and checkpoint are NEVER mutated. The returned selected
matrix is an owned, independent copy. This is a computational building block
only; no native Preview Draft Head, loader or rejection ABI has been modified.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from src.p2_mtp_draft_vocab import DraftVocab, DraftVocabError

if TYPE_CHECKING:
    import torch



def _valid_row_mapping(vocab: DraftVocab) -> bool:
    """Validate even directly constructed/fabricated frozen dataclasses."""
    if (not isinstance(vocab, DraftVocab)
            or type(vocab.target_size) is not int or vocab.target_size <= 0
            or not 0 < len(vocab.draft_to_full) < vocab.target_size):
        return False
    ids = vocab.draft_to_full
    if (any(type(v) is not int or not 0 <= v < vocab.target_size for v in ids)
            or len(set(ids)) != len(ids)):
        return False
    required = vocab.required_token_ids
    return (all(type(x) is int and 0 <= x < vocab.target_size for x in required)
            and set(required).issubset(ids))



def reduce_bf16_head(full_weight: "torch.Tensor", vocab: DraftVocab) -> "torch.Tensor":
    """Copy full-vocabulary rows into a distinct CPU BF16 draft matrix.

    Verifies complete mapping and dimensions BEFORE allocating the copy. Never
    call this on the deployed 248320-row checkpoint; use synthetic CPU fixtures
    until the exact installed Draft Head ABI is independently verified.
    """
    try:
        import torch
    except ImportError as exc:
        raise DraftVocabError("TORCH_REQUIRED") from exc
    if not isinstance(vocab, DraftVocab):
        raise DraftVocabError("DRAFT_MAPPING_REQUIRED")
    if not isinstance(full_weight, torch.Tensor):
        raise DraftVocabError("HEAD_TENSOR_REQUIRED")
    if (full_weight.device.type != "cpu" or full_weight.dtype != torch.bfloat16
            or full_weight.ndim != 2 or full_weight.shape[0] != vocab.target_size
            or full_weight.shape[1] < 1):
        raise DraftVocabError("BF16_CPU_FULL_HEAD_SHAPE_REQUIRED")
    if full_weight.requires_grad:
        raise DraftVocabError("TRAINABLE_HEAD_REJECTED")
    if not _valid_row_mapping(vocab):
        raise DraftVocabError("INVALID_REDUCED_ROW_MAPPING")
    with torch.no_grad():
        indices = torch.tensor(vocab.draft_to_full, dtype=torch.long, device="cpu")
        draft = torch.index_select(full_weight.detach(), 0, indices).contiguous()
    vocab.validate_head_rows(draft.shape[0])
    if draft.data_ptr() == full_weight.data_ptr():
        raise DraftVocabError("DRAFT_HEAD_STORAGE_NOT_INDEPENDENT")
    return draft



def remap_draft_indices_cpu(draft_indices: "torch.Tensor",
                            vocab: DraftVocab) -> "torch.Tensor":
    """CPU prototype of local draft-index -> full tokenizer token-ID mapping.

    Acceptance/rejection integration MUST be proven on the exact Preview ABI;
    passing this helper's CPU oracle does not imply acceptance correctness.
    """
    try:
        import torch
    except ImportError as exc:
        raise DraftVocabError("TORCH_REQUIRED") from exc
    if (not isinstance(draft_indices, torch.Tensor)
            or draft_indices.device.type != "cpu"
            or draft_indices.dtype not in (torch.int32, torch.int64)
            or not isinstance(vocab, DraftVocab)):
        raise DraftVocabError("DRAFT_INDEX_CPU_INT_TENSOR_REQUIRED")
    if not _valid_row_mapping(vocab):
        raise DraftVocabError("INVALID_REDUCED_ROW_MAPPING")
    if (draft_indices.numel() and
            (int(draft_indices.min()) < 0
             or int(draft_indices.max()) >= len(vocab.draft_to_full))):
        raise DraftVocabError("DRAFT_INDEX_OUT_OF_RANGE")
    lookup = torch.tensor(vocab.draft_to_full, dtype=torch.int64)
    return lookup.index_select(0, draft_indices.reshape(-1).long()).reshape(
        draft_indices.shape
    )


def compare_selected_logits(hidden: "torch.Tensor", full_head: "torch.Tensor",
                            draft_head: "torch.Tensor", vocab: DraftVocab) -> bool:
    """CPU synthetic equivalence oracle. Never a serving/release accuracy gate."""
    try:
        import torch
    except ImportError as exc:
        raise DraftVocabError("TORCH_REQUIRED") from exc
    if (not isinstance(hidden, torch.Tensor) or not isinstance(full_head, torch.Tensor)
            or not isinstance(draft_head, torch.Tensor)
            or any(t.device.type != "cpu" or t.dtype != torch.bfloat16
                   for t in (hidden, full_head, draft_head))):
        raise DraftVocabError("CPU_BF16_REQUIRED")
    if (hidden.ndim != 2 or full_head.ndim != 2 or draft_head.ndim != 2
            or hidden.shape[1] != full_head.shape[1]
            or hidden.shape[1] != draft_head.shape[1]
            or full_head.shape[0] != vocab.target_size):
        raise DraftVocabError("LOGITS_TEST_DIMENSION_MISMATCH")
    vocab.validate_head_rows(draft_head.shape[0])
    with torch.no_grad():
        ids = torch.tensor(vocab.draft_to_full, dtype=torch.long)
        selected_target = (hidden @ full_head.T).index_select(-1, ids)
        reduced = hidden @ draft_head.T
    return bool(torch.allclose(selected_target.float(), reduced.float(),
                               rtol=0.0, atol=0.015625))


def implementation_receipt(vocab: DraftVocab) -> dict:
    return {
        "status": "P2_CPU_DRAFT_HEAD_ROW_COPY_IMPLEMENTED_NOT_VLLM_CONNECTED",
        "target_rows": vocab.target_size,
        "draft_rows": len(vocab.draft_to_full),
        "mapping_sha256": vocab.fingerprint,
        "writes_to_checkpoint": False,
        "modifies_target_head": False,
        "installed_preview_loader_bound": False,
        "rejection_sampler_mapping_bound": False,
        "candidate_gpu_or_api_tested": False,
    }
