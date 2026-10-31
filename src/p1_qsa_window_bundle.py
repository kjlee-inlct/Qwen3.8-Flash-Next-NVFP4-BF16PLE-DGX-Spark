"""Single approved maintenance-window workflow: A->B, optional integrated, recovery.

Operator-only GPU work: --execute + both full pinned IDs, no auto-approval.
Uses one four-request A arm and one four-request B arm with the SAME
synthetic payload, compares per-token within/among arms in memory, and
requires restoration/HTTP readiness before attempting optional integrated
Tool/Responses + Prefix/MTP checks. Never changes model assets or main.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import signal
import sys

from src import p1_legacy_service_window as legacy
from src import p1_prefix_release as release
from src import p1_prefix_gpu_window as gpu
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_original_numeric_baseline as baseline
from src import p1_qsa_only_runtime as b
from src import p1_integrated_runtime as integrated
from src import p1_integrated_api_check as api
from src import p1_prefix_gpu_oracle as oracle

ORIGINAL_ID = "3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45"


class Blocked(Exception):
    pass


@contextmanager
def recovery_signals():
    """Do not let repeated terminal SIGINT/SIGTERM skip owned cleanup."""
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


def notify(status: str, **facts: object) -> None:
    print(json.dumps({"stage": status, **facts}, sort_keys=True), flush=True)


def check_original_running(model: str, original_id: str) -> None:
    receipt, original, _, _ = b.original_state("running")
    if receipt["id"] != original_id or original.get("Id") != original_id:
        raise Blocked("ORIGINAL_ID_DRIFT")
    if b.candidate_ids() or integrated_candidate_ids():
        raise Blocked("CANDIDATE_EXISTS_WHILE_ORIGINAL_RUNNING")
    gpu.wait_ready(8000, model, timeout_s=120)


def integrated_candidate_ids() -> list[str]:
    out = release._run(["docker", "ps", "-aq", "--no-trunc",
                        "--filter", "name=^/" + integrated.NAME + "$"])
    ids = out.splitlines() if out else []
    if len(ids) > 1 or any(re.fullmatch("[0-9a-f]{64}", cid) is None for cid in ids):
        raise Blocked("INTEGRATED_CANDIDATE_ID_AMBIGUOUS")
    return ids


def collect(port: int, payload: dict, guard) -> list[dict]:
    runs = []
    for _ in range(baseline.N_REQUESTS):
        guard()
        response = oracle.extract(oracle.request_json(port, payload))
        oracle.validate_chat_output(response)
        guard()
        runs.append(response)
    return runs


def summarize(original: list[dict], candidate: list[dict]) -> dict:
    """Strict within-arm repeatability; cross-arm is diagnostic, not causality."""
    a = baseline.compare(original)
    raw_b = baseline.compare(candidate)
    b_report = dict(raw_b)
    b_report["status"] = raw_b["status"].replace(
        "ORIGINAL_PREFIX_OFF", "QSA_ONLY_PREFIX_OFF")
    for key in ("original_qsa", "original_prefix_caching",
                "original_mtp_speculative_tokens",
                "original_reproducible_at_strict", "p1_candidate_numeric_pass"):
        b_report.pop(key, None)
    b_report["numeric_reproducible_at_strict"] = (
        raw_b["status"] == "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT")
    b_report["experiment"] = "B_QSA_EXACT_TOPK_ONLY"
    b_report["prefix_caching"] = "OFF"
    b_report["mtp_speculative_tokens"] = 2
    b_report["qsa"] = "exact-topk"
    b_report["image_id"] = b.PIN_IMAGE_ID
    a_ok = a["status"] in ("ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
                           "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
    b_ok = raw_b["status"] in ("ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
                               "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
    equal_tokens = (a_ok and b_ok and
                    all(left["token_ids"] == right["token_ids"]
                        for left, right in zip(original, candidate)))
    equal_finish = (a_ok and b_ok and
                    all(left["finish_reason"] == right["finish_reason"]
                        for left, right in zip(original, candidate)))
    cross_max = None
    cross_exceed = None
    if equal_tokens and equal_finish:
        # Only meaningful for corresponding requests with identical tokens.
        lengths_match = all(
            len(left["logprobs"]) == len(right["logprobs"]) ==
            len(left["token_ids"])
            for left, right in zip(original, candidate))
        complete = lengths_match and all(
            type(x) in (int, float) and math.isfinite(x)
            for run in (*original, *candidate) for x in run["logprobs"])
        if complete:
            deltas = [
                [abs(x - y) for x, y in zip(left["logprobs"], right["logprobs"])]
                for left, right in zip(original, candidate)
            ]
            cross_max = max(max(row) for row in deltas)
            cross_exceed = [
                index for index in range(len(deltas[0]))
                if any(row[index] > baseline.STRICT_ABS for row in deltas)
            ][:16]
    return {
        "status": "AB_MEASURED" if a_ok and b_ok else "AB_INCONCLUSIVE",
        "A": a, "B": b_report,
        "cross_arm_same_index_token_ids": equal_tokens,
        "cross_arm_same_index_finish_reasons": equal_finish,
        "cross_arm_max_abs_logprob_delta": cross_max,
        "cross_arm_positions_above_strict_first16": cross_exceed,
        "strict_abs_tolerance": baseline.STRICT_ABS,
        "causal_qsa_conclusion": "NOT_PROVEN",
        "p1_final_pass": False,
    }


def restore_b(head: str, original_id: str, model: str) -> None:
    """Called even if create/start/numeric raises, including unknown candidate ID."""
    receipt, _, _, state = b.original_state()
    ids = b.candidate_ids()
    if ids:
        if state != "exited":
            raise Blocked("UNSAFE_B_AND_ORIGINAL_COEXIST")
        b.cleanup_owned(head, ids[0], receipt)  # ownership/image/mount verification
    if state == "exited":
        # Do not restore until label-owned candidate is confirmed absent.
        if b.candidate_ids():
            raise Blocked("B_CLEANUP_UNCONFIRMED")
        b.restore_original(head, original_id, model)
    check_original_running(model, original_id)
    notify("B_CLEANED_ORIGINAL_SAME_ID_HTTP_PASS")


def restore_integrated(head: str, original_id: str, model: str) -> None:
    receipt, _, _, state = b.original_state()
    ids = integrated_candidate_ids()
    if ids:
        if state != "exited":
            raise Blocked("UNSAFE_INTEGRATED_AND_ORIGINAL_COEXIST")
        owned = integrated.owned(head)
        if owned.get("Id") != ids[0]:
            raise Blocked("INTEGRATED_CANDIDATE_ID_DRIFT")
        integrated.cleanup(head, ids[0])  # label/image/id owned
    if state == "exited":
        if integrated_candidate_ids():
            raise Blocked("INTEGRATED_CLEANUP_UNCONFIRMED")
        integrated.restore_original(head, original_id, model)
    check_original_running(model, original_id)
    notify("INTEGRATED_CLEANED_ORIGINAL_SAME_ID_HTTP_PASS")


def stop_original(head: str, original_id: str) -> None:
    release._run(["bash", str(qsa.ROOT / "scripts/stop.sh"),
                  "--expected-head", head, "--confirm-id", original_id,
                  "--execute"], timeout=120)
    b.original_state("exited")


def b_guard(head: str, original_id: str, candidate_id: str) -> None:
    receipt, _, _, _ = b.original_state("exited")
    if receipt["id"] != original_id:
        raise Blocked("ORIGINAL_ID_DRIFT_DURING_B")
    ci = b.owned(head)
    if (ci.get("Id") != candidate_id or
            (ci.get("State") or {}).get("Status") != "running"):
        raise Blocked("B_CANDIDATE_ID_OR_STATE_DRIFT")
    b.verify_mounts(ci, receipt)


def run(head: str, original_id: str, *, include_integrated: bool) -> tuple[dict, bool]:
    qsa.preflight(head)
    if original_id != ORIGINAL_ID:
        raise Blocked("ORIGINAL_ID_NOT_OPERATOR_PIN")
    receipt, original, _, _ = b.original_state("running")
    if receipt["id"] != original_id or original.get("Id") != original_id:
        raise Blocked("ORIGINAL_ID_DRIFT")
    b.preflight(head)
    if include_integrated:
        integrated.preflight(head)  # read-only, before any maintenance stop
    model, _ = baseline.precheck()
    check_original_running(model, original_id)
    payload = oracle.build_payload(model, long_prompt=True)
    prompt_sha = hashlib.sha256(json.dumps(payload["messages"], ensure_ascii=True,
                                    sort_keys=True).encode()).hexdigest()
    notify("A_ORIGINAL_4_REQUESTS_STARTED")
    a_runs = collect(8000, payload,
                     lambda: check_original_running_id_only(original_id))
    a_report = baseline.compare(a_runs)
    notify("A_COMPLETED", measurement_status=a_report["status"],
           all_pairs_max_abs_delta=a_report["all_pairs_max_abs_delta"])
    if a_report["status"] not in (
            "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT",
            "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT"):
        raise Blocked("A_MEASUREMENT_INCONCLUSIVE_NO_SERVICE_STOP")
    check_original_running(model, original_id)

    notify("B_MAINTENANCE_STOP_ATTEMPT")
    try:
        stop_original(head, original_id)
        launched = b.launch(head, original_id)
        candidate_id = launched["candidate_id"]
        notify("B_GPU_READY", candidate_id=candidate_id)
        b_runs = collect(b.PORT, payload,
                         lambda: b_guard(head, original_id, candidate_id))
        report = summarize(a_runs, b_runs)
    finally:
        # Even if stop/launch/numeric raises, inspect actual Docker ownership.
        with recovery_signals():
            restore_b(head, original_id, model)
    report["synthetic_prompt_sha256"] = prompt_sha
    report["original_same_id_http_restored"] = True
    notify("AB_COMPARE_FINISHED", comparison=report)

    if not include_integrated or report["B"]["numeric_reproducible_at_strict"] is not True:
        report["integrated"] = {"status": "SKIPPED_B_NOT_STRICT_OR_DISABLED"}
        report["p1_final_pass"] = False
        return report, (report["status"] == "AB_MEASURED" and
                        report["B"]["numeric_reproducible_at_strict"] is True)

    notify("INTEGRATED_MAINTENANCE_STOP_ATTEMPT")
    try:
        stop_original(head, original_id)
        launch = integrated.launch(head, original_id)
        candidate_id = launch["candidate_id"]
        notify("INTEGRATED_GPU_READY", candidate_id=candidate_id)
        outcomes = {}
        # Continue the second check after a fail report, but never ignore
        # unknown container/identity exceptions.
        outcomes["api"] = api.api_smoke(head, candidate_id)
        outcomes["prefix"] = api.prefix_oracle(head, candidate_id)
        report["integrated"] = outcomes
    finally:
        with recovery_signals():
            restore_integrated(head, original_id, model)
    report["integrated"]["original_same_id_http_restored"] = True
    report["p1_final_pass"] = False  # full GDN/PLE GPU state still unproven
    notify("INTEGRATED_CHECKS_FINISHED", integrated=report["integrated"])
    good = (report["status"] == "AB_MEASURED"
            and report["integrated"]["api"].get("status") == "API_SMOKE_PASS"
            and report["integrated"]["prefix"].get("strict_numeric_pass") is True)
    return report, good


def check_original_running_id_only(original_id: str) -> None:
    receipt, ci, _, _ = b.original_state("running")
    if receipt["id"] != original_id or ci.get("Id") != original_id:
        raise Blocked("ORIGINAL_CHANGED_DURING_A")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--confirm-original-id", required=True)
    parser.add_argument("--confirm-b-image-id", required=True)
    parser.add_argument("--include-integrated-if-b-strict", action="store_true")
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    if args.confirm_b_image_id != b.PIN_IMAGE_ID:
        print("P1_BUNDLE_BLOCKED_B_IMAGE_ID_DRIFT", file=sys.stderr)
        return 2
    if not re.fullmatch("[0-9a-f]{64}", args.confirm_original_id):
        print("P1_BUNDLE_BLOCKED_FULL_ORIGINAL_ID_REQUIRED", file=sys.stderr)
        return 2
    try:
        # SIGTERM and keyboard interrupt unwind finally/restore clauses.
        def terminate(_signum, _frame):
            raise Blocked("SIGTERM_INTERRUPTED_RECOVERY_ATTEMPTED")
        signal.signal(signal.SIGTERM, terminate)
        os.chdir(qsa.ROOT)
        result, good = run(args.expected_head, args.confirm_original_id,
                           include_integrated=args.include_integrated_if_b_strict)
        notify("P1_BUNDLE_COMPLETE_P1_FINAL_NOT_PROVEN",
               strict_numeric_b=result["B"]["numeric_reproducible_at_strict"],
               integrated=result["integrated"].get("status", "CHECKED"),
               p1_final_pass=False)
        return 0 if good else 2
    except BaseException as exc:
        # The stage-specific finally already attempted strict ownership-
        # guarded restoration. Never claim recovery on this error path.
        reason = (str(exc) if isinstance(exc, (Blocked, qsa.Blocked))
                  else type(exc).__name__)
        notify("P1_BUNDLE_INCOMPLETE_CHECK_ORIGINAL_SAME_ID_AND_HTTP",
               reason=reason, p1_final_pass=False)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
