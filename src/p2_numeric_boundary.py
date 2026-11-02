"""Offline first-token numeric-boundary triage for an isolated, no-MTP candidate.

Consumes only existing P1 Sampler.forward boundary digests and aligned API
logprobs. It NEVER starts a model or inspects Docker. Digests alone cannot
establish data provenance: explicit row-to-API verification is required.
"""
from __future__ import annotations

import math
import re

STRICT_ABS = 1e-4
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")


class InvalidEvidence(ValueError):
    pass


def _api_first_token(runs: list[dict]) -> tuple[float | None, str | None]:
    if len(runs) < 2:
        return None, "REQUEST_COUNT_INSUFFICIENT"
    first_ids = runs[0].get("token_ids")
    first_finish = runs[0].get("finish_reason")
    if (not isinstance(first_ids, list) or len(first_ids) != 1
            or type(first_ids[0]) is not int):
        return None, "FIRST_TOKEN_ONLY_REQUIRED"
    values = []
    for item in runs:
        ids = item.get("token_ids")
        probs = item.get("logprobs")
        if ids != first_ids or item.get("finish_reason") != first_finish:
            return None, "API_TOKEN_OR_FINISH_MISMATCH"
        if (not isinstance(probs, list) or len(probs) != 1
                or type(probs[0]) not in (int, float)
                or not math.isfinite(probs[0])):
            return None, "API_LOGPROBS_INVALID"
        values.append(float(probs[0]))
    return max(values) - min(values), None


def _valid_event(e: dict) -> bool:
    return (
        isinstance(e, dict)
        and e.get("status") == "BOUNDARY_CAPTURED"
        and e.get("logprobs_mode") == "raw_logprobs"
        and e.get("sampler_raw_logprobs_not_overridden") is True
        and e.get("shape") == [1, 248320]  # model vocab pinned to this P2 task
        and e.get("logits_dtype") in ("torch.float16", "torch.bfloat16", "torch.float32")
        and e.get("logprobs_dtype") in ("torch.float16", "torch.bfloat16", "torch.float32")
        and all(isinstance(e.get(k), str) and HEX_SHA.fullmatch(e[k])
                for k in ("pre_sampling_logits_sha256", "pre_gather_logprobs_sha256"))
    )


def classify(runs: list[dict], events: list[dict], *,
             prefix_off_verified: bool = False,
             mtp_off_verified: bool = False,
             single_active_request_verified: bool = False,
             row_api_alignment_verified: bool = False) -> dict:
    """Localize earliest *observed* differing boundary, not physical cause.

    One event per first-token-only API request. The alignment flag must come
    from independent runtime provenance, NEVER inferred from SHA equality.
    """
    delta, api_error = _api_first_token(runs)
    result = {
        "strict_abs_tolerance": STRICT_ABS,
        "first_token_api_max_abs_delta": delta,
        "strict_api_failed": delta > STRICT_ABS if delta is not None else None,
        "first_observed_difference": "INCONCLUSIVE",
        "boundary_provenance_verified": False,
        "root_cause_fixed": False,
        "gpu_or_api_executed_by_analyzer": False,
    }
    if api_error:
        result["reason"] = api_error
        return result
    if len(events) != len(runs) or not all(_valid_event(e) for e in events):
        result["reason"] = "MISSING_OR_INVALID_SAMPLER_BOUNDARY"
        return result
    if len({(e["shape"][1], e["logits_dtype"], e["logprobs_dtype"])
            for e in events}) != 1:
        result["reason"] = "BOUNDARY_DTYPE_OR_SHAPE_DRIFT"
        return result
    if not (prefix_off_verified and mtp_off_verified
            and single_active_request_verified and row_api_alignment_verified):
        result["reason"] = "ROW_TO_API_PROVENANCE_UNVERIFIED"
        return result
    result["boundary_provenance_verified"] = True
    if delta <= STRICT_ABS:
        result["first_observed_difference"] = "NO_STRICT_API_FAILURE_IN_SAMPLE"
        return result
    if len({e["pre_sampling_logits_sha256"] for e in events}) != 1:
        result["first_observed_difference"] = "RAW_LOGITS_OR_UPSTREAM"
    elif len({e["pre_gather_logprobs_sha256"] for e in events}) != 1:
        result["first_observed_difference"] = "LOGPROBS_COMPUTATION_OR_PRE_GATHER"
    else:
        result["first_observed_difference"] = "POST_SAMPLER_OR_API"
    return result
