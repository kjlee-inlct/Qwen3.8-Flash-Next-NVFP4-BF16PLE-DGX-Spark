# Track A Phase 5 — DGX Preview vLLM AST 의존성 추적 실측 결과

> 2026-10-27 Asia/Seoul · **SOURCE_DEPENDENCY_TRACE_COMPLETED / MAMBA_BLOCK_CONFIG_SOURCE_LOCATED / NVIDIA_MTP_HEAD_BRANCHES_IDENTIFIED / NO_PATCH_APPROVAL / UNIT_233_NOT_EVIDENCED / GPU_NOT_RUN**.
>
> **출처:** 사용자 제공 `붙여넣은 텍스트(1)(20261027-091133).txt`의 JSON 및 `PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED` 종료 마커. 바로 앞 대화에서는 `PASS: PHASE5_DEPENDENCY_TRACE_EXECUTED_NOT_CERTIFIED` 마커도 보고됐음. **사용자가 실행한 명령의 `EXPECTED` 체크는 `2cadc7369b4b813332a767733faa9c2529413cd9`이나, JSON 자체에 Git HEAD는 내장되지 않는다. 이 로그의 SHA 귀속은 실행 명령과 대화 맥락에 근거한다.**
>
> 사용자 메시지에 이번 새 HEAD의 `PHASE5_UNIT_PASS=233; XFAIL=0`, `PASS_SOURCE_ONLY: 156 tracked file(s)`, mock 결과는 포함되지 않았으므로 **이번 기록에서 233/233 또는 156/156을 실기 검증 PASS로 승격하지 않는다**. 직전 DGX 전체 테스트의 확정 증거는 소스 `2c7c6896430be0d9eada656f17edf97d9c5f4d3f`의 Source 152/152, mocks 38/38, unittest 223/223 XFAIL0. 후속 docs-only HEAD는 DGX 재시험한 SHA가 아니다.
>
> blazux 외부 pinned source: `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. 이 결과는 **설치된 preview vLLM Python 소스의 read-only AST 탐색**이며 실제 prefix hit, SSM state restore, Tool Calling/SSE, speculative MTP acceptance, PLE 95GiB/NVMe/GPU, TPS/TTFT, CI, 패치 적용이나 ABI 호환성 인증이 아니다.

## 1. 실행 확인 및 추적 범위

- 출력 마커 `PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED` 확인. 응답 `status=AST_DEPENDENCY_EVIDENCE_ONLY_NOT_SEMANTIC_OR_ABI_CERTIFIED`, `not_patch_approved=true`, 외부 pin 일치.
- `components`의 8개 대상(Mamba, Scheduler, ParserEngine, Qwen3, streaming, Responses serving, NVIDIA MTP 및 PLE)은 **PARSEABLE_ONLY**이며 각각 설치 소스 SHA256이 앞선 ABI/preflight 조사 값과 일치.
- `mamba_field_scan`: `state=SCANNED_READ_ONLY`; 384개 Python 소스 파일 검사, **6,448,206 bytes**, `unreadable=0`. `config`와 `v1` 범위에서 13개의 STORE/LOAD AST site 확인. 검사 범위 밖의 동적 속성 대입, 외부 config/launcher 또는 실행 시 인자 값을 입증하지 않음.

## 2. Mamba `mamba_block_size` 실제 정의/참조 후보 발견

| source path:line (vLLM package root-relative) | AST 결과 | 해석 경계 |
|---|---|---|
| `config/cache.py:125` | `STORE mamba_block_size` | 필드 정의/대입 구문 후보. config 객체 런타임 필드 채움 인증 아님 |
| `config/cache.py:267` | `LOAD self.mamba_block_size` | CacheConfig 내부 참조 |
| `config/vllm.py:2535–2536` | `LOAD self.cache_config.mamba_block_size` 2곳 | VllmConfig-level 접근 후보 |
| `v1/attention/backends/mamba_attn.py:510` | `STORE mamba_block_size` | backend **로컬 이름 대입**. CacheConfig 필드 공급자로 오인 금지 |
| `v1/attention/backends/mamba_attn.py` | `LOAD mamba_block_size` 여러 곳 | backend 사용처. source scan에서 399/408/417/516/407/519/398/416행 등이 반환됨 |

**중요 결론:** 이전 preflight의 `MambaHybridModelState` 소스에서 `self.cache_config.mamba_block_size` 참조 건수 0은 **해당 파일의 한정 결과**다. 이번에 `config/cache.py`와 `config/vllm.py`에서 별도 필드 정의/접근 구문이 발견되었으므로 **전역 미존재 가정은 반박됐다**. 반면 `MambaHybridModelState.add_request`는 아래 기존 나눗셈을 그대로 사용한다.

```text
v1/worker/gpu/model_states/mamba_hybrid.py:109–117
  line116: floor_div(
      new_req_data.num_computed_tokens - <number>,
      self.cache_config.block_size
  )
v1/worker/gpu/model_states/mamba_hybrid.py:177–224
  preprocess_state: watched attribute mamba_spec.block_size
v1/worker/gpu/model_states/mamba_hybrid.py:306–345
  postprocess_state: self._mamba_ctx.run_fused_postprocess_align(...)

v1/core/sched/scheduler.py:70–364
  line174: self.block_size = block_size [ctor argument]
v1/core/sched/scheduler.py:366–441
  line392: block_size = self.cache_config.block_size
  line396: request.num_tokens % block_size
  line411/415: end // block_size, start // block_size
  line417: request.num_prompt_tokens // self.hash_block_size
  line424: start % block_size
  line435: (request.shared_prefix_boundary - start) // block_size
v1/core/sched/scheduler.py:443–453
  _get_local_prefix_cache_hit -> kv_cache_manager.get_computed_blocks(...)
```

`Scheduler.__init__`은 `block_size` 인자를 받아 `self.block_size`에 저장한다. **여기서 LCM 자체를 계산한 흔적은 없음**. LCM/하이브리드 그룹 정렬/실제 블록 크기 계산은 `Scheduler(...,block_size=...)` 호출자를 추적해야 확인할 수 있다. `self.hash_block_size`는 별도 단위로 등장한다. 따라서 `cache_config.block_size`를 `self.block_size`로 무조건 교체하거나 Mamba seed만 바꾸면 안 된다.

**후속 PASS 필요조건:** (a) `config/cache.py`의 생성자/field validator 및 `config/vllm.py`의 값 준비, (b) `Scheduler(block_size=...)`의 실제 호출자와 LCM/group 길이, (c) `MambaHybridModelState.add_request`가 사용하는 state slot tables와 pre/post-process의 `mamba_spec.block_size` 단위, (d) aligned/misaligned 캐시 경계 synthetic tests, 모두 독립적으로 연결 확인.

## 3. NVIDIA MTP 출력 Head 경로 — 단일 tensor subset이 안전하다는 뜻 아님

실제 파일: `models/qwen3_8_flash_next/nvidia/mtp.py`, SHA256 `d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6`.

- `Qwen3_8FlashNextMTP.__init__(self,vllm_config,prefix)` lines404–442: `self.lm_head`에 **조건별로** `self.model.embed_tokens` (line425), `ParallelLMHead(config.vocab_size,config.hidden_size,...)` (line427), `PPMissingLayer()` (line435) 대입 구문 확인. `self.logits_processor=LogitsProcessor(config.vocab_size)` (line437).
- `compute_logits(self,hidden_states,spec_step_idx)` lines465–468은 `self.logits_processor(self.lm_head,hidden_states)`를 반환. `spec_step_idx`는 서명에 있으나 해당 반환 표현에 직접 전달되지 않는다. 이는 정적 함수 표현에 한정된다.
- `load_weights(self,weights)` lines470–488은 `AutoWeightsLoader`, `_qwen38_validate_native_mtp_checkpoint`, `_remap_mtp_weight_name`, `remap_weight_names`를 호출하는 경로를 포함한다. **원래 BF16 MTP 31개 텐서의 명칭/분산/일치 보장은 이 분석으로 증명되지 않는다**.
- `forward(...,spec_step_idx)`는 `self.model(...,spec_step_idx=spec_step_idx)`를 반환. 실제 draft token ID와 acceptance 품질은 별도 시험.
- blazux `VLLM_MTP_DRAFT_VOCAB` 패치가 단순 `self.lm_head.weight` 행 축소를 가정하면 **공유 embedding / 독립 ParallelLMHead / pipeline-parallel missing head 및 logits processor vocabulary** 계약에 충돌할 수 있으므로 현재 **MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED**를 유지. 품질·정합성·한국어/EOS/Tool Calling·TP/dtype/메모리 실측 전 적용 금지.

## 4. Tool Calling/Streaming Parser/Responses 호출 관계

| 컴포넌트 | Source AST 근거 | 남은 조건 |
|---|---|---|
| `ParserEngine._handle_tool_end` 844–884 | `self._flush_arg_converter`, `self._accept_tool_name`, `self._ensure_tool_id`, `find_tool_properties`, `self._try_extract_name` 등 호출 | 실제 parser stream state/token ID, offered tool schema 검증 |
| `ParserEngine._compute_arg_delta` 920–961 | `converter`, `self._fix_arg_types`, `self._safe_arg_prefix` 등 호출 | partial JSON, nested tool wrapper, 미허용 name 분리 |
| `ParserEngine._flush_arg_converter` 963–985 | `converter`, `self._fix_arg_types` 호출 | failed/partial arguments finalize 안전성 |
| `Qwen3Parser.extract_reasoning` 247–254 | `super().extract_reasoning(model_output,request)` 또는 `(None,model_output)` 반환 표현 | 실제 reasoning/tool boundary |
| `StreamingParserEngine.feed` 212–257 / `finish` 282–332 | lexer/scanner/event 관련 호출, `events` 반환 | literal marker, chunk segmentation, token-ID edge |
| `OpenAIServingResponses._process_simple_streaming_events` 1344–1415 | `ctx.response_parser.parse_delta`, `processor.emit_delta`, `processor.close_current`, `self._raise_if_error` 등 | failed/incomplete terminal event 및 SSE wire 검증 |

`_buffer_ambiguous_arguments`, `Qwen3Parser._check_skip_tool_parsing`, `_normalize_tool_arguments`, `OpenAIServingResponses._make_failed_response_event` 등은 지정 클래스 메서드 AST에서 **없음(null)**. 관련 기능이 다른 helper에 있거나 upstream과 구현 방식이 다를 수 있으므로 부재만으로 버그/patch 가능을 확정하지 않는다.

이전 **`MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED` / `PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED` 유지**. 실제 API/클라이언트/엔드포인트 호출 없음.

## 5. PLE forward 소스와 소형 CPU Gather는 다른 경로

NVIDIA `models/qwen3_8_flash_next/nvidia/ple_layer.py`의 `Qwen3_8FlashNextPLELayer.forward` lines1173–1211은 `self.ple_embedding`, `_dequantize_embeddings`, `self._apply_norm`, `qwen3_8_flash_next_ple_short_conv`, gating/projection을 포함. 이는 **실 엔진 inference의 계산 그래프 소스**다. Phase4/5에서 검증한 `VLLM_PLE_FAST_GATHER`·synthetic BF16 mmap row gather CPU 벤치가 이 실제 forward 경로의 성능 향상으로 이어졌다고 단정하지 않는다.

## 6. 다음 같은 Phase 5 우선순위 / Go-No-Go

1. **Mamba/Scheduler:** `config/cache.py:125/267`, `config/vllm.py:2535/2536`, 실제 Scheduler 생성자 호출자, `v1/attention/backends/mamba_attn.py`의 block 계산 source-only 범위를 좁혀 field→block size→state slot map을 연결하는 **추가 소스 계약 검증**. 저장·복원 테스트는 합성 fixture로.
2. **Parser/Responses:** pinned blazux patch 파일별 실제 source preimage의 다중 파일 변경 관계와 trace에서 발견한 parser/converter/streaming 함수 호출을 연결하고, strict tool schema/terminal event 조건을 별도 synthetic fixture로. 실제 HTTP endpoint는 승인이 필요.
3. **MTP:** 조건부 `lm_head` 세 가지 분기/체크포인트 명칭 재매핑/processor vocabulary 및 safe opt-in 정책을 source+CPU fake-head fixture로 검증. shared real tensor patch는 승인 전 금지.
4. **증거 미완료:** 이번 업로드는 trace JSON+종료 marker만 포함. **223→233 신규 유닛 실행 로그, Source Manifest 156/156, mocks**의 실제 결과는 별도 출력 또는 기존 전체 로그에서 확인해야 한다. 해당 결과를 추측해서 PASS로 기록하지 않는다.
5. **GPU/운영/Phase 경계:** 같은 CPU/source-only 분석은 Phase5 내 지속; 실제 vLLM patch/모델 inference/GPU/TPS/HTTP/Track B는 별도 승인 전 `NOT_RUN`. `main` PR/merge/cherry-pick/rebase/squash/sync 금지, P0/Phase1~4 refs immutable.

**중요:** 새 문서·handoff·manifest를 별도 커밋할 경우에는 사용자 DGX trace에 사용된 소스 SHA `2cadc736...`와 구분하여 **docs-only HEAD 미실측**으로 기록한다.
