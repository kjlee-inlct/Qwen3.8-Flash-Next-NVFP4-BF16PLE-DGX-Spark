"""P2 DGX pull-and-run, source-only preparation of a pinned Sampler witness.

Read-only Docker inspect/cp of the already-running protected original plus a
new *private* /tmp source stage. NEVER run/exec/stop/start a container, build an
image, load a model, call HTTP or execute GPU inference. The staged patch is
OFF by default and is not an approval to start a candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from src import p1_legacy_service_window as legacy
from src import p1_numeric_source_trace as source_trace
from src import p1_preview_qsa_exact_topk as qsa
from src import p2_numeric_sampler_witness as witness


class Blocked(RuntimeError):
    pass


def verify_original_image() -> None:
    """Check local image tag maps to the immutable original image ID."""
    if legacy.IMAGE_ID != source_trace.ORIGINAL_IMAGE:
        raise Blocked("ORIGINAL_IMAGE_POLICY_DRIFT")
    try:
        image = legacy.inspect("image", legacy.IMAGE_TAG)
    except (legacy.Blocked, OSError, ValueError, TypeError, KeyError):
        raise Blocked("ORIGINAL_IMAGE_INSPECT_FAILED") from None
    if image.get("Id") != source_trace.ORIGINAL_IMAGE:
        raise Blocked("ORIGINAL_IMAGE_TAG_ID_DRIFT")


def dockerfile() -> str:
    """Non-executable image recipe; no build or container action occurs."""
    return (
        "FROM " + legacy.IMAGE_TAG + "\n"
        "COPY --chown=0:0 --chmod=0644 sampler.py "
        + source_trace.PACKAGE_ROOT + source_trace.SOURCES["sampler"] + "\n"
        "ENV " + witness.ENV_NAME + "=0\n"
    )


def stage() -> dict:
    """Prepare source in a private fresh directory, never a pinned P1 Stage."""
    before = source_trace.original_identity()
    try:
        verify_original_image()
        original = source_trace._run_docker_cp(source_trace.SOURCES["sampler"])
        patched = witness.transform(original)  # SHA + exact anchors
    finally:
        if source_trace.original_identity() != before:
            raise Blocked("ORIGINAL_ID_OR_STARTED_AT_CHANGED") from None

    root = Path(tempfile.mkdtemp(prefix="p2-numeric-witness-", dir="/tmp"))
    try:
        root.chmod(0o700)
        for name, payload in (
            ("sampler.py", patched),
            ("Dockerfile", dockerfile().encode("utf-8")),
        ):
            path = root / name
            with path.open("xb") as out:
                out.write(payload)
            path.chmod(0o600)
    except BaseException:
        shutil.rmtree(root)
        raise
    return {
        "status": "P2_WITNESS_SOURCE_STAGED_NOT_BUILT_NOT_RUN",
        "stage_directory": str(root),
        "sampler_source_sha256": witness.SOURCE_SHA256,
        "patched_sampler_sha256": hashlib.sha256(patched).hexdigest(),
        "parent_image_id_verified": True,
        "original_same_id_running_unchanged": True,
        "witness_default_off": True,
        "docker_build_run_gpu_api_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-head", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--stage", action="store_true")
    p.add_argument("--confirm-original-id")
    args = p.parse_args(argv)
    try:
        qsa.preflight(args.expected_head)  # fork origin, exact branch/HEAD, clean source manifest
        if args.check:
            print(json.dumps({
                "status": "P2_SOURCE_PREFLIGHT_PASS_NO_DOCKER_OR_GPU",
                "source_head": args.expected_head,
                "numeric_root_cause_resolved": False,
            }, sort_keys=True))
            return 0
        if args.confirm_original_id != source_trace.ORIGINAL_ID:
            raise Blocked("EXACT_ORIGINAL_ID_CONFIRMATION_REQUIRED")
        print(json.dumps(stage(), sort_keys=True))
        return 0
    except (Blocked, witness.Blocked, source_trace.Blocked, legacy.Blocked,
            qsa.Blocked, OSError, ValueError, TypeError, KeyError):
        print("P2_DGX_SOURCE_PREP_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
