# Track A Phase 5 — DGX Scheduler Factory / Mamba State Slot 소스 계약 실측 결과

> **2026-10-27 (Asia/Seoul). 상태: DGX_OFFLINE_UNIT_276_PASS / SOURCE_169_PASS / TEN_SOURCE_CHECKS_TRUE / NO_PATCH_APPROVAL / NO_ACTIVE_SCHEDULER_OR_BLOCK_EQUALITY_OR_STATE_SLOT_CERTIFICATION.**
>
> 실제 사용자 DGX 소스 브랜치: `feature/blazux-phase5-correctness-mtp-offline`, **소스 HEAD `a5376cc06536ce786cdb6db8425e26e21b608910`**. 증거는 사용자가 제공한 터미널 출력 (276 unittest 결과, Source Manifest, 설치된 vLLM 6파일 AST JSON, source-only 종료 마커). 이 보고서/Manifest가 들어간 **후속 docs-only HEAD는 DGX에서 별도로 재시험한 SHA가 아니다.**
>
> 외부 pinned blazux source `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. 분석은 installed preview의 Python source를 **읽기 전용으로 AST 검사**한 것이며 실제 blazux patch 실행, 실제 모델/서빙/GPU/HTTP/TPS/CI 검증이 아니다.

## 이후 별도 DGX source-only 3항목 보충 (전체 276 suite 재실행 아님)

- [새 3-check 소스 결과](BLAZUX-PHASE5-DGX-THREE-CHECKS-KERNEL-RESULTS-20261027.md): `SchedulerConfig.get_scheduler_cls`의 실제 async/default/custom 분기를 확인했고, `EngineCore v1/engine/core.py:321–324`의 `cache_config.block_size = min(group_spec.block_size)` 대입 경로를 발견. Mamba seed cache-config block 분모와 preprocess Mamba spec block 분모의 불일치 **가능성**을 구체화했으나 활성 숫자·실 오류/State Slot 정합성은 측정하지 않음.
- 세 번째 로그에서 `preprocess_mamba_align_fused_kernel`는 `src_col=old_state_idx`를 쓰고 새로운 index를 Mamba spec block-size로 계산, postprocess는 ctx.block_size로 fused kernel 호출. 그러나 `precopy_mamba_align_fused_kernel`/`postprocess_mamba_fused_kernel` 실제 본체 및 ctx.block_size 초기화 소스는 검색 대상에 포함되지 않아 **미검사**. CHECK2는 `SCAN_OUTPUT_LIMIT_REACHED`로 **PARTIAL**.
- 본 문서의 기존 **276/276 PASS는 test source `a5376cc06536ce786cdb6db8425e26e21b608910`에만 귀속**하며 이번 세 inspections 또는 docs-only Git HEAD가 전체 테스트 PASS를 새로 증명하지 않음. 실제 blazux patch 승인 0건 유지.

## 1. DGX에서 실제 확인된 Gate

```text
Ran 276 tests in 0.341s
OK
PHASE5_UNIT_PASS=276; XFAIL=0
PHASE5_SOURCE_AST_OK
PASS_SOURCE_ONLY: 169 tracked file(s)
  branch=feature/blazux-phase5-correctness-mtp-offline HEAD=a5376cc06536ce786cdb6db8425e26e21b608910
PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS
PHASE5_SCHEDULER_MAMBA_CONTRACT_DONE_NOT_PATCH_APPROVED
PASS: PHASE5_SCHEDULER_MAMBA_CONTRACT_EXECUTED_NOT_CERTIFIED
```

- 신규 분석기/합성 시험의 Python suite **276/276 PASS, XFAIL=0**; Source Manifest **169/169**; AST 및 전체 offline wrapper 종료 PASS.
- `scripts/phase5-check-offline.sh`가 완료된 것은 확인되지만 **이 발췌 로그에는 Wizard Mock 개별 시험 횟수·카운트가 나오지 않는다**. 정확한 `38/38`은 이전 소스 Gate의 기록으로 유지하고, 이번 확인 증거에 없는 숫자를 새 실측으로 만들지 않는다.
- `PHASE5_SCHEDULER_MAMBA_CONTRACT_DONE_NOT_PATCH_APPROVED`와 최종 `EXECUTED_NOT_CERTIFIED`는 source inspection **종료**를 뜻하며, **patch/ABI/실 cache correctness 승인 마커가 아니다**.

## 2. SchedulerConfig.get_scheduler_cls() 네 반환 위치

설치 소스 `config/scheduler.py` SHA256 `bf399abc7216b4801fbba5fd8f5cbc1960c9458d7519a544ae3015d83dd7a7d6`. `SchedulerConfig.get_scheduler_cls(self)` 170–191행:

| Source line | AST가 읽은 반환식 | 한계 |
|---|---|---|
| 175 | `AsyncScheduler` | 언제 선택하는지 분기 predicate는 이번 JSON에 없음 |
| 178 | `Scheduler` | 실제 운영 설정에서 이 기본 경로가 선택되는지 미확인 |
| 190 | `cast(type[...], self.scheduler_cls)` | `self.scheduler_cls` 값/타입 및 조건 미확인 |
| 191 | `resolve_obj_by_qualname(self.scheduler_cls)` | 문자열 qualname 및 실제 resolve 결과 미확인 |

`v1/engine/core.py` SHA256 `f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad`, `EngineCore.__init__`:
- 148행 `Scheduler = vllm_config.scheduler_config.get_scheduler_cls()`.
- 157행 `resolve_kv_cache_block_sizes(kv_cache_config,vllm_config)`.
- 161행 지역 `Scheduler(...)`에 `block_size`·`hash_block_size` keyword 전달 (이전 narrow AST 및 소스 확인 근거).

**판정:** 동적 config factory의 **정적 정의/연결 표현은 확인**됨. 이전 `engine_static_imports_scheduler=false`는 직접 import만 찾던 검사 범위의 한계. 그러나 **`active_scheduler_class_verified=false`**: 실제 config, 선택된 branch, custom override/AsyncScheduler 여부, 반환 클래스의 runtime signature는 아직 확인하지 않았다. 네 return 식의 의미를 분기 실행 증거로 오해하지 않는다.

## 3. Mamba source contract 10개 검사 TRUE — 그러나 slot correctness 미증명

JSON `source_checks` 열 가지:

| 체크 이름 | AST 결과 |
|---|---|
| `scheduler_config_factory_declared` | true |
| `engine_assigns_scheduler_from_config_factory` | true |
| `engine_calls_factory_result_scheduler` | true |
| `mamba_seed_uses_cache_config_block` | true |
| `mamba_group_checks_spec_block` | true |
| `mamba_preprocess_uses_group_spec_block` | true |
| `mamba_align_context_helper_declared` | true |
| `mamba_postprocess_fused_hook` | true |
| `scheduler_align_uses_cache_config_block` | true |
| `backend_reads_spec_block` | true |

`missing_source_checks=[]`, 모든 6개 소스 `PARSEABLE_ONLY`이고 아래 fingerprint와 일치. `events_truncated=false`로 관련 메서드의 선택된 이벤트 출력에서 잘림이 없음. 이는 코드의 분기/런타임 의미를 모두 검증한 뜻이 아니다.

| 파일 label | SHA256 |
|---|---|
| `scheduler_config` | `bf399abc7216b4801fbba5fd8f5cbc1960c9458d7519a544ae3015d83dd7a7d6` |
| `engine_core` | `f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad` |
| `scheduler` | `c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124` |
| `mamba_worker` | `2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0` |
| `mamba_backend` | `9658330915daf4f8019a214317eb4be366eb52fd75fce8075cbb80d9ed7d3f6c` |
| `cache_config` | `8790351601be188ed1cc7ad9de2af1978b238269da4724873af1185c91165ef6` |

핵심 AST 경로:
- `mamba_hybrid.py:116` — `(num_computed_tokens-1)//self.cache_config.block_size`를 state seed index에 사용.
- `mamba_hybrid.py:123` — `get_mamba_groups(kv_cache_config)`; :131 group IDs; :133 `(self._mamba_group_ids,self._mamba_spec)` 반환.
- `mamba_hybrid.py:142` — `_ensure_align_ctx` 경로에서 `get_mamba_groups(kv_cache_config)`; :175 `ctx` 반환. 이 **함수 존재만으로 align ctx의 실제 내부 계산은 검증되지 않음**.
- `mamba_hybrid.py:195–196` — `preprocess_state`에서 group info와 align ctx 획득; :218 `ctx.run_fused_precopy(...)` 호출. Source 검사에서 `MAMBA_BLOCK_SIZE=mamba_spec.block_size` 키워드 감지; 이는 실제 CUDA kernel 실행 결과가 아님.
- `mamba_hybrid.py:339` — `postprocess_state`의 `self._mamba_ctx.run_fused_postprocess_align(...)` 호출.
- `scheduler.py:392` — `_mamba_block_aligned_split`의 `block_size=self.cache_config.block_size`; :411/:415/:435 계산에서 local block_size로 정수 나눗셈, :417 partial-tail hash 경계에 `self.hash_block_size` 사용.
- `mamba_attn.py:510,600` — `self.kv_cache_spec.block_size`; :519/:607 별도 integer division 경로.
- `config/cache.py`는 PARSEABLE_ONLY지만 `CacheConfig.__post_init__`는 `METHOD_ABSENT`. **이것은 지정된 함수명의 메서드 부재만 의미**, CacheConfig class/field 초기화 기능 부재나 설정 불능을 뜻하지 않음.

### 3.1 합성 수치 Oracle — 실제 설정 결과 아님

| 가상 Config/Spec 블록 크기 | 입력 토큰 | `(N-1)//B_config` | `(N-1)//B_spec` |
|---|---:|---:|---:|
| 16 / 16 | 17 | 1 | 1 |
| 16 / 32 | 17 | 1 | 0 |
| 16 / 32 | 33 | 2 | 1 |
| 16 / 32 | 49 | 3 | 1 |

JSON의 `equal_blocks`에서 다른 index 없음; `different_blocks`에는 17/31/32/33/48/49/64 등 여러 차이 위치 기록. 이는 **가상 integer arithmetic**일 뿐 `MambaSpec.block_size`의 실제 수치, GPU kernel indexing contract, state slot corruption/실제 버그를 증명하지 않는다.

**엄격한 미검증 상태:** `active_scheduler_class_verified=false`, `actual_config_block_equality_verified=false`, `state_slot_correctness_verified=false`, `patch_approved=false`. 이번 출력으로 실 모델의 config 및 State Slot 정합성을 합격 처리하지 않는다.

## 4. 같은 Phase5 후속 안전 Gate

1. `config/scheduler.py:get_scheduler_cls` 170–191행의 **정확한 if/return branch 조건**, AsyncScheduler 조건, `scheduler_cls` override·qualname/source identity를 더 좁은 import-free AST로 정리한다. 실제 사용자 운영 설정에서 선택된 클래스는 독립적인 read-only config 증거 없이는 확정하지 않는다.
2. `CacheConfig` 및 `MambaSpec` 각 block-size 필드의 **설정 공급자·default·그룹 생성자**를 source-only 조사. `config.cache`와 spec 값의 equality는 개별 디바이스/모델 설정 증거 없이는 주장하지 않는다.
3. `_ensure_align_ctx` / `run_fused_precopy` / `run_fused_postprocess_align`와 실제 kernel block table/offset state seed/restore 계약을 소스 AST + **합성 CPU 경계 fixture**로 점진 확인. 실 CUDA/실 inference/output correctness/acceptance/TPS는 사용자 별도 승인 전 수행 금지.
4. 다른 blazux Tool Calling/Responses/Reduced Vocabulary MTP 계열도 이전의 **NO PATCH APPROVAL** 유지. blazux Mamba/Scheduler patch는 speculative “mismatch 있을 수 있음”만으로 실행하지 않는다.

## 5. 불변 규칙 / SHA 귀속

- 사용자 DGX에서 실제 통과한 새 코드 SHA는 `a5376cc06536ce786cdb6db8425e26e21b608910`: unit **276/276 XFAIL0**, Manifest **169/169**.
- 이 결과의 docs-only 기록 HEAD는 **DGX unit을 재실행한 HEAD가 아니다**. 새 Python 코드·patch·시스템 변경 없음.
- `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e`는 불변. 새 Phase·PR·Merge 없음, `main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지. 운영 Docker/모델/weights/HF cache/ports/GPU/HTTP/TPS/CI 조작·시험 금지.
