"""Explicitly approved P1 single-GPU integration window with unconditional recovery.

This tool is NOT a scheduler and never runs until BOTH --execute and the
approval phrase are supplied. Ordinary invocation is safe and nonmutating.
On a service window it uses only the pinned same-ID stop/start controllers.
Every test runs BEFORE the window; actual API/Prefix and GPU remain untested.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from src import p1_integrated_api_check as api
from src import p1_integrated_runtime as runtime
from src import p1_prefix_gpu_oracle as oracle
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa

APPROVAL = "APPROVE_P1_EXCLUSIVE_GPU_SERVICE_INTERRUPTION"
ORIGINAL_ID_RE = re.compile(r"[a-f0-9]{64}\Z")


class WindowBlocked(Exception):
    """Do not include model content or Docker errors in failure messages."""


def assert_original_running(original_id: str) -> str:
    receipt, original, _, state = release._legacy_state_for_release()
    if (receipt["id"] != original_id or
            original.get("Id") != original_id or state != "running"):
        raise WindowBlocked("ORIGINAL_SAME_ID_NOT_RUNNING")
    _, model = gpu.candidate_cmd((original.get("Config") or {}).get("Cmd"))
    if not model:
        raise WindowBlocked("ORIGINAL_MODEL_UNKNOWN")
    return model


def safe_restore_after_window(head: str, original_id: str,
                              candidate_id: str | None,
                              model: str) -> dict:
    """Fail-closed recovery, including failed stop and failed launch paths.

    If a candidate was launched, only exact ownership-ID cleanup may precede
    restoring the original. When candidate identity is uncertain, do NOT
    start the original because both models could overlap on a single GPU.
    """
    if candidate_id is not None:
        report = runtime.restore(head, original_id, candidate_id)
        return {"status": "RESTORED_AFTER_CANDIDATE",
                "same_id_http_verified": report.get("original_id") == original_id}

    receipt, original, _, state = release._legacy_state_for_release()
    if receipt["id"] != original_id or original.get("Id") != original_id:
        raise WindowBlocked("RESTORE_ORIGINAL_ID_DRIFT")
    runtime.no_other_candidates()
    if state == "exited":
        runtime.restore_original(head, original_id, model)
        return {"status": "RESTORED_AFTER_STOP_OR_LAUNCH_FAILURE",
                "same_id_http_verified": True}
    if state == "running":
        # runtime.launch() may already have restored original on its own.
        gpu.wait_ready(8000, model, timeout_s=900)
        return {"status": "ORIGINAL_ALREADY_RUNNING_HTTP_VERIFIED",
                "same_id_http_verified": True}
    raise WindowBlocked("RESTORE_UNSAFE_ORIGINAL_STATE")


def execute_window(head: str, original_id: str) -> dict:
    """Require the original running; stop, launch, test, ALWAYS attempt restore."""
    if ORIGINAL_ID_RE.fullmatch(original_id) is None:
        raise WindowBlocked("ORIGINAL_ID_INVALID")
    plan = runtime.preflight(head)
    if plan.get("original_state") != "running" or plan.get("original_id") != original_id:
        raise WindowBlocked("PREFLIGHT_ORIGINAL_DRIFT")
    model = assert_original_running(original_id)
    # A bounded real request on the *original* is intentional only in an
    # approved maintenance window, before changing service availability.
    original_probe = oracle.probe_before_stop(model, port=8000)
    if original_probe.get("status") != "PASS_ORIGINAL_CHAT_PROTOCOL":
        raise WindowBlocked("ORIGINAL_PROTOCOL_PROBE_BLOCKED")

    candidate_id: str | None = None
    stop_attempted = False
    smoke_result: dict = {"status": "NOT_RUN"}
    oracle_result: dict = {"status": "NOT_RUN"}
    primary_error: str | None = None
    recovery: dict | None = None
    recovery_error = False

    try:
        # Mark before call: a failed/timeout stop can still leave original
        # exited, and MUST enter the guarded recovery path.
        stop_attempted = True
        release._run([
            "bash", str(qsa.ROOT / "scripts/stop.sh"),
            "--expected-head", head, "--confirm-id", original_id, "--execute",
        ], timeout=120)
        receipt, original, _, state = release._legacy_state_for_release()
        if receipt["id"] != original_id or state != "exited":
            raise WindowBlocked("STOP_IDENTITY_OR_STATE_UNCONFIRMED")
        launched = runtime.launch(head, original_id)
        candidate_id = launched.get("candidate_id")
        if not isinstance(candidate_id, str) or ORIGINAL_ID_RE.fullmatch(candidate_id) is None:
            raise WindowBlocked("LAUNCH_CANDIDATE_ID_NOT_CONFIRMED")
        # A probe failing is not an excuse to skip the other useful probe.
        try:
            smoke_result = api.api_smoke(head, candidate_id)
        except Exception:
            smoke_result = {"status": "API_SMOKE_EXCEPTION"}
        try:
            oracle_result = api.prefix_oracle(head, candidate_id)
        except Exception:
            oracle_result = {"status": "PREFIX_ORACLE_EXCEPTION",
                             "strict_numeric_pass": False}
    except BaseException as err:
        # No traceback, raw HTTP error or model text.
        primary_error = (str(err) if isinstance(err, WindowBlocked)
                         else type(err).__name__)
    finally:
        if stop_attempted:
            try:
                recovery = safe_restore_after_window(
                    head, original_id, candidate_id, model)
            except BaseException:
                recovery_error = True

    if recovery_error or not isinstance(recovery, dict) or (
            recovery.get("same_id_http_verified") is not True):
        raise WindowBlocked("ORIGINAL_RECOVERY_NOT_CONFIRMED_MANUAL_REVIEW_REQUIRED")

    success = (primary_error is None and
               smoke_result.get("status") == "API_SMOKE_PASS" and
               oracle_result.get("strict_numeric_pass") is True)
    return {
        "status": ("P1_INTEGRATED_GPU_SMOKE_AND_NUMERIC_PASS_NOT_FINAL_STATE_PROOF"
                   if success else "P1_INTEGRATED_GPU_VALIDATION_INCOMPLETE"),
        "original_protocol_precheck": "PASS",
        "gpu_window_primary_error": primary_error,
        "api": smoke_result,
        "prefix": oracle_result,
        "restore": recovery,
        "original_same_id_http_restored": True,
        "full_GDN_PLE_layer_reuse_verified": False,
        "p1_final_pass": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--confirm-original-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval", default="")
    args = parser.parse_args(argv)
    if not args.execute or args.approval != APPROVAL:
        print("P1_GPU_WINDOW_BLOCKED_EXPLICIT_APPROVAL_REQUIRED", file=sys.stderr)
        return 2
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        result = execute_window(args.expected_head, args.confirm_original_id)
        print(json.dumps(result, sort_keys=True))
        return 0 if (result["status"] ==
            "P1_INTEGRATED_GPU_SMOKE_AND_NUMERIC_PASS_NOT_FINAL_STATE_PROOF") else 2
    except (WindowBlocked, qsa.Blocked, release.ReleaseBlocked,
            runtime.legacy.Blocked, gpu.Blocked, oracle.OracleBlocked,
            OSError, TypeError, ValueError, KeyError):
        print("P1_GPU_WINDOW_BLOCKED_OR_INCOMPLETE_NO_FINAL_PASS",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
