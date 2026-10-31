"""QSA-only B: pinned Prefix-OFF GPU candidate lifecycle and numeric oracle.

No action automatically stops production. --preflight is read-only; --launch
requires the original already EXITED in a separately approved maintenance
window. --numeric sends four synthetic GPU requests ONLY with explicit IDs.
Restore is independent of numeric success and verifies same-ID original HTTP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

from src import p1_legacy_service_window as legacy
from src import p1_prefix_release as release
from src import p1_prefix_gpu_window as gpu
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_qsa_isolation_image as image_builder
from src import p1_original_numeric_baseline as baseline
from src import p1_prefix_gpu_oracle as oracle

# Proven by the operator's 2026-10-31 CPU-only DGX build, not GPU execution.
PIN_BUILD_HEAD = "c3d31b7f3ab30d91e3562acb87555df19385c1db"
PIN_IMAGE_ID = "sha256:3d1c21c8fea3ed57dafad2f97c4cd8af1c3bce1f3cb22897cd87901b021b9fe7"
PIN_PATCH_SHA = "7cb6299c6b58dc051197d4a516c85a8d07552ecf81f29db21f900b8a44a2334f"
PIN_TAG = image_builder.tag(PIN_BUILD_HEAD)
NAME = "p1-qsa-only-candidate"
LABEL = "ai.kjlee.p1-qsa-only-runtime"
PORT = 18080
OTHER_NAMES = ("p1-integrated-release", release.RELEASE_NAME, gpu.NAME)


def original_command(cmd: list[str]) -> tuple[list[str], str]:
    """Validate exact MTP2/Prefix-OFF baseline without enabling Prefix."""
    _, model = gpu.candidate_cmd(cmd)  # validation only; returned Prefix-ON cmd discarded
    if cmd.count("--no-enable-prefix-caching") != 1 or "--enable-prefix-caching" in cmd:
        raise qsa.Blocked("QSA_ORIGINAL_PREFIX_NOT_OFF")
    return cmd.copy(), model


def verify_image() -> None:
    base = release._inspect_image(legacy.IMAGE_TAG)
    child = release._inspect_image(PIN_TAG)
    if (not isinstance(base, dict) or base.get("Id") != legacy.IMAGE_ID
            or not isinstance(child, dict) or child.get("Id") != PIN_IMAGE_ID):
        raise qsa.Blocked("QSA_IMAGE_ID_OR_PARENT_DRIFT")
    image_builder.check_image(child, base, PIN_BUILD_HEAD, PIN_PATCH_SHA)
    conf, original = child.get("Config") or {}, base.get("Config") or {}
    for key in ("Entrypoint", "Cmd", "User", "WorkingDir"):
        if conf.get(key) != original.get(key):
            raise qsa.Blocked("QSA_IMAGE_RUNTIME_DEFAULT_DRIFT")


def no_other_candidates() -> None:
    for name in (NAME, *OTHER_NAMES):
        out = release._run(["docker", "ps", "-aq", "--no-trunc",
                            "--filter", "name=^/" + name + "$"])
        if out:
            raise qsa.Blocked("OTHER_P1_CANDIDATE_EXISTS")
    if gpu.candidate_ids():
        raise qsa.Blocked("OTHER_P1_GPU_CANDIDATE_EXISTS")


def original_state(required: str | None = None) -> tuple[dict, dict, dict, str]:
    receipt, original, base, state = release._legacy_state_for_release()
    if original.get("Id") != receipt["id"] or state not in ("running", "exited"):
        raise qsa.Blocked("ORIGINAL_ID_OR_STATE_DRIFT")
    if required is not None and state != required:
        raise qsa.Blocked("ORIGINAL_MUST_BE_" + required.upper())
    return receipt, original, base, state


def container_args(head: str, original: dict, base: dict,
                   receipt: dict) -> tuple[list[str], str]:
    conf, base_conf = original.get("Config") or {}, base.get("Config") or {}
    if conf.get("Entrypoint") != base_conf.get("Entrypoint"):
        raise qsa.Blocked("ORIGINAL_ENTRYPOINT_DRIFT")
    cmd, model = original_command(conf.get("Cmd"))
    extra = gpu.environment_delta(conf, base_conf)
    if any(item.split("=", 1)[0] in (
            "VLLM_QSA_EXACT_TOPK", "VLLM_PLE_FAST_GATHER",
            "VLLM_PLE_PHASE_STATS") for item in extra):
        raise qsa.Blocked("QSA_UNREVIEWED_EXPERIMENT_ENV")
    hc = original.get("HostConfig") or {}
    if hc.get("IpcMode") != "host" or hc.get("Runtime") not in ("", "runc", "nvidia"):
        raise qsa.Blocked("ORIGINAL_HOST_RUNTIME_DRIFT")
    devices = hc.get("DeviceRequests") or []
    if (len(devices) != 1 or devices[0].get("Count") not in (-1, None)
            or devices[0].get("DeviceIDs")
            or not any("gpu" in cap for cap in devices[0].get("Capabilities", []))):
        raise qsa.Blocked("ORIGINAL_GPU_DEVICE_DRIFT")
    argv = [
        "docker", "create", "--name", NAME, "--pull=never",
        "--label", LABEL + "=" + head,
        "--label", LABEL + ".image-id=" + PIN_IMAGE_ID,
        "--network=bridge", f"--publish=127.0.0.1:{PORT}:8000",
        "--gpus=all", "--ipc=host", "--memory=112g", "--memory-swap=112g",
        "--pids-limit=1024", "--restart=no", "--security-opt=no-new-privileges",
    ]
    if hc.get("Runtime"):
        argv += ["--runtime=" + hc["Runtime"]]
    if conf.get("User"):
        argv += ["--user", conf["User"]]
    if conf.get("WorkingDir"):
        argv += ["--workdir", conf["WorkingDir"]]
    for key, dst in (("cache", "/recipe/hf-cache"),
                     ("views", "/recipe/recipe-views")):
        argv += ["--mount", f"type=bind,src={receipt[key]},dst={dst},readonly"]
    for value in extra:
        argv += ["--env", value]
    argv += ["--env", "HF_HUB_OFFLINE=1",
             "--env", "TRANSFORMERS_OFFLINE=1",
             "--env", "PYTHONDONTWRITEBYTECODE=1",
             PIN_TAG, *cmd]
    if argv.count("--no-enable-prefix-caching") != 1 or "--enable-prefix-caching" in argv:
        raise qsa.Blocked("QSA_ONLY_PREFIX_CMD_DRIFT")
    return argv, model


def owned(head: str) -> dict:
    ci = legacy.inspect("container", NAME)
    hc = ci.get("HostConfig") or {}
    labels = (ci.get("Config") or {}).get("Labels") or {}
    ports = (hc.get("PortBindings") or {}).get("8000/tcp")
    if (ci.get("Name") != "/" + NAME or ci.get("Image") != PIN_IMAGE_ID
            or labels.get(LABEL) != head
            or labels.get(LABEL + ".image-id") != PIN_IMAGE_ID
            or (hc.get("RestartPolicy") or {}).get("Name") not in ("", "no")
            or ports != [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}]):
        raise qsa.Blocked("QSA_CANDIDATE_OWNERSHIP_OR_PORT_DRIFT")
    return ci


def verify_mounts(ci: dict, receipt: dict) -> None:
    mounts = ci.get("Mounts") or []
    expected = {(receipt["cache"], "/recipe/hf-cache"),
                (receipt["views"], "/recipe/recipe-views")}
    if (len(mounts) != 2 or
            any(m.get("Type") != "bind" or m.get("RW") is not False
                for m in mounts) or
            {(m.get("Source"), m.get("Destination")) for m in mounts} != expected):
        raise qsa.Blocked("QSA_CANDIDATE_MOUNTS_DRIFT")


def candidate_ids() -> list[str]:
    out = release._run(["docker", "ps", "-aq", "--no-trunc",
                        "--filter", "name=^/" + NAME + "$"])
    ids = out.splitlines() if out else []
    if len(ids) > 1 or any(re.fullmatch("[0-9a-f]{64}", x) is None for x in ids):
        raise qsa.Blocked("QSA_CANDIDATE_IDS_AMBIGUOUS")
    return ids


def cleanup_owned(head: str, candidate_id: str, receipt: dict) -> None:
    ci = owned(head)
    if ci.get("Id") != candidate_id:
        raise qsa.Blocked("QSA_CANDIDATE_ID_DRIFT")
    verify_mounts(ci, receipt)
    if (ci.get("State") or {}).get("Status") not in ("created", "exited", "running"):
        raise qsa.Blocked("QSA_CANDIDATE_STATE_DRIFT")
    release._run(["docker", "rm", "--force", candidate_id], timeout=120)
    if candidate_ids():
        raise qsa.Blocked("QSA_CANDIDATE_CLEANUP_UNCONFIRMED")


def restore_original(head: str, original_id: str, model: str) -> None:
    release._run(["bash", str(qsa.ROOT / "scripts/start.sh"),
                  "--expected-head", head, "--confirm-id", original_id,
                  "--execute"], timeout=120)
    original_state("running")
    if legacy.inspect("container", legacy.NAME).get("Id") != original_id:
        raise qsa.Blocked("ORIGINAL_RESTORE_ID_DRIFT")
    gpu.wait_ready(8000, model, timeout_s=900)


def preflight(head: str) -> dict:
    receipt, original, base, state = original_state()
    verify_image()
    no_other_candidates()
    _, model = container_args(head, original, base, receipt)
    return {"status": "QSA_ONLY_PREFLIGHT_NO_GPU_NO_MUTATION",
            "original_id": receipt["id"], "original_state": state,
            "image_id": PIN_IMAGE_ID, "port": PORT, "model": model,
            "gpu_executed": False, "p1_final_pass": False}


def launch(head: str, original_id: str) -> dict:
    receipt, original, base, _ = original_state("exited")
    if receipt["id"] != original_id:
        raise qsa.Blocked("ORIGINAL_CONFIRM_ID_MISMATCH")
    verify_image()
    no_other_candidates()
    argv, model = container_args(head, original, base, receipt)
    try:
        original_state("exited")
        release._run(argv, timeout=90)
        ci = owned(head)
        if (ci.get("State") or {}).get("Status") != "created":
            raise qsa.Blocked("QSA_CANDIDATE_NOT_CREATED")
        verify_mounts(ci, receipt)
        original_state("exited")
        release._run(["docker", "start", ci["Id"]], timeout=90)
        gpu.wait_ready(PORT, model, timeout_s=1200)
    except BaseException:
        # A failed Docker create may have created the container anyway.
        # Ambiguous identity/mount/ownership forbids recovery while GPU
        # ownership is uncertain; never bring up two models.
        try:
            ids = candidate_ids()
            if ids:
                cleanup_owned(head, ids[0], receipt)
        except BaseException:
            raise qsa.Blocked("QSA_CLEANUP_UNCONFIRMED_ORIGINAL_EXITED") from None
        try:
            restore_original(head, original_id, model)
        except BaseException:
            raise qsa.Blocked("QSA_ORIGINAL_RESTORE_UNCONFIRMED") from None
        raise qsa.Blocked("QSA_LAUNCH_FAILED_ORIGINAL_SAME_ID_HTTP_RESTORED") from None
    return {"status": "QSA_ONLY_B_HTTP_READY_ORIGINAL_EXITED",
            "candidate_id": ci["Id"], "original_id": original_id,
            "image_id": PIN_IMAGE_ID, "port": PORT,
            "numeric_reproducibility_verified": False, "p1_final_pass": False}


def restore(head: str, original_id: str, candidate_id: str) -> dict:
    receipt, original, _, _ = original_state("exited")
    if receipt["id"] != original_id:
        raise qsa.Blocked("ORIGINAL_CONFIRM_ID_MISMATCH")
    _, model = original_command((original.get("Config") or {}).get("Cmd"))
    verify_image()
    cleanup_owned(head, candidate_id, receipt)
    restore_original(head, original_id, model)
    return {"status": "QSA_ONLY_B_REMOVED_ORIGINAL_SAME_ID_HTTP_RESTORED",
            "original_id": original_id, "p1_final_pass": False}


def numeric(head: str, original_id: str, candidate_id: str) -> dict:
    receipt, original, _, _ = original_state("exited")
    if original_id != receipt["id"]:
        raise qsa.Blocked("ORIGINAL_CONFIRM_ID_MISMATCH")
    verify_image()
    ci = owned(head)
    if ci.get("Id") != candidate_id or (ci.get("State") or {}).get("Status") != "running":
        raise qsa.Blocked("QSA_CANDIDATE_NOT_RUNNING_EXACT_ID")
    verify_mounts(ci, receipt)
    _, model = original_command((original.get("Config") or {}).get("Cmd"))
    payload = oracle.build_payload(model, long_prompt=True)
    runs = []
    for _ in range(baseline.N_REQUESTS):
        result = oracle.extract(oracle.request_json(PORT, payload))
        oracle.validate_chat_output(result)
        runs.append(result)
        original_state("exited")
        ci = owned(head)
        if ci.get("Id") != candidate_id or (ci.get("State") or {}).get("Status") != "running":
            raise qsa.Blocked("QSA_CANDIDATE_CHANGED_DURING_NUMERIC")
    report = baseline.compare(runs)
    source_status = report.pop("status")
    for key in ("original_prefix_caching", "original_mtp_speculative_tokens",
                "original_qsa", "original_reproducible_at_strict",
                "p1_candidate_numeric_pass"):
        report.pop(key, None)
    report.update({
        "status": source_status.replace("ORIGINAL_PREFIX_OFF", "QSA_ONLY_PREFIX_OFF"),
        "experiment": "B_QSA_EXACT_TOPK_ONLY",
        "prefix_caching": "OFF",
        "mtp_speculative_tokens": 2,
        "qsa": "exact-topk",
        "image_id": PIN_IMAGE_ID,
        "numeric_reproducible_at_strict": (
            source_status == "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT"),
        "synthetic_prompt_sha256": hashlib.sha256(
            json.dumps(payload["messages"], ensure_ascii=True,
                       sort_keys=True).encode()).hexdigest(),
        "p1_final_pass": False,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--preflight", action="store_true")
    actions.add_argument("--launch", action="store_true")
    actions.add_argument("--numeric", action="store_true")
    actions.add_argument("--restore", action="store_true")
    parser.add_argument("--confirm-original-id")
    parser.add_argument("--confirm-candidate-id")
    parser.add_argument("--confirm-image-id")
    args = parser.parse_args()
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        if args.preflight:
            if any((args.confirm_original_id, args.confirm_candidate_id,
                    args.confirm_image_id)):
                raise qsa.Blocked("QSA_PREFLIGHT_NO_CONFIRM_IDS")
            result = preflight(args.expected_head)
        else:
            if (args.confirm_image_id != PIN_IMAGE_ID or
                    re.fullmatch("[0-9a-f]{64}", args.confirm_original_id or "") is None):
                raise qsa.Blocked("QSA_EXACT_IMAGE_AND_ORIGINAL_IDS_REQUIRED")
            if args.launch:
                if args.confirm_candidate_id:
                    raise qsa.Blocked("QSA_LAUNCH_NO_CANDIDATE_ID")
                result = launch(args.expected_head, args.confirm_original_id)
            else:
                if re.fullmatch("[0-9a-f]{64}", args.confirm_candidate_id or "") is None:
                    raise qsa.Blocked("QSA_EXACT_CANDIDATE_ID_REQUIRED")
                result = (numeric if args.numeric else restore)(
                    args.expected_head, args.confirm_original_id,
                    args.confirm_candidate_id)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] not in (
            "INCONCLUSIVE_TOKEN_IDS_DIFFER", "INCONCLUSIVE_FINISH_REASON_DIFFER",
            "INCONCLUSIVE_TOO_FEW_TOKENS", "INCONCLUSIVE_LOGPROBS_INCOMPLETE"
        ) else 2
    except (qsa.Blocked, release.ReleaseBlocked, gpu.Blocked, legacy.Blocked,
            baseline.Blocked, oracle.OracleBlocked,
            OSError, ValueError, TypeError, KeyError) as exc:
        reason = str(exc) if isinstance(exc, qsa.Blocked) else type(exc).__name__
        print("P1_QSA_ONLY_RUNTIME_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
