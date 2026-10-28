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
    print('P1_DIAG_STAGE=IMPORT_PARSER_HANDOFF', flush=True)
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
    print('P1_DIAG_STAGE=VALIDATE_TYPED_REQUEST', flush=True)
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

    print('P1_DIAG_STAGE=NONSTREAM_VALID_TOOL', flush=True)
    result = output_items(xml("Seoul"))
    funcs = [i for i in result if getattr(i, "type", "") == "function_call"]
    if (len(funcs) != 1 or funcs[0].name != "weather"
            or json.loads(funcs[0].arguments) != {"city": "Seoul"}):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_FUNCTION_CALL_WRONG")
    print('P1_DIAG_STAGE=NONSTREAM_WIRE', flush=True)
    wire = ResponsesResponse.from_request(
        typed_request, sampling, model_name="offline-test",
        created_time=123456, output=result, status="completed", usage=None,
    )
    typed = ResponsesResponse.model_validate_json(wire.model_dump_json())
    if (typed.status != "completed"
            or len([o for o in typed.output if o.type == "function_call"]) != 1):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_WIRE_ROUNDTRIP_FAILED")
    cases += 1

    print('P1_DIAG_STAGE=NONSTREAM_REJECTIONS', flush=True)
    for bad in (xml("Mars"), xml("Seoul", name="not_offered"), ""):
        try:
            output_items(bad)
        except GenerationError:
            pass
        else:
            raise StageBlocked("REAL_PARSER_TO_RESPONSES_UNSAFE_SUCCESS")
        cases += 1

    print('P1_DIAG_STAGE=NONSTREAM_PLAINTEXT', flush=True)
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
        # The serving stream consumes one mutable SimpleContext per request.
        # Recreating it for every chunk, or passing None to the generator,
        # does not exercise the installed Preview serving contract.
        context = serving.SimpleContext(response_parser=parser_instance)
        # Diagnosing a pinned Preview ABI, never assume upstream context
        # properties are present in the installed package.
        print("P1_DIAG_CONTEXT_ITEMS=" +
              ("PRESENT" if hasattr(context, "streamed_output_items")
               else "ABSENT"), flush=True)
        events = []

        async def contexts():
            for idx, chunk in enumerate(text_chunks):
                context.last_output = SimpleNamespace(
                    outputs=[SimpleNamespace(
                        text=chunk, token_ids=[], logprobs=None,
                        finish_reason="stop" if idx == len(text_chunks) - 1 else None,
                    )],
                    prompt_token_ids=[] if idx == 0 else None,
                )
                yield context

        async def completed(self, req, params, *args, **kwargs):
            print("P1_DIAG_TERMINAL_ENTERED=YES", flush=True)
            # Terminal output must be the exact typed items emitted by the
            # installed event processor, not synthetic or reparsed items.
            # Preview ABI variants may not retain these on SimpleContext.
            finished_items = [
                ev.item for ev in events if ev.type == "response.output_item.done"
            ]
            if not finished_items:
                raise StageBlocked("REAL_RESPONSES_STREAM_PROCESSOR_DONE_ITEMS_MISSING")
            # If the installed Preview DOES publish context items, require
            # content/ordering identity with the emitted done events.
            stored_items = getattr(context, "streamed_output_items", None)
            if stored_items is not None and (
                    len(stored_items) != len(finished_items)
                    or any(a.model_dump(mode="json") != b.model_dump(mode="json")
                           for a, b in zip(stored_items, finished_items))):
                raise StageBlocked("REAL_RESPONSES_STREAM_PROCESSOR_ITEMS_CONFLICT")
            return protocol.ResponsesResponse.from_request(
                req, params, model_name="offline-test",
                created_time=123456, output=finished_items,
                status="completed", usage=None,
            )

        actual_service.responses_full_generator = MethodType(completed, actual_service)
        async for event in actual_service.responses_stream_generator(
                typed_request, sampling, contexts(), context,
                "offline-test", tokenizer, None, created_time=123456):
            events.append(event)
        return events

    print('P1_DIAG_STAGE=STREAM_VALID_GENERATOR', flush=True)
    chunks = ["<tool_call>\n", "<function=weather>", "\n<parameter=city>",
              "Se", "oul", "</parameter>", "\n</function>", "\n</tool_call>"]
    streamed = asyncio.run(stream_model(chunks))
    print('P1_DIAG_STAGE=STREAM_VALID_STRUCTURE', flush=True)
    types = [ev.type for ev in streamed]
    if (not types or types[-1] != "response.completed"
            or "response.output_item.added" not in types
            or "response.output_item.done" not in types
            or not any("function_call_arguments" in x for x in types)):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_EVENTS_MISSING")
    if any(i != ev.sequence_number for i, ev in enumerate(streamed)):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_SEQUENCE_INVALID")
    finalized = [item for item in streamed[-1].response.output
                 if item.type == "function_call"]
    done_items = [ev.item for ev in streamed
                  if ev.type == "response.output_item.done"
                  and ev.item.type == "function_call"]
    if (len(finalized) != 1 or len(done_items) != 1
            or finalized[0].name != "weather"
            or json.loads(finalized[0].arguments) != {"city": "Seoul"}
            or finalized[0].call_id != done_items[0].call_id):
        raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_FINAL_TOOL_WRONG")
    print('P1_DIAG_STAGE=STREAM_VALID_WIRE', flush=True)
    for event in streamed:
        # Only fixed event-family labels, never payload or model data.
        safe_event_kinds = {
            "response.created": "CREATED",
            "response.in_progress": "IN_PROGRESS",
            "response.completed": "COMPLETED",
            "response.failed": "FAILED",
            "response.output_item.added": "ITEM_ADDED",
            "response.output_item.done": "ITEM_DONE",
            "response.function_call_arguments.delta": "ARG_DELTA",
            "response.function_call_arguments.done": "ARG_DONE",
        }
        print("P1_DIAG_EVENT_KIND=" + safe_event_kinds.get(event.type, "OTHER"),
              flush=True)
        if adapter.validate_json(event.model_dump_json()).type != event.type:
            raise StageBlocked("REAL_PARSER_TO_RESPONSES_STREAM_WIRE_INVALID")
    cases += 1

    print('P1_DIAG_STAGE=STREAM_REJECT_INVALID', flush=True)
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
            try:
                result = _child(Path(args[1]))
            except Exception as exc:
                # Only the exception *type*, never message, traceback, paths,
                # tool inputs, model contents, or user data.
                print("P1_DIAG_EXCEPTION=" + type(exc).__name__, flush=True)
                if isinstance(exc, StageBlocked):
                    # Never echo a StageBlocked message without an exact
                    # allowlist: source, paths and payloads are confidential.
                    blocked_codes = {
                        "REAL_RESPONSES_STREAM_PROCESSOR_DONE_ITEMS_MISSING":
                            "DONE_ITEMS_MISSING",
                        "REAL_RESPONSES_STREAM_PROCESSOR_ITEMS_CONFLICT":
                            "ITEMS_CONFLICT",
                    }
                    print("P1_DIAG_BLOCKED_CODE=" +
                          blocked_codes.get(str(exc), "OTHER"), flush=True)
                if type(exc).__name__ == "AttributeError":
                    # Python's AttributeError.name and traceback frame names
                    # can be attacker-controlled: emit only fixed labels.
                    attr_names = {
                        "streamed_output_items": "CTX_ITEMS",
                        "last_output": "LAST_OUTPUT",
                        "final_output": "FINAL_OUTPUT",
                        "response_parser": "PARSER",
                        "outputs": "OUTPUTS",
                        "prompt_token_ids": "PROMPT_TOKENS",
                        "token_ids": "TOKEN_IDS",
                        "text": "TEXT",
                        "finish_reason": "FINISH_REASON",
                        "logprobs": "LOGPROBS",
                        "id": "ID",
                        "call_id": "CALL_ID",
                        "name": "NAME",
                        "function": "FUNCTION",
                        "arguments": "ARGUMENTS",
                        "streamed_items_by_message": "STREAM_ITEMS",
                    }
                    print("P1_DIAG_ATTR=" +
                          attr_names.get(getattr(exc, "name", None), "OTHER"),
                          flush=True)
                    frame_names = {
                        "completed": "COMPLETED",
                        "contexts": "CONTEXTS",
                        "stream_model": "STREAM_MODEL",
                        "_process_simple_streaming_events": "PROCESSOR",
                        "responses_stream_generator": "SERVING",
                        "parse_delta": "PARSER",
                        "emit_delta": "EMIT_DELTA",
                        "open": "OPEN",
                        "close_current": "CLOSE",
                        "emit_simple_tool_call_open": "TOOL_OPEN",
                        "emit_simple_tool_call_delta": "TOOL_DELTA",
                        "emit_simple_tool_call_done": "TOOL_DONE",
                        "__getattr__": "GETATTR",
                    }
                    frame = "OTHER"
                    current = exc.__traceback__
                    while current is not None:
                        candidate = frame_names.get(current.tb_frame.f_code.co_name)
                        if candidate is not None:
                            frame = candidate
                        current = current.tb_next
                    print("P1_DIAG_ATTR_FRAME=" + frame, flush=True)
                if type(exc).__name__ == "ValidationError":
                    # Pydantic field names are static allowlisted metadata;
                    # never emit the message, input, ctx, model text or traceback.
                    safe_fields = {
                        "arguments", "call_id", "content", "delta", "function",
                        "item", "name", "namespace", "output", "output_index",
                        "response", "sequence_number", "status", "tool_calls",
                        "tools", "type",
                    }
                    field = "OTHER"
                    try:
                        errors = exc.errors(include_input=False,
                                            include_context=False,
                                            include_url=False)
                        if errors:
                            for part in reversed(errors[0].get("loc", ())):
                                if isinstance(part, str) and part in safe_fields:
                                    field = part.upper()
                                    break
                    except (TypeError, ValueError, AttributeError):
                        pass
                    print("P1_DIAG_VALIDATION_FIELD=" + field, flush=True)
                raise
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
                # Stable, allowlisted diagnostic codes without user/model data.
                allowed = {
                    "IMPORT_PARSER_HANDOFF", "VALIDATE_TYPED_REQUEST",
                    "NONSTREAM_VALID_TOOL", "NONSTREAM_WIRE",
                    "NONSTREAM_REJECTIONS", "NONSTREAM_PLAINTEXT",
                    "STREAM_VALID_GENERATOR", "STREAM_VALID_STRUCTURE",
                    "STREAM_VALID_WIRE", "STREAM_REJECT_INVALID",
                }
                stage = "CHILD_START"
                if "P1_RESPONSES_BEFORE_IMPORT" in child.stdout:
                    stage = "SERVING_IMPORT"
                if "P1_RESPONSES_AFTER_IMPORT" in child.stdout:
                    stage = "EVENT_BEHAVIOR"
                for line in child.stdout.splitlines():
                    if line.startswith("P1_DIAG_STAGE="):
                        candidate = line.partition("=")[2]
                        if candidate in allowed:
                            stage = candidate
                safe_types = {"TypeError", "AttributeError", "ValidationError",
                              "ValueError", "KeyError", "AssertionError",
                              "StageBlocked", "RuntimeError", "IndexError"}
                error_type = "OTHER"
                for line in child.stdout.splitlines():
                    if line.startswith("P1_DIAG_EXCEPTION="):
                        candidate = line.partition("=")[2]
                        if candidate in safe_types:
                            error_type = candidate
                validation_field = "OTHER"
                if error_type == "ValidationError":
                    known_fields = {
                        "ARGUMENTS", "CALL_ID", "CONTENT", "DELTA", "FUNCTION",
                        "ITEM", "NAME", "NAMESPACE", "OUTPUT", "OUTPUT_INDEX",
                        "RESPONSE", "SEQUENCE_NUMBER", "STATUS", "TOOL_CALLS",
                        "TOOLS", "TYPE", "OTHER",
                    }
                    for line in child.stdout.splitlines():
                        if line.startswith("P1_DIAG_VALIDATION_FIELD="):
                            candidate = line.partition("=")[2]
                            if candidate in known_fields:
                                validation_field = candidate
                suffix = ("_" + validation_field
                          if error_type == "ValidationError" else "")
                # Record the last fully serialized event family for a wire
                # failure, not source fields or untrusted event contents.
                known_event_kinds = {
                    "CREATED", "IN_PROGRESS", "COMPLETED", "FAILED",
                    "ITEM_ADDED", "ITEM_DONE", "ARG_DELTA", "ARG_DONE", "OTHER",
                }
                event_kind = "OTHER"
                if stage == "STREAM_VALID_WIRE":
                    for line in child.stdout.splitlines():
                        if line.startswith("P1_DIAG_EVENT_KIND="):
                            candidate = line.partition("=")[2]
                            if candidate in known_event_kinds:
                                event_kind = candidate
                event_suffix = ("_" + event_kind
                                if stage == "STREAM_VALID_WIRE" else "")
                attr_suffix = ""
                if error_type == "AttributeError":
                    allowed_attrs = {
                        "CTX_ITEMS", "LAST_OUTPUT", "FINAL_OUTPUT", "PARSER",
                        "OUTPUTS", "PROMPT_TOKENS", "TOKEN_IDS", "TEXT",
                        "FINISH_REASON", "LOGPROBS", "ID", "CALL_ID", "NAME",
                        "FUNCTION", "ARGUMENTS", "STREAM_ITEMS", "OTHER",
                    }
                    allowed_frames = {
                        "COMPLETED", "CONTEXTS", "STREAM_MODEL", "PROCESSOR",
                        "SERVING", "PARSER", "EMIT_DELTA", "OPEN", "CLOSE",
                        "TOOL_OPEN", "TOOL_DELTA", "TOOL_DONE", "GETATTR",
                        "OTHER",
                    }
                    attr = frame = "OTHER"
                    for line in child.stdout.splitlines():
                        if line.startswith("P1_DIAG_ATTR="):
                            candidate = line.partition("=")[2]
                            if candidate in allowed_attrs:
                                attr = candidate
                        elif line.startswith("P1_DIAG_ATTR_FRAME="):
                            candidate = line.partition("=")[2]
                            if candidate in allowed_frames:
                                frame = candidate
                    attr_suffix = "_" + attr + "_" + frame
                blocked_suffix = ""
                if error_type == "StageBlocked":
                    blocked_codes = {"DONE_ITEMS_MISSING", "ITEMS_CONFLICT", "OTHER"}
                    blocked_code = "OTHER"
                    for line in child.stdout.splitlines():
                        if line.startswith("P1_DIAG_BLOCKED_CODE="):
                            candidate = line.partition("=")[2]
                            if candidate in blocked_codes:
                                blocked_code = candidate
                    blocked_suffix = "_" + blocked_code
                raise StageBlocked("REAL_RESPONSES_" + stage + "_" + error_type
                                   + suffix + event_suffix + attr_suffix
                                   + blocked_suffix + "_BLOCKED")
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
