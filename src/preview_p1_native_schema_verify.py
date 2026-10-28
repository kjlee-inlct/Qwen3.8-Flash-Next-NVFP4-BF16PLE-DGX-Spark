"""Validate P1 Qwen3 Responses argument-schema port against PINNED Preview copies.

The original vLLM installation is read only. Applies two SHA-pinned patches
(marker first, then schema) solely to an auto-deleted temporary directory.
Exercises actual patched schema and Qwen3 method bodies under CPU-only fakes;
NOT a full vLLM Parser/API/GPU or deployed/serving validation.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from src.preview_p1_tool_responses_stage import (
    StageBlocked, find_installed_preview, read_preview_sources,
)
from src.preview_p1_native_marker_verify import PATCH as MARKER_PATCH, PATCH_SHA256 as MARKER_SHA

SCHEMA_PATCH = Path(__file__).resolve().parent / "preview_p1_patches/qwen-preview-native-schema.patch"
SCHEMA_SHA256 = "003a1e5ade756bd4e28c48a3d02a24b54f7a488a0e8dd304117fe3819c19a864"
# Additional installed preimages from exact operator-provided snapshot.
EXTRA_PINS = {
    "vllm/parser/abstract_parser.py": "53b13cd1f0becaaeca445ab27cfd0d0461e6be09383377062f955fd302c48c30",
    "vllm/parser/engine/adapters.py": "2f9e31e13734b7df75d424f45cf39d723bef7c5415a9bc6851b121cbb6b4ae6d",
}
TARGETS = frozenset({
    "vllm/parser/engine/parser_engine_config.py",
    "vllm/parser/engine/streaming_parser_engine.py",
    "vllm/parser/qwen3.py",
    "vllm/parser/nemotron_v3.py",
    "vllm/parser/engine/parser_engine.py",
    "vllm/entrypoints/openai/responses/serving.py",
    "vllm/parser/abstract_parser.py",
    "vllm/parser/engine/adapters.py",
})
NEW_MODULE = "vllm/parser/engine/argument_validation.py"


def _sha(path: Path, expected: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageBlocked("PATCH_MISSING_OR_SYMLINK")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise StageBlocked("PATCH_SHA_DRIFT")
    return raw


def _run_patches(sandbox: Path) -> None:
    for i, (path, sha) in enumerate(((MARKER_PATCH, MARKER_SHA), (SCHEMA_PATCH, SCHEMA_SHA256)), 1):
        payload = _sha(path, sha)
        try:
            p = subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1",
                                "--no-backup-if-mismatch"], input=payload,
                               cwd=sandbox, capture_output=True, timeout=12)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StageBlocked("PATCH_PROCESS_FAILED") from exc
        if p.returncode:
            raise StageBlocked(f"PREVIEW_NATIVE_SCHEMA_PATCH_{i}_CONTEXT_MISMATCH")


def _behavior(sandbox: Path) -> int:
    """Call modified method bodies from actual patched Preview class, no vLLM import."""
    modpath = sandbox / NEW_MODULE
    spec = importlib.util.spec_from_file_location("_offline_p1_schema", modpath)
    if spec is None or spec.loader is None:
        raise StageBlocked("SCHEMA_MODULE_UNLOADABLE")
    validation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validation)

    schema = {"type": "object", "properties": {"place": {"type": "string"}},
              "required": ["place"], "additionalProperties": False}
    tools = [{"type": "function", "function": {"name": "weather", "parameters": schema}}]
    if validation.find_parameters(tools, "weather") != schema:
        raise StageBlocked("SCHEMA_LOOKUP_INCORRECT")
    if validation.find_parameters(tools, "unknown") is not None:
        raise StageBlocked("SCHEMA_UNKNOWN_TOOL_ACCEPTED")
    for value, expected in (
        ('{"place":"대전"}', '{"place":"대전"}'),
        ('{"arguments":{"place":"서울"}}', '{"place": "서울"}'),
        ('{"arguments":"{\\"place\\":\\"서울\\"}"}', '{"place": "서울"}'),
    ):
        if validation.validate_or_unwrap(value, schema) != expected:
            raise StageBlocked("SCHEMA_UNWRAP_MISMATCH")
    for value in ('{"place":12}', '{"arguments":{"place":15}}',
                  '{"arguments":{"arguments":{"place":"x"}}}',
                  '{"place":"a","place":"b"}', '{"place":NaN}',
                  '{"arguments":"not-json"}'):
        try:
            validation.validate_or_unwrap(value, schema)
        except validation.InvalidToolArguments:
            pass
        else:
            raise StageBlocked("INVALID_ARGUMENTS_ACCEPTED")
    try:
        validation.validate_or_unwrap('{"place":"x"}',
            {'type':'object','properties':{'place':{'$ref':'https://invalid.example/schema'}}})
    except validation.InvalidToolArguments:
        pass
    else:
        raise StageBlocked("REMOTE_SCHEMA_UNEXPECTEDLY_ACCEPTED")

    class Base:
        def _handle_arg_chunk(self, event, deltas):
            deltas.append("chat_chunk")
        def _handle_tool_end(self, event, deltas):
            deltas.append("chat_end")
        def _accept_tool_name(self, name):
            return bool(name)
        def _try_extract_name(self, idx):
            return None
        def _fix_arg_types(self, value, name):
            return value
        def _ensure_tool_id(self, slot, name):
            slot.id = "test-id"

    class Slot:
        def __init__(self):
            self.name, self.args, self.id = "weather", "", ""
        def append_args(self, value):
            self.args += value

    class Event:
        def __init__(self, value):
            self.value, self.tool_index = value, 0

    class Delta:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    tree = ast.parse((sandbox / "vllm/parser/qwen3.py").read_bytes())
    original = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Qwen3Parser"), None)
    wanted = {"_handle_arg_chunk", "_handle_tool_end", "_normalize_tool_arguments", "_reject_arguments"}
    if original is None:
        raise StageBlocked("QWEN3_CLASS_MISSING")
    methods = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    if {n.name for n in methods} != wanted:
        raise StageBlocked("QWEN3_SCHEMA_HOOKS_MISSING")
    class_ast = ast.ClassDef(name="PatchedQwen3Methods", bases=[ast.Name(id="Base", ctx=ast.Load())],
                             keywords=[], body=methods, decorator_list=[])
    code = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__",
        names=[ast.alias(name="annotations")], level=0), class_ast], type_ignores=[]))
    scope = {"Base": Base, "find_parameters": validation.find_parameters,
             "validate_or_unwrap": validation.validate_or_unwrap,
             "InvalidToolArguments": validation.InvalidToolArguments,
             "DeltaToolCall": Delta, "DeltaFunctionCall": Delta,
             "FUNC_END": "</function>", "TOOL_CALL_END": "</tool_call>"}
    exec(compile(code, "<pinned-preview-qwen3-methods>", "exec"), scope)
    cls = scope["PatchedQwen3Methods"]

    def make(strict=True, offered=tools):
        q = cls()
        q._strict_responses_arguments = strict
        q._invalid_argument_slots = set()
        q._tools = offered
        q._tool_slots = [Slot()]
        q._arg_converter = lambda text, partial: text
        return q

    for body, expected in (( '{"place":"서울"}', '{"place":"서울"}'),
                           ('{"arguments":{"place":"서울"}}', '{"place": "서울"}'),
                           ('{"place":2}', None),
                           ('{"place":"x","place":"y"}', None)):
        q = make()
        deltas = []
        q._handle_arg_chunk(Event(body), deltas)
        if deltas:
            raise StageBlocked("STRICT_RESPONSES_LEAKED_PARTIAL_ARGUMENTS")
        q._handle_tool_end(Event("</function>"), deltas)
        if expected is None:
            if deltas or q._invalid_argument_slots != {0}:
                raise StageBlocked("INVALID_RESPONSES_CALL_NOT_REJECTED")
        elif len(deltas) != 1 or deltas[0].function.arguments != expected:
            raise StageBlocked("VALID_RESPONSES_CALL_NOT_EMITTED_ATOMICALLY")

    q = make(offered=[])
    deltas = []
    q._handle_arg_chunk(Event('{"place":"서울"}'), deltas)
    q._handle_tool_end(Event("</function>"), deltas)
    if deltas or q._invalid_argument_slots != {0}:
        raise StageBlocked("UNLISTED_TOOL_ACCEPTED")
    q = make()
    deltas = []
    q._handle_arg_chunk(Event('{"place":"서울"}'), deltas)
    q._handle_tool_end(Event(""), deltas)
    if deltas or q._invalid_argument_slots != {0}:
        raise StageBlocked("INCOMPLETE_TOOL_ACCEPTED")
    q = make(strict=False)
    deltas = []
    q._handle_arg_chunk(Event('{"place":2}'), deltas)
    q._handle_tool_end(Event("</function>"), deltas)
    if deltas != ["chat_chunk", "chat_end"] or q._invalid_argument_slots:
        raise StageBlocked("CHAT_LEGACY_STREAM_CHANGED")

    # Sanity: both actual integration callsites must signal parser failure.
    server = (sandbox / 'vllm/entrypoints/openai/responses/serving.py').read_text()
    if server.count('getattr(parser, "has_invalid_tool_arguments", False)') != 1 or \
            server.count('getattr(ctx.response_parser, "has_invalid_tool_arguments", False)') != 1:
        raise StageBlocked('RESPONSES_ERROR_INTEGRATION_MISSING')
    return 12


def verify(site: Path) -> dict:
    if (site / NEW_MODULE).exists():
        raise StageBlocked("NEW_ARGUMENT_MODULE_ALREADY_INSTALLED")
    originals = read_preview_sources(site, TARGETS)
    # qwen3, engine, streaming, config and serving are pinned in base validator;
    # actual Preview marker adds a 6th independently pinned Nemotron file.
    from src.preview_p1_native_marker_verify import PINNED as MARKER_PINS
    for name, expected in {**MARKER_PINS, **EXTRA_PINS}.items():
        if name in TARGETS and hashlib.sha256(originals[name]).hexdigest() != expected:
            raise StageBlocked("SOURCE_EXTRA_SHA_DRIFT")
    with tempfile.TemporaryDirectory(prefix="preview-p1-native-schema-") as tmp:
        sandbox = Path(tmp)
        for name, data in originals.items():
            p = sandbox / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        _run_patches(sandbox)
        for name in TARGETS | {NEW_MODULE}:
            ast.parse((sandbox / name).read_bytes(), filename=name)
        cases = _behavior(sandbox)
    return {"status": "NATIVE_PREVIEW_QWEN_SCHEMA_METHODS_CPU_ONLY", "cases": cases,
            "vllm_imported": False, "installed_vllm_modified": False,
            "gpu_model_http_run": False, "parser_api_compatibility_certified": False}


def main(argv: list[str]) -> int:
    if argv != ["--verify-installed"]:
        print("STOP: --verify-installed required")
        return 2
    try:
        result = verify(find_installed_preview())
    except (StageBlocked, OSError, ValueError, AssertionError, SyntaxError,
            subprocess.TimeoutExpired) as exc:
        # Only source identity/status codes, not raw model outputs or patch stdout.
        print(json.dumps({"status": "BLOCKED_NOT_APPLIED", "reason": str(exc)[:90]}))
        return 2
    print(json.dumps(result, sort_keys=True))
    print("PREVIEW_P1_NATIVE_TOOL_SCHEMA_CPU_PASS_NOT_API_OR_DEPLOYED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
