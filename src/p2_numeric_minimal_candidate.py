"""P2 Numeric FIRST-divergence minimal candidate source-only preparation.

Extracts the SHA-verified Sampler from the already DGX-staged four-COPY
bundle into a *new* one-COPY diagnostic Docker build context. Other P2
optimizations remain out of the candidate image, to isolate the first numeric
boundary on future Prefix-OFF/MTP-OFF GPU runs. No Docker build/run, HTTP,
CUDA, stop/start/exec, model loading, or original file modification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

from src import p1_legacy_service_window as legacy
from src import p1_mtp_off_numeric_isolation as mtp_off
from src import p1_numeric_source_trace as trace
from src import p1_preview_qsa_exact_topk as qsa
from src import p2_functional_bundle as bundle
from src import p2_numeric_sampler_witness as witness

STAGE_NAME = re.compile(r"p2-functional-bundle-[A-Za-z0-9_-]{1,64}\Z")
PIN_SOURCE_HASHES = {
    "sampler.py": "a62b7cd7f7eb637fdee7d8dd1e51b1bc47c3931bb1174f4f22280db28ccaead4",
    "vllm_ple_mmap.py": "a7aa7fe782c1b88f1f28fd3d7499201bc9370680167aab200fa1cee6aad35dc6",
    "mtp.py": "c6fd9daa8b9ebc07bf12af20f4b110897b470a686d4e1fba46bae2b26d51db40",
    "draft_vocab_65536.npy": "6459e0fdc8df30e0c1d1f45be7c1b6bef0d68b0e73c073a82c52ea2a7f4b26d4",
}
MAX_BYTES = 2_000_000
SINGLE_CANDIDATE_PREFIX = "p2-numeric-first-divergence-"
CONTAINER_NAME_RESERVED = "p2-numeric-first-divergence"
# No image tag, run command, or network endpoint is created or launched here.


class Blocked(RuntimeError):
    """Static reason code; never include local filenames or user data."""


def _private_stage(path: Path) -> None:
    # Realpaths must be direct /tmp children; avoid symlink traversals.
    if (not path.is_absolute() or path.parent != Path("/tmp")
            or not STAGE_NAME.fullmatch(path.name)
            or path.is_symlink() or not path.is_dir()):
        raise Blocked("UNEXPECTED_STAGE_DIRECTORY")
    st = path.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise Blocked("STAGE_OWNER_OR_MODE_DRIFT")


def _source(path: Path, name: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Blocked("STAGE_SOURCE_NOT_REGULAR")
    st = path.stat()
    if (st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600
            or not 0 < st.st_size <= MAX_BYTES):
        raise Blocked("STAGE_SOURCE_OWNER_OR_MODE_OR_SIZE_DRIFT")
    raw = path.read_bytes()
    if len(raw) != st.st_size:
        raise Blocked("STAGE_SOURCE_READ_LENGTH_DRIFT")
    if name in PIN_SOURCE_HASHES:
        if hashlib.sha256(raw).hexdigest() != PIN_SOURCE_HASHES[name]:
            raise Blocked("STAGE_SOURCE_PINNED_SHA_DRIFT")
    return raw


def source_stage(stage: Path) -> bytes:
    """Authenticate the already observed DGX source stage, not its directory name."""
    _private_stage(stage)
    files = {p.name for p in stage.iterdir()}
    if files != set(PIN_SOURCE_HASHES) | {"Dockerfile"}:
        raise Blocked("STAGE_FILE_SET_DRIFT")
    for name in PIN_SOURCE_HASHES:
        raw = _source(stage / name, name)
        if name == "sampler.py" and (
                raw.count(witness.MARKER.encode("utf-8")) != 1
                or b'VLLM_P2_NUMERIC_WITNESS", "0"' not in raw):
            raise Blocked("STAGED_SAMPLER_WITNESS_MARKER_OR_DEFAULT_DRIFT")
    dockerfile = _source(stage / "Dockerfile", "Dockerfile")
    if dockerfile != bundle.dockerfile(
            include_mtp=True, include_upstream_draft=True).encode("utf-8"):
        raise Blocked("FOUR_COPY_DOCKERFILE_DRIFT")
    return _source(stage / "sampler.py", "sampler.py")


def numeric_only_dockerfile() -> bytes:
    """Only the Sampler diagnostic is patched; the pinned base is unchanged."""
    if legacy.IMAGE_ID != trace.ORIGINAL_IMAGE:
        raise Blocked("ORIGINAL_IMAGE_POLICY_DRIFT")
    payload = (
        "FROM " + legacy.IMAGE_TAG + "\n"
        "COPY --chown=0:0 --chmod=0644 sampler.py " + bundle.SAMPLER_DEST + "\n"
        "ENV VLLM_P2_NUMERIC_WITNESS=0"
        " VLLM_PLE_UNIQUE_H2D=0"
        " VLLM_P2_DRAFT_VOCAB= VLLM_P2_DRAFT_VOCAB_SHA256=\n"
    )
    if payload.count("\nCOPY ") != 1 or "\nRUN " in payload:
        raise Blocked("NUMERIC_ONLY_RECIPE_SCOPE_DRIFT")
    return payload.encode("utf-8")


def read_only_original_guard() -> dict:
    """Check the same-ID running original and exact stock Prefix-OFF/MTP2 cmd."""
    receipt = legacy.state_receipt(Path.home())
    original = legacy.inspect("container", legacy.NAME)
    image = legacy.inspect("image", legacy.IMAGE_TAG)
    state = legacy.verify_identity(original, image, receipt)
    if (state != "running" or receipt["id"] != trace.ORIGINAL_ID
            or original.get("Image") != trace.ORIGINAL_IMAGE):
        raise Blocked("PROTECTED_ORIGINAL_NOT_SAME_ID_RUNNING")
    cmd = (original.get("Config") or {}).get("Cmd")
    # Reuse previously DGX-proven semantics, but DO NOT execute this command.
    planned_cmd = mtp_off.cmd_without_mtp(cmd)
    if ("--speculative-config" in planned_cmd
            or "--enable-prefix-caching" in planned_cmd
            or planned_cmd.count("--no-enable-prefix-caching") != 1):
        raise Blocked("NUMERIC_ONLY_PREFIX_MTP_CONTRACT_FAILED")
    return {"original_id_verified": True,
            "original_image_verified": True,
            "original_state": state,
            "baseline_prefix": "OFF",
            "baseline_mtp": 2,
            "future_numeric_candidate_prefix": "OFF",
            "future_numeric_candidate_mtp": 0,
            "prepared_command_not_executed": True}


def plan(stage_dir: Path, *, guard=read_only_original_guard) -> tuple[dict, bytes]:
    before = trace.original_identity()
    try:
        sampler = source_stage(stage_dir)
        image = legacy.inspect("image", legacy.IMAGE_TAG)
        if image.get("Id") != trace.ORIGINAL_IMAGE:
            raise Blocked("ORIGINAL_BASE_IMAGE_TAG_DRIFT")
        receipt = guard()
        recipe = numeric_only_dockerfile()
    finally:
        if trace.original_identity() != before:
            raise Blocked("ORIGINAL_ID_IMAGE_OR_START_TIME_CHANGED")
    return {
        "status": "P2_MINIMAL_NUMERIC_SOURCE_PLAN_NO_GPU_AUTHORIZATION",
        "sampler_sha256": hashlib.sha256(sampler).hexdigest(),
        "dockerfile_sha256": hashlib.sha256(recipe).hexdigest(),
        "source_stage_validated": True,
        "only_one_sampler_copy": True,
        "ple_optimization_included": False,
        "mtp_reduction_included": False,
        "draft_vocab_included": False,
        "numeric_witness_default_off": True,
        "prefix_off_mtp_off_future_candidate": True,
        "original_unchanged": True,
        "service_outage_authorized": False,
        "image_build_authorized": False,
        "gpu_window_authorized": False,
        "resource_headroom_certified": False,
        "first_divergence_measured": False,
        "strict_numeric_resolved": False,
        "future_execution_requires_separate_approved_gpu_window": True,
        **receipt,
    }, sampler


def prepare(stage_dir: Path, *, guard=read_only_original_guard) -> dict:
    info, sampler = plan(stage_dir, guard=guard)
    recipe = numeric_only_dockerfile()
    folder = Path(tempfile.mkdtemp(prefix=SINGLE_CANDIDATE_PREFIX, dir="/tmp"))
    try:
        folder.chmod(0o700)
        for name, data in (("sampler.py", sampler),
                           ("Dockerfile", recipe),
                           ("receipt.json", (json.dumps(info, sort_keys=True) + "\n").encode())):
            fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(data)
        if (_source(folder / "sampler.py", "sampler.py") != sampler
                or _source(folder / "Dockerfile", "Dockerfile") != recipe):
            raise Blocked("NUMERIC_ONLY_STAGE_WRITE_MISMATCH")
    except BaseException:
        shutil.rmtree(folder)
        raise
    return {**info, "status": "P2_MINIMAL_NUMERIC_PRIVATE_SOURCE_STAGED_NOT_BUILT",
            "private_directory": str(folder)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--preflight", action="store_true")
    m.add_argument("--prepare", action="store_true")
    p.add_argument("--expected-head", required=True)
    p.add_argument("--stage-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        qsa.preflight(args.expected_head)
        if args.preflight:
            result, _ = plan(args.stage_dir)
        else:
            result = prepare(args.stage_dir)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Blocked, legacy.Blocked, qsa.Blocked, mtp_off.Blocked,
            trace.Blocked, bundle.Blocked, OSError, ValueError, TypeError, KeyError):
        print("P2_MINIMAL_NUMERIC_STAGE_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
