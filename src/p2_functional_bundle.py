"""P2 isolated candidate: real BF16 PLE source + pinned sampler numeric witness.

A single candidate-only two-COPY Dockerfile is staged for later *separately
approved* image build/GPU testing. This command does not build an image, run a
container, load weights, touch the running service, issue HTTP or use CUDA.
Also fingerprints installed MTP-related Python ABI source without executing it.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from src import p1_legacy_service_window as legacy
from src import p1_numeric_source_trace as trace
from src import p1_preview_qsa_exact_topk as qsa
from src import p2_numeric_sampler_witness as witness
from src import p2_mtp_candidate_overlay as mtp_overlay
from src import p2_upstream_draft_asset as upstream_draft

PLE_REPO = Path("src/vllm_ple_mmap.py")
PLE_DEST = trace.PACKAGE_ROOT + "vllm_ple_mmap.py"
SAMPLER_DEST = trace.PACKAGE_ROOT + trace.SOURCES["sampler"]
# Candidate-only baked-in ID map; opt-in runtime env remains empty by default.
UPSTREAM_DRAFT_DEST = "/opt/llm/p2-orcarouter-draft-65536.npy"
# Explicit fixed candidates; missing entries do NOT certify an absence of MTP.
MTP_SOURCE_CANDIDATES = (
    "vllm/models/qwen3_8_flash_next/nvidia/mtp.py",
    "vllm/models/qwen3_8_flash_next/nvidia/model.py",
    "vllm/models/qwen4_exp.py",
    "vllm/v1/spec_decode/eagle.py",
)
MAX_PLE_BYTES = 150_000


class Blocked(RuntimeError):
    """Print only static failure category, not model or Docker stderr."""


def checked_ple(root: Path) -> bytes:
    path = root / PLE_REPO
    if path.is_symlink() or not path.is_file():
        raise Blocked("PLE_REPOSITORY_FILE_MISSING_OR_SYMLINK")
    if not 0 < path.stat().st_size <= MAX_PLE_BYTES:
        raise Blocked("PLE_REPOSITORY_SIZE_INVALID")
    data = path.read_bytes()
    try:
        source = data.decode("utf-8")
        tree = ast.parse(source)
    except (UnicodeError, SyntaxError):
        raise Blocked("PLE_REPOSITORY_AST_INVALID") from None
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    embedding = classes.get("_MmapNgramEmbedding")
    methods = {n.name for n in embedding.body if isinstance(n, ast.FunctionDef)} if embedding else set()
    if (not {"MmapPleTable", "_MmapNgramEmbedding"}.issubset(classes)
            or not {"_ple_unique_h2d_lookup", "apply"}.issubset(functions)
            or "forward" not in methods
            or source.count('VLLM_PLE_UNIQUE_H2D') < 2):
        raise Blocked("PLE_UNIQUE_H2D_SOURCE_ABI_MISSING")
    return data


def dockerfile(*, include_mtp: bool = False,
               include_upstream_draft: bool = False) -> str:
    """Candidate-only source copies. A pinned map is inert until opt-in."""
    if include_upstream_draft and not include_mtp:
        raise Blocked("UPSTREAM_DRAFT_REQUIRES_MTP")
    return (
        "FROM " + legacy.IMAGE_TAG + "\n"
        "COPY --chown=0:0 --chmod=0644 sampler.py " + SAMPLER_DEST + "\n"
        "COPY --chown=0:0 --chmod=0644 vllm_ple_mmap.py " + PLE_DEST + "\n"
        + (("COPY --chown=0:0 --chmod=0644 mtp.py "
             + trace.PACKAGE_ROOT + mtp_overlay.SOURCE_FILE + "\n")
           if include_mtp else "")
        + (("COPY --chown=0:0 --chmod=0644 draft_vocab_65536.npy "
             + UPSTREAM_DRAFT_DEST + "\n") if include_upstream_draft else "")
        + "ENV VLLM_P2_NUMERIC_WITNESS=0 VLLM_PLE_UNIQUE_H2D=0"
        + (" VLLM_P2_DRAFT_VOCAB= VLLM_P2_DRAFT_VOCAB_SHA256="
           if include_mtp else "") + "\n"
    )


def inspect_local_base_image() -> None:
    """Require Docker FROM tag to map to the exact protected original digest."""
    if legacy.IMAGE_ID != trace.ORIGINAL_IMAGE:
        raise Blocked("ORIGINAL_POLICY_IMAGE_DRIFT")
    try:
        info = legacy.inspect("image", legacy.IMAGE_TAG)
    except (legacy.Blocked, OSError, ValueError, TypeError, KeyError):
        raise Blocked("ORIGINAL_IMAGE_INSPECTION_FAILED") from None
    if not isinstance(info, dict) or info.get("Id") != trace.ORIGINAL_IMAGE:
        raise Blocked("ORIGINAL_FROM_TAG_IMAGE_ID_DRIFT")


def mtp_source_summary(data: bytes) -> dict:
    """Only hash/classes/method names, never dump installed source or checkpoint."""
    if not 0 < len(data) <= trace.MAX_SOURCE_BYTES:
        raise Blocked("MTP_ABI_SOURCE_TOO_LARGE")
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (SyntaxError, UnicodeError):
        raise Blocked("MTP_ABI_AST_INVALID") from None
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    selected = []
    for cls in classes:
        if ("mtp" not in cls.name.lower() and
                "draft" not in cls.name.lower() and
                "qwen3_8" not in cls.name.lower()):
            continue
        names = sorted(n.name for n in cls.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name in ("forward", "compute_logits", "load_weights",
                                     "_make_draft_vllm_config", "__init__"))
        selected.append({"class": cls.name, "methods": names})
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "class_signatures": selected[:24],
        "class_matches_truncated": len(selected) > 24,
        "source_only_not_runtime_abi_pass": True,
    }


def _read_mtp_source(path: str) -> bytes | None:
    """Read one allowlisted file via docker cp; never exec or inspect model."""
    if path not in MTP_SOURCE_CANDIDATES:
        raise Blocked("MTP_SOURCE_NOT_ALLOWLISTED")
    try:
        cp = subprocess.run(
            ["docker", "cp", legacy.NAME + ":" + trace.PACKAGE_ROOT + path, "-"],
            capture_output=True, check=False, timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("MTP_SOURCE_DOCKER_CP_UNAVAILABLE") from None
    if cp.returncode != 0:
        return None  # Not proven absent; paths can differ across Preview builds.
    try:
        return trace.extract_python_tar(cp.stdout)
    except trace.Blocked:
        raise Blocked("MTP_SOURCE_ARCHIVE_INVALID") from None


def read_mtp_abi() -> dict:
    result = {}
    for path in MTP_SOURCE_CANDIDATES:
        data = _read_mtp_source(path)
        result[path] = (
            {"status": "NOT_FOUND_OR_UNREADABLE_NOT_CERTIFIED"} if data is None
            else {"status": "READ_ONLY_SOURCE_FOUND", **mtp_source_summary(data)}
        )
    return {
        "status": "MTP_DRAFT_ABI_SOURCE_TRIAGE_ONLY",
        "sources": result,
        "draft_head_slicing_implemented": False,
        "draft_token_selection_proven": False,
        "loader_acceptance_runtime_verified": False,
    }


def prepare(root: Path, *, probe=read_mtp_abi,
            include_mtp: bool = False,
            include_upstream_draft: bool = False) -> dict:
    """Stage pinned numeric/PLE/MTP and optional Blazux IDs in private /tmp."""
    if include_upstream_draft and not include_mtp:
        raise Blocked("UPSTREAM_DRAFT_REQUIRES_MTP")
    before = trace.original_identity()
    try:
        inspect_local_base_image()
        original = trace._run_docker_cp(trace.SOURCES["sampler"])
        patched = witness.transform(original)
        ple = checked_ple(root)
        upstream_receipt = None
        upstream_raw = None
        if include_upstream_draft:
            # No local corpus: pinned upstream data must fit the actual
            # Orcarouter recipe tokenizer AND config. Never infer IDs.
            asset = root / upstream_draft.ASSET_RELATIVE
            recipe = Path.home() / upstream_draft.RECIPE_RELATIVE
            upstream_receipt = upstream_draft.audit(
                asset, recipe / "tokenizer.json",
                recipe / "tokenizer_config.json")
            upstream_raw = asset.read_bytes()
            if (hashlib.sha256(upstream_raw).hexdigest() !=
                    upstream_receipt["upstream_npy_sha256"]):
                raise Blocked("UPSTREAM_DRAFT_CHANGED_AFTER_VALIDATION")
        mtp_patched = None
        if include_mtp:
            mtp_raw = _read_mtp_source(mtp_overlay.SOURCE_FILE)
            if mtp_raw is None:
                raise Blocked("PINNED_MTP_SOURCE_MISSING")
            mtp_patched = mtp_overlay.transform(mtp_raw)
        mtp = probe()
    finally:
        if trace.original_identity() != before:
            raise Blocked("ORIGINAL_ID_IMAGE_OR_STARTED_AT_CHANGED") from None

    folder = Path(tempfile.mkdtemp(prefix="p2-functional-bundle-", dir="/tmp"))
    try:
        folder.chmod(0o700)
        payloads = [
            ("sampler.py", patched),
            ("vllm_ple_mmap.py", ple),
        ]
        if include_mtp:
            assert mtp_patched is not None
            payloads.append(("mtp.py", mtp_patched))
        if include_upstream_draft:
            assert upstream_raw is not None
            payloads.append(("draft_vocab_65536.npy", upstream_raw))
        payloads.append(("Dockerfile",
                         dockerfile(include_mtp=include_mtp,
                                    include_upstream_draft=include_upstream_draft).encode("utf-8")))
        for filename, data in payloads:
            target = folder / filename
            with target.open("xb") as stream:
                stream.write(data)
            target.chmod(0o600)
    except BaseException:
        shutil.rmtree(folder)
        raise
    return {
        "status": ("P2_NUMERIC_PLE_MTP_UPSTREAM_VOCAB_SOURCE_STAGED_NOT_BUILT"
                   if include_upstream_draft else
                   "P2_NUMERIC_PLE_MTP_CANDIDATE_SOURCE_STAGED_NOT_BUILT"
                   if include_mtp else
                   "P2_NUMERIC_PLE_CANDIDATE_SOURCE_STAGED_NOT_BUILT"),
        "stage_directory": str(folder),
        "parent_image_pinned": True,
        "original_container_unchanged": True,
        "sampler_source_sha256": witness.SOURCE_SHA256,
        "sampler_candidate_sha256": hashlib.sha256(patched).hexdigest(),
        "ple_candidate_sha256": hashlib.sha256(ple).hexdigest(),
        "numeric_witness_default_off": True,
        "ple_unique_h2d_default_off": True,
        "candidate_build_or_gpu_or_api_executed": False,
        "mtp_reduced_vocab_source_included": include_mtp,
        "mtp_reduced_vocab_default_off": True,
        "upstream_draft_asset_included": include_upstream_draft,
        "upstream_draft_asset_sha256": (
            upstream_receipt["upstream_npy_sha256"]
            if upstream_receipt is not None else None),
        "upstream_draft_orcarouter_metadata_verified": upstream_receipt is not None,
        "upstream_draft_mapping_fingerprint": (
            upstream_receipt["draft_mapping_fingerprint"]
            if upstream_receipt is not None else None),
        "upstream_draft_candidate_path": (
            UPSTREAM_DRAFT_DEST if include_upstream_draft else None),
        "upstream_draft_opt_in_performed": False,
        "mtp_candidate_patch_sha256": (
            hashlib.sha256(mtp_patched).hexdigest() if mtp_patched is not None
            else None),
        "mtp": mtp,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-head", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--stage", action="store_true")
    mode.add_argument("--stage-mtp", action="store_true")
    mode.add_argument("--stage-mtp-upstream", action="store_true")
    p.add_argument("--confirm-original-id")
    args = p.parse_args(argv)
    try:
        qsa.preflight(args.expected_head)
        if args.check:
            ple = checked_ple(qsa.ROOT)
            print(json.dumps({
                "status": "P2_BUNDLE_SOURCE_READY_NO_DOCKER",
                "ple_sha256": hashlib.sha256(ple).hexdigest(),
                "head": args.expected_head,
                "candidate_gpu_pass": False,
                "numeric_root_cause_resolved": False,
            }, sort_keys=True))
            return 0
        if args.confirm_original_id != trace.ORIGINAL_ID:
            raise Blocked("EXACT_ORIGINAL_CONTAINER_ID_REQUIRED")
        print(json.dumps(prepare(
            qsa.ROOT,
            include_mtp=args.stage_mtp or args.stage_mtp_upstream,
            include_upstream_draft=args.stage_mtp_upstream,
        ), sort_keys=True))
        return 0
    except (Blocked, upstream_draft.Blocked, witness.Blocked, mtp_overlay.Blocked,
            trace.Blocked, legacy.Blocked, qsa.Blocked,
            OSError, ValueError, TypeError, KeyError):
        print("P2_FUNCTIONAL_BUNDLE_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
