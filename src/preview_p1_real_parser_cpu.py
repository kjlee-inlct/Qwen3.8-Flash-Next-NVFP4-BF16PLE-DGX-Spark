"""Real installed Preview Qwen3 parser CPU integration, no model/API/GPU.

Only allowed under the existing explicit pinned one-shot Docker --bundle
p1-real-parser (runc, no network/GPU, read-only, memory-limited).  All
installed sources are read, NEVER rewritten. Three pinned patches are
applied to ephemeral copies. A child Python process imports the actual
Preview parser and its real installed dependencies with an allowlisted
source override. No fake Parser/lexer/ResponsesRequest is used.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from src.preview_p1_tool_responses_stage import (
    StageBlocked, find_installed_preview, read_preview_sources,
)
from src.preview_p1_native_schema_verify import (
    _run_patches as apply_marker_schema, EXTRA_PINS, NEW_MODULE,
)
from src.preview_p1_native_marker_verify import PINNED as MARKER_PINS
from src.preview_p1_native_responses_verify import (
    RESPONSES_PATCH, RESPONSES_SHA256, TARGETS,
)
from src.preview_p1_tool_responses_stage import PINNED_PREIMAGES

# Every installed source override is an allowlisted operator-pinned file.
SOURCE_PINS = {**PINNED_PREIMAGES, **MARKER_PINS, **EXTRA_PINS}
OVERLAY_MODULES = frozenset(
    name[:-3].replace("/", ".") for name in TARGETS | {NEW_MODULE}
)
if len(OVERLAY_MODULES) != len(TARGETS) + 1:
    raise RuntimeError("duplicate override names")


def _environment() -> None:
    # These settings are asserted in addition to the outer Docker controls.
    expected = {
        "NVIDIA_VISIBLE_DEVICES": "void",
        "CUDA_VISIBLE_DEVICES": "-1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if any(os.environ.get(key) != val for key, val in expected.items()):
        raise StageBlocked("ISOLATION_ENV_MISSING")


def _stage(site: Path, sandbox: Path) -> None:
    if (site / NEW_MODULE).exists():
        raise StageBlocked("INSTALLED_SCHEMA_MODULE_ALREADY_PRESENT")
    raw = read_preview_sources(site, TARGETS)
    for name, data in raw.items():
        digest = SOURCE_PINS.get(name)
        if digest is None or hashlib.sha256(data).hexdigest() != digest:
            raise StageBlocked("INSTALLED_PREVIEW_SOURCE_PIN_DRIFT")
        dest = sandbox / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    apply_marker_schema(sandbox)
    if (RESPONSES_PATCH.is_symlink()
            or hashlib.sha256(RESPONSES_PATCH.read_bytes()).hexdigest()
            != RESPONSES_SHA256):
        raise StageBlocked("RESPONSES_PATCH_SHA_DRIFT")
    patched = subprocess.run(
        ["patch", "--batch", "--forward", "--fuzz=0", "-p1",
         "--no-backup-if-mismatch"],
        input=RESPONSES_PATCH.read_bytes(), cwd=sandbox,
        capture_output=True, timeout=12, check=False,
    )
    if patched.returncode:
        raise StageBlocked("PREVIEW_RESPONSES_PATCH_NOT_APPLICABLE")
    for name in TARGETS | {NEW_MODULE}:
        src = sandbox / name
        if src.is_symlink() or not src.is_file():
            raise StageBlocked("OVERLAY_FILE_NOT_REGULAR")
        ast.parse(src.read_bytes(), filename=name)


def _child(sandbox: Path) -> dict:
    # The child imports installed vLLM code/deps, but selected source files
    # are read only from temporary copies via a narrowly scoped import hook.
    import importlib
    import importlib.abc
    import importlib.util

    if not sandbox.is_dir() or sandbox.is_symlink():
        raise StageBlocked("INVALID_OVERLAY_ROOT")

    class PreviewOverrideFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in OVERLAY_MODULES:
                return None
            file = sandbox / (fullname.replace(".", "/") + ".py")
            if file.is_symlink() or not file.is_file():
                raise StageBlocked("OVERLAY_TARGET_MISSING")
            return importlib.util.spec_from_file_location(fullname, file)

    sys.meta_path.insert(0, PreviewOverrideFinder())
    qwen = importlib.import_module("vllm.parser.qwen3")
    protocol = importlib.import_module("vllm.entrypoints.openai.responses.protocol")
    # Fail if a matching import resolved back into the installed package.
    for name in ("vllm.parser.qwen3",
                 "vllm.parser.engine.parser_engine",
                 "vllm.parser.engine.streaming_parser_engine",
                 "vllm.parser.engine.argument_validation",
                 "vllm.entrypoints.openai.responses.protocol"):
        module = sys.modules.get(name)
        if module is None or Path(module.__file__).resolve() != (
            sandbox / (name.replace(".", "/") + ".py")
        ).resolve():
            raise StageBlocked("REAL_PARSER_OVERLAY_IMPORT_MISMATCH")

    class TinyTokenizer:
        all_special_tokens = ["<think>", "</think>", "<tool_call>", "</tool_call>"]
        all_special_ids = [9101, 9102, 9103, 9104]
        def get_vocab(self):
            return dict(zip(self.all_special_tokens, self.all_special_ids))
        def decode(self, ids, *args, **kwargs):
            inv = dict(zip(self.all_special_ids, self.all_special_tokens))
            return "".join(inv.get(i, "") for i in ids)

    schema = {
        "type": "object",
        "properties": {"city": {"type": "string", "enum": ["Seoul"]}},
        "required": ["city"],
        "additionalProperties": False,
    }
    tools = [{"type": "function", "name": "weather", "parameters": schema}]
    req = protocol.ResponsesRequest.model_construct(
        input="weather", tools=tools, include_reasoning=True,
        tool_choice="auto",
    )

    def parser():
        return qwen.Qwen3Parser(
            TinyTokenizer(), tools=tools,
            chat_template_kwargs={"enable_thinking": False},
        )

    def xml(city, name="weather"):
        return (f"<tool_call>\n<function={name}>\n"
                f"<parameter=city>{city}</parameter>\n"
                "</function>\n</tool_call>")

    # One full request: actual lexer -> state machine -> Qwen converter ->
    # JSON schema validation -> response-oriented ToolCall result.
    valid = parser()
    _, content, calls = valid.parse(xml("Seoul"), req, enable_auto_tools=True)
    if not calls or len(calls) != 1:
        raise StageBlocked("REAL_VALID_TOOL_NOT_DELIVERED")
    if calls[0].name != "weather" or json.loads(calls[0].arguments) != {"city": "Seoul"}:
        raise StageBlocked("REAL_VALID_TOOL_ARGUMENTS_WRONG")
    if valid.has_invalid_tool_arguments:
        raise StageBlocked("REAL_VALID_TOOL_REJECTED")

    invalid = parser()
    _, _, bad_calls = invalid.parse(xml("Mars"), req, enable_auto_tools=True)
    if bad_calls or not invalid.has_invalid_tool_arguments:
        raise StageBlocked("REAL_INVALID_SCHEMA_WAS_ACCEPTED")

    unknown = parser()
    _, _, unoffered = unknown.parse(xml("Seoul", name="unknown"), req,
                                    enable_auto_tools=True)
    if unoffered or not unknown.has_invalid_tool_arguments:
        raise StageBlocked("REAL_UNOFFERED_TOOL_WAS_ACCEPTED")

    # Quoted markers and mid-line function headers are literal content.
    for text in ("A literal <function=weather> marker",
                 "Code example:\n" + "~~~\n<tool_call>\n~~~\n"):
        p = parser()
        _, content, calls = p.parse(text, req, enable_auto_tools=True)
        if calls or p.has_invalid_tool_arguments or not content:
            raise StageBlocked("REAL_LITERAL_MARKER_CONSUMED")

    # True streaming across chunk boundaries (not invoking mock methods).
    streamed = parser()
    chunks = [
        "<tool_call>\n", "<function=weather>", "\n<parameter=city>",
        "Se", "oul", "</parameter>", "\n</function>", "\n</tool_call>",
    ]
    deltas = []
    for i, part in enumerate(chunks):
        delta = streamed.parse_delta(
            part, [], req, prompt_token_ids=[] if i == 0 else None,
            finished=i == len(chunks)-1,
        )
        if delta is not None:
            deltas.extend(delta.tool_calls or [])
    if len(deltas) != 1:
        raise StageBlocked("REAL_STREAM_TOOL_COUNT_WRONG")
    if (deltas[0].function.name != "weather"
            or json.loads(deltas[0].function.arguments) != {"city": "Seoul"}):
        raise StageBlocked("REAL_STREAM_TOOL_ARGUMENTS_WRONG")
    if streamed.has_invalid_tool_arguments:
        raise StageBlocked("REAL_STREAM_VALID_TOOL_REJECTED")

    return {"status": "REAL_PINNED_PREVIEW_QWEN_PARSER_CPU_PASS",
            "cases": 6, "actual_parser_imported": True,
            "model_http_gpu_executed": False, "installed_source_modified": False,
            "responses_serving_http_verified": False}


def main(args: list[str]) -> int:
    try:
        _environment()
        if len(args) == 2 and args[0] == "--child":
            result = _child(Path(args[1]))
            print(json.dumps(result, sort_keys=True))
            print("PREVIEW_P1_REAL_PARSER_CPU_PASS_NOT_API_OR_DEPLOYED")
            return 0
        if args != ["--verify-installed"]:
            raise StageBlocked("EXPLICIT_VERIFY_INSTALLED_REQUIRED")
        site = find_installed_preview()
        with tempfile.TemporaryDirectory(prefix="p1-real-parser-cpu-") as temp:
            overlay = Path(temp)
            _stage(site, overlay)
            child = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).resolve()),
                 "--child", str(overlay)],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True, text=True, timeout=90, check=False,
                env={**os.environ, "PYTHONNOUSERSITE": "1"},
            )
            if child.returncode:
                # Fail closed: no raw server traces, filenames, token text,
                # model payload or Python exception output.
                raise StageBlocked("REAL_PARSER_IMPORT_OR_BEHAVIOR_FAILED")
            if ("PREVIEW_P1_REAL_PARSER_CPU_PASS_NOT_API_OR_DEPLOYED"
                    not in child.stdout):
                raise StageBlocked("REAL_PARSER_SUCCESS_MARKER_MISSING")
            print(child.stdout.strip())
        return 0
    except (StageBlocked, OSError, ValueError, AssertionError, SyntaxError,
            subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, StageBlocked) else "CPU_STAGE_FAILED"
        print(json.dumps({"status": "BLOCKED_NOT_APPLIED", "reason": reason[:100]}))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
