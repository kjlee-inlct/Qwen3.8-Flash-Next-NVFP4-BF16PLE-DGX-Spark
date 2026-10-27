"""Standalone Phase 5 correctness oracles — NOT vLLM parser/cache patches.

Inputs are synthetic, no model, GPU, network, HF cache or filesystem access.
The real preview/v0.32 parser, scheduler and draft-head ABI remain unverified.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence


class ContractError(ValueError):
    """Reject ambiguous or unsafe client/oracle inputs."""


def mamba_state_slot(num_computed_tokens: int, mamba_block_size: int) -> int | None:
    """CPU reference for (tokens - 1) // mamba_block_size; empty has no slot.

    Source: pinned blazux patch_mamba_block_size.py; this does not read cache.
    """
    if type(num_computed_tokens) is not int or num_computed_tokens < 0:
        raise ContractError("num_computed_tokens must be a nonnegative int")
    if type(mamba_block_size) is not int or mamba_block_size < 1:
        raise ContractError("mamba_block_size must be a positive int")
    if num_computed_tokens == 0:
        return None
    return (num_computed_tokens - 1) // mamba_block_size


def require_cache_state_alignment(
    num_computed_tokens: int,
    mamba_block_size: int,
    scheduler_block_size: int,
) -> int:
    """Fail closed unless prefix hit is aligned for both state and scheduler.

    This reference is intentionally strict: an unaligned prefix is classified
    'not safe for state restore', not silently assigned a smaller QSA slot.
    It is not the real scheduler's accept/reject decision.
    """
    slot = mamba_state_slot(num_computed_tokens, mamba_block_size)
    if type(scheduler_block_size) is not int or scheduler_block_size < 1:
        raise ContractError("scheduler_block_size must be a positive int")
    if slot is None or num_computed_tokens % mamba_block_size:
        raise ContractError("prefix has no complete aligned Mamba state block")
    if num_computed_tokens % scheduler_block_size:
        raise ContractError("prefix misaligned with scheduler boundary")
    return slot


def classify_tool_call(
    name: str,
    arguments_json: str,
    offered: Mapping[str, Mapping[str, object]],
    *,
    protocol: str,
) -> str:
    """Synthetic CLIENT execution gate, not Qwen parser output normalization.

    Returns 'executable' only for an explicitly offered, closed, valid JSON
    object with a small deterministic subset of the expected JSON schema.
    Other calls remain non-executable; Chat may preserve raw output for error
    recovery, whereas Responses requires rejection. Neither executes them.
    """
    if protocol not in ("chat", "responses"):
        raise ContractError("unsupported protocol")
    if not isinstance(name, str) or not name or not isinstance(arguments_json, str):
        raise ContractError("invalid tool call envelope")
    if name not in offered:
        return "rejected" if protocol == "responses" else "untrusted"
    try:
        params = json.loads(arguments_json)
    except (ValueError, TypeError):
        return "rejected" if protocol == "responses" else "untrusted"
    if not isinstance(params, dict):
        return "rejected" if protocol == "responses" else "untrusted"
    schema = offered[name]
    if not isinstance(schema, Mapping):
        raise ContractError("invalid offered schema")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        raise ContractError("invalid properties/required schema")
    if any(not isinstance(key, str) for key in required):
        raise ContractError("invalid required names")
    if not set(required).issubset(params):
        return "rejected" if protocol == "responses" else "untrusted"
    if set(params) - set(properties):
        return "rejected" if protocol == "responses" else "untrusted"
    for key, value in params.items():
        spec = properties[key]
        if not isinstance(spec, Mapping):
            raise ContractError("invalid field schema")
        kind = spec.get("type")
        if kind == "string":
            valid = isinstance(value, str)
        elif kind == "integer":
            valid = type(value) is int
        elif kind == "boolean":
            valid = type(value) is bool
        else:
            # Fail closed on unsupported schemas; not a full JSON-schema lib.
            raise ContractError("unsupported schema type")
        if not valid:
            return "rejected" if protocol == "responses" else "untrusted"
    return "executable"


def responses_terminal_event(events: Sequence[Mapping[str, object]]) -> str:
    """Validate a minimal synthetic Responses event sequence.

    Order/terminal/error classification only; no SSE parser or server import.
    Every event needs an increasing integer sequence number. Terminal status
    must match completed/failed/incomplete. A wire 'error' is also terminal.
    """
    if not events:
        raise ContractError("Responses stream has no events")
    terminals = {
        "response.completed": "completed",
        "response.failed": "failed",
        "response.incomplete": "incomplete",
        "error": "error",
    }
    terminal: str | None = None
    seen: set[int] = set()
    last = -1
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise ContractError("invalid event envelope")
        seq, kind = event.get("sequence_number"), event.get("type")
        if type(seq) is not int or seq < 0 or seq <= last or seq in seen:
            raise ContractError("invalid Responses sequence number")
        seen.add(seq)
        last = seq
        if kind in terminals:
            if index != len(events) - 1:
                raise ContractError("event emitted after terminal")
            if kind != "error":
                response = event.get("response")
                if not isinstance(response, Mapping) or response.get("status") != terminals[kind]:
                    raise ContractError("terminal event/response status mismatch")
            terminal = terminals[kind]
        elif not isinstance(kind, str) or not kind.startswith("response."):
            raise ContractError("unknown event type")
    if terminal is None:
        raise ContractError("missing terminal Responses event")
    return terminal


def reduced_draft_vocab(
    ids: Sequence[int],
    vocab_size: int,
    mandatory_ids: Sequence[int],
) -> frozenset[int]:
    """Risk gate for *candidate* reduced draft vocabulary, without loading .npy.

    Native Orcarouter MTP weights stay untouched. Reject OOB/duplicates/missing
    mandatory tokens rather than silently clipping, unlike upstream example.
    """
    if type(vocab_size) is not int or vocab_size < 1:
        raise ContractError("invalid vocab size")
    if not isinstance(ids, (tuple, list)) or not ids:
        raise ContractError("empty or unsupported draft vocabulary")
    if any(type(i) is not int or i < 0 or i >= vocab_size for i in ids):
        raise ContractError("draft vocabulary id outside target vocab")
    if len(set(ids)) != len(ids):
        raise ContractError("duplicate draft vocabulary id")
    if any(type(i) is not int or i < 0 or i >= vocab_size for i in mandatory_ids):
        raise ContractError("invalid mandatory token")
    selection = frozenset(ids)
    if not set(mandatory_ids).issubset(selection):
        raise ContractError("draft vocabulary omits required token")
    return selection


def argmax_draft(scores: Sequence[float], allowed: frozenset[int]) -> int:
    """Deterministic conceptual draft candidate; lower index breaks ties.

    This is NOT a vLLM sampling implementation and proves no output parity.
    """
    if not scores or not allowed or any(
        type(s) not in (float, int) or not math.isfinite(s) for s in scores
    ):
        raise ContractError("invalid logits")
    if any(type(i) is not int or i < 0 or i >= len(scores) for i in allowed):
        raise ContractError("invalid allowed draft id")
    return min(allowed, key=lambda i: (-scores[i], i))


def synthetic_acceptance(
    logits_rows: Sequence[Sequence[float]],
    verified_target_ids: Sequence[int],
    allowed: frozenset[int],
) -> tuple[int, int]:
    """Count exact matches for a deterministic argmax *illustration* only.

    A real stochastic MTP verifier may differ; never use as acceptance proof.
    """
    if len(logits_rows) != len(verified_target_ids):
        raise ContractError("target/logits length mismatch")
    if any(type(i) is not int for i in verified_target_ids):
        raise ContractError("invalid target token")
    accepted = sum(
        argmax_draft(row, allowed) == verified_target_ids[i]
        for i, row in enumerate(logits_rows)
    )
    return accepted, len(logits_rows)
