"""CPU-only P1 B2 image: exact torch.topk plus canonical block index order.

Original stock image base, Prefix OFF, MTP2, original BF16 PLE and all other
sources unchanged. Experimental only, not a runtime launcher or deployment.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from src import p1_qsa_isolation_image as b
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_legacy_service_window as legacy

TAG = "kjlee-qwen38-p1-qsa-canonical"
LABEL = "ai.kjlee.p1-qsa-canonical"
# Exact single-line change relative to the already built B image.
UNSORTED = b"    indices = torch.topk(safe, k=k, dim=1, sorted=False).indices\n"
CANONICAL = b"    indices = torch.topk(safe, k=k, dim=1, sorted=False).indices.sort(dim=1).values\n"


def tag(head: str) -> str:
    qsa.tag(head)
    return TAG + ":" + head[:12]


def canonical_transform(original: bytes) -> bytes:
    patched = qsa.transform(original)
    if patched.count(UNSORTED) != 1 or CANONICAL in patched:
        raise qsa.Blocked("CANONICAL_TOPK_ANCHOR_INVALID")
    result = patched.replace(UNSORTED, CANONICAL, 1)
    ast.parse(result.decode("utf-8"))
    if (result.count(CANONICAL) != 1 or
            result.count(b"torch.topk(safe") != 1 or
            result.count(b"torch.ops._C.persistent_topk") != 1):
        raise qsa.Blocked("CANONICAL_TOPK_SOURCE_DRIFT")
    return result


def dockerfile() -> str:
    return ("FROM " + legacy.IMAGE_TAG + "\n"
            "COPY --chown=0:0 --chmod=0644 qsa.py " + qsa.QSA + "\n"
            "ENV VLLM_QSA_EXACT_TOPK=1\n")


def labels(head: str, digest: str) -> dict[str, str]:
    return {
        LABEL: head,
        LABEL + ".base-id": legacy.IMAGE_ID,
        LABEL + ".source-qsa-sha256": qsa.SOURCE_SHA,
        LABEL + ".patched-qsa-sha256": digest,
        LABEL + ".variant": "exact-topk-index-sorted",
        LABEL + ".status": "cpu-build-not-gpu-tested",
    }


def check_image(child: dict, parent: dict, head: str, digest: str) -> None:
    roots = (child.get("RootFS") or {}).get("Layers")
    parent_roots = (parent.get("RootFS") or {}).get("Layers")
    if (not isinstance(roots, list) or not isinstance(parent_roots, list)
            or not parent_roots or len(roots) != len(parent_roots) + 1
            or roots[:len(parent_roots)] != parent_roots):
        raise qsa.Blocked("B2_IMAGE_LAYER_DRIFT")
    conf, base = child.get("Config") or {}, parent.get("Config") or {}
    if any((conf.get("Labels") or {}).get(k) != v
           for k, v in labels(head, digest).items()):
        raise qsa.Blocked("B2_IMAGE_LABEL_DRIFT")
    inherited_env = base.get("Env") or []
    expected_env = inherited_env + ["VLLM_QSA_EXACT_TOPK=1"]
    if ("VLLM_QSA_EXACT_TOPK=1" in inherited_env or
            sorted(conf.get("Env") or []) != sorted(expected_env)):
        raise qsa.Blocked("B2_EXACT_FLAG_OR_OTHER_ENV_DRIFT")
    for field in ("Entrypoint", "Cmd", "User", "WorkingDir"):
        if conf.get(field) != base.get(field):
            raise qsa.Blocked("B2_RUNTIME_DEFAULT_DRIFT")


def build(head: str) -> dict:
    receipt, original, base, state = release._legacy_state_for_release()
    if (state != "running" or original.get("Id") != receipt["id"]
            or base.get("Id") != legacy.IMAGE_ID):
        raise qsa.Blocked("B2_ORIGINAL_ID_OR_STATE_DRIFT")
    original_id = receipt["id"]
    patch = canonical_transform(qsa.read_qsa())
    patched_sha = hashlib.sha256(patch).hexdigest()
    name = tag(head)
    child = release._inspect_image(name)
    if child is None:
        with tempfile.TemporaryDirectory(prefix="p1-qsa-canonical-") as temp:
            folder = Path(temp)
            folder.chmod(0o700)
            dest = folder / "qsa.py"
            dest.write_bytes(patch)
            dest.chmod(0o600)
            (folder / "Dockerfile").write_text(dockerfile(), encoding="utf-8")
            args = ["docker", "build", "--network=none", "--pull=false",
                    "--no-cache", "--tag", name]
            for k, v in labels(head, patched_sha).items():
                args += ["--label", k + "=" + v]
            qsa.command(args + [str(folder)], timeout=900)
        child = release._inspect_image(name)
    if not isinstance(child, dict):
        raise qsa.Blocked("B2_IMAGE_NOT_FOUND")
    check_image(child, base, head, patched_sha)
    after = legacy.inspect("container", legacy.NAME)
    if (after.get("Id") != original_id
            or (after.get("State") or {}).get("Status") != "running"):
        raise qsa.Blocked("B2_ORIGINAL_SERVICE_CHANGED")
    return {
        "status": "B2_CANONICAL_QSA_CPU_BUILT_NOT_GPU_TESTED",
        "image": name, "image_id": child["Id"],
        "parent_image_id": legacy.IMAGE_ID,
        "original_same_id_running": True,
        "original_qsa_sha256": qsa.SOURCE_SHA,
        "patched_qsa_sha256": patched_sha,
        "source_difference_from_B": "sort-selected-topk-indices-by-index",
        "prefix": "original-OFF", "mtp": "original-2",
        "strict_numeric_verified": False,
        "p1_final_pass": False,
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
            OSError, ValueError, TypeError, KeyError, SyntaxError) as err:
        reason = str(err) if isinstance(err, qsa.Blocked) else type(err).__name__
        print("P1_B2_QSA_CANONICAL_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
