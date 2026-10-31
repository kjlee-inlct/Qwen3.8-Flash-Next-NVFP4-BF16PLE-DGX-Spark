"""P1 integrated candidate API + strict Prefix/MTP verification client.

HTTP inference ONLY. Never starts, stops or mutates Docker containers.
Run only after separately approved stop and candidate launch.
Sanitize results: no prompt, generated text, model arguments or raw HTTP error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src import p1_integrated_runtime as runtime
from src import p1_prefix_gpu_oracle as oracle
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa

PORT = runtime.PORT
LIMIT = 2000000


class Blocked(Exception):
    pass


def request(path: str, payload: dict | None = None, *, streaming=False):
    if path not in ("/v1/models", "/v1/responses", "/v1/chat/completions"):
        raise Blocked("ENDPOINT_NOT_ALLOWLISTED")
    content = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if streaming:
        headers["Accept"] = "text/event-stream"
    req = Request("http://127.0.0.1:" + str(PORT) + path,
                  data=content, headers=headers)
    try:
        with urlopen(req, timeout=180) as response:
            data = response.read(LIMIT + 1)
            mime = response.headers.get("Content-Type", "")
    except (HTTPError, URLError, OSError, TimeoutError):
        raise Blocked("HTTP_REQUEST_FAILED") from None
    if not data or len(data) > LIMIT:
        raise Blocked("HTTP_RESPONSE_SIZE_INVALID")
    if streaming:
        if "text/event-stream" not in mime:
            raise Blocked("SSE_CONTENT_TYPE_INVALID")
        try:
            return data.decode("utf-8")
        except UnicodeError:
            raise Blocked("SSE_ENCODING_INVALID") from None
    try:
        obj = json.loads(data)
    except ValueError:
        raise Blocked("HTTP_RESPONSE_JSON_INVALID") from None
    if not isinstance(obj, dict):
        raise Blocked("HTTP_RESPONSE_OBJECT_INVALID")
    return obj


def verify_live(head: str, candidate_id: str) -> str:
    if not re.fullmatch("[0-9a-f]{40}", head) or not re.fullmatch(
            "[0-9a-f]{64}", candidate_id):
        raise Blocked("ID_SHAPE_INVALID")
    receipt, original, _, state = release._legacy_state_for_release()
    if state != "exited" or original.get("Id") != receipt["id"]:
        raise Blocked("ORIGINAL_MUST_BE_EXITED_SAME_ID")
    runtime.verify_image()
    candidate = runtime.owned(head)
    if candidate.get("Id") != candidate_id or (
            candidate.get("State") or {}).get("Status") != "running":
        raise Blocked("CANDIDATE_ID_OR_STATE_DRIFT")
    _, model = gpu.candidate_cmd((original.get("Config") or {}).get("Cmd"))
    models = request("/v1/models")
    listed = [i.get("id") for i in models.get("data", []) if isinstance(i, dict)]
    if model not in listed:
        raise Blocked("SERVED_MODEL_ID_MISMATCH")
    return model


def tool_smoke(model: str) -> None:
    obj = request("/v1/chat/completions", {
        "model": model, "temperature": 0, "max_tokens": 128,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "user", "content": "Call weather for Seoul."}],
        "tools": [{"type": "function", "function": {
            "name": "weather",
            "description": "Fictional weather lookup test.",
            "parameters": {"type": "object", "properties": {
                "city": {"type": "string"}}, "required": ["city"],
                "additionalProperties": False}}}],
        "tool_choice": {"type": "function", "function": {"name": "weather"}},
    })
    choices = obj.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise Blocked("TOOL_CHOICES_INVALID")
    msg = choices[0].get("message") or {}
    calls = msg.get("tool_calls") or []
    for item in calls:
        fn = item.get("function") if isinstance(item, dict) else None
        if isinstance(fn, dict) and fn.get("name") == "weather":
            try:
                params = json.loads(fn.get("arguments", ""))
            except (TypeError, ValueError):
                continue
            if isinstance(params, dict) and params.get("city") == "Seoul":
                return
    raise Blocked("TOOL_CALL_OR_ARGUMENTS_MISSING")


def responses_smoke(model: str) -> None:
    inp = {"model": model, "input": "Answer only with the number 12.",
           "temperature": 0, "max_output_tokens": 96}
    obj = request("/v1/responses", inp)
    if obj.get("status") != "completed" or not isinstance(
            obj.get("output"), list) or not obj["output"]:
        raise Blocked("RESPONSES_NONSTREAM_INVALID")
    raw = request("/v1/responses", {**inp, "stream": True}, streaming=True)
    event_types = set()
    for event in raw.replace("\r\n", "\n").split("\n\n"):
        for line in event.splitlines():
            if line.startswith("data:"):
                try:
                    record = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if isinstance(record, dict) and isinstance(record.get("type"), str):
                    event_types.add(record["type"])
    if "response.failed" in event_types or "response.incomplete" in event_types:
        raise Blocked("RESPONSES_STREAM_FAILED")
    if "response.completed" not in event_types:
        raise Blocked("RESPONSES_STREAM_COMPLETION_MISSING")


def api_smoke(head: str, candidate_id: str) -> dict:
    model = verify_live(head, candidate_id)
    outcomes = {}
    for name, fn in (("tool_chat", tool_smoke), ("responses", responses_smoke)):
        try:
            fn(model)
            outcomes[name] = "PASS"
        except (Blocked, oracle.OracleBlocked) as exc:
            outcomes[name] = str(exc)
    ok = all(value == "PASS" for value in outcomes.values())
    return {
        "status": "API_SMOKE_PASS" if ok else "API_SMOKE_INCOMPLETE",
        "checks": outcomes,
        "p1_final_pass": False,
        "full_state_reuse_verified": False,
    }


def prefix_oracle(head: str, candidate_id: str) -> dict:
    model = verify_live(head, candidate_id)
    try:
        report = oracle.run_oracle(model, PORT, min_output_tokens=128,
                                   enable_cold_controls=True)
    except (oracle.OracleBlocked, ValueError, TypeError, OSError):
        return {"status": "PREFIX_ORACLE_UNAVAILABLE", "strict_numeric_pass": False,
                "full_state_reuse_verified": False, "p1_final_pass": False}
    status = report.get("status")
    delta = report.get("max_token_logprob_abs_delta")
    passed = (
        status == "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS"
        and report.get("mtp_acceptance_observed") is True
        and report.get("cache_hit_observed") is True
        and type(delta) in (float, int) and delta <= 1e-4)
    return {
        "status": status,
        "hit_token_deltas": report.get("cache_hit_token_deltas_per_request"),
        "mtp_accepted_token_delta": report.get(
            "mtp_accepted_draft_token_counter_delta"),
        "token_ids_equal": report.get("all_repeats_token_ids_equal"),
        "logprob_max_abs_delta": delta,
        "first_token_logprob_max_abs_delta": report.get(
            "max_first_token_logprob_abs_delta"),
        "no_hit_control": report.get("no_hit_strict_numeric_baseline"),
        "strict_abs_tolerance": 1e-4,
        "strict_numeric_pass": passed,
        "full_state_reuse_verified": False,
        "p1_final_pass": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--confirm-candidate-id", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--api-smoke", action="store_true")
    group.add_argument("--prefix-oracle", action="store_true")
    a = p.parse_args()
    try:
        qsa.os.chdir(qsa.ROOT)
        qsa.preflight(a.expected_head)
        result = (api_smoke(a.expected_head, a.confirm_candidate_id)
                  if a.api_smoke else
                  prefix_oracle(a.expected_head, a.confirm_candidate_id))
        print(json.dumps(result, sort_keys=True))
        success = (result.get("status") == "API_SMOKE_PASS" if a.api_smoke
                   else result.get("strict_numeric_pass") is True)
        return 0 if success else 2
    except (Blocked, qsa.Blocked, release.ReleaseBlocked,
            gpu.Blocked, OSError, TypeError, ValueError, KeyError):
        print("P1_INTEGRATED_API_BLOCKED_NO_SUCCESS", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
