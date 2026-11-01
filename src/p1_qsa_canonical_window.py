"""Operator-approved B2 window, when separately authorized: A->B2 and restore.

A and B2 use exactly the same two synthetic payloads; 4 requests with
150+ output tokens (long) plus 4 single-token outputs (first-token).
The single-token route does not use baseline.compare's >=128 token contract.
Never load a candidate GPU without an explicit --execute and pinned IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import sys

from src import p1_qsa_canonical_runtime as b2
from src import p1_qsa_window_bundle as window
from src import p1_original_numeric_baseline as baseline
from src import p1_prefix_gpu_oracle as oracle
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_legacy_service_window as legacy

N = baseline.N_REQUESTS
STRICT = baseline.STRICT_ABS


class Blocked(Exception):
    pass


def collect_first(port: int, payload: dict, guard) -> list[dict]:
    if payload.get("max_tokens") != 1 or payload.get("seed") != 42:
        raise Blocked("FIRST_TOKEN_PAYLOAD_DRIFT")
    runs = []
    for _ in range(N):
        guard()
        item = oracle.extract(oracle.request_json(port, payload))
        guard()
        ids = item.get("token_ids")
        lp = item.get("logprobs")
        if (not isinstance(ids, list) or len(ids) != 1 or
                type(ids[0]) is not int or ids[0] < 0 or
                not isinstance(lp, list) or len(lp) != 1 or
                type(lp[0]) not in (int, float) or not math.isfinite(lp[0]) or
                item.get("finish_reason") not in ("stop", "length")):
            raise Blocked("SINGLE_TOKEN_ID_OR_LOGPROB_UNAVAILABLE")
        runs.append(item)
    return runs


def compare_first(runs: list[dict]) -> dict:
    if len(runs) != N:
        raise Blocked("FIRST_TOKEN_COUNT_INVALID")
    ids = [r["token_ids"][0] for r in runs]
    reasons = [r["finish_reason"] for r in runs]
    values = [r["logprobs"][0] for r in runs]
    same = len(set(ids)) == 1 and len(set(reasons)) == 1
    delta = (max(abs(values[i] - values[j])
                 for i in range(N) for j in range(i+1, N))
             if same else None)
    return {
        "status": ("SINGLE_TOKEN_NUMERIC_WITHIN_STRICT" if same and
                   delta is not None and delta <= STRICT else
                   "SINGLE_TOKEN_NUMERIC_ABOVE_STRICT" if same else
                   "SINGLE_TOKEN_ID_OR_FINISH_INCONCLUSIVE"),
        "request_count": N,
        "tokens_each": [1]*N,
        "identical_token_ids": len(set(ids)) == 1,
        "identical_finish_reasons": len(set(reasons)) == 1,
        "all_pairs_max_abs_delta": delta,
        "strict_abs_tolerance": STRICT,
        "strict_pass": same and delta is not None and delta <= STRICT,
    }


def cross_first(a: list[dict], other: list[dict]) -> dict:
    identical = all(
        x["token_ids"] == y["token_ids"] and
        x["finish_reason"] == y["finish_reason"]
        for x, y in zip(a, other))
    max_delta = (max(abs(x["logprobs"][0] - y["logprobs"][0])
                     for x, y in zip(a, other)) if identical else None)
    return {"same_request_index_token_ids_and_finish": identical,
            "max_abs_delta": max_delta,
            "causal_qsa_conclusion": "NOT_PROVEN"}


def restore_b2(head: str, original_id: str, model: str) -> None:
    # Re-evaluate actual Docker status; do not trust an in-memory launch ID.
    with window.recovery_signals():
        receipt, _, _, state = b2.original_state()
        ids = b2.candidate_ids()
        if ids:
            if state != "exited":
                raise Blocked("B2_AND_ORIGINAL_COEXIST_UNSAFE")
            b2.cleanup_owned(head, ids[0], receipt)
        if state == "exited":
            if b2.candidate_ids():
                raise Blocked("B2_CLEANUP_UNCONFIRMED")
            b2.restore_original(head, original_id, model)
        if b2.candidate_ids():
            raise Blocked("B2_REMAINS_AFTER_RESTORE")
        window.check_original_running(model, original_id)
        window.notify("B2_REMOVED_ORIGINAL_SAME_ID_HTTP_PASS")


def b2_guard(head: str, original_id: str, candidate_id: str) -> None:
    receipt, _, _, _ = b2.original_state("exited")
    if receipt["id"] != original_id:
        raise Blocked("ORIGINAL_FULL_ID_CHANGED_DURING_B2")
    ci = b2.owned(head)
    if (ci.get("Id") != candidate_id or
            (ci.get("State") or {}).get("Status") != "running"):
        raise Blocked("B2_CANDIDATE_ID_OR_STATE_DRIFT")
    b2.verify_mounts(ci, receipt)


def preflight(head: str) -> dict:
    report = b2.preflight(head)
    model, original_id = baseline.precheck()
    if original_id != window.ORIGINAL_ID or report["original_id"] != original_id:
        raise Blocked("ORIGINAL_PIN_MISMATCH")
    window.check_original_running(model, original_id)
    return {
        "status": "B2_WINDOW_PREFLIGHT_NO_GPU_NO_MUTATION",
        "original_id": original_id,
        "image_id": b2.PIN_IMAGE_ID,
        "image_source_build_head": b2.PIN_BUILD_HEAD,
        "model": model, "candidate_port": b2.PORT,
        "p1_final_pass": False,
    }


def execute(head: str, original_id: str) -> tuple[dict, bool]:
    preflight(head)
    model, check_id = baseline.precheck()
    if check_id != original_id or original_id != window.ORIGINAL_ID:
        raise Blocked("ORIGINAL_ID_DRIFT")
    long_payload = oracle.build_payload(model, long_prompt=True)
    first_payload = dict(long_payload)
    first_payload["max_tokens"] = 1
    safe_sha = hashlib.sha256(json.dumps(long_payload["messages"],
                     sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    window.notify("A_STOCK_LONG_4_STARTED")
    a_long = window.collect(8000, long_payload,
                            lambda: window.check_original_running_id_only(original_id))
    a_long_report = baseline.compare(a_long)
    if a_long_report["status"] not in (
            "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
            "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT"):
        raise Blocked("A_LONG_INCONCLUSIVE_DO_NOT_STOP")
    window.notify("A_STOCK_FIRST_TOKEN_4_STARTED")
    a_first = collect_first(8000, first_payload,
                  lambda: window.check_original_running_id_only(original_id))
    a_first_report = compare_first(a_first)
    if a_first_report["status"] == "SINGLE_TOKEN_ID_OR_FINISH_INCONCLUSIVE":
        raise Blocked("A_FIRST_INCONCLUSIVE_DO_NOT_STOP")
    window.check_original_running(model, original_id)
    window.notify("A_STOCK_COMPLETE",
                  long_max=a_long_report["all_pairs_max_abs_delta"],
                  first_max=a_first_report["all_pairs_max_abs_delta"])

    # All A measurements and identity checks are done before stopping service.
    window.notify("B2_CANONICAL_SERVICE_STOP_ATTEMPT")
    try:
        window.stop_original(head, original_id)
        launched = b2.launch(head, original_id)
        candidate_id = launched["candidate_id"]
        window.notify("B2_GPU_READY", candidate_id=candidate_id)
        b_long = window.collect(b2.PORT, long_payload,
                  lambda: b2_guard(head, original_id, candidate_id))
        b_first = collect_first(b2.PORT, first_payload,
                  lambda: b2_guard(head, original_id, candidate_id))
        long_report = window.summarize(a_long, b_long)
        # The existing A/B utility shares baseline compare semantics.
        long_report["status"] = long_report["status"].replace("AB_", "AB2_")
        long_report["B2"] = long_report.pop("B")
        long_report["B2"]["experiment"] = "B2_CANONICAL_INDEX_SORT"
        long_report["B2"]["image_id"] = b2.PIN_IMAGE_ID
        long_report["B2"]["qsa"] = "exact-topk-canonical-indices"
        result = {
            "status": "AB2_MEASURED",
            "long_150_token": long_report,
            "first_token": {
                "A_stock": a_first_report, "B2_canonical": compare_first(b_first),
                "A_vs_B2": cross_first(a_first, b_first),
            },
            "image_id": b2.PIN_IMAGE_ID,
            "synthetic_prompt_sha256": safe_sha,
            "strict_abs_tolerance": STRICT,
            "p1_final_pass": False,
        }
    finally:
        restore_b2(head, original_id, model)
    result["original_same_id_http_restored"] = True
    window.notify("AB2_NUMERIC_REPORT", report=result)
    good = (result["long_150_token"]["status"] == "AB2_MEASURED"
            and result["long_150_token"]["B2"]["numeric_reproducible_at_strict"] is True
            and result["first_token"]["B2_canonical"]["strict_pass"] is True)
    return result, good


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute", action="store_true")
    p.add_argument("--confirm-original-id")
    p.add_argument("--confirm-image-id")
    a = p.parse_args()
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(a.expected_head)
        if a.preflight:
            if a.confirm_original_id or a.confirm_image_id:
                raise Blocked("PREFLIGHT_REQUIRES_NO_CONFIRM_IDS")
            window.notify("B2_PREFLIGHT", report=preflight(a.expected_head))
            return 0
        if (a.confirm_original_id != window.ORIGINAL_ID
                or a.confirm_image_id != b2.PIN_IMAGE_ID):
            raise Blocked("EXACT_FULL_ORIGINAL_AND_IMAGE_IDS_REQUIRED")
        def terminate(_signum, _frame):
            raise Blocked("SIGTERM_RECOVERY_ATTEMPTED")
        signal.signal(signal.SIGTERM, terminate)
        result, good = execute(a.expected_head, a.confirm_original_id)
        window.notify("B2_WINDOW_COMPLETE_P1_FINAL_NOT_PROVEN",
                      b2_long_numeric_strict=good,
                      p1_final_pass=False)
        return 0 if good else 2
    except BaseException as exc:
        reason = str(exc) if isinstance(exc, (Blocked, qsa.Blocked)) else type(exc).__name__
        window.notify("B2_WINDOW_INCOMPLETE_CHECK_RESTORE_MARKER",
                      reason=reason, p1_final_pass=False)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
