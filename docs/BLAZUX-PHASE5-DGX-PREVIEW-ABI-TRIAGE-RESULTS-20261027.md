# Track A Phase 5 — DGX 설치 preview vLLM ABI 읽기 전용 조사 실측 보고서

> 날짜: 2026-10-27 (Asia/Seoul). **Gate: SOURCE_TRIAGE_RUN_PASS / UNIT_215_XFAIL_0 / SOURCE_MANIFEST_148_148 / ABI_COMPATIBILITY_NOT_CERTIFIED / ENGINE_NOT_PATCHED / GPU_NOT_RUN / CI_NOT_RUN.**
>
> **근거:** 사용자 제공 DGX 터미널 출력(붙여넣은 텍스트(1)(20261027-071750).txt, 304행 분량). 실제 실행된 정확한 코드: `feature/blazux-phase5-correctness-mtp-offline@9e2d1647357938f6d465eb9b3ce473d03e38e779`. 이 보고서와 handoff/Manifest만 변경한 후속 Git HEAD는 사용자 DGX에서 재실행하지 않았다. 운영 Docker/모델/소스는 조사 대상으로만 사용했으며 실 배포 및 변경 여부를 보증하는 독립 runtime 감사 결과는 없다.
>
> 외부 blazux 비교 고정 SHA: [`8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa). `main`, P0, Phase1~4 보호; 같은 Phase5에서 계속 진행하고 PR/Merge 금지.

## 1. 전체 DGX 시험 결과 및 출처

```text
PHASE5_SOURCE_HEAD=9e2d1647357938f6d465eb9b3ce473d03e38e779
PASS_SOURCE_ONLY: 148 tracked file(s)
  branch=feature/blazux-phase5-correctness-mtp-offline HEAD=9e2d1647357938f6d465eb9b3ce473d03e38e779
manifest OK: kjlee-qwen38-dgx-spark-wizard, 4 target(s)
Ran 38 tests in 0.014s
OK
Ran 215 tests in 0.409s
OK
PHASE5_UNIT_PASS=215; XFAIL=0
PHASE5_SOURCE_AST_OK
PASS_SOURCE_ONLY: 148 tracked file(s)
PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS
PHASE5_PREVIEW_ABI_SOURCE_AUDIT_DONE_NOT_COMPATIBILITY_CERTIFIED
PASS: PHASE5_READONLY_ABI_TRIAGE_EXECUTED_NOT_CERTIFIED
```

사용자가 제공한 상세 로그에 의해 **Source Manifest 148/148, Wizard mocks 38/38, full unittest 215/215, XFAIL=0**, source AST 검사, bounded import-free source inventory 종료를 확인했다. `scripts/phase5-check-offline.sh`의 fail-fast 끝부분까지 도달했으므로 각 필수 검사 명령은 비영(非零) 종료 없이 완료했다. Source 검증은 untracked/ignored files, weights, 운영 Docker와 runtime을 확인하지 않는다.

## 2. 기존 조사기의 고정 경로 오류 해소 — 실제 NVIDIA/AMD MTP 및 PLE 경로

**이전 `ABSENT_OR_RELOCATED`는 경로 가정 오류**다. 실제 설치 vLLM의 package-root-relative `models/...` 트리에 다음 Python 파일이 있다. 파일 SHA는 사용자 설치 이미지에서 read-only 계산된 SHA256이다.

| 경로 | 설치 SHA256 | AST 확인 |
|---|---|---|
| `models/qwen3_8_flash_next/nvidia/mtp.py` | `d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6` | `Qwen3_8FlashNextMTP`, `Qwen3_8FlashNextMultiTokenPredictor` |
| `models/qwen3_8_flash_next/nvidia/ple_layer.py` | `6690edcd2e2b2ae309b214991a060bffbdbbcdc42334e164db0aebcc0a5b397e` | `Qwen3_8FlashNextNGramEmbedding`, `Qwen3_8FlashNextPLEFp8EmbeddingMethod`, `Qwen3_8FlashNextPLEGroupedNorm`, `Qwen3_8FlashNextPLELayer` |
| `models/qwen3_8_flash_next/nvidia/model.py` | `e74a0bf92ed73306ed28366543b00255b23ac7ec3f705b600ff0c8874442f0c6` | `Qwen3_8FlashNextForCausalLM` 등 |
| `models/qwen3_8_flash_next/amd/mtp.py` | `7735cee47d0d1e4776bebd30d907e4a62160409ce4ef2d65611559f8d58af431` | 동일 MTP 클래스 이름 (AMD 전용 구현) |
| `models/qwen3_8_flash_next/amd/ple_layer.py` | `90a09cafec33e7b69d46aa3a21a79ed386b6b7e55a55e5ac5c336de2b50a711a` | AMD PLE 클래스 |
| `models/qwen3_8_flash_next/amd/model.py` | `d900cd6fcacba18f460e00b3f018fbf36fbe6ecc310692b6adb1451f7f53cc17` | AMD 모델 본체 |

NVIDIA `Qwen3_8FlashNextMTP.compute_logits(self, hidden_states, spec_step_idx)`; `forward(self, input_ids, positions, hidden_states, intermediate_tensors, inputs_embeds, spec_step_idx)`; `load_weights(self, weights)`를 확인했다. NVIDIA PLE `Qwen3_8FlashNextPLELayer.forward(self, hidden_states, input_ids, query_start_loc, ngram_context)`를 확인했다. 이 인자는 AST에 나타난 것이며 **가중치/모델의 실제 로드·호출·shape/dtype 검증이 아니다**. AMD와 NVIDIA는 별도 파일이므로 혼용 금지.

## 3. blazux 관련 Preview 소스 anchor — 현재 사용자 DGX 실측

| 컴포넌트 | SHA256 (설치 source) | 관측 |
|---|---|---|
| `v1/worker/gpu/model_states/mamba_hybrid.py` | `2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0` | `MambaHybridModelState.add_request(self,req_index,new_req_data)`; `legacy_small_block_expression=true`, `direct_mamba_block_expression=false`, `mamba_block_field=false` |
| `v1/core/sched/scheduler.py` | `c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124` | `Scheduler._mamba_block_aligned_split` 존재, `legacy_cache_block_assignment=true`, `scheduler_block_assignment=false` |
| `parser/engine/parser_engine.py` | `f837bd5ae7bf759732a7d829209f93444b5692746d981509630c9bd3fcb39edb` | `ParserEngine._handle_tool_end(self,event,deltas)` 존재. `_normalize_tool_arguments`/`_arguments_block_emission`/`_skip_incomplete_tool_slot` 미발견 |
| `parser/qwen3.py` | `8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb` | `Qwen3Parser.extract_reasoning(self,model_output,request)` 확인, `_check_skip_tool_parsing` 미발견 |
| `parser/engine/streaming_parser_engine.py` | `d00aba98ad26a2593e022a1faf5d048348d892822f75be40d19cf1dd522570f2` | `feed(self,delta_text,delta_token_ids)`, `finish(self)`; `_marker_is_literal` 미발견 |
| `parser/engine/parser_engine_config.py` | `f7350e0ca9124001684f1f874ee72bf6a34932d3e4b84cc84567bbccf2f3e4b9` | `guard_literal_tool_markers=false` (문자열 미발견) |
| `entrypoints/openai/responses/serving.py` | `d5fdb9ca62fa767d6feb61f6b3f5280f288051eea8605d27afa698cc00067968` | `OpenAIServingResponses._process_simple_streaming_events` 존재; `_make_failed_response_event`, `response.failed`, `response.incomplete` 관련 hint 미발견 |
| `entrypoints/openai/responses/protocol.py` | `7a853679f2488f2483dc0dd8352d5dfe91ed844e99ba970a5d3b95fa6b703db3` | `ResponsesRequest`, `ResponsesResponse`, `ResponseCompletedEvent` 등 class 이름 존재 |

**위 source 명칭/해시가 해당 블록 계산이 틀리다거나 blazux 패치를 그대로 적용할 수 있음을 입증하지 않는다.** 캐시 state lifecycle, scheduler block-size 의미, 실제 parser 사용 경로, stream terminal sequence를 연결해 source 본문 수준으로 확인해야 한다.

## 4. 중요 제한 및 패치 후보 분류

- `model_search.state=CANDIDATE_LIMIT_REACHED`; `matched_file_count=43`, **출력 후보 32개**, Python 파일 탐색 `visited=536`. 따라서 모델 전체 후보 감사가 완료되었다고 기록하면 안 된다. 다만 이번 목표였던 NVIDIA·AMD Qwen3.8 MTP/PLE/모델 source는 출력 후보에 **포함되어 실제 파일 SHA와 클래스명을 확인**했다.
- **Mamba state index / Scheduler block**: `SOURCE_ANCHOR_CANDIDATE` — blazux 고정 patch가 찾는 legacy 표현 존재. 향후 읽기 전용 `add_request`, `_mamba_block_aligned_split`, KV cache config 및 slot allocation 부분 소스 본문을 같이 비교해야 한다. 런타임 패치 및 GPU state mutation 금지.
- **Qwen Tool Calling / Responses**: `SOURCE_ANCHOR_CANDIDATE_WITH_MISSING_METHODS` — blazux가 새로 추가하는 helper/terminal 이벤트가 조사기 지정 파일에는 보이지 않는다. patch 구조·순서, dependency 및 parser 서버 설정을 검증하기 전에는 적용 금지.
- **MTP reduced draft vocabulary**: `MTP_CLASS_AND_COMPUTE_LOGITS_LOCATED_NOT_COMPATIBILITY_CERTIFIED`. blazux의 reduced draft vocab 관련 hook 대상 `compute_logits(...,spec_step_idx)` 클래스/메서드 형태는 후보와 일치하지만 실제 lm_head 구조, group/shard/weight-loader, token map, acceptance 및 생성 품질 미검증. **기본 OFF/미적용**.
- **PLE**: `NVIDIA_PLE_PATH_LOCATED_SOURCE_ONLY`. 이미 검증한 BF16 mmap synthetic CPU 동등성과 혼동하지 않는다. 설치된 원본 PLE 로더/FP8용 `Fp8EmbeddingMethod` 등의 실제 instance 사용·weight/mmap 오류 여부는 이 조사로 확인되지 않는다.
- **기술적 Go/No-Go**: 사용자 DGX 증거로 **읽기 전용 AST/source 탐색 Gate는 PASS**. 실제 `preview vLLM ABI`·원본 패치의 안전한 이식·Prefix-cache 정확성·Tool/Responses 서버 정합성·GPU/MTP acceptance는 **OPEN/NOT_VERIFIED**. source slice와 exact anchor predicate 정밀 비교, 별도 mock/CPU isolated tests를 먼저 준비한다.

## 5. 이후 같은 Phase 5에서 진행할 작업

1. 외부 pinned blazux 패치 원문과 실제 설치 소스에서 **대상 함수 일부**를 읽기 전용으로 수집하여 도입 경로/기존 구현/미일치점을 확정한다. 특히 Mamba state index, Scheduler block, ParserEngine argument-schema, Qwen3 parser, Responses protocol/serving 및 `models/qwen3_8_flash_next/nvidia/mtp.py`를 우선. 프라이빗 절대경로/환경값/weights payload는 출력하지 않는다.
2. patch-by-patch `SAFE_OFFLINE_PATCH_CANDIDATE` / `ABI_MISMATCH` / `ALREADY_PRESENT` / `INCONCLUSIVE`로 상태 정의; 현재 보고서의 anchor 후보를 곧바로 `SAFE`로 승격하지 않는다. 실제 코드 수정이 필요하면 **Phase5 전용 소스/격리 fixture만** 대상. 기존 preview 이미지, 운영 container 및 main을 직접 수정하지 않는다.
3. 실제 GPU/serving endpoint, cached-vs-uncached generation, 실 95GiB PLE 및 MTP acceptance/TPS는 사용자 명시적 승인 후 격리 자원 계획을 별도 수립. Track B vLLM 0.32는 계속 별도 승인. YaRN 500K/Hybrid FP8 보류.

**GitHub 보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e`는 불변. 현재 PR/Merge 불필요; 필요하면 Phase5 head→Phase4 base Draft 리뷰 전용이며 비병합. **main PR/Merge/Cherry-pick/Rebase/Squash/Sync 절대 금지.**
