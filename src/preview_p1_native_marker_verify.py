"""Preview-native Qwen3 literal-marker/preamble port verification.

Applies the *real* pinned Preview-specific patch only to ephemeral copies;
executes its actual parser method bodies in a standard-library CPU harness.
NEVER imports vLLM, uses GPU, writes installed source, or calls a server.
This checks one feature slice, NOT Tool/Responses end-to-end compatibility.
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from types import SimpleNamespace

from src.preview_p1_tool_responses_stage import (
    StageBlocked, find_installed_preview, read_preview_sources,
)

PATCH = Path(__file__).resolve().parent / 'preview_p1_patches/qwen-preview-native-marker.patch'
PATCH_SHA256 = 'abef62917219eb80a03a4f4e924012a49b953fdd1533d0e5e16a513f26a905e8'
PINNED = {
    'vllm/parser/engine/parser_engine_config.py': 'f7350e0ca9124001684f1f874ee72bf6a34932d3e4b84cc84567bbccf2f3e4b9',
    'vllm/parser/engine/streaming_parser_engine.py': 'd00aba98ad26a2593e022a1faf5d048348d892822f75be40d19cf1dd522570f2',
    'vllm/parser/qwen3.py': '8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb',
    'vllm/parser/nemotron_v3.py': '9d77b45debb4fb820cc448dfbeeccb53b384f8124b0ef6627ddba9777dcfa6df',
}


class State(Enum):
    CONTENT=auto(); REASONING=auto(); TOOL_PREAMBLE=auto(); TOOL_NAME=auto()
    TOOL_ARGS=auto(); TOOL_BETWEEN=auto(); MESSAGE_HEADER=auto()


class Event(Enum):
    TEXT_CHUNK=auto(); REASONING_CHUNK=auto(); REASONING_END=auto()
    TOOL_CALL_START=auto(); TOOL_CALL_END=auto(); ARG_VALUE_CHUNK=auto()


@dataclass
class SemanticEvent:
    type: Event
    value: str = ''
    tool_index: int = -1
    token_count: int = 0


@dataclass
class Transition:
    next_state: State
    events: tuple = ()
    skip_in_token_id_mode: bool = False


def verify_native_methods(source: bytes) -> int:
    """Exercise methods extracted from patched Preview, not reimplementations."""
    classes = [n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='StreamingParserEngine']
    if len(classes)!=1:
        raise StageBlocked('NATIVE_CLASS_NOT_FOUND')
    names = {'_on_terminal','_emit_for_state','_on_content','_apply_transition',
             '_reset_marker_guard','_begin_line','_resolve_fence_run','_sync_marker_guard',
             '_marker_is_literal','_track_literal_text','_flush_tool_preamble',
             '_confirm_tool_preamble'}
    body = [n for n in classes[0].body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in body}!=names:
        raise StageBlocked('NATIVE_METHODS_MISSING')
    klass = ast.ClassDef(name='ActualPreviewMethods',bases=[],keywords=[],body=body,decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),klass],type_ignores=[]))
    scope = {'ParserState': State, 'EventType': Event, 'SemanticEvent': SemanticEvent,'Transition':Transition}
    exec(compile(module,'<pinned-preview-native-methods>','exec'),scope)
    cls=scope['ActualPreviewMethods']
    def make():
        x=cls()
        x.state=State.CONTENT; x.tool_index=-1
        x._has_drops=False; x._ever_had_token_ids=False
        x.skip_tool_parsing=False; x._in_skipped_tool_span=False
        x._tool_exit_terminals=frozenset({'TOOL_END'})
        x._tool_terminals=frozenset({'TOOL_START','FUNC_PREFIX','TOOL_END'})
        x._TOOL_STATES=frozenset({State.TOOL_PREAMBLE,State.TOOL_NAME,State.TOOL_ARGS,State.TOOL_BETWEEN})
        x._args_buffer=''; x._message_header_buffer=''; x._message_header_token_count=0
        x._pending_tool_start=None; x._tool_preamble_buffer=''; x._tool_preamble_token_count=0
        x._bare_tool_headers=frozenset({'FUNC_PREFIX'})
        x.config=SimpleNamespace(validate_tool_preamble=True,guard_literal_tool_markers=True,
            terminals={'TOOL_START':'<tool_call>','FUNC_PREFIX':'<function='},
            content_events={State.CONTENT:Event.TEXT_CHUNK,State.REASONING:Event.REASONING_CHUNK},
            transitions={(State.CONTENT,'TOOL_START'):Transition(State.TOOL_PREAMBLE,(Event.TOOL_CALL_START,)),
                         (State.CONTENT,'FUNC_PREFIX'):Transition(State.TOOL_NAME,(Event.TOOL_CALL_START,)),
                         (State.TOOL_PREAMBLE,'FUNC_PREFIX'):Transition(State.TOOL_NAME,())},tool_args_json=False)
        x._reset_marker_guard()
        return x
    x=make(); x._on_content('inline marker: ')
    assert [v.type for v in x._on_terminal('FUNC_PREFIX','<function=')]==[Event.TEXT_CHUNK]
    x=make(); x._on_content('```python\n')
    assert [v.type for v in x._on_terminal('TOOL_START','<tool_call>')]==[Event.TEXT_CHUNK]
    x._on_content('\n```\n')
    assert x._on_terminal('TOOL_START','<tool_call>')==[]
    x._on_content('  ')
    e=x._on_terminal('FUNC_PREFIX','<function=')
    assert Event.TOOL_CALL_START in [v.type for v in e] and x.state==State.TOOL_NAME
    x=make(); assert x._on_terminal('TOOL_START','<tool_call>')==[]
    assert x._on_content('not a call')[0].value=='<tool_call>not a call'
    x=make(); x._on_content('~~~\n')
    assert [v.type for v in x._on_terminal('TOOL_START','<tool_call>')]==[Event.TEXT_CHUNK]
    x._on_content('\n~~~\n')
    assert x._on_terminal('TOOL_START','<tool_call>')==[]
    return 5


def verify(site: Path) -> dict:
    if PATCH.is_symlink() or not PATCH.is_file() or hashlib.sha256(PATCH.read_bytes()).hexdigest()!=PATCH_SHA256:
        raise StageBlocked('NATIVE_PATCH_SHA_DRIFT')
    if shutil.which('patch') is None:
        raise StageBlocked('PATCH_UNAVAILABLE')
    original=read_preview_sources(site,set(PINNED))
    if any(hashlib.sha256(raw).hexdigest()!=PINNED[name] for name,raw in original.items()):
        raise StageBlocked('SOURCE_SHA_DRIFT')
    with tempfile.TemporaryDirectory(prefix='p1-native-qwen-cpu-') as temporary:
        copy=Path(temporary)
        for name,raw in original.items():
            dest=copy/name; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(raw)
        run=subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','--no-backup-if-mismatch'],
            input=PATCH.read_bytes(),cwd=copy,capture_output=True,timeout=12)
        if run.returncode:
            raise StageBlocked('NATIVE_PATCH_CONTEXT_MISMATCH')
        for file in copy.rglob('*.py'):
            ast.parse(file.read_bytes())
        cases=verify_native_methods((copy/'vllm/parser/engine/streaming_parser_engine.py').read_bytes())
        if 'guard_literal_tool_markers=name == "qwen3"' not in (copy/'vllm/parser/qwen3.py').read_text():
            raise StageBlocked('NATIVE_QWEN_CONFIG_NOT_WIRED')
    return {'status':'NATIVE_PREVIEW_MARKER_EXTRACTED_CPU_ONLY','cases':cases,
            'installed_source_modified':False,'vllm_imported':False,
            'gpu_model_http_tested':False}


def main(argv: list[str]) -> int:
    if argv==['--verify-installed']:
        site=find_installed_preview()
    elif len(argv)==2 and argv[0]=='--verify-site':
        site=Path(argv[1])
    else:
        print('STOP: explicit --verify-installed or --verify-site required')
        return 2
    try:
        out=verify(site)
    except (StageBlocked, OSError, ValueError, SyntaxError, subprocess.TimeoutExpired, AssertionError) as e:
        print(json.dumps({'status':'BLOCKED','reason':str(e)[:100], 'installed_source_modified':False}))
        return 2
    print(json.dumps(out,sort_keys=True))
    print('PREVIEW_P1_NATIVE_QWEN_MARKER_CPU_PASS_NOT_API_OR_DEPLOYED')
    return 0

if __name__=='__main__':
    sys.exit(main(sys.argv[1:]))
