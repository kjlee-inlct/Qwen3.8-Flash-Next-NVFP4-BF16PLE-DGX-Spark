"""Source-pinned, default-OFF numeric boundary tap for one isolated P1 image.

Stages ONE patched Preview sampler.py, never mutates the original container,
image, model, cache, or previous candidate. No GPU/API/model execution.
The opt-in tap copies just one logprob-request row to CPU, so it can perturb
timing; hashes are diagnostic evidence, not an uninstrumented determinism PASS.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from src import p1_numeric_source_trace as source_trace
from src import p1_preview_qsa_exact_topk as qsa

SAMPLER_PATH = source_trace.SOURCES["sampler"]
SAMPLER_SHA256 = "f95805b2c6d06218c724826aa5f881a606e8d0a534a566aee7c85948520dd216"
INTEGRATED_IMAGE_ID = "sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d"
TAP_ENV = "VLLM_P1_NUMERIC_TAP"
HELPER_MARKER = "# -- P1 single-candidate numeric tap, default OFF --"

INIT = """        num_logprobs = sampling_metadata.max_num_logprobs
        raw_logprobs: torch.Tensor | None = None
"""
RAW = """            if logprobs_mode == "raw_logprobs":
                raw_logprobs = self.compute_logprobs(logits)
"""
OVERRIDE = """        if processed_logprobs is not None:
            raw_logprobs = processed_logprobs
"""
INIT_PATCH = INIT + "        _p1_numeric_event = None\n"
RAW_PATCH = RAW + """                if _P1_NUMERIC_TAP_ENABLED and num_logprobs is not None:
                    _p1_numeric_event = _p1_numeric_capture(logits, raw_logprobs)
"""
OVERRIDE_PATCH = OVERRIDE + """        if _P1_NUMERIC_TAP_ENABLED and num_logprobs is not None:
            if _p1_numeric_event is None and logprobs_mode != "raw_logprobs":
                _p1_numeric_event = _p1_numeric_skip_mode(logprobs_mode)
            if _p1_numeric_event is not None:
                _p1_numeric_emit(
                    _p1_numeric_event, logprobs_mode,
                    processed_logprobs is not None,
                )
"""

HELPER = r"""

# -- P1 single-candidate numeric tap, default OFF --
# WARNING: the opt-in CPU copy synchronizes the sampled row and may change
# scheduling; the original production service must never receive this patch.
import hashlib as _p1_num_hashlib
import json as _p1_num_json
import os as _p1_num_os
import sys as _p1_num_sys
import threading as _p1_num_threading

_P1_NUMERIC_TAP_ENABLED = _p1_num_os.environ.get("VLLM_P1_NUMERIC_TAP", "0") == "1"
_P1_NUMERIC_TAP_LIMIT = 16
_p1_numeric_lock = _p1_num_threading.Lock()
_p1_numeric_count = 0


def _p1_numeric_next_seq():
    global _p1_numeric_count
    with _p1_numeric_lock:
        if _p1_numeric_count >= _P1_NUMERIC_TAP_LIMIT:
            return None
        _p1_numeric_count += 1
        return _p1_numeric_count


def _p1_numeric_hash(tensor):
    # Byte-exact, dtype-preserving. Viewing as uint8 supports bf16 without
    # requiring NumPy's bf16 support. Copy implicitly synchronizes the GPU.
    raw = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return _p1_num_hashlib.sha256(raw).hexdigest()


def _p1_numeric_capture(raw_logits, raw_logprobs):
    seq = _p1_numeric_next_seq()
    if seq is None:
        return None
    record = {"sequence": seq, "status": "BOUNDARY_CAPTURED",
              "worker_pid": _p1_num_os.getpid()}
    if (raw_logits.ndim != 2 or raw_logprobs.ndim != 2
            or tuple(raw_logits.shape) != tuple(raw_logprobs.shape)
            or raw_logits.shape[0] != 1):
        record["status"] = "SKIP_NOT_SINGLE_ROW_OR_SHAPE_DRIFT"
        return record
    try:
        record["shape"] = list(raw_logits.shape)
        record["logits_dtype"] = str(raw_logits.dtype)
        record["logprobs_dtype"] = str(raw_logprobs.dtype)
        record["pre_sampling_logits_sha256"] = _p1_numeric_hash(raw_logits)
        record["pre_gather_logprobs_sha256"] = _p1_numeric_hash(raw_logprobs)
    except Exception:
        # A broken probe must fail the isolated candidate, never produce
        # misleading "matching" or "PASS" evidence.
        raise RuntimeError("P1_NUMERIC_TAP_CAPTURE_FAILED") from None
    return record


def _p1_numeric_skip_mode(logprobs_mode):
    seq = _p1_numeric_next_seq()
    if seq is None:
        return None
    return {"sequence": seq, "worker_pid": _p1_num_os.getpid(),
            "status": "SKIP_NON_RAW_LOGPROBS_MODE"}


def _p1_numeric_emit(record, logprobs_mode, result_overridden):
    record["logprobs_mode"] = str(logprobs_mode)[:48]
    record["sampler_logprobs_overridden"] = bool(result_overridden)
    record["sampler_raw_logprobs_not_overridden"] = (
        record["status"] == "BOUNDARY_CAPTURED"
        and logprobs_mode == "raw_logprobs"
        and not result_overridden
    )
    # No prompt, generated token IDs, logits, logprob vectors or model weights.
    _p1_num_sys.stderr.write(
        "P1_NUMERIC_TAP " + _p1_num_json.dumps(record, sort_keys=True) + "\n"
    )
    _p1_num_sys.stderr.flush()
"""


class Blocked(RuntimeError):
    pass


def transform(raw: bytes) -> bytes:
    if hashlib.sha256(raw).hexdigest() != SAMPLER_SHA256:
        raise Blocked("PINNED_SAMPLER_SHA_DRIFT")
    try:
        text = raw.decode("utf-8")
        ast.parse(text)
    except (UnicodeError, SyntaxError):
        raise Blocked("SAMPLER_SOURCE_INVALID") from None
    if HELPER_MARKER in text:
        raise Blocked("ALREADY_PATCHED")
    for old in (INIT, RAW, OVERRIDE):
        if text.count(old) != 1:
            raise Blocked("SAMPLER_ANCHOR_MISMATCH")
    patched = text.replace(INIT, INIT_PATCH).replace(RAW, RAW_PATCH).replace(
        OVERRIDE, OVERRIDE_PATCH) + HELPER
    try:
        tree = ast.parse(patched)
    except SyntaxError:
        raise Blocked("SAMPLER_PATCH_INVALID") from None
    if patched.count(HELPER_MARKER) != 1:
        raise Blocked("SAMPLER_TAP_MARKER_MISMATCH")
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    names = {n.name for n in funcs}
    if not {"_p1_numeric_capture", "_p1_numeric_emit", "_p1_numeric_hash"}.issubset(names):
        raise Blocked("SAMPLER_TAP_HELPERS_MISSING")
    return patched.encode("utf-8")


def dockerfile() -> str:
    """ONE existing integrated-image parent + ONE Python source overlay.

    Does NOT enable the tap; only an explicitly approved isolated candidate
    runtime may set VLLM_P1_NUMERIC_TAP=1 after confirming ownership and SHA.
    """
    return (
        "FROM " + INTEGRATED_IMAGE_ID + "\n"
        "COPY --chown=0:0 --chmod=0644 sampler.py "
        + source_trace.PACKAGE_ROOT + SAMPLER_PATH + "\n"
        "ENV VLLM_P1_NUMERIC_TAP=0\n"
    )


def stage() -> dict:
    before = source_trace.original_identity()
    try:
        raw = source_trace._run_docker_cp(SAMPLER_PATH)
        patched = transform(raw)
    finally:
        if source_trace.original_identity() != before:
            raise Blocked("ORIGINAL_ID_OR_START_CHANGED") from None

    # Separate private temporary output: NEVER the historical Prefix Stage.
    root = Path(tempfile.mkdtemp(prefix="p1-numeric-sampler-", dir="/tmp"))
    root.chmod(0o700)
    target = root / "sampler.py"
    with target.open("xb") as out:
        out.write(patched)
    target.chmod(0o600)
    df = root / "Dockerfile"
    with df.open("x", encoding="utf-8") as out:
        out.write(dockerfile())
    df.chmod(0o600)

    return {
        "status": "SOURCE_STAGED_NOT_BUILT_NOT_GPU_VERIFIED",
        "stage_directory": str(root),
        "original_sampler_sha256": SAMPLER_SHA256,
        "patched_sampler_sha256": hashlib.sha256(patched).hexdigest(),
        "parent_integrated_image_id": INTEGRATED_IMAGE_ID,
        "tap_environment_default_off": True,
        "gpu_or_api_executed": False,
        "original_same_id_running_unchanged": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--confirm-original-id", required=True)
    p.add_argument("--stage", action="store_true", required=True)
    args = p.parse_args(argv)
    try:
        if args.confirm_original_id != source_trace.ORIGINAL_ID:
            raise Blocked("ORIGINAL_ID_CONFIRMATION_MISMATCH")
        qsa.preflight(args.expected_head)
        report = stage()
        print(json.dumps(report, sort_keys=True))
        return 0
    except (Blocked, source_trace.Blocked, qsa.Blocked, OSError, ValueError,
            TypeError, KeyError):
        print("P1_NUMERIC_SAMPLER_STAGE_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
