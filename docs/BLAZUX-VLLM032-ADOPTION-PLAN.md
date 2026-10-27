# blazux vLLM 0.32 도입 검토 및 실증 계획서

> 상태: **INITIAL_PLAN_DOCUMENT_ONLY / NOT_IMPLEMENTED / NOT_DEPLOYED / NOT_TESTED**
>
> 작성 기준: 2026-10-27 (Asia/Seoul). 외부 blazux 소스는 main SHA **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**로 고정하여 분석했다. 사용자 DGX 운영 모델의 Baseline은 PR #5에서 이미 백업됐다. 현 프로젝트의 기준 main SHA는 **2847e39b4131eb8aff78bf86ffce98892401722a** (Baseline PR #5 병합 커밋)이다. 본 계획의 출발점은 **feature/blazux-vllm032-evaluation-20261027** 브랜치이며 코드 구현/운영 배포는 포함하지 않는다.
>
> 최상위 결정: **기존 Orcarouter NVFP4/BF16 PLE/BF16 MTP=2 서비스의 정식 성능 Baseline을 먼저 확보하고 GitHub에 보존한다.** Smoke Test와 별도로 정식 Baseline **12조건×3회=36회 측정**이 완료되었고, [PR #5](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/5)에서 [원본 result.json](../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json)을 `main`에 보존했다. 단, 신규 Bash runner는 사용자 요청으로 실행 시험을 생략했다.

## 2026-10-27 Phase5 Scheduler factory / KV Resolver / Mamba Block 3개 읽기 전용 조사 실측 — 최신

- 사용자 DGX 제공 [3항목 소스 실측 정본](BLAZUX-PHASE5-DGX-THREE-SOURCE-CHECKS-20261027.md): `CHECK1/2/3_SOURCE_INSPECTION_DONE`, 별도 CPU-only read-only 검사. 이 출력은 **259 unittest/164 source Manifest의 재시험이 아니다**. 직전 확정 full DGX test 소스 `bc89de6288889943b50090ac9638ee95c2434a79`, 259/259 XFAIL0, Source164/164, Wizard Mock38/38. 이전 docs-only HEAD `17cfbc5b087a9245e2645a44131bd35f47dd7f40`는 실제 test SHA가 아님.
- **Scheduler factory:** `v1/engine/core.py:148` `Scheduler = vllm_config.scheduler_config.get_scheduler_cls()`를 확인해 기존 `engine_static_imports_scheduler=false`(직접 import 기대)가 false였던 이유를 설명. :157 tuple unpack KV resolver→:161 생성자 block_size 전달. 다만 실제 config가 어떤 클래스를 반환할지는 미확인, 기존 test 5/6을 6/6이라 재표기하면 안 됨.
- **KV blocks:** `v1/core/kv_cache_utils.py:627` DCP 공급자는 `decode_context_parallel_size`. 0/1 group 분기는 `cache_config.block_size*dcp`, 2+ groups는 AttentionSpec `spec.block_size*dcp`, 나머지 spec.block_size 그대로 LCM. Hash는 prefix/connector off 또는 Mamba non-align 시 scheduler 크기로 조기 반환. 그 외 cacheable group(없으면 전체)에서 요청된 `prefix_match_unit` or GCD, divisibility guard 대상 `hashing_sizes`. 세 조기 return 632/647/657, 일반 return 673 구분.
- **Mamba conditional mismatch risk:** Worker `add_request:116` seed와 Scheduler aligned split `:392`는 `cache_config.block_size`; preprocess `MAMBA_BLOCK_SIZE=mamba_spec.block_size`, backend `kv_cache_spec.block_size` 및 postprocess fused. 서로 다른 참조 경로 확인됐지만 **실제 사용자 모델에서 수치가 다른지, state slot corruption/오류가 있는지는 아직 미검증**. Patch Mamba/Prefix 적용 금지.
- **다음 같은 Phase5:** `get_scheduler_cls()` 반환 class/override source, KV grouped fake-config CPU branch fixtures, 실제 spec/copy context 및 Mamba seed-preprocess-postprocess 슬롯 단위 정합성 조사. Tool/Responses/MTP reduced-vocab도 미승인 유지. 사용자 명시적 승인 없는 실제 engine patch/운영 Docker/GPU/모델/HTTP/벤치/CI 금지, main/P0/Phase1~4 immutable·PR/Merge 0.

## 2026-10-27 Phase5 KV LCM → EngineCore source-only DGX 실측 PASS — 이전 스냅샷

- **실제 사용자 DGX 소스 HEAD** `bc89de6288889943b50090ac9638ee95c2434a79`에서 **Wizard Mock 38/38**, Source Manifest **164/164**, 전체 unittest **259/259 XFAIL0**, 정밀 source AST 완료. [DGX 정본 결과](BLAZUX-PHASE5-DGX-NARROW-BLOCK-FLOW-RESULTS-20261027.md). 문서 전용 후속 SHA는 DGX 재시험하지 않았다.
- **Static check 5/6:** KV resolver import, group LCM assignment, KV 반환 tuple, EngineCore resolver tuple 대입, Scheduler ctor keyword 인자 true. `engine_static_imports_scheduler=false` (모듈 최상위 import의 분석기 허용 경로와 일치하지 않음); `UNRESOLVED_OR_PARTIAL_STATIC_CHAIN`, `runtime_flow_proven=false`, `patch_approved=false`. 어떤 이름 기반 정적 증거도 실제 serving correct/ABI 승인으로 승격하지 않음.
- **주의할 값/분기:** `v1/core/kv_cache_utils.py:634` AttentionSpec group은 `kv_cache_spec.block_size * dcp`, 타 group은 `kv_cache_spec.block_size`. :640 group LCM, :659 prefix_cacheable group hashing 우선, :665 requested 또는 GCD. :632/647/657 **early returns**, :673 일반 tuple return. 조기 반환 조건/`dcp`/Mamba group 실 값 확인 전 **항상 LCM/GCD라고 주장 금지**.
- EngineCore :157은 `scheduler_block_size, hash_block_size = resolve_kv_cache_block_sizes(kv_cache_config,vllm_config)`, :161 Scheduler keyword 인자 사용. import/binding 정확한 선언, runtime branch, Mamba state slot/Sched aligned prefix hit/real correctness는 미검증.
- **다음 같은 Phase5 작업:** Scheduler import/alias 증거, KV resolver의 조기 반환 조건/`dcp` 출처, Mamba state index와 spec.slot/pre/postprocess 정렬 CPU oracle에 집중. blazux Mamba/Tool/Responses/MTP patch 계열 **승인 0건**. 운영 Docker/GPU/모델/ports/cache/HTTP/TPS/CI 별도 승인 전 미변경; main/P0/Phase1~4 불변, PR/Merge 금지.

## 2026-10-27 Phase5 EngineCore/KV LCM-to-Scheduler 좁은 범위 Source AST Gate (기존 실행 전 계획)

- 직전 실제 사용자 DGX: Source `04b871ab632b2a59d55d11f19009c48daa3ce5c0`, unit **244/244 XFAIL0**, Manifest **160/160**, Scanner `PARTIAL` (일반 block_size 대입 64개 제한). `v1/core/kv_cache_utils.py`의 LCM/GCD 정의 및 `v1/engine/core.py`의 Scheduler ctor 인자는 각각 정적 후보일 뿐 실제 import·반환·변수 대입 경로는 아직 미검증.
- 이번에도 **Phase5 하나**에서 [좁은 범위 AST 연결 분석](BLAZUX-PHASE5-NARROW-BLOCK-FLOW-20261027.md): 고정 6개 설치 source import-free 조회, KV resolver group block-size 구성/LCM/GCD·return, EngineCore의 resolver 호출/tuple unpack 및 Scheduler ctor 키워드 인자를 6개 static check로 분리. 합성 CPU **15 unittest** 추가, 이전 244+15 = **259 expected**, Manifest **164 expected**, 이번 HEAD 실제 DGX 아직 NOT_RUN.
- 모든 정적 check 일치 시에도 `STATIC_CHAIN_CANDIDATE_NOT_RUNTIME_CERTIFIED`일 뿐이며 Mamba state slot/SSM group/실 cache correctness/Tool/Responses/MTP/GPU/TPS는 별도 검증. **patch_approved=false**. 운영 GPU/model/이미지/weights/ports/HF cache/CI 변경 금지, main/P0/Phase1~4 immutable, PR/Merge 안 함.

## 2026-10-27 Phase5 Scheduler block-size LCM/생성자 DGX Source-only 실측 (이전 실측)

- **사용자 DGX 실제 소스 HEAD `04b871ab632b2a59d55d11f19009c48daa3ce5c0`**: Source Manifest 160/160, `PHASE5_UNIT_PASS=244; XFAIL=0`, Source AST/Wrapper PASS, Scheduler AST tool 종료 marker. [실측 근거 보고서](BLAZUX-PHASE5-DGX-SCHEDULER-PROVENANCE-RESULTS-20261027.md).
- `kv_cache_utils.py:640` `scheduler_block_size=math.lcm(*group_block_sizes)`; `kv_cache_utils.py:665` `hash_block_size=requested if requested is not None else math.gcd(*hashing_sizes)`; `v1/engine/core.py:161` `Scheduler(block_size=scheduler_block_size,hash_block_size=hash_block_size)`; Scheduler ctor `self.block_size=block_size`. **서로 다른 파일의 수식·변수 같은 이름을 실제 call/return flow로 확정하면 안 됨**.
- `scan.state=PARTIAL` 원인 `ASSIGN_SITE_LIMIT`=64, 384 files/6,448,206 bytes 읽음/unreadable 0. 다음 같은 Phase5에서 **EngineCore → resolve_kv_cache_block_sizes 반환 → group block size 계산**의 파일 지정 source-only 정밀 추적을 실시. Mamba state slot, 실제 prefix hit, Parser/Responses, MTP reduced draft는 미승인.
- blazux 패치 적용 승인 0, GPU/모델/운영/HTTP/TPS 미실행, `main`·P0·Phase1~4 불변 및 PR/Merge 금지. 새 docs-only SHA는 DGX 재시험하지 않았다.

## 2026-10-27 Phase5 Scheduler ctor 인자/그룹 LCM 소스 추적 추가 (기존 DGX 실행 전 계획)

- 사용자 제공 Phase5 AST trace JSON(명령 보호 SHA `2cadc7369b4b813332a767733faa9c2529413cd9`)으로 `config/cache.py`의 `mamba_block_size` 정의 후보·`config/vllm.py`의 참조, Scheduler.__init__의 `self.block_size=block_size`, Mamba/Scheduler worker의 `cache_config.block_size` 사용이 확인됐다. **실제 Scheduler 생성자 호출자/LCM/SSM state slot 단위는 여전히 미확인**. 직전 확정된 전체 unit은 223/223 at `2c7c6896...`; 새 233 unit PASS도 로그 미제공.
- 새 [Scheduler Block Provenance 실행 Gate](BLAZUX-PHASE5-SCHEDULER-BLOCK-PROVENANCE-20261027.md)에서는 기존 Phase5 브랜치에 import-free source-only `Scheduler(...)` 직접/동적 class factory 후보 탐색, positional/keyword `block_size`·`hash_block_size` 표현, LCM 대입·mamba field STORE/LOAD, 원본 Scheduler/Mamba AST method trace와 합성 **11개 회귀시험**을 하나로 묶는다. **목표 전체 244개/XFAIL0, Manifest160**, 현재 신규 DGX **NOT_RUN**.
- `Scheduler` 이름만으로 실제 class binding을 확정하거나 동적 `scheduler_cls` 호출의 위치 인자를 임의로 해석하지 않는다. PARTIAL 스캔 시 false completeness 금지. cache group/LCM 및 state restore 미확인 상태에서 blazux Mamba patch 적용 불허. Tool/Responses/MTP 및 실제 추론/GPU/운영은 계속 별도 승인 전 NO GO.
- Phase 증가 금지: CPU/source-only 후속은 모두 **Phase5**. `main`, P0, Phase1~4 불변, main PR/merge/cherry-pick/rebase/squash/sync 금지, 현재 PR/Merge 불필요.

## 2026-10-27 Phase5 DGX 읽기 전용 Dependency Trace JSON 확보 (이전 실측)

- 사용자 JSON이 `PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED`로 정상 종료했고 실행 명령은 `2cadc7369b4b813332a767733faa9c2529413cd9` 소스 HEAD를 확인하는 구조. 이번 로그에 전체 unit 233/233·Manifest 156/156은 없어 **전체 Gate PASS는 미확정**. 직전 확정 223 tests Source152/152는 별도 source SHA `2c7c6896...`에 귀속. [상세 실측 정본](BLAZUX-PHASE5-DGX-DEPENDENCY-TRACE-RESULTS-20261027.md).
- Mamba `mamba_block_size` 구문은 `config/cache.py`와 `config/vllm.py`에서 정의/참조됨(384파일 scan, unreadable0). Worker `add_request`와 Scheduler `_mamba_block_aligned_split`은 여전히 `cache_config.block_size`를 사용하고 Scheduler `self.block_size`는 외부 생성자 인자를 전달받음. 호출자 LCM/state slot unit 확인 전 Mamba patch 안전 승인 불가.
- NVIDIA MTP 출력 head는 공유 `model.embed_tokens`, 별도 `ParallelLMHead`, `PPMissingLayer`로 분기하고, `compute_logits`가 logits_processor(head,states)를 호출. reduced draft vocab은 branch별 head storage와 loader remap, TP/dtype/vocab/acceptance/다국어 품질 확인 전 **미적용**. Parser/Responses도 정적 call edges 확보에 그치며 stream/HTTP 검증 없음.
- **Phase5 안에서** cache field→Scheduler(block_size=...) 생성자 호출자→state restore 정합성부터 추가 분석. 운영 vLLM patch, GPU/model/TPS/HTTP/CI, TrackB 승인 전 금지. Main/P0/Phase1~4 immutable, blazux→main PR/merge/cherry-pick/rebase/squash/sync 영구 금지.

## 2026-10-27 Phase 5 읽기 전용 실제 Source Dependency Trace 합본 (기존 계획)

- 기존 **Patch Preflight DGX 실측 223/223 PASS/XFAIL0**는 테스트 코드 `2c7c6896...`에만 귀속. 이제 같은 Phase5에서 **Mamba/Scheduler block field 생성/LCM, Parser/Responses 호출관계, NVIDIA MTP lm_head/weight sharing**을 Source AST 기반으로 더 구체적으로 조사한다. 새 Phase 생성 안 함.
- 새 [Phase5 Dependency Trace 실행 문서](BLAZUX-PHASE5-DEPENDENCY-TRACE-READONLY-20261027.md): `src/phase5_dependency_trace.py` (import-free, read-only `config`+`v1` scope Mamba STORE/LOAD; Mamba/Scheduler/Parser/Responses/MTP/PLE method expression/AST trace), `tests/test_blazux_phase5_dependency_trace.py` 신규 10개와 통합 AST Gate. **목표 unittest 233/XFAIL0, 새 DGX 실측 NOT_RUN**.
- 실제 코드를 포함하는 patch 적용 권한은 별개: source expression/assignment/call graph는 **semantic ABI/runtime correctness가 아님**. 동적 필드·dependency·GPU·real model·MTP acceptance·tool parser SSR/HTTP는 미검증. 현재 blazux patch-family 실제 적용 승인 0건.
- `main`·P0·Phase1~4 불변, 현재 PR/Merge 불필요, blazux `main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지. 운영 Docker/model/GPU/weights/ports/cache/receipts 미변경.

## 2026-10-27 Phase 5 pinned blazux patch preflight DGX 실측 PASS (이전 확정 상태)

- 실제 DGX 소스 HEAD `2c7c6896430be0d9eada656f17edf97d9c5f4d3f`, Source Manifest **152/152 PASS**, Wizard Mock **38/38**, unittest **223/223 XFAIL=0**. 패치 **소스 전제조건 점검** 종료, 설치 엔진의 기능 패치/출력 비교/성능 측정 **미실행**. [실측 정본](BLAZUX-PHASE5-DGX-PATCH-PREFLIGHT-RESULTS-20261027.md).
- Mamba/Scheduler의 legacy source preimage anchor와 NVIDIA MTP `compute_logits` 훅 후보 확인. 그러나 cache_config.mamba_block_size 실제 공급/LCM/state restore, Parser/Responses 다중파일 및 새 helper 의존성, MTP shared `lm_head`/dtype/vocab/acceptance 미검증. **다섯 계열 적용 승인 0**.
- 동일 Source/CPU-only 안전 범위는 새 Phase 없이 **Phase5 지속**. 이전 P0/Phase1~4/`main` 불변, main PR/Merge 영구 금지. 운영 Docker/모델/GPU/HTTP/TPS/CI 미변경/미실행.

## 2026-10-27 Phase 5 pinned blazux patch preflight 통합 (기존 실행 전 계획)

- 기존 Phase5 source-only 실측 `9e2d1647...`: Source 148/148, 215 unittest PASS, 설치 NVIDIA Qwen3.8 MTP/PLE 경로 확인. 정확한 인수인계는 [DGX ABI 증거 보고서](BLAZUX-PHASE5-DGX-PREVIEW-ABI-TRIAGE-RESULTS-20261027.md)를 따른다.
- 이번 Phase5 동일 브랜치에서 [Patch preflight 오프라인 runbook](BLAZUX-PHASE5-PATCH-PREFLIGHT-READONLY-20261027.md)에 따라 Mamba/Scheduler cache config, Parser Tool Argument Schema·Literal Marker, Responses streaming terminal, MTP Reduced Vocabulary **5개 patch-family**의 read-only 12-source AST/hash/anchor/signature 조사 및 8개 fake fixture 테스트를 추가했다. **예상 223 tests/XFAIL0, 실제 새 DGX 실행 NOT_RUN**.
- 출력은 **SOURCE ONLY, NOT PATCH/ABI CERTIFICATION**. Mamba는 `mamba_block_size` 필드/그룹 LCM/slot shape, Parser/Responses는 new helper 및 다중 파일 preimage, MTP는 shared lm_head / dtype / vocab / acceptance / quality가 확인될 때까지 실제 runtime apply 금지. 운영/모델/GPU/HF cache/포트 변경·`main` PR/Merge 절대 금지.

## 2026-10-27 Phase 5 동일 브랜치의 read-only preview ABI triage 확장

- 사용자 요청대로 추가 작업도 **Phase 5에 유지**, Phase 증식 금지. 이전 Phase5 synthetic Gate `01c9eb6b...`에서 208/208 PASS를 확인했으나 이는 real prefix hit/real Parser/MTP patch PASS가 아니다.
- 실제 이미지의 MTP/PLE 모듈 경로가 `ABSENT_OR_RELOCATED`로 나온 **고정 경로 추정 문제**를 해결하기 위해 [Preview 소스 읽기 전용 조사 계획](BLAZUX-PHASE5-PREVIEW-ABI-READONLY-TRIAGE-20261027.md)과 source AST/sha256 조사기, +7 unittest를 같은 Phase에 추가. 소스 비교에는 pinned upstream blazux sha만 사용한다.
- 조사 결과를 받아 실제 source/ABI patch 가능 범위를 확정할 때까지 `patch_mamba_block_size.py`, Qwen Parser/Responses patch, reduced vocab hook은 **적용하지 않음**. 모델/이미지/캐시/GPU/서빙 변경도 금지. 테스트되지 않은 성능 수치를 만들지 않는다.
- 이전 브랜치 `main`, P0, Phase1~4 불변. PR이 필요해도 Phase5→Phase4 비병합 Draft review만. `main`으로 PR/merge/squash/cherry-pick/rebase/sync 금지.

## 2026-10-27 Phase 5 진입 보강 — 우선순위 기능과 Phase 번호 분리

- **Phase(개발 검증 묶음)와 P1/P2/P3(기능 우선순위)는 다르다.** 개발 계획상 Track A는 **Phase 1~4 오프라인 Gate 완료**, 다음 묶음은 **Phase 5 P1 정확성·P2 위험 계약**이며 Phase 6은 승인된 GPU/실 모델 A/B 전용 후보. 이는 *권장 구조*일 뿐 phase 수·검증 통과를 보장하지 않는다. Track B vLLM v0.32는 Go/No-Go를 기다리는 별도 실험 계보.
- **Phase 5 하나의 브랜치** `feature/blazux-phase5-correctness-mtp-offline` (Phase4 확정 HEAD `69860277122dffe3082c5b065e4361a571317a8e`의 자식): Prefix cache/Mamba state index·Tool Calling/Responses error/event policy·MTP reduced draft vocab 위험을 **합성 CPU oracle으로 검토**. PLE Fast Gather 소형 CPU benchmark, 설치된 preview/vLLM 소스 SHA/AST 읽기 전용 inventory 포함. [Gate5 합본 문서](BLAZUX-PHASE5-BUNDLED-CORRECTNESS-AND-MTP-20261027.md).
- **현재 구현하지 않는 기능:** Mamba/scheduler 실 코드 패치, Tool Parser/Responses serving monkeypatch, reduced vocab `lm_head` subset patch, GPU pinned H2D, tokenizer/모델 95GiB 직접 접근. 이 영역은 엔진 ABI 검증과 사용자 승인 전 **NOT_IMPLEMENTED/NOT_VERIFIED**. 특히 P1 cache/tool 회귀 oracle 통과를 실제 엔진 정합성 PASS로 표시하지 않는다. MTP reduced vocab은 실제 acceptance/다국어/EOS/클라이언트 품질 및 이전 Orcarouter BF16 MTP 31/31 보존이 입증될 때까지 **REJECT_AS_DEFAULT**.
- **브랜치/PR 정책:** 이전 Phase와 `main` 영구 불변, 소스 evidence/Manifest 및 raw DGX 로그의 HEAD 분리, `main` 대상 PR/merge/rebase/cherry-pick/squash/sync 절대 금지. 같은 Gate에 속하는 후속 fix/fixture는 새 Phase 대신 현재 Phase 5에 커밋.

## 2026-10-27 최신 운영 규칙 보강 — Phase 묶음 진행

> 아래 항목이 본 문서 최초 작성 당시의 단계별 Phase 설명보다 **최신**이다. 사용자 요청에 따라 같은 위험·승인·검증 경계를 공유하는 작업은 단일 Phase의 복수 독립 커밋으로 수행한다. 세부 프로그램과 고정 SHA는 [Phase 4 통합 Gate 문서](BLAZUX-PHASE4-BUNDLED-PLE-CPU-20261027.md)를 우선한다.

- Phase 3에서 `G2-01` 중복 PLE shard 인덱스 fail-closed 회귀 **189/189 XFAIL=0** 및 CPU byte-exact를 실제 DGX에서 확인했다. Phase 3 확정 문서 HEAD `760f227e46a358445db3d3931b5efbe40de5f609`을 최종 불변 부모로 한다.
- **Phase 4 단일 브랜치** `feature/blazux-phase4-ple-cpu-bundle`: 독립 feature A `VLLM_PLE_FAST_GATHER=0`(작은 batch inline gather), feature B `VLLM_PLE_PHASE_STATS=0`(per-table CPU gather 관측값). 각 최적화는 **서로 다른 구현 커밋** 및 독립 기본-OFF 플래그/rollback으로 보존; 같은 Phase의 공용 BF16 CPU fixture·unit tests·runbook·Manifest·실측 기록으로 묶는다.
- **영구 금지:** `main` 대상 PR/merge/cherry-pick/rebase/squash/sync. 이전 P0/Phase1/Phase2/Phase3 ref도 수정하지 않는다. GPU/모델/Docker/HF cache/포트/receipt는 승인 전 변경하지 않는다.
- 향후 Phase 분기는 **기술적 ABI/rollback 신뢰 경계 또는 새로운 운영·GPU 권한이 달라질 때만**. 동일 Phase 안에서 실패 재시험·추가 fixture·문서 정리는 추가 Phase 번호 없이 진행. 별도 Track B(vLLM 0.32)는 기존과 같이 **승인 전 시작 금지**.
## 1. 목표·범위·성공 정의

### 1.1 목표

1. blazux/qwen3.8-Flash-DGX의 최적화와 안정성 패치를 **개별 기능·위험 단위**로 파악한다.
2. 현 개인 프로젝트의 Orcarouter NVFP4 **compressed-tensors** trunk, BF16 PLE(NVMe mmap), BF16 MTP overlay **31 tensors / 4.86 GiB** 등 기존 계보와 호환되는 것만 선별한다.
3. 새 엔진 도입 자체의 효과와 모델/checkpoint·양자화·sampling·CPU affinity·KV 용량 변경 효과를 분리한다.
4. 정량 개선이 재현되고 기능 안정성을 통과하면 별도의 격리된 이미지/실험 프로파일로 후속 도입을 검토한다.
5. 기존 레거시 서비스, 설치 receipts, HF cache/recipe views, Wizard 상태 및 다른 OpenWebUI/Ollama/네트워크 운영 자산을 변경하지 않는다.

### 1.2 범위 밖

- blazux 전체 저장소를 현재 프로젝트에 무검토 merge하거나 운영 Docker를 덮어쓰지 않는다.
- 사용자 검증 없이 새 vLLM 0.32 서버를 운영 포트 8000에 띄우거나 기존 모델을 정지·제거하지 않는다.
- blazux published 성능치를 현재 Orcarouter 모델의 성능으로 취급하지 않는다.
- NVIDIA/RadixArk ModelOpt checkpoint로 바꾼 결과를 **동일 Orcarouter 모델의 blazux 패치 순수 효과**로 보고하지 않는다.
- 설치/제거 위자드 또는 GitHub CI 정상화의 별도 보류 과제를 묵시적으로 재개하지 않는다.

### 1.3 성공 조건

- 사전 Baseline: 모델/코드 SHA, 스크립트/토크나이저/코퍼스/인자, 서버/이미지/KV, PP/TG/TTFR/e2e_ttft/정확성, 결과 원본 및 SHA256이 검증·보존됨.
- 호환성: 선택한 패치별 API/shape/dtype/quantization/모델 경로 및 실제 BF16 MTP 31/31 load guard가 근거로 확인됨.
- 품질: 단기·장문·동시성·MTP·prefix-cache·tool calling·JSON/schema 출력 회귀시험에서 신규 치명적 실패가 없음.
- 성능: 원본과 candidate 모두 동일 시험 조건에 대해 반복값·변동성·CPU/GPU/page-cache/KV 자원 자료를 보유; 최소 1회 run의 우연한 차이는 개선으로 간주하지 않음.
- 운영 안전: 실제 구동은 새 소유 자산에서만 하며 레거시의 이미지/컨테이너/포트/mount/receipts에는 쓰기 없음.

### 1.4 구현 전략: Track A와 Track B는 완전히 독립

**Track A — 현행 vLLM preview 기반의 선택적 기능 개선 (현재 작업)**

- **실험 루트(P0):** `feature/blazux-vllm032-evaluation-20261027` (현재 존재하는 분석·계획 브랜치). **실제 Gate 1부터는 현재 루트 HEAD를 부모로 새 Phase 1 브랜치를 생성**한다. 이후 각 Phase는 직전 확정 실험 브랜치의 HEAD에서 별도 후속 브랜치를 만든다. 승인받지 않은 `main` 병합·체리픽·코드 이전은 금지한다.
- 순서: 기존 코드와 외부 blazux pinned SHA의 함수·텐서 경로 1:1 비교 → 계측·정확성 우선 → 합성 데이터 기반 CPU 오프라인 검증 → **기능별 기본 OFF flag**를 가진 최소 수정 → 독립 브랜치에서 성능·정확성 검증. **모든 blazux 실험은 `main`에서 영구 격리하며 검증 성공해도 `main`에 병합하지 않는다.**
- 이미 쓰는 preview 이미지, Orcarouter checkpoint, BF16 PLE mmap, MTP=2 overlay를 기준으로 비교한다. 패치가 vLLM v0.32 내부 구조를 전제로 한다면 **Track A에 강제로 포팅하지 않고 DEFER_TO_TRACK_B**.
- 본 트랙 진행은 **vLLM 0.32 Docker base 변경·모델 교체·운영 서비스 전환의 승인으로 간주하지 않는다**.

**Track B — 공식 vLLM 0.32 엔진 전환 (선택적 후속 장기 실험; 미생성·미착수)**

- 전용 브랜치 **`feature/vllm032-bf16ple-port`**는 별도 Go/No-Go 승인 이후 **동일한 blazux 실험 루트(P0)의 고정 HEAD에서 Track A와 형제(sibling) 관계로 생성**한다. **`main`에서 직접 분기하지 않으며** Track A 실험 코드를 자동 상속하지 않는다. Track B도 단계마다 별도 자식 Phase 브랜치를 생성한다.
- 비교·검증 단위: `vllm/vllm-openai:v0.32.0` 기반 코드를 **정확한 image digest로 pin**하고, Qwen4Exp 모델 로더·quantization dispatch·BF16 PLE·MTP 31/31 overlay·KV/Mamba/SSM·CUDA graph·Tool/Responses parser의 API/ABI/결과 정합성을 확인한다.
- Track B는 별도 Docker 이미지/컨테이너/receipt/모델 view/결과 디렉터리/포트를 예약·소유한다. **기존 runtime 자산을 이름만 바꿔 재사용하는 방식 금지**.
- Track B를 시작할지 자체가 별도 **Go/No-Go**. 성공하더라도 Track A의 선택 기능 병합과 결합된 PR로 올리지 않는다.

**검증 및 격리 절차:** 1:1 분석 결과 작성 → 기능별 변경 범위/flag/rollback 계약 → 오프라인 회귀 → 공개 안전 검토/Source Manifest 갱신 → Phase별 독립 커밋과 코드 리뷰 → 다음 Phase는 **직전 승인 실험 HEAD에서 새 브랜치**로 진행. 선택적으로 Phase→부모 Phase 비교용 PR을 만들 수 있지만 **병합은 기본적으로 수행하지 않으며**, blazux에서 `main`으로 향하는 PR·Merge·Squash·Cherry-pick·자동 Rebase/동기화는 금지한다. 마지막에 기능을 전부 폐기해도 `main` 및 Baseline에 영향이 없어야 한다.

참고: 2026-10-27 조회에서 `main.protected=false`였다. 따라서 **blazux→`main` 반입 금지는 GitHub가 자동 강제하는 보안 설정이 아니라 이 프로젝트의 명시적 작업 금지 규칙**이다. 어떠한 도구/자동 PR도 이 정책을 우회하지 않는다. Branch Protection/Ruleset 변경은 별도 승인 과제이며 이 실험 브랜치에서 설정을 변경하지 않는다.

### 1.5 신규 불변 원칙: 페이즈별 **폐기 가능한 Git 계보**

- **P0 실험 루트(기존):** `main@2847e39b4131eb8aff78bf86ffce98892401722a`에서 2026-10-27 한 번 생성된 `feature/blazux-vllm032-evaluation-20261027`를 시작점으로 한다. **이후의 blazux 브랜치는 `main`을 새 base로 삼지 않는다.** P0는 현재 계획·핸드오프·Baseline 링크의 고정 앵커이며, 이번 정책 반영 커밋 후 추가 실험 코드를 직접 쌓지 않는다.
- **Track A Phase 1:** 다음 세션에서 새 `feature/blazux-phase1-source-compare` 브랜치를 P0의 확인된 최신 HEAD에서 생성. **아직 생성하지 않았음**. Gate 1의 소스·함수/텐서 1:1 비교표, 상태·근거·차단 이슈가 목표다.
- **Track A Phase 2:** Phase 1의 리뷰·문서 결과를 확정한 HEAD에서 **새** `feature/blazux-phase2-offline-fixtures` 브랜치 생성. 작은 BF16 합성 safetensors·Mock·정확성 회귀 검증만 수행.
- **Track A Phase 3 이상:** 승인된 이전 Phase HEAD를 부모로 새 `feature/blazux-phase<N>-<scope>` 생성. PLE/MTP/QSA/Parser 등 기능별 고립·기본 OFF·rollback·A/B 결과를 누적하되 지난 Phase 브랜치 HEAD는 보존한다.
- **Track B(미생성):** 기술적으로 분리된 엔진 이식 실험 `feature/vllm032-bf16ple-port`는 **P0 고정 HEAD에서 별도로 분기**하며 Track A Phase 1/2 코드를 물려받지 않는다. Track B Phase 2 이후는 Track B의 선행 실험 브랜치를 부모로 생성한다. **Track B Go/No-Go 이전에는 브랜치조차 생성하지 않는다.**
- **각 Phase 브랜치의 필수 메타데이터:** 부모 브랜치/정확한 부모 commit SHA, blazux upstream PIN, 이전 Phase 결과·검증 범위, 새 변경 파일의 Source Manifest 전체 path/mode/blob SHA, 테스트/CI 및 차단 이슈, 계속/보류/폐기 결정. 새로운 Phase를 열기 전 부모 HEAD와 트리·manifest를 다시 확인한다.
- **브랜치 이동 정책:** 리뷰·비교가 필요하면 `base=직전 Phase`, `head=현재 Phase` 방향의 diff 또는 PR을 사용하되 **merge 버튼을 누르지 않는다**. phase N 커밋은 새 phase N+1이 부모 SHA로 직접 상속하므로 이전 phase에 역으로 커밋/merge할 필요가 없다. 강제 push·부모 reset/rebase 금지.
- **최종 폐기 정책:** 모든 blazux 결과는 실험 ref에만 존재해야 한다. 진행을 취소하면 새 기능을 운영 `main`으로 되돌리거나 undo할 필요 없이 실험 브랜치를 보존/아카이브하고 종료하면 된다. **Baseline PR #5와 과거 운영 계보는 실험 시작 전 이미 `main`에 존재하므로 유지되며, blazux 관련 신규 commits는 절대 반입하지 않는다.**
- 향후 사용자가 특별히 새로운 정책을 문서화하지 않는 한 **blazux 관련 모든 작업의 GitHub PR target은 `main`일 수 없고 merge/rebase/cherry-pick을 통한 반입도 금지**한다. 작업을 쉽게 하는 목적의 자동 `main` 동기화도 하지 않는다.

~~~text
main @ 2847e39 (PR #5 Baseline 유지, 실험 코드 불변)
  |
  +-- P0 feature/blazux-vllm032-evaluation-20261027 (현 계획 루트)
        |
        +-- Track A: phase1-source-compare (다음 세션에서 생성)
        |     |
        |     +-- phase2-offline-fixtures (Phase 1 확정 후 생성)
        |            |
        |            +-- phase3-<feature> ... (Phase별 새 브랜치)
        |
        +-- Track B: feature/vllm032-bf16ple-port (Go/No-Go 이후 별도 생성)
              |
              +-- 후속 vLLM032 phase 브랜치

[금지] 어떤 실험 브랜치에서도 main으로 commit/PR merge/cherry-pick/squash 이관 불가
~~~

## 2. 비교 대상 스냅샷(확정된 사실과 미검증 사항)

| 대상 | 확인 기준 | 비고 |
| --- | --- | --- |
| 현 프로젝트 GitHub main | **2847e39b4131eb8aff78bf86ffce98892401722a** | PR #5 merge; 이후 커밋 시 HEAD 재검증 필요 |
| 현 실행 컨테이너 | **qwen38-flash-orca-uncensored-bf16-mtp** | 사용자 DGX 로그에서 running 및 API PASS |
| 현 서비스 model ID | **qwen3.8-flash-next-orca-uncensored-bf16-mtp** | /v1/models |
| 현 checkpoint revision | **3a3b63161c0745390e5270179af42e46efc70799** | Orcarouter NVFP4 |
| 현 MTP overlay source | **7b719225242aacd3dbd3f9407468c2ee9a9d2594** | RadixArk, BF16 31 tensors |
| 현 런타임 기반 | **vLLM preview 계열**, docs/BENCHMARKS.md의 0.1.dev20073+g8e685d198 | 정확한 현 컨테이너 실행 버전은 현장에서 재조회 |
| blazux 원본 | **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa** | blazux/qwen3.8-Flash-DGX / Dockerfile vllm/vllm-openai:v0.32.0 |
| llama-benchy 원본 | **e9be344578cec17745066b220798b80a0d2686d3** | 버전 0.4.1.dev1+ge9be34457, 독립 runner 설치 PASS |
| 현 실측 | **2026-10-27 Smoke Test PASS + 정식 Baseline 12조건×3회=36회 완료** | [실측 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), PP/TG/TTFT 및 원본 JSON·반복값 보존 |

본 프로젝트는 자체 Fork와 배포 안전 계약을 유지한다. 모델 이름·체크포인트·가중치/텐서 index·quantization 형식·MTP overlay를 먼저 고정해 비교해야 한다.

## 3. blazux 기능별 기술 검토 매트릭스

### 3.1 기능 우선순위와 선정 규칙

| 우선순위 | 개별 단위 | 1차 목표 | 착수·완료 Gate |
| --- | --- | --- | --- |
| **P1 — 계측·정확성 선행** | PLE wait/dedup/gather/stage 단계별 계측 | 실제 BF16 PLE 병목 분해; 측정 오버헤드 포함 | 소스 비교 → 미개입 계측 → 재현성 확인 |
| **P1 — 계측·정확성 선행** | Prefix caching / Mamba·SSM state 복원 | cold/cache-hit 출력·position 일치 | 합성 state fixture + 스트리밍 회귀 |
| **P1 — 계측·정확성 선행** | Tool Calling·Responses parser | literal marker, 인자 스키마, SSE 조기 종료 검출 | API fixture·한국어/영어·모의 회귀 |
| **P2 — 선택적 최적화** | MTP draft vocabulary 축소 | 메모리 대역폭/acceptance/품질 균형 | 기존 MTP=2/31텐서 guard 유지, 기본 OFF |
| **P2 — 선택적 최적화** | PLE dedup/gather/pinned H2D | 동일 출력 확인 후 시간 감소 여부 판단 | BF16 합성 shard+기능별 개별 flag |
| **P2 — 선택적 최적화** | QSA exact/deterministic top-k | 정확성·결정성/성능 조사 | 커널 SHA pin, output equivalence, 기본 OFF |
| **P3 — 별도 실험·보류** | YaRN 500K, Hybrid FP8, FP8 KV / ModelOpt graft | native context·현 BF16 compatibility 이후 판단 | **별도 실험군/독립 PR**; 직접 적용 금지 |
| **별도 Track B** | 공식 vLLM 0.32 전환 | 새 엔진 compatibility·운영성 검토 | 별도 `feature/vllm032-bf16ple-port`, Go/No-Go |

- **P1 완료 전 P2 성능 최적화 기능을 묶어 도입하지 않는다.** P1은 우선 정확성·관측 가능성 확보이며 자동으로 성능 개선이라고 주장하지 않는다.
- 각 P2 패치는 자체 결과·영향 범위·flag(default OFF)·rollback·시험 보고서를 가져야 한다. 서로 다른 최적화는 한 커밋/PR에 혼합하지 않는다.
- 각 단계에서 판단값은 **KEEP / PORT / ADAPT / DEFER_TO_TRACK_B / REJECT**로 기록하고 원본 함수 경로 및 source SHA를 붙인다.

### 3.2 후보 기능의 기술 검토 매트릭스

아래 상태의 **분석 후보**는 곧 호환성이나 적용 완료를 뜻하지 않는다.

| 후보 | blazux 관련 코드·특성 | 현 Orcarouter/BF16 환경 위험 | 예정 검증 | 상태 |
| --- | --- | --- | --- | --- |
| PLE mmap gather | src/vllm_ple_mmap.py: BF16/F16/FP8 dtype, np.memmap, CPU dedup, page fault 병렬, pinned H2D, GPU inverse scatter | 현재 preview 기반 패치와 constructor/load_weights/n-gram hash/compile 경계 구조가 다름 | BF16 16x160 row 매핑, safetensors offset, 데이터 동일성, mmap/PTE 회귀 | INVESTIGATE |
| PLE 계측 | dedup/gather/stage/wait 분리 및 Prometheus 지표 | 계측 오버헤드, backend 프로세스 메트릭 노출 필요 | P50/P95, CPU, page-cache, fault, KV headroom 추적 | INVESTIGATE |
| MTP draft vocab | src/patch_mtp_draft_vocab.py: drafter 248320 → 65536 제한 | Draft/target vocab index, Orcarouter tokenizer, MTP 정확도/수용률/언어별 결과 변동 | off/on 동일 seed, acceptance, Korean/English, EOS/tool/JSON 회귀 | OPTIONAL |
| QSA deterministic top-k | src/patch_qsadet.py; SM121 커널 | 외부 JIT kernel SHA, torch/vLLM symbols, GPU arch, 정확성/재현성 | exact top-k 비교, temperature=0, long prompt, build provenance | OPTIONAL |
| Prefix cache/Mamba block | src/patch_mamba_block_size.py | block alignment, recurrent SSM state restore, MTP cache 연동 | cold vs warm 결과·정확성, 2회/멀티턴/tool 회귀 | HIGH_PRIORITY_CORRECTNESS |
| M-RoPE window | src/patches/qwen-mrope-cache-window.patch | YaRN >262144, draft/target cache 길이·window 불일치, 품질 저하 가능 | native 262144 먼저, extrapolation은 별도 실험, retrieval 테스트 | DEFER_UNTIL_NATIVE_PASS |
| Safe output/Tools | qwen-safe-output.patch, qwen-tool-argument-schema.patch, qwen-tool-preamble.patch, qwen-tool-marker-guard.patch | Chat vs Responses, streamed argument, hidden reasoning, literal tool tokens | parser/tool/JSON regression, exact literal, partial EOS 오류 | HIGH_PRIORITY_CORRECTNESS |
| Hybrid FP8 side layers | scripts/prepare-hybrid.sh, src/vllm_fp8_hybrid_modelopt.py | **compressed-tensors Orcarouter 경로 직접 적용 부적합**; ModelOpt 기대 | 양자화 dispatch 검증 없이 적용 금지 | NOT_DIRECTLY_APPLICABLE |
| MTP NVFP4 graft | scripts/prepare-mtp-graft.sh | blazux ModelOpt 인풋과 현 BF16 31-tensor overlay 계보가 다름 | 원본 tensor inventory/이름·shape·dtype 1:1 후 검토 | NOT_DIRECTLY_APPLICABLE |
| vLLM 0.32 전환 | Dockerfile, 공식 vllm/models/qwen4_exp/nvidia 경로 | 현 vLLM preview models/qwen3_8_flash_next/nvidia와 파일/API/patched symbols drift | 독립 이미지 빌드·ABI/API 단위 분석, 31/31 MTP load guard | SEPARATE_TRACK |

특히 blazux의 hybrid/MTP graft에서 제시한 성능 이점은 해당 NVIDIA/RadixArk 계보에 대한 것으로, 현 Orcarouter compressed-tensors에 곧바로 대입하지 않는다. blazux 공개 기록에서 vLLM 0.32 결과는 ModelOpt NVFP4/FP8-hybrid/FP8 KV 조건 등으로 측정되었으며, 이 사용자 BF16 PLE/BF16 KV/MTP overlay와 **동일한 A/B 조건이 아니다**.

## 4. 단계별 추진 계획 및 Gate

### Gate 0 — 선행 Baseline 동결 (**실측·GitHub 백업 완료; 재현성 보완 남음**)

1. **DONE:** 사용자 DGX에서 Orcarouter 모델의 PP 2048/8192 × TG 128/256 × Depth 0/4096/16384, concurrency 1, 조건별 runs=3/warmup=1, latency-mode=generation, exact-tg, NumPy seed 20261027로 **총 12개 조건·36개 측정값**을 수집했다. 원본 결과 timestamp는 **2026-10-26T22:34:42Z**.
2. **DONE:** llama-benchy 소스 **e9be344578cec17745066b220798b80a0d2686d3**, 사용자 환경 실행 버전 **0.4.1.dev1+ge9be34457**. 사용자 DGX에서 독립 runner 설치와 Smoke PASS를 확인했다.
3. **DONE:** PR #5에서 원본 `result.json`(532,605 bytes, SHA-256 **25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf**), 공개용 environment, 원본 SHA256SUMS 및 보고서/핸드오프를 본 저장소에 보존했다. 내부 Docker 전체 ID가 포함된 원본 environment는 공개하지 않았다.
4. **부분 검증:** 업로드된 원본 result/environment의 SHA-256 2개만 대조됐고, progress JSONL·로그·메모리/GPU 등 체크섬 목록의 나머지 7개 파일은 미첨부였다. 당시 실제 입력 corpus SHA/서버의 모든 sampling 파라미터는 별도 확인 필요하다.
5. **NOT_RUN:** 이번 PR에 추가된 `scripts/benchmark/run-llama-benchy.sh` 자체의 실 DGX 실행 및 새 코드 회귀/CI/공개 감사. 사용자 지시로 생략했고, 과거 수동 벤치 성공을 신규 스크립트 성공으로 주장하지 않는다.
6. **Gate 통과 해석:** 측정 원본을 동결하고 **Gate 1 정적 호환성 분석을 시작할 근거는 확보**했다. 그러나 *엄격히 동등한 A/B* 완료를 주장하려면 코퍼스 hash, sampling/요청 payload, 런타임/모델·KV·메모리·캐시 조건의 동일성 검증을 완료해야 한다. 후보 GPU 실행·운영 교체는 별도 승인과 안전 Gate를 필요로 한다.

### Gate 1 — 1:1 정적 코드·데이터 계약 비교

**이 Gate의 산출물:** 양측 함수·entry point·데이터 flow의 1:1 대조표(경로/함수/입력/출력/shape/dtype/오프셋/의존 라이브러리, 이미 구현된 기능·누락 기능, 재현 근거), 기능별 **KEEP/PORT/ADAPT/DEFER_TO_TRACK_B/REJECT** 결정표, patch provenance 및 테스트 fixture 정의. 원본을 통째로 merge하지 않는다.

- 양측 PLE mmap 파일/의존 모듈의 init/load/forward/Gather 함수, dtype dispatch, alignment, missing tensor/duplicate 처리, page-cache/pinned staging 등을 **함수별 표**로 만들고 KEEP/PORT/ADAPT/REJECT를 결정한다.
- MTP draft module과 model loader, fused experts, 31 overlay tensor 목록 및 정확한 BF16 tensor hash/load-guard를 비교한다.
- vLLM preview ↔ 0.32 상속/등록/compile/graph break/op cache와 CPU↔GPU 전송 경계를 추적한다.
- blazux 변경 의존성(일반 patch, 외부 커널, Docker base/torch/triton/transformers)과 라이선스·서드파티 출처를 적는다.
- 문서 산출물: 호환성 매트릭스, 위험도, 최소 포팅 범위, 테스트 가능한 스코프, 명시적인 보류 항목.

### Gate 2 — 오프라인/모의 회귀시험

**작은 합성 데이터 우선(기존 운영 모델 가중치 불사용):**

1. 소형 BF16 safetensors shard를 임시 독립 디렉터리에 만들고, 서로 다른 tensor 크기·offset·alignment·shard boundary·duplicate n-gram IDs·유효/무효 row index를 고정 fixture로 정의한다. FP8 scale 경로는 **별도 fixture**로 분리하며 BF16 결과와 혼합하지 않는다.
2. 현 preview 경로와 후보 PLE의 CPU index/dedup/sort/gather/inverse-scatter를 **동일 입력으로 1:1 비교**한다. dtype 변환 없는 BF16 경로는 원본 tensor 값·출력 순서의 정확한 동일성을 우선하며, 불가피한 GPU 연산 오차는 사전 합의한 tolerance와 근거를 명시한다.
3. page fault·mmap offset·Pinned H2D·비동기 copy stream 순서, 잘못된 header·비정렬 tensor·손상된 index에서 Fail-Closed 동작을 검사한다. 부하/시계열 계측은 실제 서버 실행과 분리한다.
4. MTP는 BF16 31개 overlay tensor name/shape/dtype/load guard와 depth 0/2, acceptance·다국어·EOS/JSON/tool fixture를 독립 검증한다. Tool Parser/Responses와 prefix-cache/SSM state의 합성 회귀는 각각 독립 suites로 운영한다.
5. 테스트 성공·실패와 환경, 단순 import/CPU mock과 실제 DGX GPU 검증을 별개의 상태로 기록한다. **사용자 승인 전 GPU 모델 기동 없음**.

**기능 격리 계약:** 각 성능 패치는 독립 설정값을 갖고 기본값은 OFF(기존 경로), OFF 시 기존과 기능·결과가 같아야 한다. flag ON 단일 기능만 시험한다. 실패·불일치·메모리 한도 초과 시 **기존 코드 경로로 롤백 가능함을 확인하기 전 병합 금지**.

- 기존 operational mock 및 전체 unit tests는 변경 전 증거로 유지하고, 새 코드 적용 후 새 commit에서 다시 실행한다.
- 핵심 함수별 정상·실패·경계 조건: safetensors offsets/shards, BF16 vs FP8 scale, mmap page offsets, CPU dedup→GPU inverse permutation, async H2D ordering.
- MTP load guard 31/31, draft off/on, unsupported quantization 실패 시 **Fail closed**. Draft vocab이 target logits의 범위를 잘못 축소하지 않는지 확인.
- Stream parser / tool JSON / reasoning vs visible token clocks / prefix-cache state restore 검증.
- 기존 모델/뷰·HF snapshot에 복구 불가능한 변경을 하는 테스트는 금지한다.

### Gate 3 — Track A 선택적 적용 및 Track B 독립 빌드 계약

**Track A — 현행 엔진 우선:** PLE 계측/정확성 fixture처럼 기존 vLLM preview 이미지의 인터페이스에서 포팅 가능한 사항부터 독립적으로 검증한다. **이 Gate를 시작한다고 새 vLLM 0.32 이미지를 빌드하거나 운영 모델을 띄우지 않는다.** 새 GPU 실험은 별도 승인과 사전 자원 점검 후에만 한다.

**Track B — 향후 독립 장기 브랜치에만 적용하는 자산 이름·소유권 계약(예시; 미생성):**

| 자산 | 신규 실험 전용 규칙 | 금지되는 기존 자산 재사용 |
| --- | --- | --- |
| 브랜치 | `feature/vllm032-bf16ple-port`, 승인 후 별도 생성 | 현재 blazux evaluation 브랜치와 섞어 엔진 전체 교체 |
| Docker image | `qwen38-vllm032-bf16ple:eval-<short-sha>` + pin된 base **digest** | `yslab-qwen38-bf16ple:9492b78c` 덮어쓰기 |
| Container | `qwen38-vllm032-bf16ple-eval-<run-id>` 및 전용 ownership label/정확한 ID receipt | `qwen38-flash-orca-uncensored-bf16-mtp` 교체/삭제 |
| API port | 실행 전에 실제 free port 확인 후 **127.0.0.1 바인딩만** 예약·기록 | 현 레거시 8000, Wizard 예약 18300 무단 점유 |
| Receipt/state | `$HOME/.local/state/qwen38-vllm032-bf16ple-eval/<run-id>/` 신규 소유 경로 | 레거시·Wizard의 영수증/state |
| Model view/cache | `$HOME/Workspace/llm/experiments/vllm032-bf16ple/<run-id>/` 내 전용 모델 view·읽기 정책 | 기존 HF cache/recipe-views/weight snapshots에 쓰기 |
| Bench results | `$HOME/Workspace/llm/bench-results-staging/<UTC>-vllm032-eval/` | 원본 pre-blazux 결과·해시 덮어쓰기 |

- 각 신규 실험 자산은 ownership label, 정확한 image/container ID 및 receipt가 **일치할 때만** 별도 소유 자산에 대한 정리/롤백을 검토한다. `docker rm -f` 같은 컨테이너 이름 기반 강제 삭제 금지. blazux `scripts/serve.sh` 직접 실행 금지.
- 단일 GB10에서 기존 레거시 서비스가 운영 중인 동안 **또 다른 대형 GPU 모델의 병렬 기동 절대 금지**. 별도 포트/이름만으로 메모리 충돌은 막지 못하므로 GPU activation은 사전 가용성·점검 창·사용자 승인 확인이 전제다.
- Docker base/코드/torch/triton/vLLM/patch/license digest와 model/overlay/Tokenizer 해시를 기록하고 신규 HF model download, FP8 conversion, 기존 경로 overwrite는 별도 명시적 승인 전 수행하지 않는다.

- blazux scripts/serve.sh는 운영에서 **직접 실행 금지**. 현재 blazux serve.sh에 동일 컨테이너 이름으로 docker rm -f를 실행하는 경로가 존재한다. 별도 소유권 receipt, 정확한 ID/label 확인, replace 거부 및 dry-run이 없는 한 사용하지 않는다.
- blazux 기본 PORT=18300과 본 저장소 Wizard 예약 127.0.0.1:18300의 충돌 여부를 확인하고 **임의로 덮어쓰지 않는다**.
- 단일 GB10에서 레거시 서비스가 운영 중일 때 신규 대형 GPU 이미지 동시 가동 차단 정책을 지킨다. 별도 이름/포트만 바꿔도 통합메모리 부족은 해결되지 않는다.
- HF cache/recipe-views/weight snapshots/legacy receipts 불변. 포트 8000, 기존 컨테이너, image 및 네트워크도 불변.
- Docker base는 가급적 digest까지 기록하고, Python/torch/triton/vLLM와 적용 patch SHA/결과 파일 hash를 고정한다.
- 실제 새 GPU activation/중단/교체·서비스 전환은 **별도 구체적 승인과 안전한 점검 시점** 없이는 실행하지 않는다.

### Gate 4 — 기능 정확성 및 자원 수용

- model load: Orcarouter compressed-tensors trunk+BF16 PLE+BF16 MTP 31/31을 확인; 실제 QSA, KV, SSM, vocab 동일성 확인.
- API: /health, /v1/models, /v1/chat/completions full/stream, tool-call JSON/arguments, parser, reasoning hidden/visible, EOS/stop 처리.
- MTP=0/2 비교, acceptance, 무한/조기 종료, prefix cache fresh/reuse, Korean/English 및 code/JSON/정확한 retrieval fixture.
- Native context에서는 4K, 16K, 32K, 64K, 128K, 240K까지 단계적으로 확대하되 메모리/latency 위험을 관찰한다.
- YaRN 500K는 **native 동작 확인 후 별도**. blazux 기록에서도 보고된 모든 오류의 재현/해결이 입증된 것은 아니므로 광범위한 안정성을 추정하지 않는다.
- GPU/KV 메모리, MemAvailable, swap, PLE page cache, CPU, temperature, start time, OOM 등을 기록한다.

### Gate 5 — 공정한 A/B 성능 시험

- 고정된 pre-blazux와 candidate에서 **같은 모델 가중치·overlay·Tokenizer/코퍼스·인자·도구 SHA·sampling·context·warmup·동시성·cache 조건** 적용.
- 샘플 간 순서/온도/상주 page-cache 영향 및 재부팅·cold start 차이를 통제한다. 부하 중 background service, swap, GPU/KV 메모리 동적 변화를 함께 남긴다.
- PP, TG, TTFR, E2E TTFT, peak/aggregate, P95, 32K+ long-context, prefix cache, 동시성 1/2/4/8을 별도 시리즈로 집계.
- 관찰된 결과만 기록하고 유의하지 않거나 변동이 크면 **INCONCLUSIVE**. 모델 변경·FP8 hybrid 변경을 동반하면 별도 실험군으로 표기.
- 비교 보고서에는 throughput 상승/하락뿐 아니라 정확성, 실패율, startup, 메모리/KV 여유와 operability tradeoff를 포함한다.

### Gate 6 — 코드 리뷰와 통합 결정

**Phase acceptance (main merge 금지):** 기능별 최소 변경과 default-OFF feature flag, 종전 경로 동작 동일성, BF16 합성 fixture·negative cases·MTP 31/31 load guard, 리소스/정확성 및 Baseline 대응 결과, Source Manifest의 path/mode/blob SHA, 라이선스와 독립 롤백 절차를 각 Phase 리뷰에서 확인한다. 실패한 Phase에서는 새 Phase를 열지 않는다. 성공한 결과도 **실험 계보에만 보존**하고 `main`에 넣지 않는다.

- 수집된 원시 결과가 Gate 0 Baseline과 연결되었고, patch provenance/라이선스/수정 영향 및 소유권 검사에 근거한 경우에만 **다음 Phase 분기(Go/No-Go)**를 검토한다. 그 자체로 `main` 병합을 승인하지 않는다.
- 단계별 롤백 경로는 새 소유 자산 안에서만 검증한다. 기존 레거시 rollback을 핑계로 stop/rm/prune을 호출하지 않는다.
- 전체 vLLM 0.32 포팅은 선택적 기능·계측 포팅과 별도 **Track B 실험 계보**로 유지하고, 해당 결과 역시 `main`으로 PR/병합하지 않는다.
- 운영 환경 변경은 GitHub 코드 merge와 **별개 승인 절차**로 처리한다.

## 5. 실험군·측정 결과의 저장 구조(제안)

~~~text
docs/
  BLAZUX-VLLM032-ADOPTION-PLAN.md    # 이 브랜치에서 이미 커밋된 계획서
  SESSION-HANDOFF-PROMPT.md
  benchmark/
    LLAMA-BENCHY-BASELINE-20261027.md  # PR #5에서 main에 병합된 12x3 Baseline
    A-B-COMPARISON.md                    # 실측 이후 생성
results/
  llama-benchy/
    baseline/
      pre-blazux/
        <UTC-run-id>/result.json
        <UTC-run-id>/environment.public.json
        <UTC-run-id>/SHA256SUMS
    candidates/
      blazux-vllm032/
        <UTC-run-id>/result.json
        <UTC-run-id>/environment.public.json
        <UTC-run-id>/SHA256SUMS
scripts/
  source-state-manifest.json             # 모든 변경 파일의 SHA/mode 동시 갱신
  benchmark/
    run-llama-benchy.sh               # PR #5 main에 존재, 신규 스크립트 실실행 NOT_RUN
~~~

중요: 경로는 **제안**이다. 현 DGX에 실제 생성됐거나 GitHub에 커밋된 경로로 단정하지 않는다. 공개 업로드 전 출력·요청 payload/프롬프트/토큰 스트림, 파일 경로, 환경변수, image/container full ID를 검사한다. 전체 원시 로그가 민감하면 개인 DGX에 보존하고 공개 Git에는 검증·정제 결과와 원본 해시만 보관한다.

## 6. 커밋·브랜치·Source Manifest 계약

- **Baseline 선행 PR #5는 2026-10-27 MERGED:** 새 `main` SHA **2847e39b4131eb8aff78bf86ffce98892401722a**. 정식 12×3 원본 `result.json`은 이제 `main`에 존재하며 다시 생성·덮어쓰기 금지.
- **blazux 실험 루트(P0):** `feature/blazux-vllm032-evaluation-20261027`, PR #5 병합된 main에서 **과거에 한 번** 분기. 이번 정책이 확정된 후에는 이 브랜치를 기준으로 **Phase마다 별도 새 브랜치**를 만들고, `main`을 새 base로 삼거나 역방향으로 blazux 변경을 반입하지 않는다.
- 이후 실제 기능 변경은 **Track A Phase 1부터 별도 자식 브랜치**에서 진행하며 blazux PIN/patch provenance, 합성 데이터 오프라인 시험, 독립 default-OFF flag/rollback, Source Manifest를 Phase별 커밋에 반영한다. **Track B** `feature/vllm032-bf16ple-port`는 별도 Go/No-Go 이후 **P0에서 갈라진 형제 실험 브랜치**이며 `main`에서 신규 분기하지 않는다. **이번 실험의 어떠한 PR도 `main`을 대상으로 하지 않는다.** 운영 서비스 변경은 GitHub 리뷰·커밋과 무관한 별도 승인 행위다.
- `scripts/source-state-manifest.json`은 모든 tracked 파일의 path/mode/Git blob SHA 스냅샷이다. PR #5 머지 직후 **manifest 제외 119개(전체 120개)**였고, 본 계획서 1개 추가 시 **manifest 제외 120개(전체 121개)**를 기록해야 한다. HEAD 이동 시 숫자와 실제 tree를 재확인한다.
- Manifest 자기참조 제외, 실제 Git blob/mode 전수 비교를 요구한다. `--strict`는 현재 `main`과 기존 승인된 release feature만 허용하므로 이번 신규 feature 브랜치에서 strict PASS를 주장할 수 없다.
- 기존 GitHub Actions **run=0**, `CI_NOT_VERIFIED`. CI 정상화는 사용자가 별도로 연기한 과제이고, 이번 문서 작업에서 재개하지 않는다.
- 문서 변경 커밋은 **실 DGX test, vLLM 0.32 이미지 빌드, 호환성 확인 또는 서비스 교체 성공**을 의미하지 않는다. `main`의 검증·운영 보호 및 **blazux 관련 PR/merge 금지**는 정책적 보호이며 GitHub의 Branch Protection / Ruleset 활성 상태와 구별한다. 새 Phase는 독립 브랜치로만 생성·검증하고 기존 Phase 브랜치의 HEAD는 임의 이동하지 않는다.

## 7. 위험 목록·중단 기준

| 위험 | 지표/중단 기준 | 완화 |
| --- | --- | --- |
| 기존 레거시 중단/삭제 | 컨테이너/이미지 ID, 포트, legacy receipt 다름 | 즉시 STOP, 조회만. 신규 엔진 강제 rm 실행 금지 |
| 단일 GB10 용량 초과 | MemAvailable 급감, swap/fault 급증, KV 부족/OOM | 새 대형 서버 동시 활성화 금지, 실험 전 자원 gate |
| BF16 PLE scale/index 해석 오류 | 텐서 shape/dtype/gather 결과 mismatch | 오프라인 1:1 비교, 로드 검증 실패 시 중단 |
| compressed-tensors dispatch 실패 | ModelOpt FP8 conversion/quantizer 충돌 | hybrid 모델 변환을 현 target에 직접 적용 금지 |
| BF16 MTP overlay 손실 | 31개 tensor load guard 실패/acceptance 이상 | deployment fail-closed, MTP0/2 회귀 |
| cache/SSM 오류 | prefix 반복 요청 오답, 긴 컨텍스트 재현성 문제 | cache state/정확성 시험으로 검출 |
| Tool/output 파서 변경 | literal token 조기 종료/JSON 형식 오류 | 스트리밍·non-streaming·Korean/English fixture |
| 벤치 측정 왜곡 | 모델/코퍼스/seed/latency-mode/메모리 설정 불일치 | 환경 원본·해시·메트릭 정의 함께 보존 |
| Docker 빌드 provenance 불명 | 이미지 tag만 기록, base digest 없음 | digest/dependency/patch 정확한 SHA 기록 |
| 정보 유출 | 파일·API/모델 로그에 기밀·주소·신원 | 공개 안전 감사, 민감 원본 로컬 보존 |

## 8. 현재 상태·다음 작업

**확정·완료:**
- 실 DGX legacy /v1/models·서비스 running 상태, Tokenizer SHA 확인.
- llama-benchy **0.4.1.dev1+ge9be34457** 독립 설치 PASS, Smoke PASS.
- 정식 pre-blazux **12×3=36** 실측 완료, 원본 JSON SHA-256 확인 및 [PR #5](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/5)로 **main 백업·병합 완료**.
- [정식 Baseline 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), 재실행 Bash 스크립트, Source Manifest 및 핸드오프가 main에 기록되어 있음.
- blazux 원본 **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**, 관련 핵심 소스·패치·테스트 경로를 정적 조회.
- **본 별도 브랜치의 첫 변경은 문서 작성/계획·절차 확정에 한정한다.** 구현 및 배포는 없음.

**미완료·위험/차단:**
- 원본 코퍼스 SHA·샘플링 페이로드/KV 설정/서버 환경 추가 식별 및 해당 수준의 A/B 조건 대조.
- PR #5 신규 벤치 스크립트 실제 실행(사용자 요청으로 테스트 생략), 사후 CI 및 신규 실 DGX 런타임 테스트.
- blazux 1:1 실제 함수/패치/tensor inventory 표와 현 Orcarouter compressed-tensors + BF16 PLE + BF16 MTP 오버레이의 모델 로더 호환성 검증.
- 별도 vLLM 0.32 이미지 빌드, 신규 소유 컨테이너 활성화·회수·rollback, 동시 GPU/메모리 영향 및 실제 A/B 데이터.
- 실제 서빙 서비스 stop/replace/remove/이관 및 blazux 최적화 개선 주장. 단일 GB10 기존 서비스 보호는 계속 P0이다.

**다음 단계:** (1) 현 P0 HEAD를 검증하고 **Track A Phase 1 자식 브랜치를 새로 생성** → (2) pinned blazux ↔ 현 preview의 1:1 함수·텐서 대조표 → (3) Phase 1 확정 HEAD에서 **Phase 2 신규 브랜치**를 열어 P1 계측/정확성·합성 BF16 fixture → (4) 각 후속 Phase를 별도 자식 브랜치에서 default-OFF 기능별 검증 → (5) 실험 성과/차단 증거는 **실험 브랜치에만 보존**한다. `main` PR/병합은 어떤 Phase에서도 진행하지 않는다. **Track B**는 Go/No-Go 결정 후 P0에서 `feature/vllm032-bf16ple-port` 형제 브랜치로 분기하여 별도 자산으로 실험한다. **현재 실행 중인 레거시는 변경하지 않는다.**
