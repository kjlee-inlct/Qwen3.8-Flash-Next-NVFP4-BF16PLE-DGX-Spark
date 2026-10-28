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

    return {"status": "REAL_PINNED_PREVIEW_RESPONSES_SERVING_CPU_PASS",
            "cases": cases, "serving_class_imported": True,
            "pydantic_wire_events_roundtripped": True,
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
