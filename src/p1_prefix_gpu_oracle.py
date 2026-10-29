"""Real-model P1 Prefix GPU cold/repeat oracle; never claims a hit from text equality alone."""
from __future__ import annotations
import hashlib
import json
import re
from urllib.request import Request, urlopen


def request_json(port: int, payload: dict) -> dict:
    r = Request(f"http://127.0.0.1:{port}/v1/completions",
                json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(r, timeout=180) as response:
        return json.load(response)


def metrics(port: int) -> dict[str, float]:
    with urlopen(f"http://127.0.0.1:{port}/metrics", timeout=15) as response:
        text = response.read(4_000_000).decode("utf-8")
    values = {}
    for line in text.splitlines():
        if line.startswith("#") or "prefix_cache" not in line:
            continue
        match = re.fullmatch(r'([\w:]+)(\{[^}]*\})?\s+([0-9.eE+-]+)(?:\s+.*)?', line)
        if match:
            key, labels, val = match.groups()
            if labels and 'cache_type="cpu"' in labels:
                continue
            values[key + (labels or "")] = float(val)
    return values


def hit_evidence(before: dict, after: dict) -> bool:
    for key, value in after.items():
        name = key.split("{", 1)[0].lower()
        if "prefix_cache" in name and "hit" in name:
            if name.endswith(("hits", "hits_total")) and value > before.get(key, 0.0):
                return True
            if name.endswith("hit_rate") and value > max(before.get(key, 0.0), 0.0):
                return True
    return False


def run_oracle(model: str, port: int) -> dict:
    # No personal data or user workload; same prompt on both requests.
    prompt = ("Control register A5 is asserted. Report the expected stable register state. " * 128)
    payload = {"model": model, "prompt": prompt, "temperature": 0,
               "max_tokens": 32, "seed": 42, "logprobs": 1}
    initial = metrics(port)
    cold = request_json(port, payload)
    middle = metrics(port)
    hit = request_json(port, payload)
    final = metrics(port)
    first = cold["choices"][0]
    second = hit["choices"][0]
    a = first["text"]
    b = second["text"]
    cold_tokens = (first.get("logprobs") or {}).get("tokens")
    hit_tokens = (second.get("logprobs") or {}).get("tokens")
    tokens_same = bool(cold_tokens and hit_tokens and cold_tokens == hit_tokens)
    logprobs_a = (first.get("logprobs") or {}).get("token_logprobs")
    logprobs_b = (second.get("logprobs") or {}).get("token_logprobs")
    observed_hit = hit_evidence(middle, final)
    # Different vLLM versions expose hit via per-request cached tokens instead.
    cached = ((hit.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")
    if isinstance(cached, int) and cached > 0:
        observed_hit = True
    first_token_lp_equal = bool(
        logprobs_a and logprobs_b and
        logprobs_a[0] is not None and logprobs_b[0] is not None and
        abs(logprobs_a[0] - logprobs_b[0]) <= 1e-4)
    status = ("PASS_CACHE_HIT_AND_IDENTICAL_TEXT_TOKENS" if observed_hit and a == b and tokens_same
              and first_token_lp_equal
              else "FAIL_OUTPUT_MISMATCH" if a != b or (cold_tokens and hit_tokens and not tokens_same)
              else "INCONCLUSIVE_TOKENS_UNAVAILABLE" if a == b and not tokens_same
              else "FAIL_FIRST_TOKEN_LOGPROB_MISMATCH" if observed_hit and not first_token_lp_equal
              else "INCONCLUSIVE_NO_HIT_TELEMETRY")
    return {"status": status, "requests": 2, "mtp_tokens": 2,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "cold_text_sha256": hashlib.sha256(a.encode()).hexdigest(),
            "repeat_text_sha256": hashlib.sha256(b.encode()).hexdigest(),
            "text_equal": a == b, "token_sequence_equal": tokens_same,
            "first_token_logprob_equal": first_token_lp_equal,
            "cache_hit_observed": observed_hit,
            "cache_metric_names": sorted({k.split("{", 1)[0] for k in [*initial, *final]}),
            "active_mamba_physical_mapping_observed": False}
