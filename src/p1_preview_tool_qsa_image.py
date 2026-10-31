"""P1 CPU-only Preview Tool/Responses overlay on a pinned QSA candidate image.

Builds exactly one COPY layer of existing Blazux parser/Responses patch outputs.
No vLLM imports, GPU, model load, Docker container start/stop/exec, or live edits.
PLE is SHA-inspected only; changing the BF16 mmap loader requires a separate
compatibility decision.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from src import p1_preview_qsa_exact_topk as qsa
from src import p1_prefix_release as release
from src import p1_legacy_service_window as legacy
from src import preview_p1_tool_responses_stage as stage

QSA_HEAD = "3852995a19f4778be5683496fdb0cceb56a4addf"
QSA_IMAGE_ID = "sha256:56b9df34daa5207956ded935f38ee900a44c4f8a737302b18abb03a58e46c518"
SITE = "/usr/local/lib/python3.12/dist-packages"
TAG = "kjlee-qwen38-p1-tool-qsa"
LABEL = "ai.kjlee.p1-tool-qsa"
MAX_ARCHIVE = stage.MAX_SOURCE_BYTES


def image_tag(head: str) -> str:
    qsa.tag(head)
    return TAG + ":" + head[:12]


def dockerfile() -> str:
    """One COPY of only the allowlisted patched vllm subtree."""
    return (
        "FROM " + qsa.tag(QSA_HEAD) + "\n"
        "COPY --chown=0:0 vllm/ " + SITE + "/vllm/\n"
    )


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def docker_copy(relative: str, *, missing_ok: bool = False) -> bytes | None:
    """Read a single known installed Python source via docker cp, not exec."""
    if relative != "vllm_ple_mmap.py" and relative not in stage.ALLOWED_FILES:
        raise qsa.Blocked("SOURCE_PATH_NOT_ALLOWLISTED")
    src = SITE + "/" + relative
    try:
        cp = subprocess.run(
            ["docker", "cp", legacy.NAME + ":" + src, "-"],
            check=False, capture_output=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        raise qsa.Blocked("SOURCE_COPY_UNAVAILABLE") from None
    if cp.returncode:
        if missing_ok:
            return None
        raise qsa.Blocked("SOURCE_COPY_FAILED")
    try:
        with tarfile.open(fileobj=io.BytesIO(cp.stdout), mode="r:") as archive:
            items = [item for item in archive.getmembers() if item.isfile()]
            if len(items) != 1 or not 0 < items[0].size <= MAX_ARCHIVE:
                raise qsa.Blocked("SOURCE_ARCHIVE_INVALID")
            file = archive.extractfile(items[0])
            if file is None:
                raise qsa.Blocked("SOURCE_ARCHIVE_UNREADABLE")
            return file.read()
    except (OSError, tarfile.TarError):
        raise qsa.Blocked("SOURCE_ARCHIVE_MALFORMED") from None


def inspect_ple() -> dict:
    """No modification or activation: compare installed BF16 PLE and repo source."""
    installed = docker_copy("vllm_ple_mmap.py", missing_ok=True)
    local = qsa.ROOT / "src" / "vllm_ple_mmap.py"
    source = local.read_bytes()
    if not source or len(source) > MAX_ARCHIVE:
        raise qsa.Blocked("REPO_PLE_SOURCE_INVALID")
    return {
        "status": ("MISSING" if installed is None else
                   "SAME" if sha(source) == sha(installed) else "DIFFERENT"),
        "installed_sha256": sha(installed) if installed is not None else None,
        "repository_sha256": sha(source),
        "ple_runtime_modified": False,
        "ple_phase_stats_activated": False,
    }


def prepare_overlay(context: Path) -> tuple[list[str], dict[str, str]]:
    """Rebase upstream patches against exact original Preview source in temp."""
    patches, touched = stage.read_patch_bundle()
    if touched - stage.ALLOWED_FILES or stage.NEW_FILE not in touched:
        raise qsa.Blocked("PATCH_TARGETS_UNEXPECTED")
    for relpath in sorted(touched):
        if relpath == stage.NEW_FILE:
            continue
        raw = docker_copy(relpath)
        path = context / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    stage.read_preview_sources(context, touched)
    for index, patch_data in enumerate(patches, start=1):
        try:
            cp = subprocess.run(
                ["patch", "--batch", "--forward", "--fuzz=0", "-p1",
                 "--silent", "--no-backup-if-mismatch"],
                input=patch_data, cwd=context, capture_output=True,
                check=False, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise qsa.Blocked("PATCH_TOOL_UNAVAILABLE") from None
        if cp.returncode:
            raise qsa.Blocked("PREVIEW_PATCH_CONTEXT_MISMATCH_" + str(index))
    output = {}
    for relpath in sorted(touched):
        file = context / relpath
        if (not file.is_file() or file.is_symlink()
                or not 0 < file.stat().st_size <= MAX_ARCHIVE):
            raise qsa.Blocked("PATCHED_SOURCE_INVALID")
        try:
            ast.parse(file.read_bytes(), filename=relpath)
        except (SyntaxError, UnicodeError):
            raise qsa.Blocked("PATCHED_SOURCE_SYNTAX_ERROR") from None
        output[relpath] = sha(file.read_bytes())
    stage.check_implemented_hooks(context)
    # Verify nothing outside the allowlist can enter the Docker COPY layer.
    nodes = list(context.rglob("*"))
    for node in nodes:
        if node.is_symlink():
            raise qsa.Blocked("STAGED_SYMLINK_FORBIDDEN")
    actual_files = {p.relative_to(context).as_posix()
                    for p in nodes if p.is_file()}
    if actual_files != touched:
        raise qsa.Blocked("STAGED_FILES_NOT_EXACT_ALLOWLIST")
    # Preserve importable 0755 dirs and readable 0644 files in the image,
    # even when the invoking operator uses umask 077.
    for node in nodes:
        if node.is_dir():
            node.chmod(0o755)
        elif node.is_file():
            node.chmod(0o644)
    if set(output) != touched:
        raise qsa.Blocked("PATCHED_SOURCE_SET_DRIFT")
    return sorted(touched), output


def labels(head: str, hashes: dict[str, str]) -> dict[str, str]:
    canonical = json.dumps(hashes, sort_keys=True, separators=(",", ":"))
    return {
        LABEL: head,
        "ai.kjlee.p1-tool-qsa.parent-image": QSA_IMAGE_ID,
        "ai.kjlee.p1-tool-qsa.overlay-set": sha(canonical.encode()),
        "ai.kjlee.p1-tool-qsa.status": "cpu-image-only-runtime-not-tested",
    }


def verify_child(child: dict, parent: dict, expected: dict[str, str]) -> None:
    layers = (child.get("RootFS") or {}).get("Layers")
    before = (parent.get("RootFS") or {}).get("Layers")
    if (not isinstance(layers, list) or not isinstance(before, list)
            or len(layers) != len(before) + 1
            or layers[:len(before)] != before):
        raise qsa.Blocked("IMAGE_ANCESTRY_DRIFT")
    actual = (child.get("Config") or {}).get("Labels") or {}
    if any(actual.get(k) != v for k, v in expected.items()):
        raise qsa.Blocked("IMAGE_LABELS_DRIFT")


def build(head: str) -> dict:
    receipt, original, _, state = release._legacy_state_for_release()
    if state != "running" or original.get("Id") != receipt["id"]:
        raise qsa.Blocked("ORIGINAL_NOT_RUNNING_SAME_ID")
    original_id = original["Id"]
    parent = release._inspect_image(qsa.tag(QSA_HEAD))
    if not isinstance(parent, dict) or parent.get("Id") != QSA_IMAGE_ID:
        raise qsa.Blocked("QSA_PARENT_IMAGE_DRIFT")
    # Also verify pinned original -> two-file Prefix release -> QSA image.
    qsa_parent = release._release_image(qsa.PARENT_HEAD)
    qsa.check_child(parent, qsa_parent, QSA_HEAD,
                    (parent.get("Config") or {}).get("Labels", {}).get(
                        "ai.kjlee.p1-qsa.patched", ""))
    ple = inspect_ple()
    name = image_tag(head)
    with tempfile.TemporaryDirectory(prefix="p1-tool-qsa-") as folder:
        context = Path(folder)
        context.chmod(0o700)
        touched, hashes = prepare_overlay(context)
        expected = labels(head, hashes)
        child = release._inspect_image(name)
        if child is None:
            (context / "Dockerfile").write_text(dockerfile(), encoding="utf-8")
            cmd = ["docker", "build", "--network=none", "--pull=false",
                   "--no-cache", "--tag", name]
            for key, value in expected.items():
                cmd += ["--label", key + "=" + value]
            qsa.command(cmd + [str(context)], timeout=900)
            child = release._inspect_image(name)
        if not isinstance(child, dict):
            raise qsa.Blocked("IMAGE_NOT_BUILT")
        verify_child(child, parent, expected)
    after = legacy.inspect("container", legacy.NAME)
    if (after.get("Id") != original_id or
            (after.get("State") or {}).get("Status") != "running"):
        raise qsa.Blocked("ORIGINAL_CHANGED_DURING_BUILD")
    return {
        "status": "P1_TOOL_QSA_IMAGE_BUILT_CPU_ONLY_NOT_GPU_TESTED",
        "image": name,
        "image_id": child["Id"],
        "parent_image_id": QSA_IMAGE_ID,
        "patched_parser_responses_files": len(touched),
        "ple_source_compatibility": ple,
        "tool_responses_api_verified": False,
        "original_same_id_running": True,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--build", action="store_true", required=True)
    args = p.parse_args()
    try:
        qsa.os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        print(json.dumps(build(args.expected_head), sort_keys=True))
        return 0
    except (qsa.Blocked, release.ReleaseBlocked, legacy.Blocked,
            stage.StageBlocked, OSError, ValueError, TypeError, KeyError) as err:
        reason = str(err) if isinstance(err, (qsa.Blocked, stage.StageBlocked)) else type(err).__name__
        print("P1_TOOL_QSA_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
