"""P2 offline numeric witness classifier CLI (no API/model access).

Input is a bounded, operator-supplied diagnostic JSON:
{ "runs": [ {"token_ids":[int], "finish_reason":"length",
              "logprobs":[float]}, ... ],
  "events": [ bounded candidate witness JSON objects, ... ],
  "provenance": { "prefix_off_verified":true,
                  "mtp_off_verified":true,
                  "single_active_request_verified":true } }
Never echo prompts, events, token IDs or raw logits.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.p2_numeric_boundary import classify_witness

MAX_JSON_BYTES = 2 * 1024 * 1024


def analyze_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("PAYLOAD_INVALID")
    runs = payload.get("runs")
    events = payload.get("events")
    provenance = payload.get("provenance")
    if (not isinstance(runs, list) or not isinstance(events, list)
            or not 2 <= len(runs) <= 8 or len(events) != len(runs)
            or not all(isinstance(x, dict) for x in runs + events)
            or not isinstance(provenance, dict)):
        raise ValueError("PAYLOAD_SHAPE_INVALID")
    allowed = ("prefix_off_verified", "mtp_off_verified",
               "single_active_request_verified")
    flags = {key: provenance.get(key) is True for key in allowed}
    result = classify_witness(runs, events, **flags)
    # Do not include raw payload in output. Never escalate to RELEASE_PASS.
    return {
        "status": "P2_NUMERIC_OFFLINE_WITNESS_ANALYSIS",
        "first_observed_difference": result["first_observed_difference"],
        "first_token_api_max_abs_delta": result["first_token_api_max_abs_delta"],
        "strict_api_failed": result["strict_api_failed"],
        "strict_abs_tolerance": result["strict_abs_tolerance"],
        "provenance_verified": result["boundary_provenance_verified"],
        "reason": result.get("reason"),
        "numeric_root_cause_fixed": False,
        "gpu_or_api_run_by_analyzer": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.input.is_symlink() or not args.input.is_file():
            raise ValueError("INPUT_NOT_REGULAR_FILE")
        if args.input.stat().st_size > MAX_JSON_BYTES:
            raise ValueError("INPUT_TOO_LARGE")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        output = analyze_payload(payload)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError):
        print("P2_NUMERIC_OFFLINE_INPUT_BLOCKED", file=sys.stderr)
        return 2
    print(json.dumps(output, sort_keys=True))
    return 0 if output["provenance_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
