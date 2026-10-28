"""Real Preview Responses Serving/Pydantic CPU integration, no HTTP/model/GPU.

Run only through the existing explicitly approved isolated runc CPU Docker
bundle. Reuse the previous exact source hashes and three temp-only patches.
Actual vLLM/OpenAI Pydantic classes and serving generator are imported.
Engine/model/event processor are deliberately inert CPU fixtures.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import MethodType

from src.preview_p1_real_parser_cpu import (
    OVERLAY_MODULES, StageBlocked, _environment, _stage, find_installed_preview,
)


def _child(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise StageBlocked("BAD_RESPONSES_OVERLAY")

    class Overlay(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in OVERLAY_MODULES:
                return None
            file = root / (fullname.replace(".", "/") + ".py")
            if file.is_symlink() or not file.is_file():
                raise StageBlocked("RESPONSES_OVERLAY_FILE_MISSING")
            return importlib.util.spec_from_file_location(fullname, file)

    sys.meta_path.insert(0, Overlay())
    print("P1_RESPONSES_BEFORE_IMPORT", flush=True)
    serving = importlib.import_module("vllm.entrypoints.openai.responses.serving")
    protocol = importlib.import_module("vllm.entrypoints.openai.responses.protocol")
    for name in ("vllm.entrypoints.openai.responses.serving",
                 "vllm.entrypoints.openai.responses.protocol",
                 "vllm.parser.engine.argument_validation"):
        if name.endswith("argument_validation"):
            importlib.import_module(name)
        mod = sys.modules.get(name)
        expected = (root / (name.replace(".", "/") + ".py")).resolve()
        if mod is None or Path(mod.__file__).resolve() != expected:
            raise StageBlocked("REAL_RESPONSES_SOURCE_OVERRIDE_MISSED")
    print("P1_RESPONSES_AFTER_IMPORT", flush=True)

    from vllm.sampling_params import SamplingParams
    from vllm.entrypoints.generate.base.serving import GenerationError
    from pydantic import TypeAdapter

    request = protocol.ResponsesRequest(input="offline-test", stream=True,
                                        model="offline-test", tools=[])
    sampling = SamplingParams(max_tokens=16, temperature=0, top_p=1)
    adapter = TypeAdapter(protocol.StreamingResponsesResponse)

    async def no_source():
        if False:
            yield None

    async def fixture_processor(self, *args, **kwargs):
        if self.test_mode == "processor_error":
            raise GenerationError("SENSITIVE_PRIVATE_GENERATION_ERROR")
        if False:
            yield None

    async def fixture_full(self, req, params, *args, **kwargs):
        if self.test_mode == "final_error":
            raise GenerationError("SENSITIVE_PRIVATE_FINAL_ERROR")
        return protocol.ResponsesResponse.from_request(
            req, params, model_name="offline-test", created_time=123456,
            output=[], status=self.test_mode, usage=None,
        )

    async def collect(mode: str):
        service = object.__new__(serving.OpenAIServingResponses)
        service.use_harmony = False
        service.test_mode = mode
        service._process_simple_streaming_events = MethodType(fixture_processor, service)
        service.responses_full_generator = MethodType(fixture_full, service)
        result = []
        async for event in service.responses_stream_generator(
                request, sampling, no_source(), None, "offline-test", None,
                None, created_time=123456):
            result.append(event)
        return result

    cases = 0
    terminal_map = {
        "completed": protocol.ResponseCompletedEvent,
        "incomplete": protocol.ResponseIncompleteEvent,
        "failed": protocol.ResponseFailedEvent,
    }
    for status, cls in terminal_map.items():
        events = asyncio.run(collect(status))
        if [e.type for e in events] != [
                "response.created", "response.in_progress", "response." + status]:
            raise StageBlocked("REAL_RESPONSES_WRONG_TERMINAL_EVENTS")
        if any(e.sequence_number != i for i, e in enumerate(events)):
            raise StageBlocked("REAL_RESPONSES_INVALID_SEQUENCES")
        if not isinstance(events[-1], cls) or events[-1].response.status != status:
            raise StageBlocked("REAL_RESPONSES_WRONG_TYPED_EVENT")
        for event in events:
            checked = adapter.validate_json(event.model_dump_json())
            if checked.type != event.type:
                raise StageBlocked("REAL_RESPONSES_BAD_JSON_ROUNDTRIP")
        if status == "failed" and events[-1].response.error is None:
            raise StageBlocked("REAL_RESPONSES_FAILURE_DETAILS_MISSING")
        if status == "incomplete" and events[-1].response.incomplete_details is None:
            raise StageBlocked("REAL_RESPONSES_INCOMPLETE_DETAILS_MISSING")
        cases += 1

    for mode in ("processor_error", "final_error", "queued"):
        events = asyncio.run(collect(mode))
        if [e.type for e in events] != [
                "response.created", "response.in_progress", "response.failed"]:
            raise StageBlocked("REAL_RESPONSES_FAILURE_NOT_TERMINAL")
        error = events[-1].response.error
        if (error is None or error.code != "server_error"
                or "SENSITIVE_PRIVATE" in events[-1].model_dump_json()):
            raise StageBlocked("REAL_RESPONSES_FAILURE_DETAILS_LEAKED")
        adapter.validate_json(events[-1].model_dump_json())
        cases += 1

    # Real connected Qwen -> OpenAIServingResponses conversion: use typed
    # Pydantic request/tools, actual parser, converter and output-item builder.
    # These paths were not covered by the earlier isolated parser/serving tests.
    from types import SimpleNamespace
    from vllm.entrypoints.openai.responses.protocol import ResponsesResponse
    from vllm.parser.qwen3 import Qwen3Parser

    class TinyTokenizer:
        all_special_tokens = ["<think>", "</think>", "<tool_call>", "</tool_call>"]
        all_special_ids = [9101, 9102, 9103, 9104]

        def get_vocab(self):
            return dict(zip(self.all_special_tokens, self.all_special_ids))

        def decode(self, ids, *args, **kwargs):
            by_id = dict(zip(self.all_special_ids, self.all_special_tokens))
            return "".join(by_id.get(n, "") for n in ids)

    schema = {
        "type": "object",
        "properties": {"city": {"type": "string", "enum": ["Seoul"]}},
        "required": ["city"],
        "additionalProperties": False,
    }
    # No model_construct: this is an actual validated HTTP-shaped request.
    typed_request = protocol.ResponsesRequest(
        input="weather", model="offline-test", stream=True,
        tools=[{"type": "function", "name": "weather",
                "description": "Return the city's weather", "parameters": schema}],
    )
    tokenizer = TinyTokenizer()

    def make_parser():
        return Qwen3Parser(tokenizer, tools=typed_request.tools,
                           chat_template_kwargs={"enable_thinking": False})

    def xml(city, name="weather"):
        return (f"<tool_call>\n<function={name}>\n"
                f"<parameter=city>{city}</parameter>\n"
                "</function>\n</tool_call>")

    actual_service = object.__new__(serving.OpenAIServingResponses)
    actual_service.enable_log_outputs = False
    actual_service.request_logger = None
    actual_service.enable_auto_tools = True
    actual_service.parser = Qwen3Parser
    actual_service.use_harmony = False
    actual_service._raise_if_error = lambda *a, **kw: None

    def output_items(text: str):
        final = SimpleNamespace(text=text, token_ids=[], logprobs=None,
                                finish_reason="stop")
        return actual_service._make_response_output_items(
            typed_request, final, tokenizer, parser=make_parser(),
        )

    result = output_items(xml("Seoul"))
    funcs = [i for i in result if getattr(i, "type", "") == "function_call"]
    if (len(funcs) != 1 or funcs[0].name != "weather"
            or json.loads(funcs[0].arguments) != {"city": "Seoul"}):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_FUNCTION_CALL_WRONG")
    wire = ResponsesResponse.from_request(
        typed_request, sampling, model_name="offline-test",
        created_time=123456, output=result, status="completed", usage=None,
    )
    typed = ResponsesResponse.model_validate_json(wire.model_dump_json())
    if (typed.status != "completed"
            or len([o for o in typed.output if o.type == "function_call"]) != 1):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_WIRE_ROUNDTRIP_FAILED")
    cases += 1

    for bad in (xml("Mars"), xml("Seoul", name="not_offered"), ""):
        try:
            output_items(bad)
        except GenerationError:
            pass
        else:
            raise StageBlocked("REAL_PARSER_TO_RESPONSES_UNSAFE_SUCCESS")
        cases += 1

    for harmless in ("Hello from a model.", "Example: <function=weather> literal"):
        output = output_items(harmless)
        if (not output or any(o.type == "function_call" for o in output)
                or not any(o.type == "message" for o in output)):
            raise StageBlocked("REAL_PARSER_TO_RESPONSES_CONTENT_LOST")
        cases += 1

    # Exercise actual parser delta -> installed SimpleStreamingEventProcessor
    # -> actual Responses SSE events; only the model token source is a fixture.
    async def stream_model(text_chunks):
        parser_instance = make_parser()

        async def contexts():
            for idx, chunk in enumerate(text_chunks):
                # The real generator explicitly requires a SimpleContext;
                # no GPU RequestOutput/engine initialization is performed.
                ctx = object.__new__(serving.SimpleContext)
                ctx.response_parser = parser_instance
                ctx.last_output = SimpleNamespace(
                    outputs=[SimpleNamespace(
                        text=chunk, token_ids=[], logprobs=None,
                        finish_reason="stop" if idx == len(text_chunks) - 1 else None,
                    )],
                    prompt_token_ids=[],
                )
                yield ctx

        async def completed(self, req, params, *args, **kwargs):
            return protocol.ResponsesResponse.from_request(
                req, params, model_name="offline-test",
                created_time=123456, output=[], status="completed", usage=None,
            )

        actual_service.responses_full_generator = MethodType(completed, actual_service)
        events = []
        async for event in actual_service.responses_stream_generator(
                typed_request, sampling, contexts(), None,
                "offline-test", tokenizer, None, created_time=123456):
            events.append(event)
        return events

    chunks = ["<tool_call>\n", "<function=weather>", "\n<parameter=city>",
              "Se", "oul", "</parameter>", "\n</function>", "\n</tool_call>"]
    streamed = asyncio.run(stream_model(chunks))
    types = [ev.type for ev in streamed]
    if (not types or types[-1] != "response.completed"
            or "response.output_item.added" not in types
            or "response.output_item.done" not in types
            or not any("function_call_arguments" in x for x in types)):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_EVENTS_MISSING")
    if any(i != ev.sequence_number for i, ev in enumerate(streamed)):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_SEQUENCE_INVALID")
    for event in streamed:
        if adapter.validate_json(event.model_dump_json()).type != event.type:
            raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_WIRE_INVALID")
    cases += 1

    invalid_stream = asyncio.run(stream_model(
        ["<tool_call>\n<function=weather>\n<parameter=city>",
         "Mars</parameter>\n</function>\n</tool_call>"]
    ))
    invalid_types = [ev.type for ev in invalid_stream]
    if (not invalid_types or invalid_types[-1] != "response.failed"
            or "response.completed" in invalid_types
            or any("function_call_arguments" in x for x in invalid_types)):
        raise StageBlocked("REAL_INVALID_TOOL_STREAM_NOT_REJECTED")
    cases += 1

    return {"status": "REAL_PINNED_PREVIEW_RESPONSES_SERVING_CPU_PASS",
            "cases": cases, "serving_class_imported": True,
            "pydantic_wire_events_roundtripped": True,
            "actual_parser_serving_handoff_verified": True,
            "actual_http_request": False, "actual_model_or_gpu_executed": False,
            "installed_package_modified": False}


def main(args: list[str]) -> int:
    try:
        _environment()
        if len(args) == 2 and args[0] == "--child":
            result = _child(Path(args[1]))
            print(json.dumps(result, sort_keys=True))
            print("PREVIEW_P1_REAL_RESPONSES_SERVING_CPU_PASS_NOT_HTTP_OR_DEPLOYED")
            return 0
        if args != ["--verify-installed"]:
            raise StageBlocked("EXPLICIT_VERIFY_INSTALLED_REQUIRED")
        with tempfile.TemporaryDirectory(prefix="p1-real-responses-") as tmp:
            overlay = Path(tmp)
            _stage(find_installed_preview(), overlay)
            child = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).resolve()),
                 "--child", str(overlay)],
                cwd=Path(__file__).resolve().parent.parent,
                env={**os.environ, "PYTHONNOUSERSITE": "1"},
                capture_output=True, text=True, timeout=90,
            )
            if child.returncode:
                phase = ("EVENT_BEHAVIOR" if "P1_RESPONSES_AFTER_IMPORT" in child.stdout
                         else "SERVING_IMPORT" if "P1_RESPONSES_BEFORE_IMPORT" in child.stdout
                         else "CHILD_START")
                raise StageBlocked("REAL_RESPONSES_" + phase + "_FAILED")
            if "PREVIEW_P1_REAL_RESPONSES_SERVING_CPU_PASS_NOT_HTTP_OR_DEPLOYED" not in child.stdout:
                raise StageBlocked("REAL_RESPONSES_SUCCESS_MARKER_MISSING")
            for line in child.stdout.splitlines():
                if line.startswith("{") or line.startswith("PREVIEW_P1_REAL_RESPONSES_SERVING_CPU_PASS_"):
                    print(line)
        return 0
    except (StageBlocked, OSError, ValueError, AssertionError, SyntaxError,
            subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, StageBlocked) else "RESPONSES_CPU_STAGE_FAILED"
        print(json.dumps({"status": "BLOCKED_NOT_APPLIED", "reason": reason[:100]}))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
