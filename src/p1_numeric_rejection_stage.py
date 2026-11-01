"""Read-only, source-pinned P1 RejectionSampler tap stage (no build/GPU).

The first MTP2 accepted-token logprobs come from RejectionSampler's
_get_logprobs_tensors(), not Sampler.forward(raw_logprobs). Stage an isolated
one-file child image atop the *already built* numeric-sampler child image.
The candidate-only tap writes bounded sanitized JSON lines to its private
/tmp filesystem AND stderr: docker logs might not forward worker stderr.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from src import p1_legacy_service_window as legacy
from src import p1_numeric_source_trace as source_trace
from src import p1_preview_qsa_exact_topk as qsa

ORIGINAL_SOURCE_SHA = "4bb87d7984d967be9c7e5b6a6b489c02571ef2f2913211cb3f1eea74b2e1f32f"
SOURCE_RELATIVE_PATH = "vllm/v1/sample/rejection_sampler.py"
SOURCE_PATH = source_trace.PACKAGE_ROOT + SOURCE_RELATIVE_PATH
PARENT_TAG = "kjlee-qwen38-p1-numeric-sampler:0e559c041a7c"
PARENT_ID = "sha256:414372505f665f2f26a23bfc7b2d1082ff586e0082c4dab1d47ea9ed4202ecb7"
PARENT_HEAD = "0e559c041a7c0f9f9861c5d93b858c82f83b1ad7"
PARENT_PATCH_SHA = "14ecaf0ab79fb94604ce987bb6e74b4d64778f7e3ef76cd1e51064c87509c320"
TAP_ENV = "VLLM_P1_REJECTION_TAP"
TAP_FILE = "/tmp/p1-numeric-rejection-tap.jsonl"
HELPER_MARKER = "# -- P1 RejectionSampler accepted first-token boundary tap --"

FORWARD_ANCHOR = """        assert metadata.max_spec_len <= MAX_SPEC_LEN

        bonus_logits_indices = metadata.bonus_logits_indices
"""
FORWARD_PATCH = """        assert metadata.max_spec_len <= MAX_SPEC_LEN
        if _P1_REJECTION_TAP_ENABLED:
            _p1_rejection_emit({
                "status": "REJECTION_FORWARD_ENTERED",
                "logprobs_requested": sampling_metadata.max_num_logprobs is not None,
                "mode": str(self.sampler.logprobs_mode)[:32],
            })

        bonus_logits_indices = metadata.bonus_logits_indices
"""
ACCEPTED_ANCHOR = """        accepted_logprobs = (
            accepted_logits
            if self.is_logits_logprobs_mode
            else self.sampler.compute_logprobs(accepted_logits)
        )
        return self.sampler.gather_logprobs(
"""
ACCEPTED_PATCH = """        accepted_logprobs = (
            accepted_logits
            if self.is_logits_logprobs_mode
            else self.sampler.compute_logprobs(accepted_logits)
        )
        if _P1_REJECTION_TAP_ENABLED:
            _p1_rejection_capture(
                accepted_logits, accepted_logprobs,
                self.sampler.logprobs_mode,
                self.is_processed_logprobs_mode,
                self.is_logits_logprobs_mode,
            )
        return self.sampler.gather_logprobs(
"""

HELPER = r"""

# -- P1 RejectionSampler accepted first-token boundary tap --
# Candidate-only. Per-process bounded event stream. NEVER patch original.
import hashlib as _p1_r_hashlib
import json as _p1_r_json
import os as _p1_r_os
import threading as _p1_r_threading

_P1_REJECTION_TAP_ENABLED = _p1_r_os.environ.get(
    "VLLM_P1_REJECTION_TAP", "0"
) == "1"
_P1_REJECTION_TAP_FILE = "/tmp/p1-numeric-rejection-tap.jsonl"
_p1_r_lock = _p1_r_threading.Lock()
_p1_r_count = 0
_P1_R_LIMIT = 32


def _p1_rejection_emit(event):
    global _p1_r_count
    with _p1_r_lock:
        if _p1_r_count >= _P1_R_LIMIT:
            return
        _p1_r_count += 1
        record = dict(event)
        record["sequence"] = _p1_r_count
        record["worker_pid"] = _p1_r_os.getpid()
        payload = (
            "P1_REJECTION_TAP "
            + _p1_r_json.dumps(record, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        if len(payload) > 1600:
            raise RuntimeError("P1_REJECTION_TAP_EVENT_OVERSIZE")
        # Private writable candidate overlay, no host mount, no user content.
        flags = (_p1_r_os.O_CREAT | _p1_r_os.O_APPEND | _p1_r_os.O_WRONLY
                 | _p1_r_os.O_CLOEXEC | getattr(_p1_r_os, "O_NOFOLLOW", 0))
        try:
            fd = _p1_r_os.open(_P1_REJECTION_TAP_FILE, flags, 0o600)
            try:
                if _p1_r_os.write(fd, payload) != len(payload):
                    raise RuntimeError("P1_REJECTION_TAP_SHORT_WRITE")
            finally:
                _p1_r_os.close(fd)
        except OSError:
            raise RuntimeError("P1_REJECTION_TAP_FILE_WRITE_FAILED") from None
        try:
            _p1_r_os.write(2, payload)
        except OSError:
            # The private candidate file is authoritative if stderr is lost.
            pass


def _p1_rejection_row_hash(tensor):
    if tensor.ndim != 2 or tensor.shape[0] < 1 or tensor.shape[1] < 1:
        raise RuntimeError("P1_REJECTION_TAP_INVALID_SHAPE")
    # First output row only: later speculative rows can differ in count.
    raw = tensor[:1].detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return _p1_r_hashlib.sha256(raw).hexdigest()


def _p1_rejection_capture(raw_logits, logprobs, mode, processed, is_logits):
    # Hash only the row corresponding to the first accepted-logprob slot.
    # This row-to-API mapping is still a hypothesis until parse_output is
    # separately checked; NEVER declare P1 PASS from these digests alone.
    event = {
        "status": "REJECTION_ACCEPTED_BOUNDARY",
        "mode": str(mode)[:32],
        "processed_mode": bool(processed),
        "logits_mode": bool(is_logits),
        "raw_logits_shape": [int(x) for x in raw_logits.shape],
        "logprobs_shape": [int(x) for x in logprobs.shape],
        "raw_logits_dtype": str(raw_logits.dtype),
        "logprobs_dtype": str(logprobs.dtype),
        "first_row_logits_sha256": _p1_rejection_row_hash(raw_logits),
        "first_row_logprobs_sha256": _p1_rejection_row_hash(logprobs),
    }
    _p1_rejection_emit(event)
"""


class Blocked(RuntimeError):
    pass


def transform(raw: bytes) -> bytes:
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SOURCE_SHA:
        raise Blocked("REJECTION_SOURCE_SHA_DRIFT")
    try:
        text = raw.decode("utf-8")
        ast.parse(text)
    except (UnicodeError, SyntaxError):
        raise Blocked("REJECTION_SOURCE_INVALID") from None
    if HELPER_MARKER in text:
        raise Blocked("REJECTION_ALREADY_PATCHED")
    for anchor in (FORWARD_ANCHOR, ACCEPTED_ANCHOR):
        if text.count(anchor) != 1:
            raise Blocked("REJECTION_ANCHOR_DRIFT")
    patched = text.replace(FORWARD_ANCHOR, FORWARD_PATCH).replace(
        ACCEPTED_ANCHOR, ACCEPTED_PATCH) + HELPER
    try:
        tree = ast.parse(patched)
    except SyntaxError:
        raise Blocked("REJECTION_PATCH_SYNTAX_ERROR") from None
    functions = {node.name for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    if not {"_p1_rejection_emit", "_p1_rejection_capture",
            "_p1_rejection_row_hash"}.issubset(functions):
        raise Blocked("REJECTION_HELPERS_MISSING")
    return patched.encode("utf-8")


def verify_parent() -> None:
    original = legacy.inspect("image", legacy.IMAGE_TAG)
    parent = legacy.inspect("image", PARENT_TAG)
    if original.get("Id") != source_trace.ORIGINAL_IMAGE or parent.get("Id") != PARENT_ID:
        raise Blocked("REJECTION_PARENT_IMAGE_ID_DRIFT")
    old = (original.get("RootFS") or {}).get("Layers") or []
    new = (parent.get("RootFS") or {}).get("Layers") or []
    if not old or len(new) != len(old) + 1 or new[:len(old)] != old:
        raise Blocked("REJECTION_PARENT_LAYERS_DRIFT")
    conf = parent.get("Config") or {}
    if "VLLM_P1_NUMERIC_TAP=0" not in (conf.get("Env") or []):
        raise Blocked("REJECTION_PARENT_TAP_ENV_DRIFT")
    labels = conf.get("Labels") or {}
    if (labels.get("ai.kjlee.p1.numeric-source-head") != PARENT_HEAD or
            labels.get("ai.kjlee.p1.numeric-sampler-sha256") != PARENT_PATCH_SHA or
            labels.get("ai.kjlee.p1.numeric.parent-id") != source_trace.ORIGINAL_IMAGE):
        raise Blocked("REJECTION_PARENT_LABEL_DRIFT")


def read_original_source() -> bytes:
    try:
        cp = subprocess.run(
            ["docker", "cp", legacy.NAME + ":" + SOURCE_PATH, "-"],
            capture_output=True, check=False, timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("REJECTION_DOCKER_CP_UNAVAILABLE") from None
    if cp.returncode != 0:
        raise Blocked("REJECTION_DOCKER_CP_FAILED")
    return source_trace.extract_python_tar(cp.stdout)


def dockerfile() -> str:
    return (
        f"FROM {PARENT_TAG}\n"
        "COPY --chown=0:0 --chmod=0644 rejection_sampler.py "
        + SOURCE_PATH + "\n"
        f"ENV {TAP_ENV}=0\n"
    )


def stage() -> dict:
    verify_parent()
    before = source_trace.original_identity()
    try:
        raw = read_original_source()
        patched = transform(raw)
    finally:
        if source_trace.original_identity() != before:
            raise Blocked("REJECTION_ORIGINAL_ID_OR_START_CHANGED") from None
    root = Path(tempfile.mkdtemp(prefix="p1-numeric-rejection-", dir="/tmp"))
    root.chmod(0o700)
    for filename, data in (
        ("rejection_sampler.py", patched),
        ("Dockerfile", dockerfile().encode("utf-8")),
    ):
        dest = root / filename
        with dest.open("xb") as f:
            f.write(data)
        dest.chmod(0o600)
    return {
        "status": "REJECTION_SOURCE_STAGED_NOT_BUILT_NOT_GPU_VERIFIED",
        "stage_directory": str(root),
        "original_rejection_sha256": ORIGINAL_SOURCE_SHA,
        "patched_rejection_sha256": hashlib.sha256(patched).hexdigest(),
        "parent_numeric_sampler_image_id": PARENT_ID,
        "original_same_id_running_unchanged": True,
        "tap_default_off": True,
        "gpu_or_api_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--confirm-original-id", required=True)
    parser.add_argument("--stage", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        if args.confirm_original_id != source_trace.ORIGINAL_ID:
            raise Blocked("REJECTION_ORIGINAL_ID_MISMATCH")
        qsa.preflight(args.expected_head)
        print(json.dumps(stage(), sort_keys=True))
        return 0
    except (Blocked, source_trace.Blocked, legacy.Blocked, qsa.Blocked,
            OSError, ValueError, TypeError, KeyError):
        print("P1_NUMERIC_REJECTION_STAGE_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
