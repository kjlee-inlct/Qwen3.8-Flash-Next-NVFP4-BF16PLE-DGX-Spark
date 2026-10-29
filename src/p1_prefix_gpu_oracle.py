"""P1 isolated GPU prefix-cache oracle: fail closed without nonempty token and hit evidence.

No model content or user data is printed; only synthetic request hashes, token
counts, cache deltas, finish reasons and equality indicators are reported.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
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
    message = (base * (100 if long_prompt else 1))
    message += "\nFinal question: What is seven plus five? Answer with the number 12."
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Respond with a short factual answer."},
            {"role": "user", "content": message}],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 96,
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
        if line.startswith("#") or "prefix_cache" not in line:
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


def run_oracle(model: str, port: int) -> dict:
    payload = build_payload(model, long_prompt=True)
    prompt_repr = json.dumps(payload["messages"], ensure_ascii=True, sort_keys=True)
    initial = metrics(port)
    cold_raw = request_json(port, payload)
    cold = extract(cold_raw)
    middle = settled_metrics(port, initial, require_queries=True)
    repeat_raw = request_json(port, payload)
    repeat = extract(repeat_raw)
    final = settled_metrics(port, middle, require_queries=True)

    a, b = cold["content"], repeat["content"]
    cold_tokens, hit_tokens = cold["token_ids"], repeat["token_ids"]
    token_source = "token_ids" if cold_tokens is not None and hit_tokens is not None else "logprob_token_strings"
    if token_source == "logprob_token_strings":
        cold_tokens, hit_tokens = cold["tokens"], repeat["tokens"]
    tokens_same = bool(cold_tokens and hit_tokens and cold_tokens == hit_tokens)
    logprobs_available = bool(cold["logprobs"] and repeat["logprobs"] and
                              cold["logprobs"][0] is not None and
                              repeat["logprobs"][0] is not None)
    lp_delta = (abs(cold["logprobs"][0] - repeat["logprobs"][0])
                if logprobs_available else None)
    lp_same = lp_delta is not None and lp_delta <= 1e-4

    # Confirm *repeat* cache hit after allowing a metrics-publishing interval.
    hit_delta = counter_delta(middle, final, "prefix_cache_hits_total")
    query_delta = counter_delta(middle, final, "prefix_cache_queries_total")
    cached = repeat["cached_prompt_tokens"]
    hit = hit_delta > 0 or (cached is not None and cached > 0)
    cold_hit_delta = counter_delta(initial, middle, "prefix_cache_hits_total")

    if not a.strip() or not b.strip():
        status = "INCONCLUSIVE_EMPTY_FINAL_CONTENT"
    elif cold["finish_reason"] not in ("stop", "length") or repeat["finish_reason"] not in ("stop", "length"):
        status = "FAIL_CHAT_FINISH_REASON_UNEXPECTED"
    elif not cold["tokens"] or not repeat["tokens"]:
        status = "INCONCLUSIVE_TOKEN_LOGPROBS_MISSING"
    elif cold["token_ids"] is None or repeat["token_ids"] is None:
        status = "INCONCLUSIVE_TOKEN_IDS_UNAVAILABLE"
    elif not tokens_same or a != b:
        status = "FAIL_NONIDENTICAL_OUTPUT"
    elif not logprobs_available:
        status = "INCONCLUSIVE_FIRST_TOKEN_LOGPROB_UNAVAILABLE"
    elif not lp_same:
        status = "FAIL_FIRST_TOKEN_LOGPROB_MISMATCH"
    elif hit:
        status = "PASS_CACHE_HIT_AND_NONEMPTY_OUTPUT_TOKENS_LOGPROB"
    elif query_delta > 0:
        status = "FAIL_REPEAT_PREFIX_CACHE_MISS"
    else:
        status = "INCONCLUSIVE_PREFIX_CACHE_METRICS_NOT_UPDATED"

    return {
        "status": status, "requests": 2, "mtp_configured_tokens": 2,
        "oracle_endpoint": "/v1/chat/completions",
        "thinking_disabled": True,
        "prompt_sha256": hashlib.sha256(prompt_repr.encode()).hexdigest(),
        "cold_text_sha256": hashlib.sha256(a.encode()).hexdigest(),
        "repeat_text_sha256": hashlib.sha256(b.encode()).hexdigest(),
        "cold_content_nonempty": bool(a.strip()),
        "repeat_content_nonempty": bool(b.strip()),
        "cold_output_tokens": len(cold_tokens or []),
        "repeat_output_tokens": len(hit_tokens or []),
        "cold_finish_reason": cold["finish_reason"],
        "repeat_finish_reason": repeat["finish_reason"],
        "cold_prompt_tokens": cold["prompt_tokens"],
        "repeat_prompt_tokens": repeat["prompt_tokens"],
        "repeat_cached_prompt_tokens": cached,
        "text_equal": a == b,
        "token_sequence_equal": tokens_same,
        "token_evidence_type": token_source,
        "first_token_logprob_equal": lp_same,
        "first_token_logprob_abs_delta": lp_delta,
        "cache_hit_observed": hit,
        "cold_hit_counter_delta": cold_hit_delta,
        "repeat_hit_counter_delta": hit_delta,
        "repeat_query_counter_delta": query_delta,
        "cache_metric_names": sorted({k.split("{", 1)[0] for k in [*initial, *middle, *final]}),
        "active_mamba_physical_mapping_observed": False,
    }
