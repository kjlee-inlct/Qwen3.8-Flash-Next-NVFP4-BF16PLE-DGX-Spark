# Track A Phase 5 — DGX Narrow KV LCM → EngineCore Scheduler Source-Flow 실측

> **2026-10-27 (Asia/Seoul) / DGX CPU-only Gate PASS / source chain 5-of-6 / one import unresolved / NO_PATCH_APPROVAL / NO_RUNTIME_ABI_OR_GPU_CERTIFICATION.**
>
> **사용자 DGX 실제 시험 소스** `feature/blazux-phase5-correctness-mtp-offline@bc89de6288889943b50090ac9638ee95c2434a79`. 사용자 제공 터미널 기록 `붙여넣은 텍스트(1)(20261027-112439).txt` (410줄)에서 전체 테스트/JSON/마커를 확인했다. **이 보고서와 Source Manifest를 포함한 후속 docs-only Git SHA는 재시험 소스 HEAD가 아니다.**
>
> 고정 외부 blazux source pin `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. 오프라인 Python AST 출력은 실제 서비스 동작/SSM state slot correctness/ABI/GPU/MTP acceptance/PLE throughput/HTTP/TPS/CI를 인증하지 않는다.

## 1. 사용자 실제 DGX 결과

```text
PHASE5_SOURCE_HEAD=bc89de6288889943b50090ac9638ee95c2434a79
PASS_SOURCE_ONLY: 164 tracked file(s)
manifest OK: kjlee-qwen38-dgx-spark-wizard, 4 target(s)
Ran 38 tests in 0.014s
OK
Ran 259 tests in 0.369s
OK
PHASE5_UNIT_PASS=259; XFAIL=0
PHASE5_SOURCE_AST_OK
PASS_SOURCE_ONLY: 164 tracked file(s)
PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS
PHASE5_NARROW_BLOCK_FLOW_DONE_NOT_PATCH_APPROVED
PASS: PHASE5_NARROW_BLOCK_FLOW_EXECUTED_NOT_CERTIFIED
```

- Source Manifest **164/164**, Wizard mock **38/38**, 전체 unittest **259/259**, XFAIL **0**, AST/Bash/발행 검증을 포함한 기존 오프라인 wrapper PASS.
- 임시 CPU-only source inspection은 고정된 설치 Python 파일 6개를 `PARSEABLE_ONLY`로 분석. `patch_approved=false`, `runtime_flow_proven=false`. 이번 narrow output의 `bounded_output_truncated=false`는 **해당 6파일 조사에만 한정**. 이전 광역 Scheduler scan의 `ASSIGN_SITE_LIMIT=64` / PARTIAL 상태는 별도 역사적 사실로 유지.
- 설치 vLLM 파일은 읽기 전용으로 조사했으며 운영 container/원본 모델 payload/HF cache/실 HTTP·GPU·모델 추론/실 prefix hit·CI 실행을 검증하지 않는다.

## 2. KV group scheduler block-size 값의 정적 공급 경로

| 설치 Python 소스:라인 | 소스 AST 관측 | 검증 경계 |
|---|---|---|
| `v1/core/kv_cache_utils.py:634` | `group_block_sizes = [g.kv_cache_spec.block_size * dcp if isinstance(g.kv_cache_spec, AttentionSpec) else g.kv_cache_spec.block_size for g in groups]` | **AttentionSpec** 그룹은 `dcp` 배수 적용. 다른 그룹은 spec block-size 사용. `dcp`의 실제 런타임 값 및 해당 모델의 그룹 구성은 미검증 |
| `v1/core/kv_cache_utils.py:640` | `scheduler_block_size = math.lcm(*group_block_sizes)` | 해당 코드 경로에서의 LCM 계산 |
| `v1/core/kv_cache_utils.py:659` | `hashing_sizes = [block_size for group, block_size in zip(groups, group_block_sizes) if group.kv_cache_spec.prefix_cacheable] or group_block_sizes` | Prefix-cache 가능 그룹 우선, 비어 있으면 전체 그룹 후보 |
| `v1/core/kv_cache_utils.py:665` | `hash_block_size = requested if requested is not None else math.gcd(*hashing_sizes)` | 명시 요청값 또는 GCD. **Scheduler block-size LCM과 별도 의미** |
| `v1/core/kv_cache_utils.py:673` | `return scheduler_block_size, hash_block_size` | 일반 반환값 형태 |
| `v1/engine/core.py:157` | `scheduler_block_size, hash_block_size = resolve_kv_cache_block_sizes(kv_cache_config, vllm_config)` | **반환값의 직접 tuple 대입 표현** 및 해당 resolver의 정적 import 확인 |
| `v1/engine/core.py:161` | `Scheduler(..., block_size=scheduler_block_size, hash_block_size=hash_block_size)` | 대입된 지역 변수를 생성자 이름 호출에 전달하는 표현 확인 |
| `v1/core/sched/scheduler.py:174` | `self.block_size = block_size` | 생성자 내부 대입은 기존 소스 fingerprint로 확인 |

### 중요한 분기: 항상 LCM/GCD를 계산하지 않는다

KV resolver `resolve_kv_cache_block_sizes(kv_cache_config, vllm_config)`의 AST에는 **서로 다른 네 개의 return expression**이 있다.

- 632행: `return bs, bs`
- 647행: `return scheduler_block_size, scheduler_block_size`
- 657행: `return scheduler_block_size, scheduler_block_size`
- 673행: `return scheduler_block_size, hash_block_size`

이는 **조기 반환 후보가 세 개 존재한다는 정적 증거**이다. 이번 AST 결과에는 분기 조건과 실행 가능성 분석이 포함되지 않았으므로, 모든 호출에서 640행의 LCM과 665행의 GCD가 적용된다고 주장하지 않는다. 조기 반환 조건·호출 시 config 값을 별도로 확인해야 한다.

## 3. 정적 연결 검사 여섯 개의 실제 결과

| `static_chain.checks` | DGX JSON |
|---|---|
| `engine_static_imports_resolver` | **true** |
| `engine_static_imports_scheduler` | **false** |
| `kv_scheduler_size_lcm_assignment` | **true** |
| `kv_function_returns_both_sizes` | **true** |
| `engine_assigns_scheduler_size_from_resolver` | **true** |
| `engine_ctor_uses_scheduler_size_variable` | **true** |

`static_chain.status=UNRESOLVED_OR_PARTIAL_STATIC_CHAIN`, `missing=["engine_static_imports_scheduler"]`, `bounded_output_truncated=false`, `runtime_flow_proven=false`.

**미해결 import 주의:** `engine_core.imports_of_interest`에는 `resolve_kv_cache_block_sizes: vllm.v1.core.kv_cache_utils.resolve_kv_cache_block_sizes`만 출력됐다. 현재 analyzer는 모듈 최상위 `ast.Import/ImportFrom` 선언에 더해 **`vllm.v1.core.sched.scheduler.Scheduler` 형태의 경로만** 성공으로 인정한다. `false`는 이 문자열 형식의 정적 import match에 실패했다는 뜻일 뿐이며, Scheduler가 실제로 import되지 않았다거나 바인딩이 잘못되었다고 단정할 수 없다. 모듈 내 지역 import, 다른 export 경로, alias/indirection 등을 실제 설치 소스의 범위 제한 AST로 확인해야 한다.

단지 여섯 bool을 모두 `true`로 만들기 위해 조건을 완화하는 것은 금지. 원본 source SHA/정확한 import binding/실제 호출자와 조기 반환 분기의 증거를 먼저 확보한다.

## 4. 이번 6파일 SHA256 fingerprint

| label | 설치 preview source SHA256 |
|---|---|
| `engine_core` | `f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad` |
| `kv_utils` | `f6643bad29b7b3cb044482b6736a042afa91a4f43a11f034317a8e8029d3a8a4` |
| `scheduler` | `c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124` |
| `mamba_worker` | `2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0` |
| `mamba_backend` | `9658330915daf4f8019a214317eb4be366eb52fd75fce8075cbb80d9ed7d3f6c` |
| `cache_config` | `8790351601be188ed1cc7ad9de2af1978b238269da4724873af1185c91165ef6` |

## 5. 남은 위험과 다음 단일 Phase 5 Gate

1. `v1/engine/core.py`의 **Scheduler 실제 import/binding 정의**를 같은 read-only AST로 확인. 한 함수의 이름만 같은 다른 클래스나 alias인지 구분; `static_chain` false의 원인을 먼저 밝힌다.
2. `v1/core/kv_cache_utils.py:632/647/657`의 **조기 반환 조건**, `dcp` 공급자, `group_block_sizes`의 AttentionSpec 대비 Mamba/SSM spec, cacheable subset hashing policy를 context-limited source trace로 확인한다. 사용자 모델의 실제 값은 아직 미확인.
3. `MambaHybridModelState.add_request:116`는 `self.cache_config.block_size`로 state index를 계산하고 `preprocess_state`는 `mamba_spec.block_size`를 참조한다. Backend `_compute_common_metadata`는 `self.kv_cache_spec.block_size`를 사용한다. group LCM과 **Mamba slot allocation/seed/copy/restore**의 실제 정렬 단위가 같은지, 다른 경우 변경 위험이 어디인지 소스+합성 CPU fixture로 입증하기 전 blazux `patch_mamba_block_size.py`를 적용하지 않는다.
4. Qwen Tool Argument/Marker/Responses Terminal, reduced MTP vocab 모두 기존 **NO PATCH APPROVAL** 상태를 유지. 운영 Docker/원본 모델·weights/HF cache/ports/GPU/HTTP/성능·CI 미실행. Phase6는 사용자 명시적 승인 전 계획으로만 둔다.

**GitHub 보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` 불변. Phase5만 docs/source-CPU 탐색, 현재 PR/Merge 불필요, `main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지.
