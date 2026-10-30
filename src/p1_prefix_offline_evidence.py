"""Read-only offline P1 GPU oracle log review: numeric token offsets + per-hit SHA.

Never contacts Docker/HTTP, emits model tokens, modifies Stage or declares P1
PASS. The existing oracle JSON already contains per-token numeric deltas and
per-request bounded state-hash events, so a new GPU run is unnecessary.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import stat

from src.p1_prefix_gpu_oracle import compare_snapshot_windows

MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_TOKEN_DRIFTS = 4096
MAX_LINES = 50000
STRICT_TOL = 1e-4


class OfflineEvidenceBlocked(ValueError):
    pass


def parse_oracle_report(data: str) -> dict:
    """Scan logs with text prefixes; JSON is not necessarily at column 0."""
    if not isinstance(data, str) or len(data.encode("utf-8")) > MAX_LOG_BYTES:
        raise OfflineEvidenceBlocked("LOG_SIZE_INVALID")
    reports = []
    decoder = json.JSONDecoder()
    for line_no, line in enumerate(data.splitlines(), start=1):
        if line_no > MAX_LINES:
            raise OfflineEvidenceBlocked("LOG_TOO_MANY_LINES")
        if '"candidate_request_snapshot_windows"' not in line:
            continue
        # Try the opening of each object. The caller's printed terminal echo
        # may embed logs or include non-JSON prefix before the oracle object.
        starts = []
        for marker in ('{"active_candidate_abi"', '{"status"', '{'):
            p = line.find(marker)
            if p >= 0 and p not in starts:
                starts.append(p)
        for pos in starts:
            try:
                value, _ = decoder.raw_decode(line[pos:])
            except (json.JSONDecodeError, ValueError):
                continue
            if (isinstance(value, dict)
                    and "candidate_request_snapshot_windows" in value
                    and isinstance(value.get("status"), str)):
                reports.append(value)
                break
    if not reports:
        raise OfflineEvidenceBlocked("ORACLE_JSON_NOT_FOUND")
    return reports[-1]


def _valid_nonnegative(value: object) -> bool:
    return (type(value) in (float, int)
            and math.isfinite(value) and value >= 0)


def token_drift_summary(report: dict, *, strict: float = STRICT_TOL) -> dict:
    """Summarize existing per-token max(|Cold - HIT_i|) without token data."""
    values = report.get("per_token_cold_repeat_max_deltas")
    output = {
        "status": "INCONCLUSIVE_NO_PER_TOKEN_LOGPROB_EVIDENCE",
        "strict_abs_tolerance": strict,
        "all_token_ids_equal": report.get("all_repeats_token_ids_equal") is True,
        "strict_logprob_gate_passed": False,
    }
    if (not _valid_nonnegative(strict) or strict == 0
            or not isinstance(values, list) or not values
            or len(values) > MAX_TOKEN_DRIFTS
            or not all(_valid_nonnegative(x) for x in values)):
        return output
    indexed = sorted(enumerate(values, start=1),
                     key=lambda pair: (-pair[1], pair[0]))
    failing = [i for i, v in enumerate(values, start=1) if v > strict]
    output.update({
        "status": ("TOKEN_LOGPROB_DIFF_EXCEEDS_STRICT_GATE"
                   if failing else "TOKEN_LOGPROB_DIFF_WITHIN_STRICT_GATE"),
        "token_count": len(values),
        "over_tolerance_token_count": len(failing),
        "first_over_tolerance_token_index_1_based":
            failing[0] if failing else None,
        "max_abs_delta": indexed[0][1],
        "largest_token_positions_1_based": [
            {"token_position": i, "max_abs_delta": v,
             "over_strict_tolerance": v > strict}
            for i, v in indexed[:8]],
        "cold_to_repeat_max_deltas":
            report.get("cold_to_repeat_max_deltas"),
        "repeat_to_repeat_consecutive_max_deltas":
            report.get("repeat_to_repeat_consecutive_max_deltas"),
        "strict_logprob_gate_passed": (
            not failing and report.get("all_repeats_token_ids_equal") is True),
    })
    return output


def classify_numeric_control(report: dict, *, strict: float = STRICT_TOL) -> dict:
    """Triangulate Cold-vs-HIT using BOTH no-HIT numerical baselines.

    Control/control alone passing is insufficient. The original Cold run must
    also agree with the salted cold controls; neither result alone attributes
    a difference to prefix state. Never claims a causal fault or PASS.
    """
    output = {
        "status": "INCONCLUSIVE_CONTROL_TRIANGULATION",
        "strict_abs_tolerance": strict,
        "cold_reference_to_no_hit_controls_max_abs_delta": None,
        "no_hit_control_to_control_max_abs_delta": None,
        "cold_to_hit_max_abs_delta": None,
        "cache_specific_numeric_fault_proven": False,
        "strict_p1_gate_relaxed": False,
    }
    if not isinstance(report, dict):
        return output
    controls = report.get("same_input_cold_controls")
    if (not isinstance(controls, dict)
            or controls.get("status") !=
            "CONTROL_NO_PREFIX_HIT_OBSERVED_NUMERIC_PARITY_MEASURED"
            or controls.get("all_controls_no_prefix_hit_observed") is not True
            or controls.get("all_controls_token_ids_match_reference") is not True
            or controls.get("cold_reference_logprob_comparison_available") is not True):
        return output
    cold_ref = controls.get("cold_reference_to_control_max_abs_delta")
    ctrl_ctrl = controls.get("control_to_control_max_abs_delta")
    cold_hit = report.get("max_token_logprob_abs_delta")
    if (not _valid_nonnegative(strict) or strict == 0
            or not all(_valid_nonnegative(x)
                       for x in (cold_ref, ctrl_ctrl, cold_hit))):
        return output
    output.update({
        "cold_reference_to_no_hit_controls_max_abs_delta": cold_ref,
        "no_hit_control_to_control_max_abs_delta": ctrl_ctrl,
        "cold_to_hit_max_abs_delta": cold_hit,
    })
    if ctrl_ctrl > strict:
        output["status"] = "NO_HIT_CONTROL_REPRODUCIBILITY_EXCEEDS_STRICT"
    elif cold_ref > strict:
        output["status"] = "COLD_REFERENCE_TO_NO_HIT_CONTROL_EXCEEDS_STRICT"
    elif cold_hit > strict:
        output["status"] = "CACHE_PATH_ASSOCIATED_DRIFT_NOT_CAUSAL_PROOF"
    else:
        output["status"] = "MEASURED_NUMERIC_COMPARISONS_WITHIN_STRICT"
    return output


def analyze_report(report: dict) -> dict:
    """Keep original verdict separate from sampled-state and numeric evidence."""
    if not isinstance(report, dict):
        raise OfflineEvidenceBlocked("ORACLE_REPORT_INVALID")
    windows = report.get("candidate_request_snapshot_windows")
    hits = report.get("cache_hit_repeat_request_indices_1_based")
    comparison = compare_snapshot_windows(windows, hits)
    abi = report.get("active_candidate_abi")
    if not isinstance(abi, dict):
        abi = {}
    baseline = report.get("no_hit_strict_numeric_baseline")
    if not isinstance(baseline, dict):
        baseline = {}
    return {
        "status": "OFFLINE_EVIDENCE_REVIEW_NOT_P1_PASS",
        "original_oracle_status": report.get("status"),
        "cache_hit_request_indices_1_based": hits,
        "cache_hit_token_deltas_per_request":
            report.get("cache_hit_token_deltas_per_request"),
        "all_repeats_token_ids_equal":
            report.get("all_repeats_token_ids_equal") is True,
        "mtp_accepted_draft_token_counter_delta":
            report.get("mtp_accepted_draft_token_counter_delta"),
        "numeric": token_drift_summary(report),
        "numeric_control_triangulation": classify_numeric_control(report),
        "no_hit_control_status": baseline.get("status"),
        "no_hit_control_to_control_max_abs_delta":
            baseline.get("no_hit_control_to_control_max_abs_delta"),
        "sampled_state_cold_hit": comparison,
        "candidate_state_snapshot_event_count":
            abi.get("candidate_state_snapshot_event_count"),
        "candidate_state_snapshot_sample_count":
            abi.get("candidate_state_snapshot_sample_count"),
        "full_GDN_PLE_layer_reuse_verified": False,
        "p1_final_pass": False,
    }


def read_existing_log(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise OfflineEvidenceBlocked("LOG_FILE_MISSING_OR_SYMLINK")
    if (not stat.S_ISREG(path.stat().st_mode)
            or path.stat().st_size > MAX_LOG_BYTES):
        raise OfflineEvidenceBlocked("LOG_FILE_INVALID")
    return analyze_report(parse_oracle_report(
        path.read_text(encoding="utf-8", errors="replace")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = read_existing_log(args.log)
    except (OSError, OfflineEvidenceBlocked) as error:
        code = (str(error) if isinstance(error, OfflineEvidenceBlocked)
                else "LOG_IO_ERROR")
        print("P1_OFFLINE_EVIDENCE_BLOCKED_" + code)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("P1_OFFLINE_EVIDENCE_PARSED_READONLY_NO_GPU_NOT_P1_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
