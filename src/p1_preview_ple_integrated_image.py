"""P1 integrated Preview image: preserve BF16 PLE mmap and add opt-in stats.

CPU-only Docker image assembly on the pinned Prefix/QSA/Tool+Responses parent.
No runtime start, stop, exec, GPU, model read, or original filesystem writes.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from src import p1_prefix_release as release
from src import p1_legacy_service_window as legacy
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_preview_tool_qsa_image as tool

PARENT_HEAD = "b89641b4fb522ad46c2239a2128fba16008feeb9"
PARENT_IMAGE_ID = "sha256:e01dffd7542432476d81635e38a706fd73942c7f0832d8eacab34e9d2518cc66"
ORIGINAL_PLE_SHA = "91f17b6203f402785279836c479ead347416da4394049850a47f0ba347649b48"
NEW_PLE_SHA = "9c13cf71001618838532ee9145443647a09a087f68ef82e2c3909028b893617e"
PLE_PATH = "/usr/local/lib/python3.12/dist-packages/vllm_ple_mmap.py"
TAG = "kjlee-qwen38-p1-integrated"
LABEL = "ai.kjlee.p1-integrated"


def tag(head: str) -> str:
    qsa.tag(head)
    return TAG + ":" + head[:12]


def dockerfile() -> str:
    """Image extends the exact Tool/Responses parent with one PLE module."""
    return (
        "FROM " + tool.image_tag(PARENT_HEAD) + "\n"
        "COPY --chown=0:0 --chmod=0644 vllm_ple_mmap.py " + PLE_PATH + "\n"
    )


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_ple_source() -> bytes:
    """Never overwrite the original running PLE with unrecognized sources."""
    path = qsa.ROOT / "src" / "vllm_ple_mmap.py"
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < 2000000:
        raise qsa.Blocked("PLE_SOURCE_UNSAFE")
    raw = path.read_bytes()
    if digest(raw) != NEW_PLE_SHA:
        raise qsa.Blocked("REPOSITORY_PLE_SHA_DRIFT")
    try:
        root = ast.parse(raw, filename="vllm_ple_mmap.py")
    except (SyntaxError, UnicodeError):
        raise qsa.Blocked("REPOSITORY_PLE_SYNTAX_INVALID") from None
    classes = {n.name for n in root.body if isinstance(n, ast.ClassDef)}
    funcs = {n.name for n in root.body if isinstance(n, ast.FunctionDef)}
    if not {"MmapPleTable", "_MmapNgramEmbedding"}.issubset(classes) or "apply" not in funcs:
        raise qsa.Blocked("PLE_ABI_ANCHORS_MISSING")
    if not all(x in raw for x in (
        b"VLLM_PLE_PHASE_STATS", b"VLLM_PLE_FAST_GATHER",
        b"def stats_snapshot", b"device_copy_call_s",
        b"VLLM_PLE_MMAP", b"BF16",
    )):
        raise qsa.Blocked("PLE_STATS_OR_BF16_ANCHORS_MISSING")
    return raw


def verify_installed_ple() -> None:
    """Exact historical original source at immutable Git baseline 9492b78c."""
    installed = tool.docker_copy("vllm_ple_mmap.py")
    if installed is None or digest(installed) != ORIGINAL_PLE_SHA:
        raise qsa.Blocked("ORIGINAL_PLE_SHA_DRIFT")


def labels(head: str) -> dict[str, str]:
    return {
        LABEL: head,
        "ai.kjlee.p1-integrated.parent": PARENT_IMAGE_ID,
        "ai.kjlee.p1-integrated.source": NEW_PLE_SHA,
        "ai.kjlee.p1-integrated.original": ORIGINAL_PLE_SHA,
        "ai.kjlee.p1-integrated.phase-stats": "opt-in-disabled-by-default",
        "ai.kjlee.p1-integrated.runtime": "not-gpu-tested",
    }


def check_child(child: dict, parent: dict, head: str) -> None:
    base = (parent.get("RootFS") or {}).get("Layers")
    layers = (child.get("RootFS") or {}).get("Layers")
    if (not isinstance(base, list) or not isinstance(layers, list)
            or len(layers) != len(base) + 1
            or layers[:len(base)] != base):
        raise qsa.Blocked("PLE_IMAGE_ANCESTRY_DRIFT")
    configuration = child.get("Config") or {}
    found = configuration.get("Labels") or {}
    if any(found.get(k) != v for k, v in labels(head).items()):
        raise qsa.Blocked("PLE_IMAGE_LABELS_DRIFT")
    variables = configuration.get("Env") or []
    if any(v in variables for v in ("VLLM_PLE_PHASE_STATS=1",
                                   "VLLM_PLE_FAST_GATHER=1")):
        raise qsa.Blocked("PLE_EXPERIMENTAL_ENV_ALREADY_ENABLED")


def build(head: str) -> dict:
    receipt, original, _, state = release._legacy_state_for_release()
    if state != "running" or original.get("Id") != receipt["id"]:
        raise qsa.Blocked("ORIGINAL_NOT_RUNNING_SAME_ID")
    original_id = original["Id"]
    ancestor = release._inspect_image(tool.image_tag(PARENT_HEAD))
    if not isinstance(ancestor, dict) or ancestor.get("Id") != PARENT_IMAGE_ID:
        raise qsa.Blocked("TOOL_PARENT_IMAGE_ID_DRIFT")
    if ((ancestor.get("Config") or {}).get("Labels") or {}).get(
            tool.LABEL) != PARENT_HEAD:
        raise qsa.Blocked("TOOL_PARENT_PROVENANCE_DRIFT")
    # Fail closed before any build if the original or repo PLE has changed.
    verify_installed_ple()
    raw = checked_ple_source()
    name = tag(head)
    child = release._inspect_image(name)
    if child is None:
        with tempfile.TemporaryDirectory(prefix="p1-ple-integrated-") as temp:
            ctx = Path(temp)
            ctx.chmod(0o700)
            target = ctx / "vllm_ple_mmap.py"
            with target.open("xb") as dest:
                dest.write(raw)
            target.chmod(0o600)
            (ctx / "Dockerfile").write_text(dockerfile(), encoding="utf-8")
            argv = [
                "docker", "build", "--network=none", "--pull=false",
                "--no-cache", "--tag", name,
            ]
            for key, value in labels(head).items():
                argv.extend(["--label", key + "=" + value])
            qsa.command(argv + [str(ctx)], timeout=900)
        child = release._inspect_image(name)
    if not isinstance(child, dict):
        raise qsa.Blocked("PLE_CHILD_IMAGE_MISSING")
    check_child(child, ancestor, head)
    after = legacy.inspect("container", legacy.NAME)
    if (after.get("Id") != original_id or
            (after.get("State") or {}).get("Status") != "running"):
        raise qsa.Blocked("ORIGINAL_CHANGED_DURING_BUILD")
    return {
        "status": "P1_INTEGRATED_IMAGE_BUILT_CPU_ONLY_NOT_GPU_VERIFIED",
        "image": name,
        "image_id": child["Id"],
        "parent_image_id": PARENT_IMAGE_ID,
        "original_ple_sha256": ORIGINAL_PLE_SHA,
        "candidate_ple_sha256": NEW_PLE_SHA,
        "ple_phase_stats_default_off": True,
        "ple_fast_gather_default_off": True,
        "original_same_id_running": True,
        "model_gpu_or_api_verified": False,
        "strict_numeric_gate_passed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--build", required=True, action="store_true")
    args = parser.parse_args()
    try:
        qsa.os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        print(json.dumps(build(args.expected_head), sort_keys=True))
        return 0
    except (qsa.Blocked, release.ReleaseBlocked, legacy.Blocked, OSError,
            ValueError, KeyError, TypeError) as err:
        reason = str(err) if isinstance(err, qsa.Blocked) else type(err).__name__
        print("P1_INTEGRATED_PLE_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
