"""Original-service numeric reproducibility baseline, source-only harness.

Only explicitly invoked mode sends FOUR sequential synthetic Chat requests to
the existing loopback port 8000. It does not stop/restart/create containers,
edit files, load models, enable Prefix, or modify runtime parameters.

This baseline compares stock original Prefix-OFF + MTP2 + QSA default against
itself; it cannot prove cache-specific correctness or a QSA causal effect.
No model text, raw token strings, prompts, sensitive paths or logprob vectors
are emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

from src import p1_prefix_release as release
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_gpu_oracle as oracle
from src import p1_preview_qsa_exact_topk as qsa

N_REQUESTS = 4
PORT = 8000
STRICT_ABS = 1e-4
MIN_OUTPUT = 128


class Blocked(Exception):
    pass


def precheck() -> tuple[str, str]:
    """Verify pinned original ID, running status, Prefix OFF and MTP=2."""
    receipt, original, _, state = release._legacy_state_for_release()
    if state != "running" or original.get("Id") != receipt["id"]:
        raise Blocked("ORIGINAL_NOT_RUNNING_SAME_ID")
    cmd = (original.get("Config") or {}).get("Cmd")
    # candidate_cmd demands exact original --no-enable-prefix-caching,
    # MTP method=mtp num_speculative_tokens=2, GPU settings and model name.
    _, model = gpu.candidate_cmd(cmd)
    return model, receipt["id"]


def compare(runs: list[dict]) -> dict:
    """Only compare numeric logprobs when actual token identities match."""
    if len(runs) != N_REQUESTS:
        raise Blocked("REQUEST_COUNT_INVALID")
    first = runs[0]
    token_ids = first.get("token_ids")
    same_ids = (isinstance(token_ids, list) and bool(token_ids) and
                all(run.get("token_ids") == token_ids for run in runs))
    same_finish = all(run.get("finish_reason") == first.get("finish_reason")
                      for run in runs)
    lengths = [len(r.get("token_ids") or []) for r in runs]
    complete = (same_ids and all(
        len(run.get("logprobs") or []) == len(token_ids)
        and all(type(lp) in (int, float) and math.isfinite(lp)
                for lp in run["logprobs"])
        for run in runs))
    max_first = None
    max_all_pairs = None
    max_first_token = None
    exceed_positions = None
    if complete:
        values = [r["logprobs"] for r in runs]
        max_first = max(abs(a-b) for vec in values[1:]
                        for a,b in zip(values[0],vec))
        max_all_pairs = max(abs(a-b) for i in range(N_REQUESTS)
                            for j in range(i+1,N_REQUESTS)
                            for a,b in zip(values[i],values[j]))
        max_first_token = max(abs(values[0][0]-vec[0]) for vec in values[1:])
        exceed_positions = [
            i for i in range(len(token_ids))
            if any(abs(values[0][i]-vec[i]) > STRICT_ABS
                   for vec in values[1:])
        ][:16]
    enough = min(lengths) >= MIN_OUTPUT
    status = ("INCONCLUSIVE_TOKEN_IDS_DIFFER" if not same_ids else
              "INCONCLUSIVE_FINISH_REASON_DIFFER" if not same_finish else
              "INCONCLUSIVE_TOO_FEW_TOKENS" if not enough else
              "INCONCLUSIVE_LOGPROBS_INCOMPLETE" if not complete else
              "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT" if
              max_all_pairs > STRICT_ABS else
              "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT")
    # Do not call original baseline success a P1 acceptance result.
    return {
        "status": status,
        "original_prefix_caching": "OFF",
        "original_mtp_speculative_tokens": 2,
        "original_qsa": "stock",
        "request_count": N_REQUESTS,
        "tokens_each": lengths,
        "identical_token_ids": same_ids,
        "identical_finish_reasons": same_finish,
        "all_logprobs_available": complete,
        "reference_to_repeats_max_abs_delta": max_first,
        "all_pairs_max_abs_delta": max_all_pairs,
        "first_token_max_abs_delta": max_first_token,
        "strict_exceed_positions_0_based_first16": exceed_positions,
        "strict_abs_tolerance": STRICT_ABS,
        "original_reproducible_at_strict": (
            complete and enough and same_finish and max_all_pairs <= STRICT_ABS),
        "p1_candidate_numeric_pass": False,
        "full_state_reuse_verified": False,
        "p1_final_pass": False,
    }


def baseline(model: str, original_id: str) -> dict:
    payload = oracle.build_payload(model, long_prompt=True)
    results = []
    for _ in range(N_REQUESTS):
        result = oracle.extract(oracle.request_json(PORT, payload))
        oracle.validate_chat_output(result)
        results.append(result)
        # Abort promptly if the production instance ID or state changes.
        _, current_id = precheck()
        if current_id != original_id:
            raise Blocked("ORIGINAL_ID_CHANGED_DURING_PROBE")
    output = compare(results)
    safe_prompt = json.dumps(payload["messages"], ensure_ascii=True, sort_keys=True)
    output["synthetic_prompt_sha256"] = hashlib.sha256(safe_prompt.encode()).hexdigest()
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--probe-original", action="store_true", required=True)
    args = parser.parse_args()
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        model, original_id = precheck()
        report = baseline(model, original_id)
        print(json.dumps(report, sort_keys=True))
        # Exit zero for a completed measurement, even if numerical reproducibility
        # fails. The report status explicitly distinguishes that situation.
        return 0 if report["status"] in (
            "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
            "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT",
        ) else 2
    except (Blocked, qsa.Blocked, oracle.OracleBlocked,
            release.ReleaseBlocked, gpu.Blocked,
            OSError, ValueError, TypeError, KeyError):
        print("P1_ORIGINAL_NUMERIC_BASELINE_BLOCKED_OR_INCONCLUSIVE",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
