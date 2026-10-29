"""P1 isolated GPU prefix-cache oracle: fail closed without nonempty token and hit evidence.

No model content or user data is printed; only synthetic request hashes, token
counts, cache deltas, finish reasons and equality indicators are reported.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OracleBlocked(ValueError):
    """Sanitized reason code; never contains HTTP response body or model text."""


def request_json(port: int, payload: dict) -> dict:
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    req = Request(url, json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=180) as response:
            data = json.load(response)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        raise OracleBlocked("CHAT_HTTP_OR_JSON_UNAVAILABLE") from None
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or (
            len(data["choices"]) != 1):
        raise OracleBlocked("CHAT_RESPONSE_SHAPE")
    return data


def build_payload(model: str, *, long_prompt: bool) -> dict:
    base = ("Unit-test reference: a fictional hardware monitor reads a "
            "register holding a stable state. This sentence is fixed. ")
    message = (base * (450 if long_prompt else 1))
    message += ("\nFinal question: Output the integers from 1 through 40, "
                "in ascending order, separated by comma and space, with no explanation."
                if long_prompt else
                "\nFinal question: What is seven plus five? Answer with the number 12.")
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Respond with a short factual answer."},
            {"role": "user", "content": message}],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 256 if long_prompt else 96,
        "logprobs": True,
        "top_logprobs": 1,
        "return_token_ids": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def extract(response: dict) -> dict:
    choice = response["choices"][0]
    message = choice.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise OracleBlocked("CHAT_CONTENT_NOT_STRING")
    lp = (choice.get("logprobs") or {}).get("content")
    tokens = []
    probs = []
    if isinstance(lp, list):
        for item in lp:
            if not isinstance(item, dict) or not isinstance(item.get("token"), str):
                raise OracleBlocked("CHAT_LOGPROBS_MALFORMED")
            tokens.append(item["token"])
            value = item.get("logprob")
            probs.append(value if isinstance(value, (int, float)) and math.isfinite(value)
                         else None)
    token_ids = choice.get("token_ids")
    if token_ids is not None and (
            not isinstance(token_ids, list) or
            not all(type(v) is int and v >= 0 for v in token_ids)):
        raise OracleBlocked("CHAT_TOKEN_IDS_MALFORMED")
    usage = response.get("usage") or {}
    cached = ((usage.get("prompt_tokens_details") or {}).get("cached_tokens"))
    if cached is not None and (type(cached) is not int or cached < 0):
        cached = None
    return {
        "content": content,
        "token_ids": token_ids,
        "tokens": tokens,
        "logprobs": probs,
        "finish_reason": choice.get("finish_reason"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "cached_prompt_tokens": cached,
    }


def validate_chat_output(result: dict) -> None:
    if not result["content"].strip():
        raise OracleBlocked("CHAT_EMPTY_FINAL_CONTENT")
    if not result["tokens"] or not result["logprobs"] or result["logprobs"][0] is None:
        raise OracleBlocked("CHAT_TOKEN_LOGPROBS_MISSING")
    if result["token_ids"] is None:
        raise OracleBlocked("CHAT_TOKEN_IDS_UNAVAILABLE")
    if len(result["token_ids"]) != len(result["tokens"]):
        raise OracleBlocked("CHAT_TOKEN_IDS_COUNT_MISMATCH")
    if result["finish_reason"] not in ("stop", "length"):
        raise OracleBlocked("CHAT_FINISH_REASON_UNEXPECTED")


def probe_before_stop(model: str, port: int = 8000) -> dict:
    """Validate protocol on original *running* service before any stop/patch."""
    response = extract(request_json(port, build_payload(model, long_prompt=False)))
    validate_chat_output(response)
    return {"status": "PASS_ORIGINAL_CHAT_PROTOCOL",
            "content_nonempty": True,
            "logprob_tokens": len(response["tokens"]),
            "finish_reason": response["finish_reason"],
            "token_ids_returned": response["token_ids"] is not None}


def metrics(port: int) -> dict[str, float]:
    try:
        with urlopen(f"http://127.0.0.1:{port}/metrics", timeout=15) as response:
            body = response.read(4_000_000).decode("utf-8")
    except (HTTPError, URLError, OSError, TimeoutError, UnicodeError):
        raise OracleBlocked("PREFIX_METRICS_UNAVAILABLE") from None
    result = {}
    for line in body.splitlines():
        if line.startswith("#") or not any(
                tag in line for tag in ("prefix_cache", "spec_decode")):
            continue
        match = re.fullmatch(r'([\w:]+)(\{[^}]*\})?\s+([0-9.eE+-]+)(?:\s+.*)?', line)
        if not match:
            continue
        name, labels, number = match.groups()
        if labels and 'cache_type="cpu"' in labels:
            continue
        value = float(number)
        if math.isfinite(value):
            result[name + (labels or "")] = value
    return result


def counter_delta(before: dict, after: dict, suffix: str) -> float:
    return sum(max(0.0, value - before.get(key, 0.0))
               for key, value in after.items()
               if key.split("{", 1)[0] == "vllm:" + suffix)


def settled_metrics(port: int, before: dict, *, require_queries: bool,
                    timeout_s: float = 12.0, interval_s: float = 1.0) -> dict:
    """Allow delayed vLLM stats flush; never treat *_created as hit counters."""
    deadline = time.monotonic() + timeout_s
    latest = metrics(port)
    while require_queries and counter_delta(before, latest, "prefix_cache_queries_total") <= 0:
        if time.monotonic() >= deadline:
            break
        time.sleep(interval_s)
        latest = metrics(port)
    return latest


def logprob_diagnostics(runs: list[dict]) -> dict:
    """Report absolute per-request numeric drift, never lowering strict gate.

    Separating cold-to-cache from repeat-to-repeat distinguishes one-time
    cache-path shifts from nondeterminism across already-cached requests.
    No token strings or logits are emitted.
    """
    vectors = [r["logprobs"] for r in runs]
    length = len(runs[0]["token_ids"])
    if not all(len(v) == length and
               all(isinstance(x, (float, int)) and math.isfinite(x)
                   for x in v) for v in vectors):
        return {"logprob_diagnostic_complete": False,
                "cold_to_repeat_max_deltas": None,
                "repeat_to_repeat_consecutive_max_deltas": None,
                "per_token_cold_repeat_max_deltas": None}
    def max_diff(a: list, b: list) -> float:
        return max(abs(x - y) for x, y in zip(a, b))
    return {
        "logprob_diagnostic_complete": True,
        "cold_to_repeat_max_deltas": [
            max_diff(vectors[0], v) for v in vectors[1:]],
        "repeat_to_repeat_consecutive_max_deltas": [
            max_diff(vectors[i], vectors[i + 1])
            for i in range(1, len(vectors) - 1)],
        "per_token_cold_repeat_max_deltas": [
            max(abs(v[i] - vectors[0][i]) for v in vectors[1:])
            for i in range(length)],
    }



def cold_control_diagnostics(model: str, port: int, payload: dict,
                             reference: dict) -> dict:
    """Two extra same-token-input cold controls in the *candidate* window.

    Unique per-request cache salts should isolate prefix reuse if supported
    by the pinned Preview. Never assume salt support: actual no-hit metrics
    are required. An unsupported API, malformed response, token divergence or
    missing metrics is explicitly inconclusive. This is a diagnostic only:
    strict 1e-4 acceptance is NOT relaxed or bypassed.
    """
    before = metrics(port)
    samples = []
    query_deltas = []
    hit_deltas = []
    for _ in range(2):
        salted = dict(payload)
        salted["cache_salt"] = secrets.token_urlsafe(32)
        try:
            sample = extract(request_json(port, salted))
            validate_chat_output(sample)
            after = settled_metrics(port, before, require_queries=True)
        except OracleBlocked:
            return {"status": "UNAVAILABLE_API_OR_METRICS",
                    "completed_controls": len(samples),
                    "cold_reference_logprob_comparison_available": False}
        query_deltas.append(counter_delta(before, after, "prefix_cache_queries_total"))
        hit_deltas.append(counter_delta(before, after, "prefix_cache_hits_total"))
        samples.append(sample)
        before = after

    output = {
        "status": "INCONCLUSIVE",
        "completed_controls": len(samples),
        "cache_query_deltas": query_deltas,
        "cache_hit_deltas": hit_deltas,
        "all_controls_no_prefix_hit_observed": False,
        "all_controls_token_ids_match_reference": False,
        "cold_reference_logprob_comparison_available": False,
        "cold_reference_to_control_max_abs_delta": None,
        "control_to_control_max_abs_delta": None,
        "strict_abs_tolerance_unchanged": 1e-4,
    }
    if not all(q > 0 and hit == 0 for q, hit in zip(query_deltas, hit_deltas)):
        output["status"] = "INCONCLUSIVE_CONTROLS_NOT_VERIFIED_COLD"
        return output
    output["all_controls_no_prefix_hit_observed"] = True
    if not all(s["token_ids"] == reference["token_ids"] for s in samples):
        output["status"] = "INCONCLUSIVE_CONTROL_TOKEN_IDS_DIFFER"
        return output
    output["all_controls_token_ids_match_reference"] = True
    vectors = [reference["logprobs"], *[s["logprobs"] for s in samples]]
    length = len(reference["token_ids"])
    if not length or not all(
        len(v) == length and all(
            isinstance(x, (float, int)) and math.isfinite(x) for x in v)
        for v in vectors
    ):
        output["status"] = "INCONCLUSIVE_CONTROL_LOGPROBS_MISSING"
        return output
    output["cold_reference_logprob_comparison_available"] = True
    output["cold_reference_to_control_max_abs_delta"] = max(
        abs(x - y) for v in vectors[1:]
        for x, y in zip(vectors[0], v))
    output["control_to_control_max_abs_delta"] = max(
        abs(x - y) for x, y in zip(vectors[1], vectors[2]))
    output["status"] = "CONTROL_NO_PREFIX_HIT_OBSERVED_NUMERIC_PARITY_MEASURED"
    return output


def run_oracle(model: str, port: int, *, min_output_tokens: int = 0,
               enable_cold_controls: bool = False) -> dict:
    """Cold + three strictly serialized repeats, one candidate GPU boot.

    MTP/EAGLE hybrid caches may miss the *first* repeated request and start
    hitting only on a later repeat. The 450x synthetic prefix is deliberately
    longer than the previous 2142-token oracle; no physical Mamba block size
    is assumed. Do not claim full P1 correctness without active Mamba ABI.
    """
    payload = build_payload(model, long_prompt=True)
    prompt_repr = json.dumps(payload["messages"], ensure_ascii=True, sort_keys=True)
    initial = metrics(port)
    observations = []
    last = initial
    for index in range(4):
        result = extract(request_json(port, payload))
        # A malformed result cannot be treated as a cache-correctness PASS.
        validate_chat_output(result)
        after = settled_metrics(port, last, require_queries=True)
        query_delta = counter_delta(last, after, "prefix_cache_queries_total")
        hit_delta = counter_delta(last, after, "prefix_cache_hits_total")
        cached = result["cached_prompt_tokens"]
        observations.append({
            "response": result,
            "query_delta": query_delta,
            "hit_delta": hit_delta,
            "cached_prompt_tokens": cached,
        })
        last = after

    cold = observations[0]["response"]
    repetitions = [o["response"] for o in observations[1:]]
    same_text = all(r["content"] == cold["content"] for r in repetitions)
    same_tokens = all(r["token_ids"] == cold["token_ids"] for r in repetitions)
    same_finishes = all(r["finish_reason"] == cold["finish_reason"]
                        for r in repetitions)
    token_lps = [cold["logprobs"], *[r["logprobs"] for r in repetitions]]
    lp_complete = all(len(lp) == len(cold["token_ids"]) and
                      all(v is not None for v in lp) for lp in token_lps)
    numeric_drift = logprob_diagnostics([cold, *repetitions])
    max_lp_delta = None
    first_lp_delta_max = None
    if lp_complete:
        max_lp_delta = max(abs(a - b)
                           for lp in token_lps[1:]
                           for a, b in zip(cold["logprobs"], lp))
        first_lp_delta_max = max(abs(cold["logprobs"][0] - lp[0])
                                 for lp in token_lps[1:])
    query_deltas = [o["query_delta"] for o in observations]
    hit_deltas = [o["hit_delta"] for o in observations]
    repeat_hits = [
        o["hit_delta"] > 0 or
        (o["cached_prompt_tokens"] is not None and o["cached_prompt_tokens"] > 0)
        for o in observations[1:]
    ]
    hit_indices = [i + 2 for i, hit in enumerate(repeat_hits) if hit]
    # Strict live acceptance evidence requires actual accepted draft tokens,
    # not merely the configured MTP=2 flag or a speculative metric name.
    accepted_counter = "vllm:spec_decode_num_accepted_tokens_total"
    accepted_delta = sum(
        max(0.0, val - initial.get(key, 0.0))
        for key, val in last.items()
        if key.split("{", 1)[0] == accepted_counter)
    observed_spec_metric_names = sorted({
        key.split("{", 1)[0] for key in last if "spec_decode" in key
    })
    long_enough = all(
        len(r["token_ids"]) >= min_output_tokens
        for r in [cold, *repetitions])
    if not same_text or not same_tokens or not same_finishes:
        status = "FAIL_NONIDENTICAL_OUTPUT_OR_FINISH"
    elif not any(repeat_hits):
        if sum(query_deltas[1:]) > 0:
            status = "FAIL_ALL_REPEATS_PREFIX_CACHE_MISS"
        else:
            status = "INCONCLUSIVE_PREFIX_CACHE_METRICS_NOT_UPDATED"
    elif not long_enough:
        status = "INCONCLUSIVE_GENERATION_TOO_SHORT_FOR_LONG_DECODE"
    elif not lp_complete:
        status = "INCONCLUSIVE_TOKEN_LOGPROBS_MISSING"
    elif max_lp_delta is None or max_lp_delta > 1e-4:
        status = "INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE"
    else:
        status = "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS"
    controls = {"status": "NOT_RUN"}
    if (enable_cold_controls and same_text and same_tokens and
            same_finishes and lp_complete):
        try:
            controls = cold_control_diagnostics(model, port, payload, cold)
        except OracleBlocked:
            controls = {"status": "UNAVAILABLE_API_OR_METRICS"}
    return {
        "status": status, "requests": len(observations),
        "same_input_cold_controls": controls,
        "mtp_configured_tokens": 2,
        "mtp_speculative_metric_names_observed": observed_spec_metric_names,
        "mtp_accepted_draft_token_counter_delta": accepted_delta,
        "mtp_acceptance_observed": accepted_delta > 0,
        "minimum_requested_output_tokens": min_output_tokens,
        "minimum_generation_length_observed": min(
            len(r["token_ids"]) for r in [cold, *repetitions]),
        "all_output_lengths_sufficient": long_enough,
        "oracle_endpoint": "/v1/chat/completions",
        "thinking_disabled": True,
        "prompt_sha256": hashlib.sha256(prompt_repr.encode()).hexdigest(),
        "cold_text_sha256": hashlib.sha256(cold["content"].encode()).hexdigest(),
        "all_repeats_text_equal": same_text,
        "all_repeats_token_ids_equal": same_tokens,
        "all_finish_reasons_equal": same_finishes,
        "output_content_nonempty": bool(cold["content"].strip()),
        "cold_output_tokens": len(cold["token_ids"]),
        "cold_prompt_tokens": cold["prompt_tokens"],
        "repeat_prompt_tokens": [r["prompt_tokens"] for r in repetitions],
        "cache_hit_observed": bool(hit_indices),
        "cache_hit_repeat_request_indices_1_based": hit_indices,
        "cache_query_token_deltas_per_request": query_deltas,
        "cache_hit_token_deltas_per_request": hit_deltas,
        "cached_prompt_tokens_per_request": [
            o["cached_prompt_tokens"] for o in observations],
        "all_token_logprobs_available": lp_complete,
        "max_token_logprob_abs_delta": max_lp_delta,
        "max_first_token_logprob_abs_delta": first_lp_delta_max,
        **numeric_drift,
        "logprob_strict_abs_tolerance": 1e-4,
        "active_mamba_physical_mapping_observed": False,
    }
