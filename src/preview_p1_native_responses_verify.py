"""P1 Preview-native Responses terminal status and failure handling source validation.

Stages Qwen marker, schema, and Responses patches against immutable installed
Preview source only in an ephemeral directory; runs patched ACTUAL serving
methods with a no-vLLM CPU harness. Never imports vLLM or uses network/GPU.
Parser/API/serving runtime and model compatibility remain NOT_CERTIFIED.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from contextlib import AsyncExitStack
from pathlib import Path
from types import SimpleNamespace

from src.preview_p1_tool_responses_stage import StageBlocked, find_installed_preview, read_preview_sources
from src.preview_p1_native_schema_verify import (
    _run_patches as run_marker_schema_patches,
    TARGETS as SCHEMA_TARGETS,
    EXTRA_PINS,
    NEW_MODULE,
)
from src.preview_p1_native_marker_verify import PINNED as MARKER_PINS

RESPONSES_PATCH = Path(__file__).resolve().parent / "preview_p1_patches/qwen-preview-native-responses.patch"
RESPONSES_SHA256 = "606638c63230c1b02b91b44991109275c7eed0541773f824feff35609a14b2b0"
PROTOCOL = "vllm/entrypoints/openai/responses/protocol.py"
SERVING = "vllm/entrypoints/openai/responses/serving.py"
TARGETS = frozenset(SCHEMA_TARGETS | {PROTOCOL})


def actual_methods(path: Path, class_name: str, method_names: set[str]):
    cls = next((x for x in ast.parse(path.read_bytes()).body
                if isinstance(x, ast.ClassDef) and x.name == class_name), None)
    if cls is None:
        raise StageBlocked("RESPONSES_CLASS_MISSING")
    methods = [x for x in cls.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name in method_names]
    if {x.name for x in methods} != method_names:
        raise StageBlocked("RESPONSES_METHODS_MISSING")
    return methods


def behavioral_test(serving_source: Path, protocol_source: Path) -> int:
    """Test the actual patched serving methods, not a standalone event oracle."""
    proto = protocol_source.read_text()
    for token in ('error: ResponseError | None = None', 'class ResponseFailedEvent(',
                  'class ResponseIncompleteEvent(', '| ResponseIncompleteEvent',
                  '    ResponseFailedEvent\n    | ResponseIncompleteEvent',
                  'ResponseFunctionCallArgumentsDeltaEvent',
                  'ResponseFunctionCallArgumentsDoneEvent',
                  '| ResponseFunctionCallArgumentsDeltaEvent',
                  '| ResponseFunctionCallArgumentsDoneEvent'):
        if token not in proto:
            raise StageBlocked("RESPONSES_TYPED_PROTOCOL_MISSING")
    class GenerationError(Exception):
        status_code = 500
    class ErrorResponse: pass
    class ResponseError:
        def __init__(self, **kw): self.__dict__.update(kw)
    class FakeResponse:
        def __init__(self, status): self.status = status; self.error = None
        def model_dump(self, **kw): return {"status": self.status}
        @classmethod
        def from_request(cls, request, sampling_params, **kw):
            return cls(kw["status"])
    class Event:
        def __init__(self, **kw): self.__dict__.update(kw)
    class SimpleStreamingEventProcessor:
        def __init__(self, tools): pass
        def resolve_target_state(self, msg): return 0, None
        def close_current(self): return []
    class DummyState:
        NONE = 0
    class SimpleContext:
        def __init__(self, text='', finished='stop', parser=None):
            output = SimpleNamespace(text=text, token_ids=[], finish_reason=finished)
            self.last_output = SimpleNamespace(outputs=[output], prompt_token_ids=[])
            self.response_parser = parser
    class FakeParser:
        has_invalid_tool_arguments = False
        def __init__(self, content): self.content = content
        def parse_delta(self, **kwargs): return SimpleNamespace(content=self.content, tool_calls=None)
        def parse(self, *args, **kwargs): return None, self.content, None
    scope = {
        "GenerationError": GenerationError, "ErrorResponse": ErrorResponse,
        "ResponseError": ResponseError, "ResponsesResponse": FakeResponse,
        "ResponseCreatedEvent": Event, "ResponseInProgressEvent": Event,
        "ResponseCompletedEvent": Event, "ResponseIncompleteEvent": Event,
        "ResponseFailedEvent": Event, "StreamingResponsesResponse": Event,
        "AsyncExitStack": AsyncExitStack, "SimpleStreamingEventProcessor": SimpleStreamingEventProcessor,
        "SimpleContext": SimpleContext, "_StateType": DummyState,
        "DeltaMessage": lambda **kw: SimpleNamespace(tool_calls=None,**kw),
        "as_list": list, "split_delta": lambda delta: [],
        "time": __import__("time"), "asyncio": asyncio,
    }
    names = {"responses_stream_generator", "_make_failed_response_event", "_process_simple_streaming_events", "_make_response_output_items", "responses_background_stream_generator"}
    available = [x.name for x in ast.parse(serving_source.read_bytes()).body if isinstance(x, ast.ClassDef) and x.name == "OpenAIServingResponses" for x in x.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
    names = names & set(available)
    if not {"responses_stream_generator", "_make_failed_response_event", "_process_simple_streaming_events", "_make_response_output_items"}.issubset(names):
        raise StageBlocked("RESPONSES_REQUIRED_METHOD_MISSING")
    body = actual_methods(serving_source, "OpenAIServingResponses", names)
    code = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),ast.ClassDef(name="RealPatchedServingMethods",bases=[],keywords=[],body=body,decorator_list=[])],type_ignores=[]))
    exec(compile(code,"<real-preview-responses-methods>","exec"),scope)
    cls = scope["RealPatchedServingMethods"]
    request = SimpleNamespace(tools=[], include_reasoning=True, request_id='offline')
    sampler = SimpleNamespace()

    async def empty_gen():
        if False: yield None
    async def one_delta(self,*a,**kw):
        yield a[-1](Event(type="response.output_text.delta", sequence_number=-1))
    async def raises(self,*a,**kw):
        raise GenerationError('private potentially sensitive model body')
        if False: yield None
    async def final_response(self,*a,**kw):
        if getattr(self, 'raise_final', False): raise GenerationError('private content')
        return self.final_status
    async def drive(status='completed', mode=None):
        x=cls(); x.use_harmony=False; x.final_status = status; x.raise_final=(mode=='raise_final')
        x._process_simple_streaming_events = (raises if mode=='raise_stream' else one_delta).__get__(x,cls)
        x.responses_full_generator=final_response.__get__(x,cls)
        out=[]
        async for ev in x.responses_stream_generator(request,sampler,None,None,'model',None,None,123):
            out.append(ev)
        return out
    cases=0
    terminal_map={'completed':'response.completed','incomplete':'response.incomplete','failed':'response.failed'}
    for status, expected in terminal_map.items():
        events=asyncio.run(drive(FakeResponse(status)))
        assert [v.type for v in events]==['response.created','response.in_progress','response.output_text.delta', expected],status
        assert [v.sequence_number for v in events]==[0,1,2,3],status
        if status=='failed': assert events[-1].response.error.code=='server_error'
        cases+=1
    for result in (ErrorResponse(), FakeResponse('cancelled'), FakeResponse('queued')):
        events=asyncio.run(drive(result))
        assert events[-1].type=='response.failed' and len(events)==4
        assert events[-1].response.error.message=='Model response could not be delivered'
        cases+=1
    for mode in ('raise_final','raise_stream'):
        events=asyncio.run(drive(FakeResponse('completed'),mode))
        assert events[-1].type=='response.failed' and 'response.completed' not in [e.type for e in events]
        assert events[-1].response.error.message=='Model response could not be delivered'
        cases+=1
    # The actual background SSE resume coroutine must terminate on every
    # terminal event, without waiting forever for a further background signal.
    for terminal in terminal_map.values():
        x=cls()
        x.event_store={'offline':(deque([Event(type='response.created'),
            Event(type=terminal)]),asyncio.Event())}
        async def replay():
            return [e.type async for e in x.responses_background_stream_generator('offline')]
        actual=asyncio.run(asyncio.wait_for(replay(),timeout=1))
        assert actual==['response.created',terminal]
        cases+=1
    # Resuming immediately after a terminal event should not manufacture a
    # duplicate terminal. The caller must not ask to resume beyond the end.
    # Actual streaming parser path, including a reasoning-only successful stop.
    async def run_simple(text, parser=None, finish='stop'):
        x=cls(); x.parser=None; x._raise_if_error=lambda *_:None
        async def data(): yield SimpleContext(text,finish,parser)
        result=[]
        async for e in x._process_simple_streaming_events(request,sampler,data(),None,'m',None,None,0,lambda x:x):
            result.append(e)
        return result
    for text,parser in (('',None),('   ',None),('secret reasoning',FakeParser(''))):
        try:
            asyncio.run(run_simple(text,parser))
        except GenerationError: pass
        else: raise StageBlocked('EMPTY_STOP_ACCEPTED')
        cases+=1
    asyncio.run(run_simple('valid answer'))
    cases+=1
    # Verify fallback nonstream output behavior via its real source method.
    x=cls();x.enable_log_outputs=False;x.request_logger=None;x.enable_auto_tools=True
    output=SimpleNamespace(text='',finish_reason='stop',logprobs=[],token_ids=[])
    request.is_include_output_logprobs=lambda:False
    for parser in (None,FakeParser('')):
        try: x._make_response_output_items(request,output,None,parser)
        except GenerationError: pass
        else: raise StageBlocked('NONSTREAM_EMPTY_STOP_ACCEPTED')
        cases+=1
    # Valid parser output is unaffected by the failure rule.
    scope["build_response_output_items"] = lambda **kw: [kw]
    x._make_response_output_items(request,SimpleNamespace(text='ok',finish_reason='stop',logprobs=None,token_ids=[]),None,FakeParser('ok'))
    cases+=1
    assert cases == 18,cases
    return cases


def verify(site: Path) -> dict:
    # Refuse replacing any already-installed schema module.
    if (site / NEW_MODULE).exists():
        raise StageBlocked('ARGUMENT_VALIDATOR_ALREADY_INSTALLED')
    originals = read_preview_sources(site,TARGETS)
    for name,pin in {**MARKER_PINS,**EXTRA_PINS}.items():
        if name in originals and hashlib.sha256(originals[name]).hexdigest()!=pin:
            raise StageBlocked('SOURCE_PREIMAGE_DRIFT')
    if RESPONSES_PATCH.is_symlink() or not RESPONSES_PATCH.is_file():
        raise StageBlocked('RESPONSES_PATCH_MISSING')
    payload = RESPONSES_PATCH.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=RESPONSES_SHA256:
        raise StageBlocked('RESPONSES_PATCH_SHA_DRIFT')
    with tempfile.TemporaryDirectory(prefix='p1-preview-responses-') as tmp:
        root=Path(tmp)
        for name,src in originals.items():
            file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(src)
        run_marker_schema_patches(root)
        if shutil.which('patch') is None:
            raise StageBlocked('PATCH_EXECUTABLE_MISSING')
        result=subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','--no-backup-if-mismatch'],input=payload,cwd=root,capture_output=True,timeout=12)
        if result.returncode:
            raise StageBlocked('RESPONSES_PATCH_CONTEXT_MISMATCH')
        for file in root.rglob('*.py'):
            ast.parse(file.read_bytes())
        cases=behavioral_test(root/SERVING,root/PROTOCOL)
    return {'status':'PREVIEW_NATIVE_RESPONSES_TERMINAL_METHODS_CPU_ONLY',
            'cases':cases, 'installed_vllm_modified':False,
            'gpu_model_http_run':False,'complete_vllm_parser_api_certified':False}


def main(argv:list[str])->int:
    if argv!=['--verify-installed']:
        print('STOP: --verify-installed required')
        return 2
    try:
        result=verify(find_installed_preview())
    except (StageBlocked, OSError, AssertionError, ValueError, SyntaxError, subprocess.TimeoutExpired) as e:
        print(json.dumps({'status':'BLOCKED_NOT_APPLIED','reason':str(e)[:90]}))
        return 2
    print(json.dumps(result,sort_keys=True))
    print('PREVIEW_P1_NATIVE_RESPONSES_TERMINALS_CPU_PASS_NOT_API_OR_DEPLOYED')
    return 0

if __name__=='__main__':
    sys.exit(main(sys.argv[1:]))
