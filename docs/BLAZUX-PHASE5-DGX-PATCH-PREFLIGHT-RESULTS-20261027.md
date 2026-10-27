# Track A Phase 5 — DGX pinned blazux patch source-preflight 실측 결과 (2026-10-27)

> **최종 판정: PHASE5_PATCH_PREFLIGHT_SOURCE_ONLY_PASS / SOURCE_152_OF_152 / WIZARD_MOCK_38_OF_38 / UNIT_223_OF_223 / XFAIL_0 / PATCH_APPLY_NOT_APPROVED.**
>
> **실측 정확한 HEAD:** `feature/blazux-phase5-correctness-mtp-offline@2c7c6896430be0d9eada656f17edf97d9c5f4d3f`. 사용자 제공 DGX Spark 터미널 로그 `붙여넣은 텍스트(1)(20261027-074812).txt`의 출력만을 근거로 한다. GitHub에서 GPU·단위시험을 대신 재실행하지 않았으며, 본 보고서/manifest를 추가하는 **후속 docs-only SHA는 사용자 DGX에서 시험하지 않은 SHA**다.
>
> 비교용 고정 blazux 원본: [`8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa). 운영 Docker, 모델, GPU, HF cache, ports, 이전 Phase, `main`은 작업 대상이 아니다. **소스 속 이름/문자열 일치는 ABI 적합성/버그 존재/패치 적용 승인/GPU correctness를 의미하지 않는다.**

## 1. 실제 DGX 오프라인 통합 시험

```text
PHASE5_SOURCE_HEAD=2c7c6896430be0d9eada656f17edf97d9c5f4d3f
PASS_SOURCE_ONLY: 152 tracked file(s)
  branch=feature/blazux-phase5-correctness-mtp-offline HEAD=2c7c6896430be0d9eada656f17edf97d9c5f4d3f
manifest OK: kjlee-qwen38-dgx-spark-wizard, 4 target(s)
Ran 38 tests in 0.014s
OK
Ran 223 tests in 0.330s
OK
PHASE5_UNIT_PASS=223; XFAIL=0
PHASE5_SOURCE_AST_OK
PASS_SOURCE_ONLY: 152 tracked file(s)
PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS
NOT_VERIFIED: installed vLLM parser/cache ABI, real prefix hit, HTTP APIs,
NOT_VERIFIED: MTP acceptance, real PLE throughput, GPU/serving, CI
PHASE5_PATCH_PREFLIGHT_SOURCE_ONLY_DONE_NO_APPLY_APPROVAL
PASS: PHASE5_PATCH_PREFLIGHT_EXECUTED_NOT_CERTIFIED
```

- Source Manifest **전후 152/152**, Wizard mock **38/38**, 전체 unittest **223/223**, XFAIL/XPASS **0**, AST 및 fail-fast wrapper 성공.
- 기존 215개 unit의 오프라인 oracle/fixture에 Phase5 source-preflight용 신규 8개 unit가 추가됐다. 이로써 **새 HEAD의 소스-only Gate**에 대한 첫 DGX 실행 증거가 확보됐다.
- 설치 이미지의 **기존 파일을 읽기만 하는 임시 CPU container**에서 `src/phase5_patch_readiness.py` 실행. 도구 출력의 `components` 12개가 모두 `PARSEABLE_ONLY`. 명시적으로 `SOURCE_ONLY_NOT_PATCH_OR_ABI_CERTIFIED`.
- Source 검증 자체는 untracked/ignored, real model payload, Docker 전체 상태 및 serving runtime을 검증하지 않는다.

## 2. 패치별 실제 출력과 차단 요소

| 패치 계열 | 사용자 DGX `preflight.status` | 근거 및 다음 조건 |
|---|---|---|
| **Mamba + Scheduler / Prefix-cache** | `SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY` | Mamba legacy `self.cache_config.block_size` 1회, `mamba_block_size` 참조 0회. Scheduler `block_size = self.cache_config.block_size` 1회, `block_size = self.block_size` 0회. **cache config의 실제 `mamba_block_size` 생성·그룹 LCM·SSM state slot/복원 구조 검증 전 변경 금지** |
| **Tool Argument Schema** | `MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED` | ParserEngine/Qwen3/Adapter/Abstract Parser/Responses 사이 다중 파일 선행 변경과 새 `argument_validation` helper. JSON schema dependency·streamed partial argument·strict Chat/Responses 정책 미검증 |
| **Tool Literal Marker** | `MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED` | Streaming parser `_marker_is_literal` 0회, config `guard_literal_tool_markers` 0회. 실제 토큰 ID 및 부분 문자열 경계 미검증 |
| **Responses Terminal** | `PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED` | `ResponseCompletedEvent` 5회, `ResponseFailedEvent` 0회, `ResponseIncompleteEvent` 0회 (조사한 protocol 파일). serving `_make_failed_response_event` 0회, `response.failed` 0회, `response.incomplete` 0회. SSE/HTTP 오류 계약, streaming 상태 불명 |
| **MTP Reduced Draft Vocabulary** | `MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED` | NVIDIA `Qwen3_8FlashNextMTP.compute_logits`/ `load_weights` AST 함수 위치 확인. `self.lm_head` 4회, `self.logits_processor` 2회. 공유 `lm_head.weight` 소유권/weight shape/dtype/샤딩, vocab, sampling, acceptance·한국어/EOS/Tool 품질은 불명 |

다섯 분류 모두 **사전점검 결과**이며 `APPLY_APPROVED`/엔진 ABI 인증/실제 실행 PASS인 항목은 **0개**다. `SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY`는 해당 파일에서 일부 기존 문자열이 보인다는 뜻이지, pinned blazux patch의 전체 hunk/전후 제어 흐름이 일치한다는 뜻이 아니다.

## 3. 정확한 설치 소스 fingerprint (사용자 DGX 출력)

| label | SHA256 | 소스-only 관측 |
|---|---|---|
| `mamba` | `2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0` | `MambaHybridModelState.add_request(self,req_index,new_req_data)` lines 109–117, AST `277d0189…` |
| `scheduler` | `c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124` | `_mamba_block_aligned_split` lines 366–441, `_get_local_prefix_cache_hit` lines 443–453 |
| `parser_engine` | `f837bd5ae7bf759732a7d829209f93444b5692746d981509630c9bd3fcb39edb` | `_handle_tool_end` lines 844–884, `_compute_arg_delta` lines 920–961; 신규 argument helper 0회 |
| `qwen3` | `8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb` | `_check_skip_tool_parsing` 및 `_normalize_tool_arguments` 0회 |
| `adapters` | `2f9e31e13734b7df75d424f45cf39d723bef7c5415a9bc6851b121cbb6b4ae6d` | `prepare_tool_argument_schema`, rejection/error helper 0회 |
| `abstract_parser` | `53b13cd1f0becaaeca445ab27cfd0d0461e6be09383377062f955fd302c48c30` | Schema/rejection adapter helper 0회 |
| `stream` | `d00aba98ad26a2593e022a1faf5d048348d892822f75be40d19cf1dd522570f2` | `StreamingParserEngine.feed(self,delta_text,delta_token_ids)`, `finish(self)` |
| `config` | `f7350e0ca9124001684f1f874ee72bf6a34932d3e4b84cc84567bbccf2f3e4b9` | literal marker guard 0회 |
| `responses_protocol` | `7a853679f2488f2483dc0dd8352d5dfe91ed844e99ba970a5d3b95fa6b703db3` | completed event 관련 anchor 존재, failed/incomplete 미관측 |
| `responses_serving` | `d5fdb9ca62fa767d6feb61f6b3f5280f288051eea8605d27afa698cc00067968` | `_process_simple_streaming_events` lines 1344–1415 |
| `mtp_nvidia` | `d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6` | `Qwen3_8FlashNextMTP.compute_logits(self,hidden_states,spec_step_idx)` lines 465–468, AST `83eb59ba…`; `load_weights(self,weights)` lines 470–488 |
| `ple_nvidia` | `6690edcd2e2b2ae309b214991a060bffbdbbcdc42334e164db0aebcc0a5b397e` | `Qwen3_8FlashNextPLELayer.forward(self,hidden_states,input_ids,query_start_loc,ngram_context)` lines 1173–1211 |

SHA256은 source bytes, AST 지문은 특정 함수의 구문 트리 hash이다. 설치 이미지 업데이트/ABI drift 시 재조사가 필요하다. 이러한 hash가 일치해도 **실제 inference 출력·caching·수정 효과가 검증되는 것은 아니다**.

## 4. 다음 실제 개발 우선순위 (여전히 Phase 5 / GPU 미사용)

1. **Mamba/Scheduler**: pinned blazux `patch_mamba_block_size.py`의 정확한 preimage 2곳과 설치 소스 해당 함수의 주변 문맥을 단계별 비교. `cache_config.mamba_block_size` 필드 공급자, `self.block_size` 그룹 LCM 생성 및 SSM state-slot seed/restore의 단위가 동일한지 읽기 전용 source 검사 + 합성 CPU fixture로 우선 검증. 불명인 경우 `BLOCKED_BY_CACHE_CONFIG`.
2. **Tool/Responses**: argument-schema, literal-marker, safe-output 패치에 들어 있는 변경 경로의 dependency graph/원래 함수 시그니처/추가 모듈 경로를 비교. Partial tool output·요청별 schema·Chat passthrough vs Responses reject·SSE terminal 상태에 대한 오프라인 fixture 확장. **설치 엔진 직접 patch 금지**.
3. **MTP**: `lm_head` 공유 진입점, `compute_logits` 구현(4 line) 및 `load_weights`의 원래 shape/weight naming, `logits_processor.org_vocab_size`와 실제 MTP 31 BF16 텐서 계약을 소스만으로 연결 확인. Reduced vocabulary는 명시적 opt-in 전제, EOS/한국어/Tool 품질·acceptance 실제 검증 전 기본 OFF/미적용.
4. **실 모델 GPU/HTTP**: 승인받지 않은 상태라 여전히 `NOT_RUN`. Phase6 후보 계획으로만 보관하고 운영 모델/컨테이너에 적용하지 않는다.

**Phase 수 최소화:** 위 1~3번의 같은 CPU/source-only 승인 경계 작업은 새로운 Phase를 만들지 않고 현재 Phase 5 브랜치에서 이어서 수행한다. 보고서는 정확한 사용자 실측 SHA와 docs-only 커밋 SHA를 구별한다.

**GitHub/PR 보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` 불변. 지금 PR/Merge 불필요. 필요해도 Phase5→Phase4 **비병합 Draft**만 리뷰용으로 허용하고 `main` 대상 PR/merge/cherry-pick/rebase/squash/sync 영구 금지.
