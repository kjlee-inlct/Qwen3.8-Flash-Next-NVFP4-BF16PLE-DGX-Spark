"""One approved P1 GPU diagnostic window: pinned sampler-only image, automatic same-ID restore.

This is a runtime MUTATION, not a preflight: do not use --execute absent
explicit approval. No Prefix/QSA/PLE source modifications or image builds.
A candidate cleanup failure BLOCKS original restart to prevent two GPU owners.
The caller must not SIGKILL this program: SIGTERM/SIGINT/SIGHUP are handled.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from src import p1_integrated_runtime as integrated
from src import p1_legacy_service_window as legacy
from src import p1_numeric_sampler_overlay as overlay
from src import p1_original_numeric_baseline as baseline
from src import p1_prefix_gpu_oracle as oracle
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa

IMAGE_TAG = "kjlee-qwen38-p1-numeric-sampler:0e559c041a7c"
IMAGE_ID = "sha256:414372505f665f2f26a23bfc7b2d1082ff586e0082c4dab1d47ea9ed4202ecb7"
IMAGE_SOURCE_HEAD = "0e559c041a7c0f9f9861c5d93b858c82f83b1ad7"
PATCH_SHA = "14ecaf0ab79fb94604ce987bb6e74b4d64778f7e3ef76cd1e51064c87509c320"
NAME = "p1-numeric-sampler-window"
LABEL = "ai.kjlee.p1-numeric-window"
PORT = 18080
N_REQUESTS = 4
MAX_TOKENS = 1
STRICT_ABS = 1e-4


class Blocked(Exception):
    pass


def verify_image() -> None:
    parent = legacy.inspect("image", legacy.IMAGE_TAG)
    child = legacy.inspect("image", IMAGE_TAG)
    if parent.get("Id") != overlay.BASE_IMAGE_ID or child.get("Id") != IMAGE_ID:
        raise Blocked("IMAGE_ID_DRIFT")
    before = (parent.get("RootFS") or {}).get("Layers") or []
    after = (child.get("RootFS") or {}).get("Layers") or []
    if not before or len(after) != len(before) + 1 or after[:len(before)] != before:
        raise Blocked("IMAGE_ANCESTRY_DRIFT")
    bconf = parent.get("Config") or {}
    conf = child.get("Config") or {}
    for key in ("Entrypoint", "Cmd", "User", "WorkingDir"):
        if bconf.get(key) != conf.get(key):
            raise Blocked("IMAGE_CONFIG_DRIFT_" + key)
    benv = set(bconf.get("Env") or [])
    cenv = set(conf.get("Env") or [])
    if cenv - benv != {overlay.TAP_ENV + "=0"} or benv - cenv:
        raise Blocked("IMAGE_ENV_DRIFT")
    tags = conf.get("Labels") or {}
    if (tags.get("ai.kjlee.p1.numeric-source-head") != IMAGE_SOURCE_HEAD or
            tags.get("ai.kjlee.p1.numeric-sampler-sha256") != PATCH_SHA or
            tags.get("ai.kjlee.p1.numeric.parent-id") != overlay.BASE_IMAGE_ID):
        raise Blocked("IMAGE_PROVENANCE_DRIFT")


def candidate_ids() -> list[str]:
    data = release._run(["docker", "ps", "-aq", "--no-trunc",
                         "--filter", "name=^/" + NAME + "$"])
    ids = data.splitlines() if data else []
    if len(ids) > 1 or any(re.fullmatch(r"[a-f0-9]{64}", x) is None for x in ids):
        raise Blocked("CANDIDATE_ID_LIST_AMBIGUOUS")
    return ids


def owned(head: str, expected_id: str | None = None) -> dict:
    ci = legacy.inspect("container", NAME)
    tags = (ci.get("Config") or {}).get("Labels") or {}
    policy = ((ci.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name")
    if (ci.get("Name") != "/" + NAME or ci.get("Image") != IMAGE_ID
            or tags.get(LABEL) != head or policy not in ("no", "")):
        raise Blocked("CANDIDATE_OWNERSHIP_DRIFT")
    if expected_id is not None and ci.get("Id") != expected_id:
        raise Blocked("CANDIDATE_ID_DRIFT")
    return ci


def prepare(head: str, original_id: str) -> tuple[dict, dict, str, list[str]]:
    qsa.preflight(head)
    receipt, original, base, state = release._legacy_state_for_release()
    if (state != "running" or receipt["id"] != original_id
            or original.get("Id") != original_id
            or original.get("Image") != overlay.BASE_IMAGE_ID):
        raise Blocked("ORIGINAL_NOT_RUNNING_SAME_ID")
    # Validate exact MTP=2, Prefix OFF, sampling/model flags, without applying
    # candidate_cmd's Prefix-ON replacement to the actual candidate argv.
    config = original.get("Config") or {}
    original_cmd = config.get("Cmd")
    _unused_prefix_on_cmd, model = gpu.candidate_cmd(original_cmd)
    if ((config.get("Entrypoint") != (base.get("Config") or {}).get("Entrypoint"))
            or (original.get("HostConfig") or {}).get("IpcMode") != "host"):
        raise Blocked("ORIGINAL_LAUNCH_ABI_DRIFT")
    extra = gpu.environment_delta(config, base.get("Config") or {})
    if any(v.partition("=")[0] in (
            overlay.TAP_ENV, "VLLM_QSA_EXACT_TOPK", "VLLM_PLE_FAST_GATHER",
            "VLLM_PLE_PHASE_STATS") for v in extra):
        raise Blocked("EXPERIMENT_ENV_DRIFT")
    verify_image()
    integrated.no_other_candidates()
    if candidate_ids():
        raise Blocked("NUMERIC_CANDIDATE_ALREADY_EXISTS")
    runtime = (original.get("HostConfig") or {}).get("Runtime") or ""
    if runtime not in ("", "runc", "nvidia"):
        raise Blocked("ORIGINAL_RUNTIME_DRIFT")
    argv = ["docker", "create", "--pull=never", "--name", NAME,
            "--label", LABEL + "=" + head,
            "--network=bridge", "--publish", f"127.0.0.1:{PORT}:8000",
            "--gpus=all", "--ipc=host", "--memory=112g",
            "--memory-swap=112g", "--pids-limit=1024",
            "--restart=no", "--security-opt=no-new-privileges"]
    if runtime:
        argv.append("--runtime=" + runtime)
    if config.get("User"):
        argv += ["--user", config["User"]]
    if config.get("WorkingDir"):
        argv += ["--workdir", config["WorkingDir"]]
    for key, target in (("cache", "/recipe/hf-cache"),
                        ("views", "/recipe/recipe-views")):
        argv += ["--mount",
                 f"type=bind,src={receipt[key]},dst={target},readonly"]
    for item in extra:
        argv += ["--env", item]
    argv += ["--env", "HF_HUB_OFFLINE=1",
             "--env", "TRANSFORMERS_OFFLINE=1",
             "--env", "PYTHONDONTWRITEBYTECODE=1",
             "--env", overlay.TAP_ENV + "=1",
             IMAGE_TAG, *original_cmd]
    return receipt, original, model, argv


def verify_candidate(head: str, cid: str, receipt: dict,
                     original_cmd: list[str]) -> None:
    ci = owned(head, cid)
    if (ci.get("State") or {}).get("Status") != "created":
        raise Blocked("CANDIDATE_NOT_CREATED")
    conf = ci.get("Config") or {}
    if conf.get("Cmd") != original_cmd:
        raise Blocked("CANDIDATE_PREFIX_OR_MTP_DRIFT")
    env = conf.get("Env") or []
    if env.count(overlay.TAP_ENV + "=1") != 1 or overlay.TAP_ENV + "=0" in env:
        raise Blocked("CANDIDATE_TAP_NOT_ENABLED")
    mounts = ci.get("Mounts") or []
    expected = {(receipt["cache"], "/recipe/hf-cache"),
                (receipt["views"], "/recipe/recipe-views")}
    if (len(mounts) != 2 or
            {(m.get("Source"), m.get("Destination")) for m in mounts} != expected
            or any(m.get("Type") != "bind" or m.get("RW") is not False
                   for m in mounts)):
        raise Blocked("CANDIDATE_MOUNTS_DRIFT")
    binds = ((ci.get("HostConfig") or {}).get("PortBindings") or {}).get("8000/tcp")
    if binds != [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}]:
        raise Blocked("CANDIDATE_BIND_DRIFT")


def probe_logs(cid: str) -> list[dict]:
    # Never print raw Docker logs: potentially contain engine/debug data.
    try:
        cp = subprocess.run(["docker", "logs", "--tail", "1000", cid],
                            capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("CANDIDATE_LOGS_UNAVAILABLE") from None
    if cp.returncode != 0 or len(cp.stdout) + len(cp.stderr) > 2_000_000:
        raise Blocked("CANDIDATE_LOGS_UNAVAILABLE_OR_OVERSIZE")
    records = []
    for line in (cp.stdout + b"\n" + cp.stderr).decode("utf-8", errors="replace").splitlines():
        if "P1_NUMERIC_TAP " not in line:
            continue
        try:
            item = json.loads(line.split("P1_NUMERIC_TAP ", 1)[1])
        except (ValueError, TypeError):
            continue
        if isinstance(item, dict) and item.get("status") in (
                "BOUNDARY_CAPTURED", "SKIP_NOT_SINGLE_ROW_OR_SHAPE_DRIFT",
                "SKIP_NON_RAW_LOGPROBS_MODE"):
            records.append(item)
    return records


def analyse(runs: list[dict], taps: list[list[dict]]) -> dict:
    ids = [x.get("token_ids") for x in runs]
    values = [(x.get("logprobs") or [None])[0] for x in runs]
    valid = (len(runs) == N_REQUESTS and
             all(isinstance(t, list) and len(t) == 1 for t in ids) and
             all(t == ids[0] for t in ids) and
             all(type(x) in (float, int) and math.isfinite(x) for x in values))
    delta = max(abs(values[0] - x) for x in values[1:]) if valid else None
    complete = len(taps) == N_REQUESTS and all(
        len(group) == 1 and group[0].get("status") == "BOUNDARY_CAPTURED"
        and group[0].get("logprobs_mode") == "raw_logprobs"
        and group[0].get("sampler_raw_logprobs_not_overridden") is True
        and re.fullmatch(r"[a-f0-9]{64}", group[0].get("pre_sampling_logits_sha256", ""))
        and re.fullmatch(r"[a-f0-9]{64}", group[0].get("pre_gather_logprobs_sha256", ""))
        for group in taps)
    logit_same = (len({group[0]["pre_sampling_logits_sha256"] for group in taps}) == 1
                  if complete else None)
    logprob_same = (len({group[0]["pre_gather_logprobs_sha256"] for group in taps}) == 1
                    if complete else None)
    status = (
        "INCONCLUSIVE_API_OR_TOKEN_IDENTITY" if not valid else
        "INCONCLUSIVE_TAP_ABSENT_OR_MODE_OR_SHAPE" if not complete else
        "DIVERGENCE_INPUT_LOGITS" if not logit_same else
        "DIVERGENCE_LOGSOFTMAX_GIVEN_SAME_LOGITS" if not logprob_same else
        "SAME_SAMPLER_HASHES_API_DRIFT" if delta > STRICT_ABS else
        "SAMPLER_AND_API_WITHIN_STRICT_FOR_ONE_TOKEN"
    )
    return {
        "status": status, "probe_requests": len(runs),
        "tokens_each": [len(x.get("token_ids") or []) for x in runs],
        "all_same_token_ids": valid,
        "first_token_logprob_max_abs_delta": delta,
        "strict_abs_tolerance": STRICT_ABS,
        "tap_events_per_request": [len(x) for x in taps],
        "tap_statuses_per_request": [[z.get("status") for z in x] for x in taps],
        "pre_sampling_logits_identical_sha256": logit_same,
        "pre_gather_logprobs_identical_sha256": logprob_same,
        "final_p1_pass": False,
        "prefix_cache": "OFF", "mtp_draft_tokens": 2, "qsa": "stock",
        "diagnostic_only": True,
    }


def run_diagnostic(model: str, cid: str) -> dict:
    payload = oracle.build_payload(model, long_prompt=False)
    payload["max_tokens"] = MAX_TOKENS
    samples, taps = [], []
    previous = len(probe_logs(cid))
    for _ in range(N_REQUESTS):
        raw = oracle.request_json(PORT, payload)
        sample = oracle.extract(raw)
        if (not isinstance(sample.get("token_ids"), list)
                or len(sample["token_ids"]) != MAX_TOKENS):
            raise Blocked("API_TOKEN_COUNT_MISSING")
        samples.append(sample)
        events = probe_logs(cid)
        for _ in range(15):
            if len(events) > previous:
                break
            time.sleep(0.2)
            events = probe_logs(cid)
        taps.append(events[previous:])
        previous = len(events)
    return analyse(samples, taps)


def restore_original(head: str, original_id: str, model: str) -> None:
    release._run(["bash", str(qsa.ROOT / "scripts/start.sh"),
                  "--expected-head", head,
                  "--confirm-id", original_id, "--execute"], timeout=120)
    current = legacy.inspect("container", legacy.NAME)
    if (current.get("Id") != original_id or current.get("Image") != overlay.BASE_IMAGE_ID
            or (current.get("State") or {}).get("Running") is not True):
        raise Blocked("ORIGINAL_RESTORE_ID_OR_STATE_DRIFT")
    gpu.wait_ready(8000, model, timeout_s=900)


def cleanup(head: str) -> None:
    ids = candidate_ids()
    if not ids:
        return
    owned(head, ids[0])
    release._run(["docker", "rm", "--force", ids[0]], timeout=120)
    if candidate_ids():
        raise Blocked("CANDIDATE_CLEANUP_UNCONFIRMED")


def execute(head: str, original_id: str) -> dict:
    receipt, original, model, argv = prepare(head, original_id)
    # Catch the stop/start side effects even if a subprocess exits with an
    # error after changing Docker state.
    window_entered = False
    cleanup_confirmed = False
    diagnostic = None
    failure = None
    try:
        # Create first: if source/config/port cannot be staged, no downtime.
        release._run(argv, timeout=120)
        ci = owned(head)
        verify_candidate(head, ci["Id"], receipt, (original.get("Config") or {})["Cmd"])
        window_entered = True
        release._run(["bash", str(qsa.ROOT / "scripts/stop.sh"),
                      "--expected-head", head, "--confirm-id",
                      original_id, "--execute"], timeout=120)
        now = legacy.inspect("container", legacy.NAME)
        if (now.get("Id") != original_id
                or (now.get("State") or {}).get("Status") != "exited"):
            raise Blocked("ORIGINAL_STOP_UNCONFIRMED")
        if gpu.available_kib() < gpu.MIN_AFTER_STOP_KIB:
            raise Blocked("MEMAVAILABLE_BELOW_EXISTING_POLICY")
        release._run(["docker", "start", ci["Id"]], timeout=120)
        gpu.wait_ready(PORT, model, timeout_s=1200)
        diagnostic = run_diagnostic(model, ci["Id"])
        print(json.dumps(diagnostic, sort_keys=True), flush=True)
    except BaseException as exc:
        failure = (str(exc) if isinstance(exc, Blocked) else type(exc).__name__)
        print("P1_NUMERIC_GPU_DIAGNOSTIC_INTERRUPTED_OR_BLOCKED_" + failure,
              file=sys.stderr, flush=True)
    finally:
        # Do not restart the original while a possibly running candidate can
        # still own GPU memory. Only remove exactly the owned candidate.
        try:
            cleanup(head)
            cleanup_confirmed = True
        except BaseException:
            print("CRITICAL: CANDIDATE_CLEANUP_UNCONFIRMED_ORIGINAL_NOT_RESTARTED",
                  file=sys.stderr, flush=True)
        if cleanup_confirmed:
            try:
                orig = legacy.inspect("container", legacy.NAME)
                if orig.get("Id") != original_id:
                    raise Blocked("ORIGINAL_CONTAINER_ID_DRIFT")
                if (orig.get("State") or {}).get("Status") == "exited":
                    restore_original(head, original_id, model)
                else:
                    # Original can remain running if stop failed without side
                    # effect. Still require its health after candidate cleanup.
                    if (orig.get("State") or {}).get("Status") != "running":
                        raise Blocked("ORIGINAL_UNEXPECTED_STATE")
                    gpu.wait_ready(8000, model, timeout_s=900)
                print("P1_NUMERIC_ORIGINAL_SAME_ID_HTTP_RESTORED", flush=True)
            except BaseException:
                print("CRITICAL: ORIGINAL_HTTP_RESTORE_UNCONFIRMED",
                      file=sys.stderr, flush=True)
                cleanup_confirmed = False
    if not cleanup_confirmed:
        raise Blocked("RECOVERY_UNCONFIRMED")
    if failure is not None:
        raise Blocked("WINDOW_FAILED_ORIGINAL_RESTORED_" + failure)
    if diagnostic is None:
        raise Blocked("DIAGNOSTIC_MISSING")
    return diagnostic


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--confirm-original-id", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute-approved-window", action="store_true")
    args = p.parse_args(argv)
    try:
        if (os.geteuid() == 0 or
                not re.fullmatch(r"[a-f0-9]{40}", args.expected_head or "") or
                args.confirm_original_id != overlay.source_trace.ORIGINAL_ID):
            raise Blocked("EXACT_CONFIRMATION_OR_USER_REQUIRED")
        if args.preflight:
            receipt, original, model, _ = prepare(
                args.expected_head, args.confirm_original_id)
            print(json.dumps({
                "status": "P1_NUMERIC_GPU_PREFLIGHT_READY_NOT_EXECUTED",
                "original_id": receipt["id"], "candidate_image_id": IMAGE_ID,
                "original_state": original["State"]["Status"],
                "candidate_port": PORT,
                "model": model,
                "original_will_be_stopped": False,
            }, sort_keys=True))
            return 0
        result = execute(args.expected_head, args.confirm_original_id)
        return 0 if result["status"] not in (
            "INCONCLUSIVE_API_OR_TOKEN_IDENTITY",
            "INCONCLUSIVE_TAP_ABSENT_OR_MODE_OR_SHAPE") else 2
    except (Blocked, qsa.Blocked, release.ReleaseBlocked,
            legacy.Blocked, gpu.Blocked, oracle.OracleBlocked,
            OSError, ValueError, TypeError, KeyError):
        print("P1_NUMERIC_GPU_WINDOW_BLOCKED_OR_INCONCLUSIVE",
              file=sys.stderr, flush=True)
        return 2


def _on_signal(*_):
    raise Blocked("INTERRUPTED")


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _on_signal)
    raise SystemExit(main())
