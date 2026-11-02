"""Exact-SHA pinned P2 *candidate-only* single-token Sampler witness patch.

Source transform only: no Docker, GPU, inference, or original-service action.
The tap is default OFF and intentionally synchronizes GPU tensors when enabled;
measurements taken with it are diagnostic, not production reproducibility proof.
"""
from __future__ import annotations

import ast
import hashlib

SOURCE_SHA256 = "f95805b2c6d06218c724826aa5f881a606e8d0a534a566aee7c85948520dd216"
ENV_NAME = "VLLM_P2_NUMERIC_WITNESS"
MARKER = "# -- P2 single-row numeric witness, default OFF --"

# Exact installed Preview code is verified by SHA before any transformation.
# Anchors are not assumed from current upstream vLLM.
INIT = "        num_logprobs = sampling_metadata.max_num_logprobs\n        raw_logprobs: torch.Tensor | None = None\n"
RAW = "            if logprobs_mode == \"raw_logprobs\":\n                raw_logprobs = self.compute_logprobs(logits)\n"
SAMPLED = "        sampled = sampled.long()\n"

HELPER = r'''

# -- P2 single-row numeric witness, default OFF --
import hashlib as _p2_hashlib
import json as _p2_json
import os as _p2_os
import threading as _p2_threading

_P2_WITNESS_ENABLED = _p2_os.environ.get("VLLM_P2_NUMERIC_WITNESS", "0") == "1"
_P2_WITNESS_FILE = "/tmp/p2-numeric-witness.jsonl"  # candidate-private only
_p2_witness_lock = _p2_threading.Lock()
_p2_witness_count = 0
_P2_WITNESS_LIMIT = 8


def _p2_witness_available():
    with _p2_witness_lock:
        return _p2_witness_count < _P2_WITNESS_LIMIT


def _p2_witness_hash(tensor):
    data = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return _p2_hashlib.sha256(data).hexdigest()


def _p2_witness_capture(logits, logprobs):
    if (logits.ndim != 2 or logprobs.ndim != 2 or
            logits.shape[0] != 1 or tuple(logits.shape) != tuple(logprobs.shape)):
        return None
    # Captured *before* in-place sample/penalty paths can touch logits.
    return {
        "status": "BOUNDARY_CAPTURED", "logprobs_mode": "raw_logprobs",
        "shape": [int(x) for x in logits.shape],
        "logits_dtype": str(logits.dtype), "logprobs_dtype": str(logprobs.dtype),
        "pre_sampling_logits_sha256": _p2_witness_hash(logits),
        "pre_gather_logprobs_sha256": _p2_witness_hash(logprobs),
    }


def _p2_witness_emit(record, logprobs, sampled, processed, mode):
    global _p2_witness_count
    if processed is not None or mode != "raw_logprobs":
        return
    if (sampled.ndim != 1 or sampled.shape[0] != 1 or
            logprobs is None or logprobs.ndim != 2 or
            tuple(logprobs.shape) != tuple(record["shape"])):
        return
    token = int(sampled[0].item())
    if not 0 <= token < record["shape"][1]:
        raise RuntimeError("P2_WITNESS_TOKEN_OUT_OF_BOUNDS")
    # Only one scalar logprob; no token IDs, text, full logits or logprob vector.
    value = float(logprobs[0, token].item())
    record = dict(record)
    record.update({
        "sampler_raw_logprobs_not_overridden": True,
        "selected_token_id_sha256": _p2_hashlib.sha256(str(token).encode()).hexdigest(),
        "selected_token_logprob": value,
        "worker_pid": _p2_os.getpid(),
        "witness_kind": "P2_SAMPLER_SELECTED_TOKEN",
    })
    with _p2_witness_lock:
        if _p2_witness_count >= _P2_WITNESS_LIMIT:
            return
        _p2_witness_count += 1
        record["sequence"] = _p2_witness_count
        payload = ("P2_NUMERIC_WITNESS " + _p2_json.dumps(
            record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(payload) > 1800:
            raise RuntimeError("P2_WITNESS_RECORD_OVERSIZE")
        flags = (_p2_os.O_CREAT | _p2_os.O_APPEND | _p2_os.O_WRONLY
                 | _p2_os.O_CLOEXEC | getattr(_p2_os, "O_NOFOLLOW", 0))
        try:
            fd = _p2_os.open(_P2_WITNESS_FILE, flags, 0o600)
            try:
                if _p2_os.write(fd, payload) != len(payload):
                    raise RuntimeError("P2_WITNESS_SHORT_WRITE")
            finally:
                _p2_os.close(fd)
        except OSError:
            raise RuntimeError("P2_WITNESS_FILE_WRITE_FAILED") from None
        try:
            _p2_os.write(2, payload)
        except OSError:
            pass  # Candidate-private file is authoritative, not stderr.
'''


class Blocked(RuntimeError):
    pass


def transform(raw: bytes) -> bytes:
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise Blocked("PINNED_PREVIEW_SAMPLER_SHA_DRIFT")
    try:
        source = raw.decode("utf-8")
        ast.parse(source)
    except (UnicodeError, SyntaxError):
        raise Blocked("SOURCE_INVALID") from None
    if MARKER in source:
        raise Blocked("ALREADY_PATCHED")
    for anchor in (INIT, RAW, SAMPLED):
        if source.count(anchor) != 1:
            raise Blocked("EXACT_SAMPLER_ANCHOR_DRIFT")
    source = source.replace(INIT, INIT + "        _p2_witness_record = None\n")
    source = source.replace(RAW, RAW + (
        "                if _P2_WITNESS_ENABLED and num_logprobs is not None and _p2_witness_available():\n"
        "                    _p2_witness_record = _p2_witness_capture(logits, raw_logprobs)\n"
    ))
    source = source.replace(SAMPLED, SAMPLED + (
        "        if _P2_WITNESS_ENABLED and _p2_witness_record is not None:\n"
        "            _p2_witness_emit(_p2_witness_record, raw_logprobs, sampled, "
        "processed_logprobs, logprobs_mode)\n"
    )) + HELPER
    try:
        ast.parse(source)
    except SyntaxError:
        raise Blocked("PATCHED_SOURCE_INVALID") from None
    if source.count(MARKER) != 1:
        raise Blocked("PATCH_MARKER_INVALID")
    return source.encode("utf-8")
