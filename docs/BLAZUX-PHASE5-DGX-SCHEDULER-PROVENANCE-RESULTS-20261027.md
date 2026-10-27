# Track A Phase 5 — DGX Scheduler block-size 출처 추적 실측 보고서

> **날짜:** 2026-10-27 (Asia/Seoul)
>
> **실제 사용자 DGX 테스트 소스 HEAD:** `04b871ab632b2a59d55d11f19009c48daa3ce5c0`, 브랜치 `feature/blazux-phase5-correctness-mtp-offline`.
>
> **증거:** 사용자가 제공한 `붙여넣은 텍스트(1)(20261027-102956).txt` (20줄, JSON 포함). `PHASE5_UNIT_PASS=244; XFAIL=0`, `PASS_SOURCE_ONLY: 160 tracked file(s)`, `PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED`, `PASS: PHASE5_SCHEDULER_PROVENANCE_EXECUTED_NOT_CERTIFIED`가 실제 출력된 것만 기록한다. 이 보고서·Manifest가 추가된 **후속 docs-only HEAD는 DGX에서 재시험한 SHA가 아님**.
>
> **결론:** SOURCE_ONLY_244_UNIT_PASS / SOURCE_MANIFEST_160_PASS / SCAN_PARTIAL_ASSIGN_SITE_LIMIT / SCHEDULER_AND_LCM_SOURCE_ANCHORS_IDENTIFIED / RUNTIME_VALUE_FLOW_NOT_PROVEN / PATCH_APPROVAL_ZERO / GPU_NOT_RUN. 고정 blazux `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. Source AST 이름·대입식만으로 실제 cache correctness, ABI, GPU/TPS, Tool/Responses 또는 MTP acceptance를 인증하지 않는다.

## 1. DGX 실제 오프라인 검사

```text
Ran 244 tests in 0.370s
OK
PHASE5_UNIT_PASS=244; XFAIL=0
PHASE5_SOURCE_AST_OK
PASS_SOURCE_ONLY: 160 tracked file(s)
  branch=feature/blazux-phase5-correctness-mtp-offline HEAD=04b871ab632b2a59d55d11f19009c48daa3ce5c0
PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS
PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED
PASS: PHASE5_SCHEDULER_PROVENANCE_EXECUTED_NOT_CERTIFIED
```

Wrapper `scripts/phase5-check-offline.sh`가 성공 종료했으므로 해당 스크립트에 포함된 기본 Mock 실행 경로도 오류 없이 완료됐지만 **이번 첨부 로그에는 Mock 시험 수(38 등)가 따로 포함되어 있지 않다**. 신규 소스 244개 unittest와 Source Manifest 160개는 실제 출력으로 독립 확인됐다. Source 검증은 untracked/ignored, 모델 payload, Docker 상태, 실 서비스 결과는 포함하지 않는다.

## 2. 핵심 생성자 후보 및 LCM 계산 위치

| 실제 파일:라인 (설치 vLLM 패키지 상대경로) | AST 표현 | 상태/의미 |
|---|---|---|
| `v1/engine/core.py:161`, `EngineCore.__init__` | `Scheduler(block_size=scheduler_block_size, hash_block_size=hash_block_size)` | **직접 이름 호출 후보 1개**; `NAME_MATCH_SCHEDULER_NOT_RESOLVED` — import class binding은 미추적 |
| `v1/core/kv_cache_utils.py:640`, `resolve_kv_cache_block_sizes` | `scheduler_block_size = math.lcm(*group_block_sizes)` | **그룹 블록들의 LCM 계산 소스 위치 발견**. 실제 `EngineCore` 지역 변수에 연결되는 함수 return/호출 edge 확인 전 end-to-end 확정 금지 |
| `v1/core/kv_cache_utils.py:665`, `resolve_kv_cache_block_sizes` | `hash_block_size = requested if requested is not None else math.gcd(*hashing_sizes)` | **Hash block-size 별도 GCD/요청값**. Scheduler block-size와 별도 의미 |
| `v1/core/sched/scheduler.py:174`, `Scheduler.__init__` | `self.block_size = block_size` | 생성자가 공급 인자를 보관. 수치나 LCM을 생성자 내부에서 계산했다고 볼 수 없음 |
| `v1/core/sched/scheduler.py:392`, `_mamba_block_aligned_split` | `block_size = self.cache_config.block_size` | Hybrid LCM 후보인 `self.block_size` 대신 config KV block을 사용하는 기존 코드 |
| `v1/worker/gpu/model_states/mamba_hybrid.py:116`, `add_request` | `(new_req_data.num_computed_tokens - 1) // self.cache_config.block_size` | 기존 Mamba slot/index 계산이 config KV block 기준 |
| `v1/attention/backends/mamba_attn.py:510` | `mamba_block_size = self.kv_cache_spec.block_size` | **Attention metadata의 로컬 값**, CacheConfig 필드 대입이나 Scheduler LCM 공급자로 오인 금지 |
| `config/cache.py:50/125/264` | `block_size`, `mamba_block_size` 설정 선언 및 기본값 처리 | 초기값·실제 모델 config 유효성 별도 검증 필요 |
| `config/scheduler.py:117` | `scheduler_cls = None` | 동적 Scheduler class config 가능성. 이 스캔에서 `scheduler_cls(...)` 호출 후보 0이라고 동적 생성 자체를 부정할 수 없음 |

**생성자/그룹 관계는 추정 근거가 강해졌지만 아직 완성되지 않았다.** `v1/engine/core.py`에서 `scheduler_block_size` 지역 값의 **대입/분해대입/함수 호출부**와 `resolve_kv_cache_block_sizes`의 return을 연결하고, 이 클래스가 `v1/core/sched/scheduler.py:Scheduler`의 실제 import 대상인지 확인해야 한다. `math.lcm`이 group block 크기를 바탕으로 계산되는 것은 코드 표현으로 확인되지만 **실제 사용자 checkpoint와 Mamba group 크기/slot 배치가 무엇인지**는 이 시험에서 계산·측정하지 않았다.

## 3. 스캔 완전성: 중요 PARTIAL

```text
scan.state                 = PARTIAL
scan.directories           = ["config", "v1"]
scan.candidate_py_files    = 384
scan.visited               = 384
scan.bytes                 = 6448206
scan.unreadable_or_unparseable = 0
scan.limits                = ["ASSIGN_SITE_LIMIT"]
scheduler_constructor_candidates.direct_name_matches = 1
scheduler_constructor_candidates.dynamic_unresolved   = 0
```

- `MAX_ASSIGN_SITES=64`에 도달하여 `block_assignments` 목록이 잘렸다. Python 소스 **384개 모두 읽었고** syntax/unreadable=0이지만, **모든 관련 assignment가 출력됐다는 뜻은 아니다**. 모듈 수·바이트 한계에는 도달하지 않았다.
- 특히 일반 `block_size` 변수 대입들이 한도를 빠르게 채울 수 있어, 다음 Gate는 **관련 3~5개 파일만 우선** 추적하도록 스코프를 좁히고, 추가 필드/생성자 링크가 누락되지 않았는지 확인해야 한다. `scan.state=PARTIAL`을 `COMPLETE`로 쓰지 말 것.
- `mamba_field_references`에는 `config/cache.py:267` 및 `config/vllm.py:2535–2536`의 LOAD가 출력되었다. `config/cache.py:125` field **정의/대입**은 `block_assignments`에 나타나지만 **`mamba_field_references`에서 STORE로 출력되지 않았다고 하여 field 정의를 부정하면 안 된다**. AST `AnnAssign` 선언/field 생성과 런타임 Store 구분 유의.
- 관심 있는 실제 `Scheduler` 직접 후보는 `v1/engine/core.py:161` 한 곳 출력. `NAME_MATCH_SCHEDULER_NOT_RESOLVED`는 import binding/alias를 인증하지 않았다는 명시적 제한. 동적 `scheduler_cls` 호출 후보 `0`은 이 AST 탐색 방법과 스코프에서의 결과일 뿐이다.

## 4. 다음 같은 Phase5 CPU/source-only Gate (우선순위)

1. `v1/engine/core.py`의 `EngineCore.__init__` 안에서 `scheduler_block_size` 및 `hash_block_size` **실제 변수 대입/tuple unpack**과 `resolve_kv_cache_block_sizes` 호출/반환 연결 확인. `Scheduler` import/alias 바인딩을 source-only로 교차 검증.
2. `v1/core/kv_cache_utils.py:resolve_kv_cache_block_sizes`의 `group_block_sizes`, `hashing_sizes` 생성 부분·return 및 `math.lcm` 적용 그룹의 정확한 키/단위를 추출. `v1/engine/core.py`에서 반환 변수가 Scheduler에 전달되는지 verify.
3. `v1/core/sched/scheduler.py`의 `self.block_size`, `hash_block_size`, `cache_config.block_size` 사용처를 **Mamba group state slot 정렬/복원**과 연계, `MambaHybridModelState.add_request/preprocess_state/postprocess_state` 및 `v1/attention/backends/mamba_attn.py`의 `self.kv_cache_spec.block_size` 차이를 분석한다. 필요시 수치 없는 fake config/group 기반 CPU fixture를 추가한다.
4. **이번 Gate는 증거 문서화만** 하고 실제 blazux patch/모델/운영 Docker/ports/GPU/HTTP/TPS/CI는 별도 명시적 승인까지 실행하지 않는다. Qwen Tool/Responses와 reduced draft MTP도 미승인 상태 유지.

## 5. GitHub 보호 및 정확한 SHA 귀속

- **검증된 소스 HEAD:** `04b871ab632b2a59d55d11f19009c48daa3ce5c0`, full unittest **244/244 XFAIL0**, Source160/160 PASS. 이후 이 보고서, runbook, handoff, adoption plan, manifest 변경만 하는 새 docs-only HEAD는 **DGX에서 244-test 재실행을 증명하지 않는다**.
- `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` immutable. 이번에도 `main` PR/Merge/Cherry-pick/Rebase/Squash/Sync 금지, 현 PR/Merge 불필요. 모든 후속 실험은 **같은 Phase5**.
