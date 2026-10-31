"""P1 numeric diagnosis: QSA-only experimental image atop the ORIGINAL base.

This one-variable image uses the exact original Orcarouter BF16 PLE image,
Prefix OFF (preserved), MTP2 (preserved by future command), and only adds
the pinned Preview QSA exact-topk source + env switch. It is NOT the
existing Prefix-ON/Tool/Responses/PLE integrated image.

CPU-only build; no Docker run/exec, GPU, service stop/start or model load.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from src import p1_legacy_service_window as legacy
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa

TAG = "kjlee-qwen38-p1-qsa-isolation"
LABEL = "ai.kjlee.p1-qsa-isolation"
ORIGINAL_IMAGE_ID = legacy.IMAGE_ID


def tag(head: str) -> str:
    qsa.tag(head)
    return TAG + ":" + head[:12]


def dockerfile() -> str:
    return (
        "FROM " + legacy.IMAGE_TAG + "\n"
        "COPY --chown=0:0 --chmod=0644 qsa.py " + qsa.QSA + "\n"
        "ENV VLLM_QSA_EXACT_TOPK=1\n"
    )


def labels(head: str, patched_sha: str) -> dict[str, str]:
    return {
        LABEL: head,
        "ai.kjlee.p1-qsa-isolation.base-id": ORIGINAL_IMAGE_ID,
        "ai.kjlee.p1-qsa-isolation.original-qsa": qsa.SOURCE_SHA,
        "ai.kjlee.p1-qsa-isolation.patched-qsa": patched_sha,
        "ai.kjlee.p1-qsa-isolation.prefix": "original-OFF",
        "ai.kjlee.p1-qsa-isolation.mtp": "original-2",
        "ai.kjlee.p1-qsa-isolation.status": "cpu-build-not-gpu-tested",
    }


def check_image(image: dict, base: dict, head: str, patched_sha: str) -> None:
    roots = (image.get("RootFS") or {}).get("Layers")
    old = (base.get("RootFS") or {}).get("Layers")
    if (not isinstance(roots, list) or not isinstance(old, list)
            or not old or len(roots) != len(old) + 1 or roots[:len(old)] != old):
        raise qsa.Blocked("QSA_ISOLATION_ANCESTRY_DRIFT")
    config = image.get("Config") or {}
    actual = config.get("Labels") or {}
    if any(actual.get(key) != value for key, value in labels(head, patched_sha).items()):
        raise qsa.Blocked("QSA_ISOLATION_LABEL_DRIFT")
    env = config.get("Env") or []
    if env.count("VLLM_QSA_EXACT_TOPK=1") != 1:
        raise qsa.Blocked("QSA_ISOLATION_FLAG_DRIFT")
    if any(v.split("=", 1)[0] in ("VLLM_PLE_PHASE_STATS", "VLLM_PLE_FAST_GATHER")
           and v.endswith("=1") for v in env):
        raise qsa.Blocked("QSA_ISOLATION_UNEXPECTED_PLE_FLAGS")


def build(head: str) -> dict:
    receipt, original, base, state = release._legacy_state_for_release()
    if (state != "running" or original.get("Id") != receipt["id"]
            or not isinstance(base, dict) or base.get("Id") != ORIGINAL_IMAGE_ID):
        raise qsa.Blocked("QSA_ISOLATION_ORIGINAL_DRIFT")
    original_id = original["Id"]
    # Without this exact transform, the experiment is not one-variable.
    patched = qsa.transform(qsa.read_qsa())
    patched_sha = qsa.digest(patched)
    name = tag(head)
    child = release._inspect_image(name)
    if child is None:
        with tempfile.TemporaryDirectory(prefix="p1-qsa-isolation-") as temp:
            folder = Path(temp)
            folder.chmod(0o700)
            dest = folder / "qsa.py"
            with dest.open("xb") as target:
                target.write(patched)
            dest.chmod(0o600)
            (folder / "Dockerfile").write_text(dockerfile(), encoding="utf-8")
            cmd = ["docker", "build", "--network=none", "--pull=false",
                   "--no-cache", "--tag", name]
            for key, value in labels(head, patched_sha).items():
                cmd += ["--label", key + "=" + value]
            qsa.command(cmd + [str(folder)], timeout=900)
        child = release._inspect_image(name)
    if not isinstance(child, dict):
        raise qsa.Blocked("QSA_ISOLATION_IMAGE_MISSING")
    check_image(child, base, head, patched_sha)
    after = legacy.inspect("container", legacy.NAME)
    if (after.get("Id") != original_id or
            (after.get("State") or {}).get("Status") != "running"):
        raise qsa.Blocked("QSA_ISOLATION_ORIGINAL_CHANGED")
    return {
        "status": "QSA_ONLY_IMAGE_CPU_BUILT_NOT_GPU_TESTED",
        "image": name,
        "image_id": child["Id"],
        "original_image_id": ORIGINAL_IMAGE_ID,
        "original_same_id_running": True,
        "original_qsa_sha256": qsa.SOURCE_SHA,
        "patched_qsa_sha256": patched_sha,
        "qsa_exact_topk_enabled": True,
        "prefix": "original-OFF",
        "mtp": "original-2",
        "numeric_reproducibility_verified": False,
        "p1_final_pass": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--build", action="store_true", required=True)
    args = parser.parse_args()
    try:
        qsa.os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        print(json.dumps(build(args.expected_head), sort_keys=True))
        return 0
    except (qsa.Blocked, release.ReleaseBlocked, legacy.Blocked,
            OSError, ValueError, KeyError, TypeError) as err:
        reason = str(err) if isinstance(err, qsa.Blocked) else type(err).__name__
        print("P1_QSA_ISOLATION_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
