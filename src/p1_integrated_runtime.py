"""P1 integrated GPU runtime: guarded service window, same-ID original recovery.

All actions fail closed. Preflight never mutates Docker/GPU. Launch requires
the original already exited through the separately approved stop.sh workflow.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from src import p1_prefix_release as release
from src import p1_prefix_gpu_window as gpu
from src import p1_legacy_service_window as legacy
from src import p1_preview_ple_integrated_image as integrated
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_preview_tool_qsa_image as tool

PIN_HEAD = "bf80867dc5be4fbae0a2f4c93b00363165b759d1"
PIN_IMAGE_ID = "sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d"
PIN_TAG = integrated.tag(PIN_HEAD)
NAME = "p1-integrated-release"
LABEL = "ai.kjlee.p1-integrated-runtime"
PORT = 18080


def verify_image() -> None:
    image = release._inspect_image(PIN_TAG)
    parent = release._inspect_image(tool.image_tag(integrated.PARENT_HEAD))
    if (not isinstance(image, dict) or image.get("Id") != PIN_IMAGE_ID
            or not isinstance(parent, dict)
            or parent.get("Id") != integrated.PARENT_IMAGE_ID):
        raise qsa.Blocked("PINNED_IMAGE_ID_DRIFT")
    integrated.check_child(image, parent, PIN_HEAD)
    qsa_image = release._inspect_image(qsa.tag(tool.QSA_HEAD))
    if not isinstance(qsa_image, dict) or qsa_image.get("Id") != tool.QSA_IMAGE_ID:
        raise qsa.Blocked("QSA_PARENT_ID_DRIFT")
    tool.verify_child(parent, qsa_image, {
        tool.LABEL: integrated.PARENT_HEAD,
        "ai.kjlee.p1-tool-qsa.parent-image": tool.QSA_IMAGE_ID,
    })
    prefix = release._release_image(qsa.PARENT_HEAD)
    qsa.check_child(qsa_image, prefix, tool.QSA_HEAD,
                    ((qsa_image.get("Config") or {}).get("Labels") or {}).get(
                        "ai.kjlee.p1-qsa.patched", ""))


def no_other_candidates() -> None:
    for name in (NAME, release.RELEASE_NAME, gpu.NAME):
        existing = release._run(
            ["docker", "ps", "-aq", "--no-trunc", "--filter", "name=^/" + name + "$"])
        if existing:
            raise qsa.Blocked("P1_CANDIDATE_CONTAINER_EXISTS")
    if gpu.candidate_ids():
        raise qsa.Blocked("P1_DEBUG_CANDIDATE_EXISTS")


def container_args(head: str, original: dict, base: dict,
                   receipt: dict) -> tuple[list[str], str]:
    cmd, model = gpu.candidate_cmd((original.get("Config") or {}).get("Cmd"))
    extra = gpu.environment_delta(original.get("Config") or {},
                                  base.get("Config") or {})
    if any(item.partition("=")[0] in (
            "VLLM_QSA_EXACT_TOPK", "VLLM_PLE_FAST_GATHER",
            "VLLM_PLE_PHASE_STATS") for item in extra):
        raise qsa.Blocked("EXPERIMENT_ENV_DRIFT")
    argv = [
        "docker", "create", "--name", NAME, "--pull=never",
        "--label", LABEL + "=" + head,
        "--network=bridge", f"--publish=127.0.0.1:{PORT}:8000",
        "--gpus=all", "--ipc=host",
        "--memory=112g", "--memory-swap=112g", "--pids-limit=1024",
        "--restart=no", "--security-opt=no-new-privileges",
    ]
    conf = original.get("Config") or {}
    runtime = (original.get("HostConfig") or {}).get("Runtime") or ""
    if runtime:
        argv += ["--runtime=" + runtime]
    if conf.get("User"):
        argv += ["--user", conf["User"]]
    if conf.get("WorkingDir"):
        argv += ["--workdir", conf["WorkingDir"]]
    for key, dest in (("cache", "/recipe/hf-cache"),
                      ("views", "/recipe/recipe-views")):
        argv += ["--mount", f"type=bind,src={receipt[key]},dst={dest},readonly"]
    for variable in extra:
        argv += ["--env", variable]
    argv += [
        "--env", "HF_HUB_OFFLINE=1", "--env", "TRANSFORMERS_OFFLINE=1",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "VLLM_PLE_PHASE_STATS=0",
        "--env", "VLLM_PLE_FAST_GATHER=0",
        PIN_TAG, *cmd,
    ]
    return argv, model


def owned(head: str) -> dict:
    ci = legacy.inspect("container", NAME)
    labels = (ci.get("Config") or {}).get("Labels") or {}
    restart = ((ci.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name")
    if (ci.get("Name") != "/" + NAME or ci.get("Image") != PIN_IMAGE_ID
            or labels.get(LABEL) != head or restart not in ("no", "")):
        raise qsa.Blocked("CANDIDATE_OWNERSHIP_MISMATCH")
    return ci


def preflight(head: str) -> dict:
    receipt, original, base, state = release._legacy_state_for_release()
    if original.get("Id") != receipt["id"] or state not in ("running", "exited"):
        raise qsa.Blocked("ORIGINAL_RECEIPT_OR_STATE_DRIFT")
    verify_image()
    no_other_candidates()
    argv, model = container_args(head, original, base, receipt)
    if PIN_TAG not in argv or not model:
        raise qsa.Blocked("CANDIDATE_CMD_INVALID")
    return {"status": "P1_INTEGRATED_PREFLIGHT_PASS_NO_GPU_NO_MUTATION",
            "image_id": PIN_IMAGE_ID, "original_id": receipt["id"],
            "original_state": state, "port": PORT, "mutated": False}


def cleanup(head: str, candidate_id: str) -> None:
    ci = owned(head)
    if ci.get("Id") != candidate_id:
        raise qsa.Blocked("CANDIDATE_CONFIRM_ID_MISMATCH")
    if (ci.get("State") or {}).get("Status") not in (
            "created", "exited", "running"):
        raise qsa.Blocked("CANDIDATE_STATE_INVALID")
    release._run(["docker", "rm", "--force", candidate_id], timeout=120)


def restore_original(head: str, original_id: str, model: str) -> None:
    release._run([
        "bash", str(qsa.ROOT / "scripts/start.sh"),
        "--expected-head", head, "--confirm-id", original_id, "--execute",
    ], timeout=120)
    ci = legacy.inspect("container", legacy.NAME)
    if ci.get("Id") != original_id or (ci.get("State") or {}).get("Status") != "running":
        raise qsa.Blocked("ORIGINAL_RESTORE_SAME_ID_UNCONFIRMED")
    gpu.wait_ready(8000, model, timeout_s=900)


def launch(head: str, original_id: str) -> dict:
    receipt, original, base, state = release._legacy_state_for_release()
    if original_id != receipt["id"]:
        raise qsa.Blocked("ORIGINAL_CONFIRM_ID_MISMATCH")
    if state != "exited":
        raise qsa.Blocked("ORIGINAL_MUST_ALREADY_BE_EXITED")
    verify_image()
    no_other_candidates()
    argv, model = container_args(head, original, base, receipt)
    created = False
    try:
        release._run(argv, timeout=90)
        created = True
        ci = owned(head)
        if (ci.get("State") or {}).get("Status") != "created":
            raise qsa.Blocked("CANDIDATE_NOT_CREATED")
        mounts = ci.get("Mounts") or []
        expected = {(receipt["cache"], "/recipe/hf-cache"),
                    (receipt["views"], "/recipe/recipe-views")}
        if (len(mounts) != 2 or
                any(m.get("Type") != "bind" or m.get("RW") is not False
                    for m in mounts) or
                {(m.get("Source"), m.get("Destination")) for m in mounts} != expected):
            raise qsa.Blocked("CANDIDATE_MOUNTS_DRIFT")
        release._run(["docker", "start", ci["Id"]], timeout=90)
        gpu.wait_ready(PORT, model, timeout_s=1200)
    except BaseException:
        if created:
            try:
                cleanup(head, owned(head)["Id"])
            except BaseException:
                raise qsa.Blocked("CANDIDATE_CLEANUP_UNCONFIRMED_ORIGINAL_EXITED") from None
        try:
            restore_original(head, receipt["id"], model)
        except BaseException:
            raise qsa.Blocked("ORIGINAL_RESTORE_UNCONFIRMED") from None
        raise qsa.Blocked("LAUNCH_FAILED_ORIGINAL_HTTP_RESTORED") from None
    return {"status": "P1_INTEGRATED_HTTP_READY_ORIGINAL_EXITED",
            "candidate_id": ci["Id"], "original_id": original_id, "port": PORT,
            "image_id": PIN_IMAGE_ID, "strict_numeric_verified": False}


def restore(head: str, original_id: str, candidate_id: str) -> dict:
    receipt, original, _, state = release._legacy_state_for_release()
    if original_id != receipt["id"] or state != "exited":
        raise qsa.Blocked("ORIGINAL_RECEIPT_OR_STATE_DRIFT")
    verify_image()
    _, model = gpu.candidate_cmd((original.get("Config") or {}).get("Cmd"))
    cleanup(head, candidate_id)
    restore_original(head, original_id, model)
    return {"status": "P1_INTEGRATED_REMOVED_ORIGINAL_SAME_ID_HTTP_RESTORED",
            "original_id": original_id}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    actions = p.add_mutually_exclusive_group(required=True)
    actions.add_argument("--preflight", action="store_true")
    actions.add_argument("--launch", action="store_true")
    actions.add_argument("--restore", action="store_true")
    p.add_argument("--confirm-original-id")
    p.add_argument("--confirm-candidate-id")
    args = p.parse_args()
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        if args.preflight:
            if args.confirm_original_id or args.confirm_candidate_id:
                raise qsa.Blocked("PREFLIGHT_NO_IDS")
            out = preflight(args.expected_head)
        elif args.launch:
            if not re.fullmatch("[0-9a-f]{64}", args.confirm_original_id or "") or args.confirm_candidate_id:
                raise qsa.Blocked("LAUNCH_EXACT_ORIGINAL_ID_REQUIRED")
            out = launch(args.expected_head, args.confirm_original_id)
        else:
            if (not re.fullmatch("[0-9a-f]{64}", args.confirm_original_id or "")
                    or not re.fullmatch("[0-9a-f]{64}", args.confirm_candidate_id or "")):
                raise qsa.Blocked("RESTORE_BOTH_EXACT_IDS_REQUIRED")
            out = restore(args.expected_head, args.confirm_original_id,
                          args.confirm_candidate_id)
        print(json.dumps(out, sort_keys=True))
        return 0
    except (qsa.Blocked, release.ReleaseBlocked, gpu.Blocked, legacy.Blocked,
            OSError, ValueError, TypeError, KeyError) as exc:
        print("P1_INTEGRATED_RUNTIME_BLOCKED_" + (
            str(exc) if isinstance(exc, qsa.Blocked) else type(exc).__name__),
            file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
