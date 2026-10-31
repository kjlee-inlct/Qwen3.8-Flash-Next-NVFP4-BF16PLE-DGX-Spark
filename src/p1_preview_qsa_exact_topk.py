"""CPU-only P1 optional exact top-k image builder for pinned Preview QSA ABI.

Never edits the original or the pinned two-COPY Prefix ON release.
Only builds a separately labeled one-COPY QSA candidate, without GPU or weights.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

from src import p1_prefix_release as release
from src import p1_legacy_service_window as legacy

ROOT = Path(__file__).resolve().parents[1]
PARENT_HEAD = "c0160408ab22f0550390d2e9b4595df41a600519"
PARENT_ID = "sha256:85f2ac46b780c6e3079fdec577dff38104473871e5a1390e4c83239152b52aba"
SOURCE_SHA = "c4ffe3674cafa0ce2dabc39a39f0ddbb4b594bc358ad210ffce9d04383350c7f"
QSA = "/usr/local/lib/python3.12/dist-packages/vllm/models/qwen3_8_flash_next/nvidia/ops/qsa.py"
LABEL = "ai.kjlee.p1-qsa-exact"
TAG = "kjlee-qwen38-p1-qsa-exact"

ANCHOR = """        topk_op = (
            torch.ops._C.cooperative_topk
            if use_cooperative_topk
            else torch.ops._C.persistent_topk
        )
        topk_op(logits, visible_blocks, blocks, topk_workspace, block_topk, columns)
"""
FALLBACK = "".join("    " + line if line.strip() else line
                   for line in ANCHOR.splitlines(keepends=True))
REPLACEMENT = (
    "        if _P1_EXACT_TOPK:\n"
    "            _p1_exact_topk(logits, visible_blocks, blocks, block_topk, columns)\n"
    "        else:\n" + FALLBACK
)
HELPER = """
# P1 experimental opt-in: default unmodified stock QSA selection.
import os as _p1_qsa_os
_P1_EXACT_TOPK = _p1_qsa_os.environ.get("VLLM_QSA_EXACT_TOPK", "0") == "1"


def _p1_exact_topk(logits, visible_blocks, blocks, block_topk, columns):
    # The score kernel may leave non-visible logit columns uninitialized.
    if (logits.ndim != 2 or logits.shape[1] != columns or
            visible_blocks.ndim != 1 or visible_blocks.shape[0] != logits.shape[0]
            or blocks.shape != (logits.shape[0], block_topk)
            or block_topk < 1 or columns < 1):
        raise RuntimeError("P1_QSA_EXACT_SHAPE_DRIFT")
    invalid = (torch.arange(columns, device=logits.device)[None, :] >=
               visible_blocks[:, None])
    safe = logits.masked_fill(invalid, float("-inf"))
    k = min(block_topk, columns)
    indices = torch.topk(safe, k=k, dim=1, sorted=False).indices
    blocks[:, :k].copy_(indices)
    if k < block_topk:
        blocks[:, k:].fill_(-1)
"""


class Blocked(Exception):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def transform(raw: bytes, *, expected_sha: str = SOURCE_SHA) -> bytes:
    """SHA and exact-anchor checked source rewrite, never in place."""
    if digest(raw) != expected_sha:
        raise Blocked("QSA_SHA_DRIFT")
    try:
        source = raw.decode("utf-8")
        ast.parse(source)
    except (UnicodeError, SyntaxError):
        raise Blocked("QSA_INVALID_PYTHON") from None
    if source.count(ANCHOR) != 1 or "_P1_EXACT_TOPK" in source:
        raise Blocked("QSA_ANCHOR_DRIFT")
    result = source.replace(ANCHOR, REPLACEMENT) + HELPER
    ast.parse(result)
    if (result.count("torch.ops._C.persistent_topk") != 1
            or result.count("torch.topk(safe") != 1):
        raise Blocked("QSA_FALLBACK_OR_PATCH_DRIFT")
    return result.encode("utf-8")


def tag(head: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise Blocked("HEAD_INVALID")
    return TAG + ":" + head[:12]


def dockerfile() -> str:
    return (
        "FROM " + release.release_tag(PARENT_HEAD) + "\n"
        "COPY --chown=0:0 --chmod=0644 qsa.py " + QSA + "\n"
        "ENV VLLM_QSA_EXACT_TOPK=1\n"
    )


def labels(head: str, patched_sha: str) -> dict[str, str]:
    return {
        LABEL: head,
        "ai.kjlee.p1-qsa.parent": PARENT_ID,
        "ai.kjlee.p1-qsa.source": SOURCE_SHA,
        "ai.kjlee.p1-qsa.patched": patched_sha,
        "ai.kjlee.p1-qsa.status": "experimental-gpu-not-verified",
    }


def command(argv: list[str], *, timeout: int = 60) -> str:
    try:
        cp = subprocess.run(argv, check=True, text=True, capture_output=True,
                            timeout=timeout)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        raise Blocked("COMMAND_FAILED_" + argv[0].upper()) from None
    return cp.stdout.strip()


def preflight(head: str) -> None:
    tag(head)
    if os.geteuid() == 0:
        raise Blocked("ROOT_FORBIDDEN")
    if command(["git", "rev-parse", "--show-toplevel"]) != str(ROOT):
        raise Blocked("WRONG_CHECKOUT")
    if command(["git", "branch", "--show-current"]) != "feature/blazux-phase6-runtime-gates":
        raise Blocked("WRONG_BRANCH")
    if command(["git", "rev-parse", "HEAD"]) != head:
        raise Blocked("HEAD_DRIFT")
    if command(["git", "status", "--porcelain=v1", "--untracked-files=all"]):
        raise Blocked("DIRTY_CHECKOUT")
    origin = command(["git", "remote", "get-url", "origin"]).removesuffix(".git")
    if origin not in (
        "https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark",
        "git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark",
    ):
        raise Blocked("WRONG_REMOTE")
    command([sys.executable, str(ROOT / "scripts/verify-source-state.py")])
    if command(["git", "rev-parse", "HEAD"]) != head:
        raise Blocked("HEAD_CHANGED")


def read_qsa() -> bytes:
    try:
        cp = subprocess.run(["docker", "cp", legacy.NAME + ":" + QSA, "-"],
                            check=True, capture_output=True, timeout=45)
        with tarfile.open(fileobj=io.BytesIO(cp.stdout), mode="r:") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            if len(members) != 1 or not 0 < members[0].size <= 2_000_000:
                raise Blocked("QSA_ARCHIVE_INVALID")
            fh = tf.extractfile(members[0])
            if fh is None:
                raise Blocked("QSA_ARCHIVE_EMPTY")
            raw = fh.read()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            tarfile.TarError):
        raise Blocked("QSA_DOCKER_CP_FAILED") from None
    if digest(raw) != SOURCE_SHA:
        raise Blocked("QSA_SOURCE_DRIFT")
    return raw


def check_child(child: dict, parent: dict, head: str, patched_sha: str) -> None:
    layers = (child.get("RootFS") or {}).get("Layers")
    base_layers = (parent.get("RootFS") or {}).get("Layers")
    if (not isinstance(layers, list) or not isinstance(base_layers, list)
            or len(layers) != len(base_layers) + 1
            or layers[:len(base_layers)] != base_layers):
        raise Blocked("CHILD_IMAGE_LAYERS_DRIFT")
    config = child.get("Config") or {}
    existing_labels = config.get("Labels") or {}
    if any(existing_labels.get(k) != v for k, v in labels(head, patched_sha).items()):
        raise Blocked("CHILD_IMAGE_LABELS_DRIFT")
    if "VLLM_QSA_EXACT_TOPK=1" not in (config.get("Env") or []):
        raise Blocked("CHILD_FLAG_MISSING")


def build(head: str) -> dict:
    receipt, ci, _, state = release._legacy_state_for_release()
    if state != "running" or ci.get("Id") != receipt["id"]:
        raise Blocked("ORIGINAL_NOT_RUNNING_SAME_ID")
    original_id = ci["Id"]
    parent = release._release_image(PARENT_HEAD)
    if parent.get("Id") != PARENT_ID:
        raise Blocked("PARENT_IMAGE_ID_DRIFT")
    patched = transform(read_qsa())
    patched_sha = digest(patched)
    name = tag(head)
    child = release._inspect_image(name)
    if child is None:
        with tempfile.TemporaryDirectory(prefix="p1-qsa-exact-") as tmp:
            context = Path(tmp)
            context.chmod(0o700)
            dest = context / "qsa.py"
            with dest.open("xb") as out:
                out.write(patched)
            dest.chmod(0o600)
            (context / "Dockerfile").write_text(dockerfile(), encoding="utf-8")
            argv = ["docker", "build", "--network=none", "--pull=false",
                    "--no-cache", "--tag", name]
            for k, v in labels(head, patched_sha).items():
                argv += ["--label", k + "=" + v]
            command(argv + [str(context)], timeout=900)
        child = release._inspect_image(name)
    if child is None:
        raise Blocked("CHILD_IMAGE_MISSING")
    check_child(child, parent, head, patched_sha)
    after = legacy.inspect("container", legacy.NAME)
    if (after.get("Id") != original_id or
            (after.get("State") or {}).get("Status") != "running"):
        raise Blocked("ORIGINAL_CHANGED_DURING_BUILD")
    return {
        "status": "QSA_EXACT_IMAGE_BUILT_CPU_ONLY_NOT_GPU_TESTED",
        "image": name, "image_id": child["Id"],
        "original_same_id_running": True,
        "qsa_exact_topk": "experimental",
        "strict_numeric_gate_passed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--build", action="store_true", required=True)
    args = p.parse_args()
    try:
        os.chdir(ROOT)
        preflight(args.expected_head)
        print(json.dumps(build(args.expected_head), sort_keys=True))
        return 0
    except (Blocked, release.ReleaseBlocked, legacy.Blocked,
            OSError, TypeError, ValueError, KeyError) as err:
        reason = str(err) if isinstance(err, Blocked) else type(err).__name__
        print("P1_QSA_EXACT_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
