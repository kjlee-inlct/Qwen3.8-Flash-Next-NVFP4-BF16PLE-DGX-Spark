# SESSION-HANDOFF-PROMPT.md

## 2026-10-28 DGX A5 실제 오프라인 회귀 영수증 — 99/99·Source216/216 PASS

- **검증된 DGX checkout exact HEAD**: `6afade42bdf40f73c644f96ecbc17b4f3ad36f7f` (`feature/blazux-phase6-runtime-gates`), `git pull --ff-only`로 `882b590... → 6afade4...` fast-forward 확인. `bash scripts/phase6-gate.sh`: `Ran 99 tests in 0.016s`, `OK`; `PASS_SOURCE_ONLY: 216 tracked file(s)`와 동일 HEAD; 종료 마커 `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, 사용자 래퍼 `PHASE6_A5_OFFLINE_SOURCE_VALIDATION_COMPLETED`를 확인했다.
- **정확한 검증 범위**: Python 오프라인 회귀 및 Source Manifest의 tracked path/mode/blob 무결성만 검증했다. 로그에 Docker 내부 객체 관찰, GPU/모델 추론, 커널 실행 또는 실시간 ABI 결과는 없다. 이 영수증을 P6-A 활성 ABI 합격으로 승격하면 안 된다. **P6-A ACTIVE `BLOCKED_MISSING_IN_PROCESS_EVIDENCE`; P6-B/C/D `NOT_RUN`.**
- 사전 승인된 PRE-B 벤치 1회는 이미 소진되었으므로 재실행하지 않는다. 다음은 [P6-A5 관측 가능성 정본](BLAZUX-PHASE6-A5-ACTIVE-ABI-OBSERVABILITY-DECISION-20261028.md)의 별도 승인 필요 검증 경로만 유지한다. 이 로그를 기록한 **후속 문서·Manifest 커밋 자체는 DGX 미시험**으로 분리한다. 운영 Docker/기존 모델/포트/원본 결과 변경, PR/CI/merge 없음.

---


## 2026-10-28 P6-A5 BLOCKED 원인 및 안전한 후속 결정

[**P6-A5 실제 ABI 관측 가능성 결정서**](BLAZUX-PHASE6-A5-ACTIVE-ABI-OBSERVABILITY-DECISION-20261028.md)에 기존 `/metrics`가 시작 시 CacheConfig `block_size=8`만 보여 주며, **실제 선택된 Scheduler/Mamba 그룹·block-table·GPU state의 physical ID/stride/할당 경계를 노출하지 않는 구조적 증거 공백**을 명시했다. 이는 **관측 부족에 의한 `BLOCKED`이지 관측된 ABI `FAIL`이 아니다.** 기존 HTTP/기본 Docker metadata 반복은 Full P6-A를 PASS로 만들지 못한다.

**다음 단계**는 운영 서비스 비변경을 원칙으로 하는 별도 승인용 **향후 in-process attestation** 설계이며 현재 운영 프로세스에 코드를 삽입하거나 재시작/attach/exec하지 않는다. 대안인 격리 GPU/모델 ABI 검증도 별도 승인과 자원 판정이 있어야 하며 기존 활성 프로세스의 실측으로 승격할 수 없다. 승인 소진된 12×3 벤치 재실행 금지. 마지막 실제 DGX 오프라인 99/99·Source212/212 PASS는 `882b590119afcdadb06afe9938c7f3e10c866656`에만 적용되며, 이번 문서·Manifest 신규 HEAD는 DGX NOT_RUN. P6-A ACTIVE `BLOCKED`, P6-B/C/D `NOT_RUN`, patch/PR/merge/CI/운영 변경 없음.

---


## 2026-10-28 DGX 실제 로그 반영 — P6-A 부분 관찰 / 신규 PRE-B 1회 완료

**2026-10-28 DGX 신규 증거 반영:** `d031d419...`에서 99/99 tests + Source211/211 PASS, P6-A 시작 시 cache metric `block_size=8`, `enable_prefix_caching=false`, `gpu_memory_utilization=0.8`만 노출; **실물 ABI BLOCKED**. 승인된 PRE-B 기존 서비스 신규 12×3/36회가 **`PASS_PROVISIONAL_PRE_B_36`**로 1회 완료됐으며 `result.json` SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d` (콘솔 보고; GitHub에서 원본 별도 재해시 아님). **추가 실행/재시도 금지**. `13668e0...` 및 본 문서만 변경하는 후속 HEAD는 DGX NOT_RUN, P6-B/C/D NOT_RUN. 자세한 영수증: [BLAZUX-PHASE6-RESULTS.md](BLAZUX-PHASE6-RESULTS.md).

기존 이력·상시 운영 규칙은 아래에 원문을 유지한다.

---


## 현재 진행 작업만 인수인계할 때 읽을 우선 문서 (2026-10-28)

- **새 대화에 바로 붙여 넣을 현재 작업 전용 프롬프트**: [PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md). 이 요약은 지금 진행 중인 Phase6 실서비스 ABI 관찰 + 승인된 기존 서비스 벤치 재측정만 다루고, 본 문서 아래에 누적된 과거 확정 사실·완료 이력·운영 금지 규칙은 링크로 참조한다.
- **마지막 실제 DGX-tested 소스 SHA**: `fb5deae540812a300cb8404a53a202e505c40577` (70/70 Phase6 unit, Source204/204, 기존 Baseline 원본 SHA/12×3 검증 PASS, 신규 inference `NOT_RUN`). **현재 기능 구현 GitHub 코드 SHA**: `d031d4196eab1f5f1603d6541eaf5a31b02192c0` (새 live `/metrics` 관찰기와 guarded provisional 12×3 스크립트, 아직 DGX NOT_RUN); 현재 문서만 변경한 새 commit은 별도로 DGX 테스트한 SHA가 아니다.
- CI/PR: 2026-10-28 구현 HEAD 조회 당시 **Open PR 0**, combined statuses `[]`, 조회 가능한 PR-triggered workflow runs `[]`. 이 정보는 GitHub CI PASS를 뜻하지 않는다. 현재 진행 단계에서는 별도 기능 merge/PR이 없으며 본 문서 갱신으로 기존 보호 규칙을 변경하지 않는다.

---

## 2026-10-28 최신 Phase6 실제 A 관찰 시도 + 승인된 기존 서비스 벤치 스크립트 검증 — 선행 상태

- **사용자 신규 실행 승인**: 실제 P6-A ABI 검증을 시도하고 이미 과거 Baseline이 있더라도 신규 벤치를 **스크립트 검증 목적**으로 수행, 오래된 문서를 갱신. 이 승인은 운영 서비스 재시작/변경·새 GPU 모델·blazux patch/CI/PR/Merge 권한이 아님. **DGX는 사용자 조작**, GitHub가 제공하는 스크립트를 검사해 실행하고 결과를 수집한다. [현재 실행·안전 경계 정본](BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md).
- **직전 실제 DGX 통합 검사 exact SHA `fb5deae540812a300cb8404a53a202e505c40577`**: Phase6 70/70 unittest PASS, Source204/204 PASS, 기존 2026-10-26/27 llama-benchy 12×3/36 pre-blazux result SHA·runner/tokenizer/frozen matrix PASS, `PLAN_READY_NOT_EXECUTED`, `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`. 70/204는 해당 소스 SHA 전용이며 새 GitHub 코드에 자동 귀속하지 않음.
- **신규 Phase6 P6-A 실제 노출형 관찰기**: clean checkout/source manifest·Docker pinned image/StartedAt/ID 전후 확인 후 loopback `GET /v1/models`, `GET /metrics`만 조회; vLLM `vllm:cache_config_info`가 이미 제공하는 경우만 block_size/prefix_caching/gpu_utilization의 allowlist 값 표시. 이 메트릭은 **시작 시 공개된 cache-config 값**이며 실제 Scheduler class/그룹별 MambaSpec/physical table·GPU state pointers를 증명하지 못함. 이 필드의 실제 in-process 안전 observer가 없으면 `P6-A ACTIVE ABI BLOCKED` 유지. `docker exec`, ptrace, live code instrumentation, 2nd model start는 이 승인에 포함되지 않음.
- **신규 Phase6 P6-AB 실제 부하 검증**: `scripts/phase6-ab-provisional-run.sh --preflight`(무부하) 후 `--execute`(기존 `127.0.0.1:8000/v1` 모델에 **추론 부하 12조건×3회/총36회**). P6-A 여전히 BLOCKED이므로 결과를 **PROVISIONAL_PRE_B_EXISTING_SERVICE_NOT_GATE_PASS**로만 기록. Pre-blazux 원본은 불변; private staging에 별도 `phase6-pre-b-provisional` 새 결과 + SHA·36 raw repeats 및 허용된 공개용 12조건 numeric summary. Runner/head·Tokenizer·현재 corpus 해시·Docker image/StartedAt·RAM ≥8GiB preflight, 진행 중 RAM <4GiB 또는 identity drift/1시간 초과시 **벤치 자식 프로세스 그룹만 중단**, 레거시 운영 컨테이너 stop/restart/exec 절대 하지 않음. 현재 데이터만으로 정상 서비스 응답시간 불변을 보장하지 않으며 부하 시 영향 가능.
- **새 HEAD GitHub 소스 상태**: 신규 A observer 12 synthetic/offline tests + 벤치 watchdog/결과 검증 17 tests, 새 runbook 등으로 기존 70건에서 **99건 예상**, Source204에서 **211 tracked 파일 예상**. **신규 HEAD DGX NOT_RUN**이며 결과를 받기 전 PASS 주장 금지. P6-B/C/D 미실행. 과거 Baseline의 실제 corpus SHA·샘플링·KV(cache) 동일성 여전히 미확정 → 원본↔신규 strict 성능 개선율 금지; 새로운 같은 조건 PRE-B/POST-B 쌍으로만 추후 비교 가능. `main`/P0/Phase1–5, 고정 이미지/기존 서비스/원본 Baseline 보호.


## 2026-10-28 P6-AB-0 DGX 검증 확정 — 최신 체크포인트

- **DGX operator-tested exact source SHA** `fb5deae540812a300cb8404a53a202e505c40577`: dedicated Phase6 checkout (`~/Workspace/llm/blazux-phase6-gates`) `git pull --ff-only` from `0ad5e62...`, Phase6 unittest **70/70 PASS** (`Ran 70 tests`, `OK`), `PASS_SOURCE_ONLY: 204 tracked file(s)` **204/204 PASS**. Offline marker `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`; P6-AB stdout marker `PHASE6_AB_BENCH_CHECKPOINT_PLAN_ONLY_NO_LOAD`, `PHASE6_AB_BENCH_BASELINE_LOCKED_NEW_BENCH_NOT_RUN`, final `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`.
- **검증된 기록 범위**: 기존 pre-blazux `result.json` **원본 SHA256 match=true**, `environment.public.json` runner SHA/tokenizer SHA/매트릭스 provenance match=true, **12 conditions × 3 measured repeats = 36 raw measurements** (`generation`, concurrency=1, PP[2048,8192], TG[128,256], context depth[0,4096,16384], warmup=1, NumPy seed=20261027). **지금 새 36회 벤치를 실행한 것이 아님**: P6-AB 상태 `PLAN_READY_NOT_EXECUTED`, `pre_b_checkpoint_run=NOT_RUN`, `performance_benchmark_authorized=false`.
- **여전히 미해결**: 2026-10-26/27 역사적 실제 Gutenberg corpus SHA 없음, sampling/KV 정확한 동등성 `UNVERIFIED` → 과거 기준선과 엄밀한 동일조건 비교 `BLOCKED`. Active Scheduler class/CacheConfig/그룹별 MambaSpec/block tables/GPU state 주소 미관측 → **P6-A 실제 ABI BLOCKED**, P6-A→B 진행 `BLOCKED_UNTIL_REAL_A_GATE`, P6-B/C/D NOT_RUN/BLOCKED. 기존 운영 port 8000 대상 `scripts/benchmark/run-llama-benchy.sh`는 사용자로부터 별도 부하 승인받지 않았으므로 **실행 금지**.
- **향후 분리 절차**: A 실런타임 정확성에 대한 독립적 증거와 PASS 선행, 그 다음 target-specific serving/HTTP/모델 GPU 작업 및 벤치마크를 별도 승인받아 정확히 12×3 새 `phase6-pre-b-unmodified` private staging 작성 → B 단계를 마친 후 동일 조건 `post-B` 대조. P6-AB fresh run은 계획이며 P6-D 공식 회귀/안정성 시험과 구분; 임계값 사전 승인·코퍼스/샘플링/KV 일치를 먼저 확보. [P6-A→B 체크포인트 정본](BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md).
- 이 DGX 통합 로그는 정확히 `fb5deae...` 코드만 시험한 증거임. 다음 문서·Source Manifest 증거 커밋은 **DGX 미시험 docs-only SHA**. `main`/P0/Phase1–5/기존 원본 benchmark/Docker/weights/port/cache 불변, CI/PR/merge/패치/GPU/모델/API/신규 벤치 수행 없음.


## 2026-10-28 최신 결정: P6-A → P6-AB 성능 체크포인트 → P6-B (계획 승인, 추론/벤치 실행 미승인)

- **사용자 요청**: P6-A에서 P6-B로 이동하기 전 벤치마크를 남겨 추후 B/C 개선·회귀를 판단할 기준점 확보. [P6-A→B 벤치 체크포인트 정본](BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md)을 신설; **옵션/권장 중간 성능 기록**이며 A/B/C correctness 및 P6-D 공식 성능 Gate를 대체하지 않음.
- **최근 DGX 사용자 실제 확인 SHA** `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`: Phase6 57/57 unittest PASS, Source200/200 PASS, CPU-only 1회 고정 이미지 소스 AST 8컴포넌트·역사적 SHA 7개 검증 `PASS_PINNED_SOURCE_AST_ONLY`, 운영 컨테이너 실행/고정 이미지 동일성 전후 PASS, 호스트 MemAvailable=14064MiB, `PHASE6_A3B1_DGX_SOURCE_PROBE_COMPLETED`. **실제 활성 Scheduler/CacheConfig/MambaSpec/물리 table/state pointer는 미관측**, P6-A 실제 ABI `BLOCKED`; P6-B/C/D NOT_RUN.
- **지금 구현한 중간 단계 P6-AB-0**: 최초 pre-blazux `result.json` SHA256 `25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf`와 12조건×3회 원본 숫자, `environment.public.json`의 runner/tokenizer 및 반복·seed를 검증하는 `scripts/phase6-ab-benchmark-plan.sh` 및 CPU stdlib 계약 검사만 포함. **신규 추론·벤치 측정은 하지 않음**; 이번 코드 HEAD는 DGX NOT_RUN, 신규 **13 unittest/4 tracked files**, 다음 기대 총 Phase6 **70 tests / Source204** (실제 DGX PASS는 아직 아님).
- **향후 진짜 PRE-B 재측정 P6-AB-1**: P6-A 실제 PASS, 격리 후보 또는 운영 API 대상의 구체적 HTTP/GPU 부하 및 모델 접근 승인, 동일 12×3·1 warmup·3 repeats, runner/tokenizer/corpus SHA, 샘플링·KV/cache 및 컨테이너 환경·자원 기록을 조건으로 별도 36회; 기존 `scripts/benchmark/run-llama-benchy.sh`는 운영 `127.0.0.1:8000`을 대상으로 하므로 **허가 없이 실행 금지**. 원본 pre-blazux 실측과 새 PRE-B 결과는 독립 저장, 과거 corpus/sampler/KV 동등성이 없으면 **strict A/B 비교 BLOCKED**; 대신 향후 동일 조건의 pre-B/post-B 신규 쌍으로 비교할 것. 임계값은 사전 승인 전 미확정. P6-AB-1 벤치 실행 자체는 이번 메시지의 계획 요청으로 별도 명시 승인된 것이 아님.
- main/P0/Phase1–5, PR#5 원본 baseline, 기존 DGX 운영 Docker/서비스/포트/HF cache 불변; blazux 패치, 모델/GPU 벤치 실행, CI, PR, Merge 없음. 신규 문서/Source Manifest를 동일 Phase6 브랜치 단일 커밋으로 맞추고, 정확한 마지막 DGX-tested SHA와 후속 문서/소스 HEAD 구분.


## 2026-10-28 최신: 사용자 P6-A3b-1 격리 CPU-only 소스 조사 1회 명시 승인 (아직 DGX 실행 전)

- **사용자 승인 범위**: 기존 고정 이미지 ID로 일회용 `docker run --rm` **1회**, CPU-only 설치 vLLM 소스 SHA256/AST 확인만 승인. `scripts/phase6-a3b1-cpu-container-gate.sh --execute`가 유일한 승인된 진입점. GPU/모델·가중치/HF 캐시/운영 Docker stop/restart/exec/HTTP/벤치/CI/패치/PR/merge 및 실제 Scheduler/CacheConfig/MambaSpec 객체 생성은 승인하지 않음. 기존 preview 스크립트는 계속 비실행. [안전 실행 정본](BLAZUX-PHASE6-A3B1-CPU-ISOLATED-GATE.md).
- **직전 실제 DGX 테스트 코드 SHA** `7dc77164447bdd272b3ff791341d8ec5379a1edd`: Phase6 오프라인 테스트 **45/45 PASS**, Source Manifest **196/196 PASS**, P6-A3b-0 CPU 합성 그룹 LCM32/GCD16·가상 Mamba32/cache16, `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME` 및 `PHASE6_A3B0_DGX_PREPARATION_VERIFIED_NO_RUNTIME`. 32/16은 실제 운영값이 아니며 patch/bug 증거도 아님. 새 GitHub 커밋의 코드는 DGX NOT_RUN; 목표 **57 test·200 source 파일은 기대값**, 새 HEAD의 검증 결과를 만들지 말 것.
- **새 A3b-1 fail-closed 경계**: clean Phase6 전용 checkout/전체 Manifest, `MemAvailable>=4GiB` 현재값, 운영 컨테이너 running 및 pinned digest 실행 전후 검증, 로컬 이미지 고정, `runc`, CPU 1/메모리 512MiB/total memory+swap 512MiB(별도 swap 불가), 네트워크·GPU·파일쓰기 제한, nonroot UID65534, drop ALL caps, no-new-privileges, HF offline. vLLM import/실제 config constructor 금지. 표준출력은 Python 독립 오라클로 8개 AST anchor+**7개 historical SHA 일치**만 allowlist 판정. KV resolver의 소스 SHA는 이번 검사에서 **미고정**(AST anchor만), 과대 표기 금지. 부적합 시 BLOCKED, 보안 완화·root fallback·자동 재시도 금지.
- **Gate 상태**: A3b-1 최종 PASS가 나와도 `PASS_PINNED_SOURCE_AST_ONLY` 한정. 실제 운영 중인 Scheduler 선택 클래스/CacheConfig·Mamba 그룹별 block_size/물리 block-table 및 CUDA 상태 주소 `NOT_OBSERVED`; **P6-A 실제 런타임 BLOCKED**, P6-B/C/D NOT_RUN/BLOCKED. 이전 A3a 호스트 MemAvailable 14085MiB, NVML GPU 메모리 N/A는 새로운 GPU 안전성 증거 아님. Pre-blazux 12×3 baseline/원본 보존, 역사적 corpus SHA/sampler/KV 비교 미확정, P6-D 여전히 BLOCKED. main/P0/Phase1~5 불변.


## 2026-10-28 Phase6 P6-A3b-0 CPU-only 실행 전 준비 — 최신

- **실제 마지막 DGX 검증 소스**: `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`, Phase6 28/28 unittest PASS, Source Manifest 190/190 PASS, A3a passive resource `OBSERVED_METADATA_ONLY`. 이후 `a9e628b39fb97fe4ba57bd2b9fbc04a937c056c9`는 문서·Manifest 전용 기록 커밋(미재시험). Host MemAvailable 14085 MiB, SwapFree 8735 MiB, GPU NVML 메모리 total/free/used `N/A`, GPU 순간 util 0%, 35°C. 추가 GPU/모델 동시 실행 안전성 증명 안 됨.
- **이 새 커밋 준비 작업**: `src/phase6_a3b_cpu_config.py` strict-schema stdlib synthetic block group LCM/GCD *diagnostic* (실 resolver Early return/DCP/hash/prefix 분기는 재현하지 않음), `tests/fixtures/phase6_a3b_synthetic.json`, `tests/test_blazux_phase6_a3b_cpu.py` (17개 신규 합성 단위시험), `scripts/phase6-a3b-cpu-prepare.sh` (브랜치·clean·Source Manifest→synthetic CPU→미리보기), `scripts/phase6-a3b-container-preview.sh --preview` (문자열 미리보기만 출력, 모든 실행 옵션 차단), [A3b CPU 실행 전 계획](BLAZUX-PHASE6-A3B-CPU-CONFIG-PREP.md). Phase6 합계 **45개 테스트 예상**, 전체 Source Manifest **196개 예상**이지만 **새 HEAD DGX NOT_RUN**; 실행 로그 받기 전 PASS로 승격 금지.
- **별도 승인 경계**: 실제 `docker run`/`docker exec`는 사용자가 이번에 승인하지 않았으며 GitHub 추가된 실행 경로에서도 수행하지 않음. 향후 CPU-only 임시 컨테이너 승인 시 제안 격리: pinned image digest, `runc`, `--network=none`, read-only, `--cpus=1`, `--memory=512m`, `--memory-swap=512m`, `--pids-limit=64`, GPU/모델/HF cache/port 미마운트 및 CUDA 비활성. 허용되는 초기가능 검사는 pinned vLLM **소스 SHA/AST 읽기 전용뿐**으로, 실제 CacheConfig/Scheduler 생성/운영 프로세스 구성 재현은 아님. Source hash drift, missing effective config inputs, unsafe dependencies -> BLOCKED.
- **P6-A 실제 런타임** Scheduler 선택 클래스/CacheConfig/MambaSpec/group/물리 block-table/state 텐서 주소는 여전히 `NOT_OBSERVED/BLOCKED`, P6-B/C/D `NOT_RUN/BLOCKED`. Pre-blazux Baseline 12×3 원본 유지, 역사적 corpus SHA/sampling/KV 여전히 미확정. GPU 모델 시작, 운영 컨테이너 변경, HTTP/벤치, CI, blazux patch, PR/Merge 금지. `main`/P0/Phase1–5 불변. 후속 정본/Manifest 기록 커밋은 DGX-tested SHA가 아님.


## 2026-10-28 Phase6 P6-A3a DGX 실측 및 다음 진입 경계 — 최신

- **DGX 사용자가 실제 실행한 SHA**: `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`; 전용 `~/Workspace/llm/blazux-phase6-gates` checkout fast-forward 후 Phase6 unittest **28/28 PASS**, Source Manifest **190/190 PASS**, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`. 읽기 전용 자원 관찰 결과 `PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED`, 최종 `PHASE6_A3A_DGX_OBSERVATION_COMPLETED`.
- **A3a 관측값 (snapshot)**: 운영 컨테이너 running=true, pinned image digest match=true, Docker 명시적 memory limit 없음(`null`); 호스트 `MemTotal=124543 MiB`, `MemAvailable=14085 MiB`, `SwapTotal=16383 MiB`, `SwapFree=8735 MiB`. GPU NVML은 단일 device에서 `utilization=0.0%`, `temperature=35°C`, `memory.total/free/used=N/A`여서 GPU telemetry `PARTIAL`. 순간적으로 관측한 숫자이며 별도 GPU/모델을 띄울 수 있는 용량·운영 간섭 부재를 증명하지 않음. `explicit_container_memory_limit_mib=null`은 무제한 물리 GPU 메모리 증거가 아님.
- **정확한 상태 구분**: P6-A3a `OBSERVED_METADATA_ONLY`, P6-A 활성 Scheduler/CacheConfig/MambaSpec/physical block-table/state pointers **NOT_OBSERVED/BLOCKED**; P6-B/C/D `NOT_RUN/BLOCKED`; 기존 운영 서비스 변경, GPU 계산, 신규 모델 load, HTTP, CI, benchmark, blazux patch/PR/merge **실행하지 않음**. 이전 A2 baseline raw result/runner SHA PASS, 기존 Gutenberg cache SHA `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; baseline 당시 corpus SHA·sampling/KV 동일성 여전히 미확정 → P6-D 차단.
- **다음은 P6-A3b 관찰 방법 승인 설계**: 기존 비침습 인터페이스로 활성 객체를 노출하는지 먼저 확인(관측 가능한 부분만); 불가능하면 PIN된 이미지를 사용한 격리 CPU-only 구성 재현은 별도 `docker run` 승인과 자원 제한 필요(재현된 구성은 운영 프로세스 실측이 아님). 실제 block-table/tensor ptr·stride는 별도 GPU/model 실행 또는 지원되는 관측기 없이는 검증 불가. 이번 메모리 snapshot만으로 단일 DGX에서 GPU 모델 동시 실행 승인 금지; 기존 서비스에 attach/ptrace/debug/exec 금지. [A3 관찰 및 승인 결정](BLAZUX-PHASE6-A3-RESOURCE-OBSERVATION.md).
- 이번 후속 정본/Manifest 커밋은 **문서 전용, DGX 신규 시험 NOT_RUN**. **28/28·190/190은 오직 위 정확한 소스 SHA에 귀속**. `main`/P0/Phase1–5 및 PR#5 벤치 원본 불변; 신규 PR/Merge/CI 없음.


## 2026-10-28 이전 P6-A3a 준비 계획 (역사적 기록; 실측 완료)

- **가장 최근 실제 DGX 테스트 SHA**: `0513b118260047b9965e16b20bdadf690c112c5d` — Phase6 offline **15/15 PASS**, full Source **186/186 PASS**; A2 preflight pinned running Docker image PASS, baseline original SHA256 및 llama-benchy runner SHA PASS. Current Gutenberg cache SHA `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; historical corpus SHA unavailable and sampling/KV unknown, strict A/B BLOCKED. Subsequent `be7a463274765627d0fd0da3a9d70907c5f0cf83` is **docs/Manifest-only** and NOT separately DGX tested.
- **이 커밋의 신규 P6-A3a**: `scripts/phase6-a3-readonly-resources.sh` + `src/phase6_a3_readonly_resources.py` + 13개 stdlib regression + [A3 read-only Gate/decision](BLAZUX-PHASE6-A3-RESOURCE-OBSERVATION.md). Old 15 + new 13 = **28 expected** Phase6 tests, full **190 expected tracked source files**; both counts NOT_RUN on new commit until operator DGX log. Existing operational container identity via `docker inspect`, host `/proc/meminfo`, optional `nvidia-smi` passive NVML metrics only. `nvidia-smi` N/A on unified-memory DGX is PARTIAL/UNAVAILABLE, **not** zero or sufficient GPU headroom.
- **Gate boundary**: A3a completed metadata never equals P6-A runtime PASS. Actual selected Scheduler object, effective CacheConfig/MambaSpec block sizes, Mamba group table and physical GPU tensor allocations/pointers are still `NOT_OBSERVED`; P6-A/B/C/D runtime BLOCKED. CPU-only configured reproduction or isolated GPU/model inspection requires separate scoped approval, startup memory budget and zero legacy interference proof. No `docker exec/run`, live process attach/ptrace, model start, GPU computation, HTTP, benchmark, CI, blazux patch, PR or merge under this approval.
- Only Phase6 GitHub branch may change; `main`, P0, Phase1–5 and original benchmark baseline remain immutable. Same commit updates handoff + adoption + exit boundary + Phase6 results/plan + all-tree Source Manifest. Latest GitHub commit SHA of this documentation update is not a new DGX-tested commit.


## 2026-10-28 Phase6 A2 DGX verified — earlier checkpoint

- **Exact DGX operator-tested SHA** `0513b118260047b9965e16b20bdadf690c112c5d`, dedicated `~/Workspace/llm/blazux-phase6-gates` checkout, ff-only fast-forward from `c7f4ca7`. Bash syntax passed; Phase6 unittest **15/15 PASS**; `PASS_SOURCE_ONLY: 186 tracked file(s)` at exact SHA, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`. Read-only preflight ended `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED` and user shell `PHASE6_A2_PREFLIGHT_DGX_COMPLETED`.
- **Observed deployment-only evidence**: pinned image digest match=true, running=true; allowlisted launch flags `--gpu-memory-utilization=0.8`, `--max-model-len=262144`, `--max-num-batched-tokens=8192`, `--max-num-seqs=8`. `deployment.status=PASS` applies solely to Docker metadata; it does **not** verify process-selected Scheduler class/CacheConfig, MambaSpec blocks/groups or physical GPU state.
- **Benchmark evidence**: baseline raw result SHA256 match=true; pinned llama-benchy runner Git SHA match=true; cached Gutenberg corpus SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`, but **historical corpus SHA not available** and `historical_corpus_matches_current=null`; sampling/KV equivalence `UNVERIFIED`. The cached bytes' current hash does not prove what was used during the historical 2026-10-26/27 baseline. No P6-D comparison, benchmark execution, regression thresholds, or throughput claim authorized. [Benchmark rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md).
- **Gate classification**: `P6-A2 passive preflight=COMPLETED` with deployment PASS and benchmark PARTIAL, but `P6-A REAL ACTIVE RUNTIME=BLOCKED`; `P6-B/C/D=NOT_RUN/BLOCKED`. Next decision: distinguish (A3a) non-intrusive source/launch metadata, which cannot certify active Python objects, from (A3b) active Scheduler/Mamba/group/pointer observation that requires a separately authorized, safe and feasible observer/isolated GPU plan. Do not attach/deploy/instrument the running service or invoke Docker exec/run, live model, GPU, HTTP, CI or benchmark under existing approval.
- Historical Phase5 DGX-tested code SHA remains `780b780fc7572226a6a9ff2e52cd8e1921c8738b`; previous Phase6 offline exact SHA `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`. This follow-up **documentation/manifest commit is not DGX-tested**; a new HEAD does not inherit the 15/15 run. main/P0/Phase1–5 protected; no patch/PR/merge.


## 2026-10-28 Phase6 A1/A2 previous checkpoint

- **DGX measured exact Phase6 code SHA** `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`: dedicated `~/Workspace/llm/blazux-phase6-gates` clean checkout, 7/7 Phase6 unittest PASS, 182/182 Source Manifest PASS, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, final `PHASE6_DGX_OFFLINE_GATE_COMPLETED`. The same SHA operator's **A1 source-only** log ended `PHASE6_A1_READONLY_SOURCE_INVENTORY_COMPLETED`; image tag `yslab-qwen38-bf16ple:9492b78c`, image ID short `b0984c4b724b`; `P6_A_RUNTIME_STATUS=BLOCKED`. Do not attribute these DGX results to the newer GitHub commit.
- **Next bundled step** on dedicated DGX checkout after `git pull --ff-only`: `bash scripts/phase6-gate.sh` (new offline unit suite+manifest) followed by `bash scripts/phase6-readonly-preflight.sh` (Docker `inspect` metadata ONLY + fixed pre-blazux result SHA, bench runner SHA, cached current Gutenberg corpus hash and optional historical private corpus SHA, no private raw data output). The latter prints `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED`. Its deployment `PASS` is solely pin/running metadata, not active Scheduler, MambaSpec/group, tensor pointer/stride, actual GPU address, or active config correctness. P6-A overall stays **BLOCKED**.
- [Frozen Phase6 benchmark comparison rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md) require original 12×3 immutable raw Baseline, runner and tokenizer/seed, corpus and sampler parity, equivalent cache/KV/environment, correctness P6-A/B/C, and preapproved regression thresholds. Legacy `scripts/benchmark/run-llama-benchy.sh` targets production port 8000 and has NOT_RUN wrapper status: **do not execute** for Phase6 without separate benchmark/isolation approval.
- User has not authorized DGX GPU, real model loading, HTTP/benchmark, CI, operational change, any blazux runtime patch, PR, or merge. A2 is explicit user-operated read-only observation, NOT permission to launch new compute; all new Phase6 code on the fresh commit is NOT_RUN until operator log. Main/P0/Phase1–5 remain untouched. Update these canonical docs and entire Source Manifest together.


## 2026-10-28 Phase6 implementation-preparation approval (current)
- User approved **new Phase6 branch + offline Gate scripts/tests/docs + GitHub commit only**. DGX/GPU/CI/operational service/model/patch/PR/merge are NOT approved.
- Phase6 branch `feature/blazux-phase6-runtime-gates` starts from Phase5 docs-only `11fd777e2c49c030eee671133ab0af3a3ca9c26d`. Phase5 tested SHA remains `780b780fc7572226a6a9ff2e52cd8e1921c8738b` (G1–G8 source/CPU PASS). No Phase5 repeat.
- [Phase6 gate plan](BLAZUX-PHASE6-GATE-PLAN.md) and [Phase6 result ledger](BLAZUX-PHASE6-RESULTS.md) are canonical. `scripts/phase6-gate.sh` is offline-only; supplied JSON fixture PASS is **not** active DGX P6-A PASS. Runtime P6-A/B/C/D remain BLOCKED. Separate explicit approvals required for every runtime scope.
- Phase6 implementation and documentation plus full Source Manifest are one commit on Phase6 only. Preserve main/P0/Phase1–5 heads, no PR/merge. No DGX test claim on documentation/implementation SHA.


## 2026-10-28 현재 세션 인수인계 진입점 — Phase6 범위 확정만 진행 (실행 미승인)

> **최신 활성 과제**: Phase5 소스·CPU 오프라인 Gate는 **종료 완료**. 현재 새 대화에 인계할 것은 **Phase6 승인 범위·검증 우선순위·통합 Gate 설계**뿐이다. Phase6 실행 또는 새 브랜치 생성/PR/머지는 아직 승인되지 않았다. 역사적 완료사항과 공통 운영 규칙은 이 문서 아래 및 관련 정본에서 읽고, 새 대화용 프롬프트에 중복 복제하지 말 것.

- **확정 종료 증거**: 전용 DGX checkout에서 실행한 코드 SHA `780b780fc7572226a6a9ff2e52cd8e1921c8738b`, Wizard Mock 38/38, unit 310/310 XFAIL0, Source177/177, G1–G8 PASS 및 G8 13,824 합성 조합. [실측 정본](BLAZUX-PHASE5-DGX-GROUPED-GATE-RESULTS-20261028.md), [Phase5 종료/Phase6 경계](BLAZUX-PHASE5-MAMBA-GROUPED-EXIT-GATE-20261028.md). `a205a3f958c250e2e30cb20fc99424666b2e0ff5`은 Phase5 결과를 보존한 **문서 전용** 선행 HEAD로 그 SHA에서 DGX 재시험은 없음; 이 진입점이 포함되는 후속 문서 커밋 역시 재시험 증거가 아니다.
- **2026-10-28 GitHub 확인 시점**: Phase5 실험 브랜치 `feature/blazux-phase5-correctness-mtp-offline` (선행 HEAD `a205a3f958c250e2e30cb20fc99424666b2e0ff5`), `main=2847e39b4131eb8aff78bf86ffce98892401722a`. 현재 open PR **0**, Actions 전체 workflow run **0**, 해당 선행 HEAD commit status **0** / PR-triggered workflow run **0**. `.github/workflows/test.yml` 파일 존재 ≠ CI PASS. 다른 Phase0–4 protected heads는 과거와 동일. 최신 ref/PR/CI는 새 대화에서 **다시 조회**.
- **Phase6 아직 NOT_RUN/BLOCKED**: 실행 중인 실모델 `CacheConfig.block_size` 대 `MambaSpec.block_size` 숫자 관계, 활성 scheduler/backend/group/slot/tensor 물리 경계, GPU Mamba 복사·rollback·prefix cache hit, speculative MTP acceptance, Parser/Tool/Responses HTTP 계약, PP/TG/TPS·메모리/안정성 및 실제 CI. Source-only와 synthetic PASS를 GPU/ABI 검증이나 수정 승인으로 확대하지 않는다.
- **다음 대화 우선순위**: (1) 최신 GitHub 상태 재확인 + 이 문서 상단·[적용 계획](BLAZUX-VLLM032-ADOPTION-PLAN.md)·종료 정본 읽기; (2) P6-A 읽기 전용 활성 구성/ABI 관찰, P6-B 격리 GPU state correctness, P6-C MTP/Tool/Responses, P6-D 정확성 충족 후 성능·안정성의 **각 Gate 전제·정확성 oracle·성공/실패/차단·rollback 및 증거 경계**를 구체화; (3) 사용자가 Phase6 브랜치/실환경 테스트/모델 접근/CI/patch/PR/merge에 대해 **각각 명시적으로 승인한 범위**만 수행; (4) 승인된 소스·CPU 자료 수집은 GitHub 연결 도구로 정본 스크립트/테스트/문서·Manifest를 **같은 커밋**에서 업데이트, DGX 전용 checkout의 `pull --ff-only`와 **묶음 명령 하나**로 증거 수집. 임의의 GPU/model/weights/HF cache/운영 Docker/serving/ports/CI 작업 금지.
- **인수인계 원칙**: 새 대화용 프롬프트에는 이 현재 과제·미완료·최신 HEAD/PR/CI·DGX PASS 출처·다음 우선순위·금지동작만 포함하고, 완료된 과거 phases 및 세부 정책은 [영구 정본](SESSION-HANDOFF-PROMPT.md), [적용 계획](BLAZUX-VLLM032-ADOPTION-PLAN.md), [검증 보고서](BLAZUX-PHASE5-DGX-GROUPED-GATE-RESULTS-20261028.md) 링크 참조로 처리. GitHub 커넥터의 commit/PR/review/merge는 **필요하고 현 승인 범위에 있을 때 직접 수행**하되 인수인계 작성 자체를 이유로 PR/merge를 만들지 않는다.


## 2026-10-28 DGX Phase5 G1–G8 오프라인 종료 PASS — 현재 정본 (Phase6 준비)

- **최신 전체 DGX PASS의 정확한 실행 소스 SHA: `780b780fc7572226a6a9ff2e52cd8e1921c8738b`** (별도 Phase5 checkout, user-provided `붙여넣은 텍스트(1)(20261027-171555).txt`): Wizard Mock **38/38**, Python **310/310 XFAIL=0**, Source Manifest **177/177**, AST/오프라인 전체 wrapper PASS, 설치 이미지 고정 소스 검사 **G1–G8 모두 PASS**, **G8 13,824 synthetic alignment/tiling cases / 23,552 spans**, `BATCH_SOURCE_CPU_CHECKS_PASS=25528` (독립 unittest 수 아님), `PHASE5_MAMBA_BATCH_SOURCE_CPU_DONE_NOT_CERTIFIED`, `PASS: PHASE5_BATCH_OFFLINE_AND_PINNED_SOURCE_EXECUTED_NOT_CERTIFIED`, 사용자 쉘 `PHASE5_FINAL_OFFLINE_GATE_COMPLETED`. **Log final status 0; error/traceback 없음.**
- [DGX 통합 결과 정본](BLAZUX-PHASE5-DGX-GROUPED-GATE-RESULTS-20261028.md), [Phase5 종료 기준과 Phase6 인계](BLAZUX-PHASE5-MAMBA-GROUPED-EXIT-GATE-20261028.md). 첫 G8 실패 SHA `ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5`의 `310 unittest FAILED(errors=15)`는 Python `staticmethod` binding 오류였으며 **고친 후 `780b780fc7572226a6a9ff2e52cd8e1921c8738b`에서 재시험 PASS로 해결**. 역사적 FAIL 기록을 삭제하지 않는다.
- **현재 결론: Phase5 scope=소스·CPU 오프라인 Gate PASS 및 마감 가능**. CUDA/Triton 실 GPU 복사, 활성 `CacheConfig.block_size` vs `MambaSpec.block_size` 값, 실제 Mamba 그룹/텐서·물리 블록 범위, prefix-hit/rollback, MTP acceptance, Parser/Tool/Responses HTTP, TPS 및 CI는 **Phase5 PASS에 포함되지 않은 Phase6 후보**, 현재 `NOT_RUN/BLOCKED`. **이것을 검증 없이 패치 승인이나 Phase6 실환경 완료로 주장 금지.**
- **다음 묶음 Phase6 승인 제안**: (P6-A) 읽기 전용 actual config/group/block table과 Scheduler/Mamba division provenance/ABI evidence, (P6-B) 최소 재현 GPU Mamba pre/postprocess/prefix-hit 및 state integrity, (P6-C) MTP speculative acceptance·Tool/Responses 및 오류 계약, (P6-D) 정확성 전제 충족 뒤 baseline 대비 PP/TG/TPS/메모리/안정성. 운영 컨테이너/모델/weights/HF cache/포트/환경/CI/패치 변경 및 Phase6 브랜치·PR/머지는 **개별 범위 명시 승인 전 금지**. 우선 순서와 각 P6 Gate의 오라클/전제조건을 확정하고 한 번씩 묶어 실행할 것.
- **문서 동기화 영구 규칙 유지**: 사용자 새 지시, DGX 실측, FAIL/fix, 미해결·연기·다음 Gate마다 동일 브랜치/커밋에서 `SESSION-HANDOFF-PROMPT.md` + `BLAZUX-VLLM032-ADOPTION-PLAN.md` + 정본 결과/종료 기준 + 전체 `source-state-manifest.json` 동기화. GitHub 직접 CAS/FF-only 커밋 → DGX 전용 checkout에서 `pull --ff-only` → 저장소 tracked 통합 스크립트 실행; 파일 다운로드/붙여넣기 배포 금지. **DGX 실측 SHA와 이후 docs-only 기록 커밋 SHA 분리**; docs-only 커밋에서 신규 DGX unit PASS 주장 금지. main/P0/Phase1–4 HEAD 불변, PR/CI 상태 확인.


## 2026-10-28 필수 영구 규칙: 코드·테스트·문서·핸드오프를 항상 한 커밋에서 동기화

1. 신규 요청 규칙, 사용자 DGX 실측, 오류 원인, 수정·예외·보류, 누락된 계약, 다음 단계 Gate 및 실행 명령을 발견하면 **즉시 같은 Phase 브랜치의 `docs/SESSION-HANDOFF-PROMPT.md`, 관련 `docs/BLAZUX-VLLM032-ADOPTION-PLAN.md`, 해당 검증 정본/종료 기준 문서와 `scripts/source-state-manifest.json`을 함께 갱신**한다. 단순 대화상의 약속은 영구 인수인계가 아니다. 별도 언급이 없어도 작업 완료 전 항상 이 네 범주를 대조한다. 기록 중복 없이 서로 다른 문서에는 정본 링크와 최신 상태만 요약한다.
2. **실제 테스트 PASS·FAIL의 출처를 실행한 정확한 SHA에 귀속**한다. 후속 문서/테스트 수정 SHA에 이전 PASS를 옮겨 쓰지 않는다. 최신 실행의 실패가 있으면 이전 성공 기록을 삭제하거나 덮어씌우지 않고 `PASS / FAIL / BLOCKED / NOT_RUN` 및 원인·수정·재시험 필요 여부를 함께 남긴다. 그룹 A가 실패한 경우 그 뒤 그룹 B/G1–G8는 **NOT_RUN**이다. 예상 시험 수와 실측 시험 수를 구별한다.
3. **1개씩 질문·검사 지시 금지:** 근거 수집은 하나의 묶음 Gate로 구성하되 각 필수 검사, source SHA, bounds, source/CPU vs GPU-runtime 한계, 최종 마커를 누락 없이 기록한다. Github 커넥터로 직접 코드·스크립트·문서·Manifest를 동일 브랜치에 CAS/fast-forward 커밋한 다음, 사용자가 별도 Phase 전용 DGX checkout에서 `git pull --ff-only` 및 커밋된 단일 Gate를 실행한다. 채팅 파일 다운로드/복사로 배포하지 않는다.
4. 이전·현재·다음 단계 변경 범위, 보호 브랜치 HEAD, PR/CI 실제 상태, 최신 DGX의 전체 로그/출처, 잔여 위험·미완료/보류, 다음 명령까지 `SESSION-HANDOFF-PROMPT.md`에서 재현 가능해야 한다. 운영 Docker/모델/GPU/weights/HF cache/포트, blazux 실제 patch, Phase6 생성/PR/Merge는 별도 승인 전 금지.
5. **해결된 과거 실패의 이력 보존 (현재 FAIL 아님):** DGX `ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5`에서 Source177/177, Wizard38/38을 통과했지만 unit **310 실행, FAILED(errors=15)**. 원인은 `Phase5MemcopyTiledPartitionTests.setUpClass: cls.f = pure_oracles()["tiled_spans"]`에서 Python 함수가 인스턴스의 bound method로 변환돼 예상 6인자 대신 7인자가 된 것. G8 알고리즘의 실제 GPU 결함 증거가 아님. **Group B/G1–G8 NOT_RUN**. 현재 테스트 소스에서 `cls.f = staticmethod(...)`로 바인딩 수정하고 같은 이름의 기존 10개 G8 회귀시험에 staticmethod descriptor 확인을 추가; 후속 수정 코드 `780b780fc7572226a6a9ff2e52cd8e1921c8738b`에서 DGX 전체 Gate **310/310 XFAIL0, Source177/177, G1–G8 PASS**로 해결됐다. 이전 `3c364209`의 300/300/Source176/G1–G7 PASS도 별도 역사적 증거로 보존한다.


## 2026-10-28 DGX Phase5 grouped G1–G7 전체 PASS 및 마지막 G8 alignment/tile CPU 보강 — 최신

- [새 DGX 실측 정본](BLAZUX-PHASE5-DGX-GROUPED-GATE-RESULTS-20261028.md): **실제 DGX 검증 코드 SHA `3c36420998061f7a3e656eb77390c04b7d2ef935`**, Source Manifest **176/176**, Wizard Mock **38/38**, 전체 Python unit **300/300 XFAIL0**, Source AST/Bash/audit wrapper PASS, G1–G7 PASS, CPU source internal 343개 check PASS. 설치 vLLM `_memcpy_u64_tiled:40–119` 전체 본문 확인, 최종 `PHASE5_GROUPED_GATE_EXECUTION_COMPLETED`. 이는 CUDA GPU correctness/활성 블록 설정값/Tool·Responses·MTP 실동작 증명이 아님.
- 같은 Phase5 후속 **G8**: `_memcpy_u64_tiled` 소스의 aligned uint64 head/body/tail, misaligned uint8 fallback, tile rounding/mask에서 누락·중복 byte coverage 여부를 **8×8 정렬×4 tiles×3 copy chunks×18 length = 13,824개 합성 조합**으로 검증. 기존 `scripts/phase5-mamba-batch-check.sh`에 G8 연결, `tests/test_blazux_phase5_mamba_batch_gate.py`에 표준 라이브러리 시험 10개 보강. standalone local CPU oracle 13,824 조합 PASS이나 **새 GitHub HEAD에서의 DGX 전체 Gate는 NOT_RUN**. 다음 DGX에서 한번의 `scripts/phase5-mamba-batch-check.sh`로 그룹 A + G1–G8 전체 실행할 것.
- Phase5 source/CPU exit PASS ≠ **Phase6/runtime/patch 승인**. 운영 CacheConfig와 MambaSpec numeric block equality, active Mamba group topology, state tensor actual bounds, GPU state rollback/prefix hit, Parser/Responses/MTP runtime, inference/TPS 및 CI는 Phase6 승인 이후 각각 명시적으로 검증해야 할 사항. main/P0/Phase1–4 보호, Phase5 PR/Merge 없음, 외부 patch 0.


## 2026-10-28 Phase5 grouped Mamba G1–G7 exit Gate — DGX NOT_RUN

- [단일 검증/Phase6 readiness runbook](BLAZUX-PHASE5-MAMBA-GROUPED-EXIT-GATE-20261028.md): `scripts/phase5-mamba-batch-check.sh`를 **동일 Phase5 브랜치에 커밋**, 사용자는 전용 clean Phase5 checkout에서 fast-forward pull 후 **스크립트 한 번만** 실행. 스크립트는 전체 `scripts/phase5-check-offline.sh`(Source Manifest/mock/unit/AST/audit)와 설치 vLLM pinned SHA4파일/물리 주소/metadata/helper + V1/V2 mapping/multi-group/SD·DS conv/temporal/token bias/zero-boundary/negative-sentinel의 **G1–G7 CPU-only 합성 Gate**를 묶는다. `_memcpy_u64_tiled` 본체도 bound 내 출력해 누락 여부를 확인한다.
- 신규 `tests/test_blazux_phase5_mamba_batch_gate.py`의 **24개 stdlib 테스트는 이 세션의 격리된 로컬 staging에서만 PASS**, **새 Github HEAD의 DGX 전체 suite/Manifest Gate는 NOT_RUN**. 마지막 실제 DGX 전체 Gate PASS=코드 `a5376cc06536ce786cdb6db8425e26e21b608910`의 276/276 XFAIL0, Source169/169; 새 예상 300건을 DGX 실측으로 표현 금지.
- Phase6 진입을 빠르게 준비하되 **source/CPU Gate 완료 ≠ GPU runtime correctness/실 모델의 CacheConfig=MambaSpec 값/실 block-table 메모리 안전/CI/patch 승인**. Phase6 브랜치/실 GPU 실험/서빙·Docker·weights·모델·HF cache·HTTP/TPS/CI 및 모든 blazux patch는 **별도 명시적 승인 전 금지**. 현재 Phase5에서 기록·검증만 하고 main/P0/Phase1–4 불변, PR/Merge 없음.


## 2026-10-28 Phase5 Mamba P1/P2 실물리 State address + Metadata source inspection — 최신

- [정본 P1/P2 전체 본문 실측 보고서](BLAZUX-PHASE5-DGX-PHYSICAL-STATE-METADATA-RESULTS-20261028.md): 사용자 DGX 로그 `붙여넣은 텍스트(1)(20261027-161759).txt`에서 설치 `mamba_utils.py` SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3` 고정, `_copy_mamba_state_block:122–252` 및 `_populate_metadata:843–957` **전체 본문**, `OUTPUT_PARTIAL=False`, physical pointer/index/stride, DS/SD conv vs temporal bias 및 group-local metadata/table ptr 공급 확인.
- Group table `int32*` + `bt_row_idx*block_table_stride_req`(elements) + logical column → physical block ID(`int64`) → `state_base_addr + physical_id*state_block_stride_bytes`. DS conv는 row-stride와 element bias, SD conv는 `inner_size*elem_size` bias, temporal은 `src_col+token_bias` 물리 블록 ID와 natural copy size 사용. Metadata는 group→layer→state 순서로 수집하며 group-local index, tensor data_ptr/stride/element_size, 동일한 group table `stride(0)` 요구.
- **여전히 미확정:** helper 내부의 포괄적인 bounds guard 부재는 OOB 증거가 아님; active `B_cache==B_mamba`, `_memcpy_u64_tiled` 본체, 실제 tensor physical ranges, GPU/serving correctness, CI, patch 승인 전부 미검증. 다음은 여러 정적+합성 CPU 경계검사를 **한 번의 batch Gate**로 수행. 마지막 전체 DGX PASS `a5376cc`: unit 276/XFAIL0 Source169; 이번 소스 검사와 docs-only HEAD는 전체 unit 재시험 아님. main/P0/Phase1–4 불변, PR/Merge/patch/GPU/운영 금지.


> 기준: **2026-10-27 (Asia/Seoul)**. 이 파일은 다른 ChatGPT/개발 세션에서 현재 프로젝트를 그대로 이어받기 위한 **상시 인수인계 프롬프트**다. 2026-10-26 Wizard 시험은 역사적 운영 증거이며, **blazux Track A Phase 1 Gate 1 / DGX 오프라인 테스트는 완료**했다. 아래 Phase5 DGX Mamba 두 Triton 커널 및 Context block-size 설정 읽기 전용 검사 결과가 최신이다. 마지막 전체 276/276 Gate PASS는 소스 a5376cc...에 귀속하고, 신규 docs-only HEAD에서 재실행된 것이 아니다. 실제 active block equality/slot correctness 및 패치 승인은 여전히 없다.  
> 개인 저장소: [kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark).  
> **중요:** 이 문서의 commit/시험 결과는 기록 당시의 스냅샷이다. 새 세션에서는 GitHub의 실제 최신 `main`, PR, CI와 사용자 DGX의 새로운 로그를 확인해야 한다.

---

## 2026-10-27 Phase5 DGX Mamba pre-copy/postprocess Triton 본체 및 Context block-size 확인 — 최신

- 사용자 제공 `붙여넣은 텍스트(1)(20261027-152442).txt` (649줄): 운영 이미지 ID `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`를 참조한 **별도 CPU-only/read-only/no-network runc**의 `v1/worker/mamba_utils.py` AST/소스 검사 완료. Source SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3`, 전체 소스1521 lines. `FOUND_KERNELS=[precopy_mamba_align_fused_kernel,postprocess_mamba_fused_kernel]`, `CONTEXT_CLASS_FOUND=True`, `OUTPUT_PARTIAL=False`, `PHASE5_MAMBA_KERNEL_SOURCE_INSPECTION_DONE`, `PATCH_APPROVED=False` 및 `RUNTIME_CORRECTNESS_VERIFIED=False`. 이번 명령은 **전체 단위시험/Manifest Gate를 재실행하지 않음**. 마지막 실제 전체 DGX PASS는 코드 `a5376cc06536ce786cdb6db8425e26e21b608910` 276/276 XFAIL0/Manifest169. 이전 docs-only SHA `2def41755c2b55e95a094acabcaf1bd90d5e3259`는 Manifest171; 새로운 보고서/Manifest docs-only SHA도 DGX 검증 SHA가 아님.
- **핵심 해결:** `MambaSpecDecodeGPUContext.create:720–728`는 Mamba group에서 동일 block_size/speculative blocks/mode를 assert, **:772 `block_size=mamba_spec.block_size`**를 context `cls(...)`에 공급. context field `block_size: int` (:682), fused postprocess V1 :1012/V2 :1110 모두 `block_size=self.block_size`. **preprocess 및 postprocess 공급값이 MambaSpec 기반**이라는 source contract 확인. 명시적 `__init__/__post_init__` absent는 방법 이름 부재만 의미.
- **Precopy kernel 437–519:** batch→req mapping(optional, 음수 sentinel skip), `src_col=old_state_idx`, `dst_col=postadvance_state_idx`, fresh src negative/same column이면 no-copy; 다를 때 `token_bias`와 state/layout/table metadata를 공통 `_copy_mamba_state_block` 호출로 전달. **postprocess kernel 255–388:** computed/token acceptance V1/V2 분기, `aligned_new_computed=(new_num_computed//B_mamba)*B_mamba`, `dest_idx=aligned_new_computed//B_mamba-1`, `needs_copy`, same column + zero bias skip; batch-vs-req indexing 구분, 역시 `_copy_mamba_state_block` 이용.
- **영구 근거:** [Mamba fused kernel 본체/context DGX 보고서](BLAZUX-PHASE5-DGX-MAMBA-FUSED-KERNEL-BODIES-RESULTS-20261027.md). `run_fused_precopy`와 `run_fused_postprocess_align` 본체와 memory metadata 전달/forward-context init 진입 확인. **아직 공통 `_copy_mamba_state_block` 본문과 `_populate_metadata`의 실제 pointer/stride/offset mapping을 분석하지 않음**, 활성 사용자 모델의 `cache_config.block_size` vs `mamba_spec.block_size` 값 동일성 미확정. Worker 초기 seed 분모는 여전히 CacheConfig; actual GPU state/slot correctness, ABI, prefix-hit/errors, patches 미검증.
- **다음 동일 Phase5:** 고정 경로의 `_copy_mamba_state_block`, `_populate_metadata` 함수 본체만 우선 조사하여 state index→logical column→physical block/conv offset mapping을 source/합성 CPU oracle로 검증. 운영 Docker/GPU/모델/weights/HF cache/ports/HTTP/CI/patch 변경 승인 0. main/P0/Phase1~4 불변, PR/Merge/cherry-pick/rebase/squash/sync 금지.

---

## 2026-10-27 Phase5 Scheduler 설정 분기 / CacheConfig min block / Mamba Align Kernel 소스 3회 확인 — 이전 실측

- **사용자 DGX 읽기 전용 출력** `붙여넣은 텍스트(1)(20261027-145706).txt`: `CHECK1_SCHEDULER_FACTORY_SOURCE_DONE`, `CHECK2_BLOCK_ORIGINS_SOURCE_DONE`, `CHECK3_MAMBA_SLOT_SOURCE_DONE`. 운영 Docker 이미지 ID 조회 후 별도의 network-none, read-only, GPU-none runc 임시 컨테이너에서 Python source만 조회. 이번 명령은 **전체 276 unit 또는 Source Manifest 170를 재실행하지 않음**. 마지막 전체 PASS는 소스 HEAD `a5376cc06536ce786cdb6db8425e26e21b608910`: unit276/276 XFAIL0, Source169/169, static checks10/10 true. 이전 docs-only HEAD `321d979eca30b20e5724afbddfe15fe6bf962fbe`, Manifest170. 새 이번 docs-only HEAD도 DGX 전체 재시험한 SHA가 아님.
- **CHECK1**: `SchedulerConfig.get_scheduler_cls:170–191`에서 scheduler_cls is None이면 async_scheduling true → `AsyncScheduler` :175, false → `Scheduler` :178 (양쪽 함수 내부 import). custom scheduler_cls가 non-string 객체면 cast 반환 :190, 문자열이면 `resolve_obj_by_qualname` :191. 선언 default `scheduler_cls=None`, `async_scheduling=None`; 활성 runtime 값·실 반환 class/ABI 미확인. `EngineCore.__init__:148`은 local Scheduler에 factory 결과 대입; 직전 direct-import AST false는 analyzer 한계.
- **CHECK2 (PARTIAL)**: `SCAN_OUTPUT_LIMIT_REACHED`, 162 files/3,571,805 bytes/103 matches. `v1/engine/core.py:321–324`에서 **`cache_config.block_size = min(g.kv_cache_spec.block_size for g in kv_cache_groups)`** 대입 후보 발견. MambaSpec block 크기는 개별 spec에서 공급되고 frozen spec/align mode position-indexed table 사용; 실제 활성 값이 다른지 모름. `CacheConfig.DEFAULT_BLOCK_SIZE=16`은 runtime 실측값이 아님. `mamba_get_block_table_tensor:1125` align index는 `(seq_lens-1)//kv_cache_spec.block_size`.
- **CHECK3**: `mamba_hybrid.add_request:116` 초기 seed 분모는 `cache_config.block_size`, `mamba_utils.preprocess_mamba_align_fused_kernel:431`는 `new_state_idx=(computed_after+MAMBA_BLOCK_SIZE-1)//MAMBA_BLOCK_SIZE-1` 및 `src_col=old_idx`, spec 크기는 `mamba_spec.block_size` 전달. `run_fused_precopy`가 이전 src/dst/bias를 kernel에 전달, `run_fused_postprocess_align`는 `postprocess_mamba_fused_kernel(block_size=self.block_size)` 호출. **실 kernel 함수 `precopy_mamba_align_fused_kernel`·`postprocess_mamba_fused_kernel`은 이전 검색 target에 포함되지 않아 본문 미검사**, ctx.block_size 생성/stride·block_table 실제 address/slot mapping도 미확인.
- **정본 보고서**: [Phase5 DGX 3-check kernel source](BLAZUX-PHASE5-DGX-THREE-CHECKS-KERNEL-RESULTS-20261027.md)와 소스 fingerprint·판정·한계 보존. 다음 **동일 Phase5**에서 고정 `mamba_utils.py` source의 두 kernel 본체/ctx block_size provenance, `EngineCore` min-group block assignment 도달, MambaSpec 설정값 공급 및 synthetic CPU 경계 fixture. 운영 Docker/config/GPU/weights/HF cache/ports/HTTP/CI 접근/patch 금지, blazux 전 계열 `patch_approved=false`. 새 phase/PR/merge 없음; main/P0/Phase1~4 HEAD immutable.

---

## 2026-10-27 Phase5 Scheduler/Mamba Source Contract DGX 276 PASS — 이전 전체 Gate

- **사용자 실제 DGX 소스 HEAD `a5376cc06536ce786cdb6db8425e26e21b608910`**: `Ran 276 tests`, `PHASE5_UNIT_PASS=276; XFAIL=0`, `PHASE5_SOURCE_AST_OK`, `PASS_SOURCE_ONLY: 169 tracked file(s)`, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS` PASS, isolated `PHASE5_SCHEDULER_MAMBA_CONTRACT_DONE_NOT_PATCH_APPROVED` 및 `EXECUTED_NOT_CERTIFIED`. 설치 6파일 `PARSEABLE_ONLY`, static `source_checks` **10/10 true**, `missing_source_checks=[]`. Wizard Mock 개별 **38/38 수치는 이번 사용자 발췌 로그에는 없으므로 해당 숫자를 새 SHA의 독립 실측으로 기록 금지**. 마지막 259/259은 이전 코드 `bc89de62...`의 역사적 Gate.
- **Factory의 source 반환 네 분기 위치**: `config/scheduler.py:175` `AsyncScheduler`, :178 `Scheduler`, :190 `cast(type[...],self.scheduler_cls)`, :191 `resolve_obj_by_qualname(self.scheduler_cls)`. `EngineCore.__init__:148`에서 local `Scheduler = vllm_config.scheduler_config.get_scheduler_cls()`, :161 ctor kw call. 그러나 branch predicates/actual config class/override·스케줄러 서빙 ABI는 여전히 미확인. `active_scheduler_class_verified=false`.
- **Mamba/Cache:** `MambaHybridModelState.add_request:116` seed = `(N-1)//self.cache_config.block_size`, group `_get_mamba_group_info`, align ctx helper `_ensure_align_ctx:135–175`, preprocess `MAMBA_BLOCK_SIZE=mamba_spec.block_size`, `ctx.run_fused_precopy:218`, `self._mamba_ctx.run_fused_postprocess_align:339`, scheduler aligned split `cache_config.block_size`, backend `kv_cache_spec.block_size`. 실제 **`actual_config_block_equality_verified=false`, `state_slot_correctness_verified=false`**. Synthetic 16/16과 16/32의 토큰17 index (1 vs 0)는 math sensitivity일 뿐 실 장애 증거 아님. `CacheConfig.__post_init__` `METHOD_ABSENT`는 그 메서드가 없다는 좁은 의미.
- **영구 보고서:** [Phase5 DGX Scheduler/Mamba Contract 결과](BLAZUX-PHASE5-DGX-SCHEDULER-MAMBA-CONTRACT-RESULTS-20261027.md) 및 [runbook](BLAZUX-PHASE5-SCHEDULER-MAMBA-SLOT-CONTRACT-20261027.md). 6개 installed preview source SHA256, ten source checks, 상세 AST 및 검사 경계 기록. 해당 보고서/Source Manifest의 **docs-only 후속 Git SHA는 DGX에서 276 테스트를 재실행한 SHA가 아니다.**
- **다음 같은 Phase5:** Scheduler factory default/override 분기 predicate·active class의 실 config (승인된 read-only 범위), CacheConfig vs MambaSpec block-size 공급자와 실제 값, `_ensure_align_ctx`/precopy/postprocess fused state slot 경계·복원 계약을 Source/합성 CPU로 좁혀 검증. **`patch_approved=false`**, blazux Mamba/Tool/Responses/MTP 5계열 모두 실제 패치 승인 0. 운영 Docker/model/weights/HF cache/ports/GPU/HTTP/CI 및 실 prefix hit/TPS 미검증/미변경.
- **보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` 불변; 현재 PR/Merge 불필요, `main` PR/Merge/Cherry-pick/Rebase/Squash/Sync 영구 금지. 계속 단일 Phase5만 사용.

---

## 2026-10-27 Phase5 Scheduler Dynamic Factory / Mamba Slot Unit Source Gate — 이전 구현 계획 (DGX 당시 미실행)

- **동일 Phase5 브랜치:** `feature/blazux-phase5-correctness-mtp-offline`. 직전 docs-only HEAD `3729277eba4d5c7f1e1d6a3603bbbd939ea8661a`를 부모로 신규 Source-only 검증 묶음 준비. 새 Phase/PR/Merge 생성 금지. 사용자 DGX에서 실제 **전체** 검증한 마지막 소스 SHA는 `bc89de6288889943b50090ac9638ee95c2434a79`, Source **164/164**, Wizard Mock **38/38**, unit **259/259 XFAIL0**; 이후 3개의 read-only inspection만 실시했으며 unit 재검증 기록은 없음. **이번 신규 분석 코드는 DGX NOT_RUN**.
- **확정된 3개 source 검사:** `EngineCore.__init__:148` `Scheduler=vllm_config.scheduler_config.get_scheduler_cls()`; 이전 `engine_static_imports_scheduler=false`는 직접 import를 가정한 analyzer의 범위 한계. 실제 Scheduler factory 반환 class/default/override는 아직 미검증. KV resolver은 group count 0/1 `cache_config.block_size*dcp` 두 번 반환; 2+ groups AttentionSpec만 DCP scale 후 LCM; prefix/connector off 또는 Mamba non-align 이면 hash=scheduler로 early return; 나머지 prefix_cacheable group subset GCD/override 및 hashing_sizes divisibility. Mamba `add_request:116`는 `cache_config.block_size` 분모, pre-copy `MAMBA_BLOCK_SIZE=mamba_spec.block_size`, Scheduler aligned split은 `cache_config.block_size`, backend는 `kv_cache_spec.block_size`. 실제 두 값이 다른지 모름.
- **신규 파일:** `src/phase5_scheduler_mamba_contract.py` 읽기 전용 고정 6파일(AST, SHA, SchedulerConfig.get_scheduler_cls, EngineCore factory assignment, Mamba group·seed·precopy·postprocess, Scheduler and backend spec field). `tests/test_blazux_phase5_scheduler_mamba_contract.py` **신규 17개 synthetic Python/CPU tests** (가상 block-size 16/16, 16/32 경계 비교는 **실제 GPU slot bug의 증거가 아님**). `scripts/phase5-check-offline.sh` Source AST gate 추가. [동일 Phase5 runbook](BLAZUX-PHASE5-SCHEDULER-MAMBA-SLOT-CONTRACT-20261027.md). **전체 목표 unittest 276/XFAIL0, Manifest 169개**, 신규 DGX 미실행. ※ 과거 전체 259 PASS를 신규 276 PASS로 올려 적지 말 것.
- **적용 승인 경계:** 모든 AST checks true여도 `active_scheduler_class_verified=false`, `actual_config_block_equality_verified=false`, `state_slot_correctness_verified=false`, `patch_approved=false`. 실제 Scheduler class/value, Mamba align context/seed/copy/restore, prefix hits 및 GPU/실 모델 동작 전부 미검증. Blazux 5계열 아무 patch도 설치 엔진에 적용 금지. Docker/weights/HF cache/ports/GPU/HTTP/TPS/CI/서빙 조작 금지.
- **GitHub 운영 규칙:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` immutable. `main` 대상 PR/merge/rebase/cherry-pick/squash/sync 금지, 현재 PR/Merge 불필요. 동일 Phase5에서만 별도 Source/CPU fixture 보강.

---

## 2026-10-27 Phase5 읽기 전용 3개 소스 확인 완료 — 이전 실측 최신

- **사용자 업로드** `붙여넣은 텍스트(1)(20261027-114116).txt`는 DGX 소스 inspection `CHECK1_SOURCE_INSPECTION_DONE` / `CHECK2_SOURCE_INSPECTION_DONE` / `CHECK3_SOURCE_INSPECTION_DONE` 세 마커. 운영 이미지 ID `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`에서 별도 read-only, runc, network=none, NVIDIA_VISIBLE_DEVICES=void 컨테이너로 Python AST/source 조회. **이번 3개 검사에는 259 unittest/164 manifest 재실행 내용이 없다.** 최근 독립 전체 Gate PASS는 사용자 DGX 소스 `bc89de6288889943b50090ac9638ee95c2434a79`에서 259/259 XFAIL0, Source164/164, Mock38/38. 해당 실측 문서 이전 docs-only HEAD `17cfbc5b087a9245e2645a44131bd35f47dd7f40`; 이번 보고서/Manifest만 바꾼 새 docs SHA는 DGX 재시험이 아니다.
- **CHECK1 Scheduler binding 해결된 의문:** `v1/engine/core.py:148`에서 `Scheduler = vllm_config.scheduler_config.get_scheduler_cls()`. :157–159에서 `resolve_kv_cache_block_sizes` tuple unpack, :161에서 그 지역 `Scheduler` 호출. 이전 narrow AST의 `engine_static_imports_scheduler=false`는 **직접 import가 아닌 runtime config class factory 설계**를 analyzer가 모델링하지 못해 발생한 한정 false; **실제 선택된 클래스/사용자 설정/ABI는 미확인**. 기존 5/6 기록은 역사적 분석기 출력으로 보존; 새 사실을 근거 없이 6/6 통과로 변경하지 않는다.
- **CHECK2 KV Resolver 분기 정확히 확인:** `v1/core/kv_cache_utils.py:627` `dcp=decode_context_parallel_size`. `len(groups)<=1`에서는 `bs=cache_config.block_size*dcp` 후 `return bs,bs`. 2+ groups일 때 AttentionSpec은 `spec.block_size*dcp`, 다른 그룹(Mamba 포함)은 `spec.block_size` 그대로 LCM. `prefix caching/connector 모두 OFF`(647행) 또는 **하나라도 Mamba non-align**(657행)이면 hash=scheduler size로 조기 반환. 나머지는 prefix_cacheable 그룹 우선 `hashing_sizes`(없으면 모든 group)와 `prefix_match_unit` override/GCD, divisibility guard는 `hashing_sizes`에만 적용. 632/647/657/673 반환 각각 분리.
- **CHECK3 Mamba Block-size 단위 위험 확인:** Worker `MambaHybridModelState.add_request:116` seed 분모 `self.cache_config.block_size`, Scheduler `_mamba_block_aligned_split:392`도 config.block_size. Preprocess `MAMBA_BLOCK_SIZE=mamba_spec.block_size`, Mamba backend `self.kv_cache_spec.block_size` (all-mode/replayssm), postprocess `run_fused_postprocess_align`. Mamba group spec.block_size/mode/speculative_blocks 같다는 assert는 그룹끼리만 검증하며 config field와 spec field의 **실제 값 일치를 증명하지 않는다**. 따라서 **조건부 mismatch risk**, GPU 실제 prefix hit/SSM copy/rollback bug 확정 아님.
- **영구 실측:** [DGX 3-check 정본 보고서](BLAZUX-PHASE5-DGX-THREE-SOURCE-CHECKS-20261027.md). 다음 **같은 Phase5**에서 `config/scheduler.py:get_scheduler_cls` 반환/override source, fake KV group/early-return/DCP CPU fixtures, `_ensure_align_ctx` + Mamba slot state seed/preprocess/postprocess 복원 계약부터 조사한다. 실제 blazux patch 적용 승인 0, 운영 Docker/모델/weights/HF cache/ports/GPU/HTTP/TPS/CI 미변경.
- **GitHub 정책:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` immutable. 현재 PR/Merge 필요 없음, blazux→main PR/Merge/Cherry-pick/Rebase/Squash/Sync 영구 금지.

---

## 2026-10-27 Phase5 Narrow KV LCM → EngineCore Source-only DGX PASS — 이전 스냅샷

- **사용자 DGX 실제 시험 소스** `feature/blazux-phase5-correctness-mtp-offline@bc89de6288889943b50090ac9638ee95c2434a79`. 사용자가 제공한 `붙여넣은 텍스트(1)(20261027-112439).txt`: **Manifest 164/164**, **Wizard Mock 38/38**, 전체 unittest **259/259 XFAIL0**, AST/wrapper PASS, `PHASE5_NARROW_BLOCK_FLOW_DONE_NOT_PATCH_APPROVED` 및 `PHASE5_NARROW_BLOCK_FLOW_EXECUTED_NOT_CERTIFIED`. 보고서/Manifest만 추가한 **docs-only 후속 SHA는 DGX에서 재시험하지 않음**.
- **정적 6조건 중 5 true**: `engine_static_imports_resolver=true`, `kv_scheduler_size_lcm_assignment=true`, `kv_function_returns_both_sizes=true`, `engine_assigns_scheduler_size_from_resolver=true`, `engine_ctor_uses_scheduler_size_variable=true`; **`engine_static_imports_scheduler=false`** 하나 남아 `status=UNRESOLVED_OR_PARTIAL_STATIC_CHAIN`. 좁은 6파일 검사 `bounded_output_truncated=false`, `runtime_flow_proven=false`, `patch_approved=false`. False는 analyzer가 기대하는 모듈 최상위 `vllm.v1.core.sched.scheduler.Scheduler` import 패턴을 못 찾았다는 뜻이지 실제 import/dispatch 오류 확정 아님.
- **실제 코드 경로:** `v1/core/kv_cache_utils.py:634`에서 AttentionSpec은 `kv_cache_spec.block_size * dcp`, 나머지 group은 `kv_cache_spec.block_size`로 `group_block_sizes`. :640 `math.lcm(*group_block_sizes)`. :659 cacheable group을 먼저 골라 hash sizes 구성(없으면 전체). :665 requested 또는 `math.gcd(*hashing_sizes)`. :673 `return scheduler_block_size, hash_block_size`; **632/647/657행 별도 early return** 존재하므로 unconditional LCM/GCD 주장은 금지. `v1/engine/core.py:157` tuple unpack resolver 결과 → :161 `Scheduler(block_size=scheduler_block_size,hash_block_size=hash_block_size)`. `Scheduler.__init__:174`는 `self.block_size=block_size`.
- **상태 구분:** 259 unit PASS는 **합성 검증과 Source AST gate**에 한하며 실제 model/GPU/prefix cache hit/SSM state restore/Responses/MTP acceptance/TPS/CI는 미검증. 위 5개 true를 실 runtime block 크기/slot correctness로 과대 해석 금지.
- **영구 문서:** [2026-10-27 Phase5 DGX Narrow Block Flow 보고서](BLAZUX-PHASE5-DGX-NARROW-BLOCK-FLOW-RESULTS-20261027.md), [실행 Gate/Runbook](BLAZUX-PHASE5-NARROW-BLOCK-FLOW-20261027.md). 좁은 source SHA256 6개 및 세부 불일치·분기 기록.
- **다음 같은 Phase5:** `EngineCore`의 Scheduler 실제 import/binding 패턴/alias를 확인하고, `resolve_kv_cache_block_sizes`의 early return 조건 및 `dcp` 공급 경로, Mamba hybrid group spec·state slot seed/pre/postprocess 정렬을 **소스+합성 CPU**로 검증. 새 Phase 만들지 않는다. blazux 패치 5개 계열 적용 승인 여전히 **0건**.
- **GitHub 보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` 불변. 현재 PR/Merge 불필요, blazux→`main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지. 원본 Docker/serving/ports/model/weights/HF cache/GPU/HTTP/CI 사용자 별도 승인 전 미변경.

---

## 2026-10-27 Phase5 LCM → 반환 → EngineCore 생성자 정밀 조사 구현 — 이전 계획 (DGX 실행 전)

- **브랜치:** `feature/blazux-phase5-correctness-mtp-offline`, 직전 문서 HEAD `f61e9dc03162997253e468ab8e33737b680b1b86`. 사용자 DGX에서 실제 시험된 Source HEAD는 `04b871ab632b2a59d55d11f19009c48daa3ce5c0`: unit **244/244 XFAIL0**, Source **160/160**, Scheduler provenance AST 종료. 조사 범위는 `ASSIGN_SITE_LIMIT=64`로 **PARTIAL**이었다. 이전 실측과 이번 새 코드의 시험 결과는 절대 혼합하지 않는다.
- **출처 확보 내용:** `v1/core/kv_cache_utils.py:640`의 `scheduler_block_size=math.lcm(*group_block_sizes)`, :665 `hash_block_size=requested or math.gcd(*hashing_sizes)`와 `v1/engine/core.py:161`의 `Scheduler(block_size=scheduler_block_size,hash_block_size=hash_block_size)`는 각각 별개 소스 단서. 실제 KV resolver 반환→EngineCore 지역 변수 대입→Scheduler 생성자 연결, 정확한 imports와 branch 조건은 미확정. Mamba worker `add_request:116`와 Scheduler `_mamba_block_aligned_split:392`는 계속 KV config block_size 사용.
- **같은 Phase5 신규 구현:** `src/phase5_block_flow_narrow.py` = 설치된 vLLM을 import하지 않는 고정 6 Python 파일 AST 분석. EngineCore 관련 함수 import/variable assignment/ctor keyword와 KV resolver group LCM/GCD/return, Mamba/Scheduler/Backend static traces. `tests/test_blazux_phase5_block_flow_narrow.py` = **신규 15 stdlib synthetic tests**. `scripts/phase5-check-offline.sh` AST gate 포함. [단일 실행 Runbook](BLAZUX-PHASE5-NARROW-BLOCK-FLOW-20261027.md). 전체 기대 unit **259/XFAIL0**, Source Manifest **164 tracked**, **현재 신규 HEAD DGX NOT_RUN**.
- **차단 정책:** 정적 6조건이 다 참이면 `STATIC_CHAIN_CANDIDATE_NOT_RUNTIME_CERTIFIED`, 아니면 `UNRESOLVED_OR_PARTIAL_STATIC_CHAIN`. 반드시 `runtime_flow_proven=false`, `patch_approved=false`. Mamba cache group/LCM/state slot/SSM restore 및 parser/Responses/MTP runtime 미검증. 실제 blazux patch·GPU·운영 Docker·모델·ports·HF cache·HTTP/TPS/CI 금지.
- **GitHub 보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` immutable. 현재 PR/Merge 불필요, `main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지. 새 Phase 만들지 않고 동일 Phase5에서 계속.

---

## 2026-10-27 Phase5 DGX Scheduler LCM / ctor source-only 실측 결과 — 우선 스냅샷

- **사용자 DGX 실제 소스 `04b871ab632b2a59d55d11f19009c48daa3ce5c0`**: `PHASE5_UNIT_PASS=244; XFAIL=0`, Source Manifest 160/160 PASS, AST/Wrapper PASS, `PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED`, 최종 `PHASE5_SCHEDULER_PROVENANCE_EXECUTED_NOT_CERTIFIED`. 새로운 **docs-only** SHA에서는 DGX 244개를 재실행하지 않음. 이번 로그에 개별 mock 시험 수는 미표시(Wrapper는 완료). [상세 Source-only 결과](BLAZUX-PHASE5-DGX-SCHEDULER-PROVENANCE-RESULTS-20261027.md).
- **핵심 실제 AST:** `v1/engine/core.py:161` `Scheduler(block_size=scheduler_block_size,hash_block_size=hash_block_size)` direct-name 후보 1 (`NAME_MATCH_SCHEDULER_NOT_RESOLVED`); `v1/core/kv_cache_utils.py:640` `scheduler_block_size=math.lcm(*group_block_sizes)`; `kv_cache_utils.py:665` `hash_block_size=requested if requested is not None else math.gcd(*hashing_sizes)`; `Scheduler.__init__:174` `self.block_size=block_size`; `_mamba_block_aligned_split:392`와 `MambaHybridModelState.add_request:116`은 legacy `cache_config.block_size`. 아직 EngineCore의 실제 import/return/assignment 연결, hybrid group/mamba state slot 단위는 미증명. blazux patch 적용 금지.
- **한계:** `scan.state=PARTIAL` 이유 `ASSIGN_SITE_LIMIT` (일반 block_size assignment 64개로 잘림); scan file 384/384, 6,448,206 bytes, unreadable 0. dynamic ctor 0은 스코프 안 결과. **PARTIAL을 COMPLETE라고 기록하면 안 됨**.
- **다음 같은 Phase5:** `v1/engine/core.py`와 `v1/core/kv_cache_utils.py:resolve_kv_cache_block_sizes`만 대상으로 `group_block_sizes` 생성→`scheduler_block_size` LCM→반환→EngineCore Scheduler 인자를 precise import/AST source-only 분석하고 Mamba spec.slot alignment를 synthetic CPU fixture로 확인. 범위를 좁혀 ASSIGN_SITE_LIMIT 회피, 새 Phase 생성 금지.
- **보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0/Phase1~4 그대로. PR/Merge 불필요, `main` PR/Merge/Cherry-pick/Rebase/Squash/Sync 영구 금지. 운영 Docker/GPU/weights/HF cache/model/ports/HTTP/TPS/CI/배포 모두 별도 승인 전 미진행. 모든 blazux 적용 승인 **0건**.

---

## 2026-10-27 Phase 5 Scheduler 생성자·LCM 출처 읽기 전용 조사 묶음 (이전 구현 계획)

- **단일 Phase5 유지:** 브랜치 `feature/blazux-phase5-correctness-mtp-offline`의 검증된 기존 문서 HEAD `fbfe28774ed8b7915ab6c44f6b5fe8a0c5f906d1`에서 새 source-only 분석기·회귀시험·runbook·Manifest를 추가한다. **확정 실기 결과는 이전 코드 `2c7c6896...`의 unit223/223, Mock38/38, Source152/152**. 사용자 마지막 AST JSON은 보호 명령 맥락 SHA `2cadc7369b4b813332a767733faa9c2529413cd9`의 `PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED` 확인에 한정; 그 소스의 **233 tests/156 Source 전체 Gate는 로그 미제공으로 미확정**. 새 이번 소스 HEAD 또한 DGX **NOT_RUN**.
- **왜 추가하는가:** config/cache.py:125에 mamba_block_size STORE, config/vllm.py:2535–2536에 LOAD가 있지만 `MambaHybridModelState.add_request:116`은 `cache_config.block_size`로 slot을 나누고 `Scheduler._mamba_block_aligned_split:392`도 legacy block_size 사용. Scheduler.__init__:174의 `self.block_size`는 계산된 값이 아니라 **생성자 인자 `block_size` 저장**. 따라서 실제 생성자 **호출부/동적 scheduler_cls factory·LCM/그룹 정렬·state-slot restore** 검증이 다음 우선순위다.
- **새 파일:** `src/phase5_scheduler_provenance.py` = installed vLLM을 **import하지 않는** `config`+`v1` bounded source-only AST 조사기. 직접 `Scheduler(...)` 및 동적 `scheduler_cls(...)` 후보 호출, keyword/positional block_size/hash_block_size, `lcm` 대입·mamba_block_size STORE/LOAD, Scheduler/Mamba 원래 함수 AST trace를 수집하고 **소스 이름/표현 힌트는 실제 바인딩·semantic correctness가 아님**을 명시한다. `tests/test_blazux_phase5_scheduler_provenance.py` 신규 **11개 stdlib synthetic tests**, `scripts/phase5-check-offline.sh` AST gate 확장. 233+11 = **244 unit(XFAIL0) 목표, 아직 미실행**, Manifest 예상 **160 tracked**.
- **Runbook/승인 경계:** [Scheduler Block Size Provenance 소스 조사](BLAZUX-PHASE5-SCHEDULER-BLOCK-PROVENANCE-20261027.md)에서 clean 별도 DGX checkout ff-only + `scripts/phase5-check-offline.sh` + 기존 이미지 ID의 `--runtime=runc --network=none --read-only --tmpfs /tmp:rw,mode=1777,size=256m CUDA_VISIBLE_DEVICES=-1` 임시 CPU-only 조사. 마커 `PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED`. 검색 한계 `PARTIAL`/dynamic factory unresolved면 결과를 과대 판정하지 않는다.
- **변경·PR 금지:** blazux Mamba/Scheduler, Qwen Tool/Responses, MTP Reduced Draft Vocabulary 어느 patch도 아직 적용 승인 없음. 운영 Docker/서빙/모델·HF cache/receipts/ports/GPU·HTTP/실 모델 추론·TPS/CI 시험 금지. `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` 불변. PR/Merge 불필요; blazux→main PR/merge/cherry-pick/rebase/squash/sync 영구 금지.

---

## 2026-10-27 Phase 5 — DGX AST dependency trace JSON 확인, unit gate 미확정 (이전 증거)

- **사용자 첨부:** `붙여넣은 텍스트(1)(20261027-091133).txt`는 `PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED`와 AST JSON을 포함. 앞선 사용자가 실행한 보호 명령 `EXPECTED=2cadc7369b4b813332a767733faa9c2529413cd9`에 의해 SHA 귀속(단 JSON 자체에는 HEAD 필드 없음). **233/233 unittest, 156/156 manifest 및 mock 결과는 이 첨부에 없어 PASS로 기록하지 말 것.** 마지막 확인된 전체 Source/unit PASS는 이전 `2c7c6896...`에서 Source152/152, mock38/38, unit223/223/XFAIL0.
- **Mamba 핵심 발견:** source scan `SCANNED_READ_ONLY`, 384개 Python 파일/6,448,206bytes/unreadable0. `config/cache.py:125`의 `mamba_block_size` STORE, `config/cache.py:267` 및 `config/vllm.py:2535–2536`의 LOAD 확인. **이전 특정 worker 파일에 없는 것과 전역 field 부재는 다르다.** worker `add_request:116`은 `self.cache_config.block_size`로 나눔; Scheduler `__init__:174`의 `self.block_size`는 생성자 인자 `block_size` 그대로; scheduler `_mamba_block_aligned_split:392`은 `self.cache_config.block_size` 사용, hash_block_size도 별도. 실제 `Scheduler(block_size=...)` 호출자/LCM/SSM state seed/restore 단위 미검증.
- **MTP 중요 분기:** `Qwen3_8FlashNextMTP.__init__`가 `self.model.embed_tokens`, `ParallelLMHead(...)`, `PPMissingLayer()`를 조건별 `self.lm_head`에 지정; `compute_logits`는 `self.logits_processor(self.lm_head,hidden_states)` 반환, `load_weights`에 native checkpoint 검증/name remap. Reduced draft vocab 단순 subset은 alias/weight dtype/vocab/TP/acceptance 검증 전 **NO GO**.
- **Tool/Responses:** ParserEngine argument converter/_flush_arg_converter, Qwen3 extraction, StreamingParser feed/finish, Responses parse_delta/emit_delta/_raise_if_error 등 정적 call edge 확인. blazux 일부 helper는 해당 클래스에 null; 기능 전체 부재/버그 단정 금지.
- **영구 증거:** [Phase5 DGX 의존성 추적 결과](BLAZUX-PHASE5-DGX-DEPENDENCY-TRACE-RESULTS-20261027.md), [기존 재현 및 Gate](BLAZUX-PHASE5-DEPENDENCY-TRACE-READONLY-20261027.md). 이후 docs-only SHA는 실제 DGX 소스 HEAD와 구분. **다섯 blazux patch 적용 승인 0건**, real prefix hit/Tool SSE/MTP acceptance/GPU/model/TPS/CI 미실행.
- **다음:** 같은 Phase5에서 Mamba CacheConfig 실제 필드 설정 → Scheduler 생성자 block_size 호출자/LCM → Mamba state slot pre/postprocess 연결을 source-only로 분석, 이어 Parser/Responses multi-file dependency, MTP head/weights contract의 CPU fixture. `main`과 P0/Phase1~4 불변, PR/merge 금지, 운영 Docker/weights/cache/ports/GPU 미변경.

---

## 2026-10-27 Track A Phase 5 Dependency Trace 통합 추가 — 이전 구현 계획

- **확정된 직전 DGX 증거:** 코드 HEAD `2c7c6896430be0d9eada656f17edf97d9c5f4d3f`에서 Source 152/152 PASS, Mock 38/38, unittest **223/223 XFAIL0**, pinned blazux 5계열 source preflight PASS, **적용 승인 0건**. 해당 결과는 [Phase5 DGX 실측 정본](BLAZUX-PHASE5-DGX-PATCH-PREFLIGHT-RESULTS-20261027.md). 이번 작업 출발한 문서 전용 HEAD `e0dbed59b3ef8c5b7a3c843a904c4c96532f22e6`는 DGX에서 재실행된 HEAD가 아니다.
- **같은 Phase 5에서 신규 실행 준비:** `src/phase5_dependency_trace.py`에서 설치 vLLM을 import하지 않고 Source AST의 계산 RHS·assignments·calls·redacted return shapes 조사. Mamba add/preprocess/postprocess, Scheduler __init__/prefix hit, ParserEngine/Qwen3/Streaming Parser/Responses, NVIDIA MTP `lm_head`/`logits_processor`/weights 및 PLE forward를 통합 출력. `config`+`v1`의 `mamba_block_size` 대입(STORE)/사용(LOAD) 위치 탐색; **스캔 한계·symlink·unreadable·누락은 fail-closed 성격으로 명시**.
- **검증 구성:** 합성 Python source만 사용하는 `tests/test_blazux_phase5_dependency_trace.py` **10개**, `scripts/phase5-check-offline.sh` AST 포함. 현재 목표 전체 unit **233 tests XFAIL=0**이며 **아직 DGX NOT_RUN**. Source Manifest 예정 **156개** (전 153 + 새 3). 단위시험/ABI 결과를 미리 PASS라고 주장 금지.
- **재현 문서:** [Phase5 Source Dependency Trace](BLAZUX-PHASE5-DEPENDENCY-TRACE-READONLY-20261027.md). 기존 Phase5 전용 clean checkout에서 ff-only로 최신 SHA 확인 후 **격리된 CPU-only, network=none, --read-only, runc** 컨테이너 한 번만 실행. 기존 운영 Docker, MTP 원본 31 BF16 텐서, 95GiB PLE/weights, GPU·ports·HF cache/receipt 절대 변경하지 않는다.
- **중요 차단:** `mamba_block_size`는 실제 config 객체 런타임 공급자/LCM/slot restore 확인 전 Mamba 수정 금지. Parser/Responses의 streamed tool args/terminal error는 호출명 AST만으로 판단 불가. MTP draft vocab은 공유 head/dtype/TP/tokenizer/acceptance 및 한국어·Tool Calling 품질 미확인으로 **기본 적용 금지**. 이 조사기는 **SOURCE_EVIDENCE_ONLY / APPLY_APPROVED=0**, 후속 source/CPU test는 동일 Phase5, GPU/서빙/Track B는 사용자 별도 승인.
- **보호 정책:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` immutable. PR·Merge 지금 불필요, 허용 시 Phase5→Phase4 *비병합 Draft*만 검토, `main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지.

---

## 2026-10-27 Track A Phase 5 DGX pinned blazux Patch Preflight 실측 PASS — 이전 확정 스냅샷

- **소스 코드 실측 HEAD:** `feature/blazux-phase5-correctness-mtp-offline@2c7c6896430be0d9eada656f17edf97d9c5f4d3f`; 사용자 DGX 출력에서 **152/152 Source Manifest, 38/38 Wizard Mock, unittest 223/223 XFAIL=0, AST 및 Source-only patch preflight PASS**. 마지막 `PHASE5_PATCH_PREFLIGHT_SOURCE_ONLY_DONE_NO_APPLY_APPROVAL`, `PHASE5_PATCH_PREFLIGHT_EXECUTED_NOT_CERTIFIED`. 이 후속 보고서/manifest 문서 커밋은 **DGX에서 시험한 소스 HEAD가 아님**.
- **patch-family 실측 상태 5개:** Mamba/Scheduler=`SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY`; Tool Argument Schema, Tool Literal Marker=`MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED`; Responses terminal=`PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED`; reduced MTP draft vocab=`MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED`. **APPLY_APPROVED=0, runtime/ABI correctness=NOT_VERIFIED**. 어떤 상태도 blazux 최적화를 운영 이미지에 적용한 것이 아님.
- **원래 설치된 12개 파일 SHA/AST**는 [Phase5 DGX Patch Preflight 영구 보고서](BLAZUX-PHASE5-DGX-PATCH-PREFLIGHT-RESULTS-20261027.md) 참조. Mamba legacy block-size 1 / dedicated mamba field 0, Scheduler legacy 1 / `self.block_size` assignment 0. MTP NVIDIA `compute_logits(self,hidden_states,spec_step_idx)` (lines465–468) 및 `load_weights(self,weights)` (470–488), `lm_head`/logits_processor source anchors; Parser/Responses 신규 helper 대부분 부재. **field 정의·group LCM·state restore, Parser multi-file patch preimages, MTP shared head/weight-vocab/acceptance를 확인하기 전 실제 patch 금지**.
- **범위와 다음 순서:** 같은 Phase5에서 우선 Mamba/Scheduler cache config·group LCM·state slot 생성/복원 소스 계약, 다음 Tool/Responses multi-file preimage/context, 마지막 MTP lm_head 실제 호출·TP/dtype/vocab 계약을 **읽기 전용으로 추적**. 사용자 명시적 승인 없는 GPU/HTTP/모델 load/serving/TPS/CI 금지. Track B 0.32/YaRN/Hybrid FP8 별도 보류.
- **시험 기준 분리:** Phase 4 독립 FAST/STATS는 기본 OFF, Phase5 CPU 정확성/소형 bench는 이전 실측 그대로 보존. 새 GitHub 문서 전용 SHA에서 223 unit 재실행한 것으로 주장 금지.
- **GitHub refs:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` 불변. **PR/Merge 지금 필요 없음**, 필요하면 Phase5→Phase4 Draft 비병합 리뷰만. blazux→`main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지. 운영 Docker/모델/cache/포트/receipt 절대 변경 금지.

---

## 2026-10-27 Track A Phase 5 pinned blazux Patch Preflight 추가 — 이전 계획 (DGX 실행 전)

- **현재 실제 검증 증거:** 사용자 DGX에서 소스 `9e2d1647357938f6d465eb9b3ce473d03e38e779`가 148/148 Source Manifest, 38/38 Mock, unittest 215/215 XFAIL0 및 preview source-only ABI 탐색 종료. 그 실측을 문서화한 기존 Phase5 docs HEAD는 `e3ea43e95cb444197400389b0dfe3064a3e9f879`. **새 소스 HEAD에서 223개 unittest 및 patch preflight 결과는 아직 NOT_RUN**.
- **이번 범위 묶음:** `src/phase5_patch_readiness.py`의 import-free vLLM source file 12개 read-only SHA256/AST method fingerprint/patch anchor 카운트 및 conservative classification, `tests/test_blazux_phase5_patch_readiness.py` 신규 **8개 fake-source stdlib 회귀**, `scripts/phase5-check-offline.sh` AST 검사 확장, [Patch Preflight Runbook](BLAZUX-PHASE5-PATCH-PREFLIGHT-READONLY-20261027.md). 전체 단위시험 **223 예상, XFAIL 0**; 직접 DGX 로그 수신 전 PASS를 선언하지 말 것.
- **P1 Mamba/Prefix**: pinned blazux Mamba seed/Scheduler LCM 변경은 source anchor뿐 아니라 cache_config.mamba_block_size 정의/slot-table layout/worker-scheduler 일관성을 검증해야 하며 실제 vLLM 코드 적용은 아직 금지. **P1 Tool/Responses**: parser_engine/qwen3/adapters/abstract_parser/streaming/config/Responses protocol+serving/new argument validator의 다중 파일 preimage 의존성; partial tool calls 및 SSE terminal 정확성 미확인. **P2 MTP**: installed NVIDIA `models/qwen3_8_flash_next/nvidia/mtp.py`, `compute_logits(...,spec_step_idx)` 확인; reduced draft hook의 shared lm_head/dtype/vocab/acceptance 의미 미확인, 적용 금지.
- **분류는 승인 아님:** `SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY`, `MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED`, `PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED`, `MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED`, `SOURCE_MISSING_OR_UNPARSEABLE` 등은 patch 전제 확인만 뜻한다. 제품 수준 성능/정합성 및 HTTP/GPU/실 모델/CI 미검증 유지.
- **Phase/브랜치 정책:** 같은 안전 경계는 Phase5에서 계속하며 Phase6/GPU 영역은 사용자 명시적 승인 필요. `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0, Phase1~4 immutable. 현시점 PR/merge 불필요. Phase5→Phase4 비병합 Draft review 외 PR 금지, `main` PR/merge/cherry-pick/rebase/squash/sync 영구 금지. 운영 Docker·이미지·HF cache·model/ports/receipts 절대 변경하지 않음.

---

## 2026-10-27 Track A Phase 5 DGX preview ABI 소스 triage 실측 완료 — 이전 스냅샷

- **사용자 DGX 실측 소스 SHA:** `feature/blazux-phase5-correctness-mtp-offline@9e2d1647357938f6d465eb9b3ce473d03e38e779`; Source **148/148 PASS**, Wizard mock **38/38 PASS**, unittest **215/215 OK XFAIL=0**, AST 검사 및 마지막 `PHASE5_READONLY_ABI_TRIAGE_EXECUTED_NOT_CERTIFIED` PASS. 실측은 사용자 stdout로 확인, GitHub에서 DGX를 재실행하지는 않았다.
- **실제 source 경로 해소:** 설치된 `vllm/models/qwen3_8_flash_next/nvidia/mtp.py`(SHA256 `d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6`), `nvidia/ple_layer.py` (SHA256 `6690edcd2e2b2ae309b214991a060bffbdbbcdc42334e164db0aebcc0a5b397e`) 및 NVIDIA `model.py` 존재; AMD 대응 구현은 **별도 소스**로 확인. `Qwen3_8FlashNextMTP.compute_logits(self,hidden_states,spec_step_idx)`, `forward`, `load_weights` AST 함수/인자 확인. 이전 `ABSENT_OR_RELOCATED`는 이전 조사지의 경로 가정 오류였음.
- **blazux anchor triage:** Mamba `legacy_small_block_expression=true`, `direct_mamba_block_expression=false`, Scheduler `legacy_cache_block_assignment=true`, `scheduler_block_assignment=false`. `ParserEngine`의 `_normalize_tool_arguments`/`_arguments_block_emission`/`_skip_incomplete_tool_slot`, `StreamingParserEngine._marker_is_literal`, Responses failed/incomplete 관련 helper 미발견. `parser_engine_config.guard_literal_tool_markers` 미발견. **이 결과는 source anchor 힌트**이고 ABI/기능 PASS, 실제 버그 확정, patch의 안전한 적용 허가는 아님.
- **범위 한계:** `model_search= CANDIDATE_LIMIT_REACHED`, 536 Python 파일 탐색 중 matched 43개/표시 32개; 전체 모델 검사 미완료이나 Qwen3.8 NVIDIA·AMD MTP/PLE 대상 파일은 실제 목록에 포함. 모든 세부 path/method/SHA 근거: [Phase5 ABI 실측 정본](BLAZUX-PHASE5-DGX-PREVIEW-ABI-TRIAGE-RESULTS-20261027.md).
- **다음 같은 Phase5 내 작업:** pinned blazux `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`의 Mamba/Scheduler, Parser/Responses, MTP 원본 patch와 설치된 함수 본문/정확한 source anchor를 읽기 전용으로 비교하여 `SAFE_OFFLINE_PATCH_CANDIDATE/ABI_MISMATCH/ALREADY_PRESENT/INCONCLUSIVE` 판정. **GPU/HTTP 실제 모델 서빙, cached-vs-uncached, MTP acceptance, TPS/CI는 별도 승인 전 미실행.** 이전 Phase/P0/main 보호, PR/merge 현재 불필요, main 방향 작업 영구 금지.
- **Git SHA 구별:** 사용자 실기 HEAD `9e2d1647...`와 이번 증거 보고서/handoff/source manifest만 갱신하는 docs-only HEAD는 구별할 것. 새 docs SHA는 DGX에서 215 tests 재실행된 코드가 아님.

---

## 2026-10-27 Track A Phase 5 read-only preview ABI triage 추가 (이전 계획)

- **기반:** Phase 5 이전 실기 PASS 코드는 `01c9eb6ba311e3ace5f68ecc49fa56f8e0b37d94` (144/144 Source, 208/208 unittest XFAIL0, 12조건 합성 PLE CPU benchmark, 설치 preview source inventory). 확정 docs HEAD `f3e5fa32a30cb258acd66a9700c6db2a78eb71cc`에서 같은 Phase5의 후속 코드·시험·문서만 커밋. **Phase5를 세분화해 새 Phase를 만들지 않는다**.
- **이번 추가:** `src/phase5_preview_abi_audit.py`가 vLLM을 import하지 않고 기존 이미지의 설치 소스 경로·SHA256·클래스/함수 인자·blazux pinned anchor를 AST/문자열로 읽는다. qwen4_exp·qwen3_8 트리의 모델 MTP/PLE 후보 파일을 우선 찾고, 후보가 많으면 한계 도달을 명시. symlink·out-of-tree·너무 큰 파일은 읽지 않는다. 실제 preview source patch/load/GPU 실행 없음.
- **신규 오프라인 회귀:** `tests/test_blazux_phase5_preview_abi_audit.py` 7개; Phase5 `scripts/phase5-check-offline.sh`에 AST 파일 포함. **예상 전체 unit 215, XFAIL 0**이며 새 HEAD의 DGX 실제 실행 결과는 아직 **NOT_RUN**. 조사지의 source string/AST 일치만으로 블록 상태 정확성/Tool Calling/Responses/MTP reduced vocab 기능 PASS 인증 금지.
- **상세 재현 절차 및 Gate:** [Phase5 Preview vLLM ABI 읽기 전용 triage](BLAZUX-PHASE5-PREVIEW-ABI-READONLY-TRIAGE-20261027.md). Phase5 전용 DGX 체크아웃에서 `git fetch`/clean/ff-only pull 및 소스 검증을 하고, 운영 이미지 ID만 조회하는 `--runtime=runc --network=none --read-only CUDA_VISIBLE_DEVICES=-1` 임시 CPU 컨테이너로 도구 한 번 실행. 사용자 로그와 정확한 SHA를 받은 뒤 같은 Phase5에 영구 보고서 추가.
- **정확한 외부 pin:** blazux `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. `qwen38_mtp/ple`의 이전 `ABSENT_OR_RELOCATED`는 지정 경로 부재이지 모듈 자체 부재를 뜻하지 않는다. 실제 모델 MTP/PLE·cache/Parser ABI 승인 보류.
- **브랜치 보호:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` 불변. 지금 PR/Merge 불필요; 필요할 때 Phase5→Phase4 비병합 Draft PR만. `main` PR/Merge/Cherry-pick/Rebase/Squash/Sync 영구 금지.

---

## 2026-10-27 Track A Phase 5 — DGX CPU/Source Gate 실기 PASS (이전 실측 스냅샷)

- **실제 DGX 검증 코드 SHA:** `feature/blazux-phase5-correctness-mtp-offline@01c9eb6ba311e3ace5f68ecc49fa56f8e0b37d94`. 사용자 로그: Source Manifest **144/144**, full unit **208/208 OK XFAIL=0**, `PHASE5_SOURCE_AST_OK`, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS` PASS, 최종 `PHASE5_BUNDLED_DGX_OFFLINE_EXECUTION` PASS. 임시 컨테이너/설치 엔진 소스 인벤토리 stdout 근거로 기록.
- **기존 정확성 회귀 유지:** BF16 PLE workers 1/4 byte exact, Phase3 중복 샤드 reject, Phase4 FAST/Stats 4-way matrix 전부 byte_exact=1.
- **새 합성 PLE CPU 벤치:** 작은 13×7 BF16 file-backed warm cache table, N=16/64/256/512/513/1024 × 후보 범위 1/13 = **12조건**, 각 모드 4 warmup+21 repeats, `VLLM_PLE_PHASE_STATS=0`, 모든 byte_exact=true, 마지막 `PHASE5_SYNTHETIC_CPU_BENCH_ALL_OK`. N=16/13 median OFF **0.21798ms**, ON **0.01669ms**; 그 외 12조건 원본 및 p95는 [Phase5 정본](BLAZUX-PHASE5-DGX-VALIDATION-RESULTS-20261027.md). 실제 95GiB NVMe/GPU/TPS 성능 개선률로 절대 취급 금지.
- **설치 vLLM 읽기 전용 inventory:** `MambaHybridModelState`, `Scheduler._mamba_block_aligned_split`, `ParserEngine`, `Qwen3Parser`, `StreamingParserEngine`, `OpenAIServingResponses` 소스가 `PRESENT_SOURCE_PARSEABLE`, SHA256 기록. 조사기가 지정한 `qwen38_mtp`와 `qwen38_ple` 경로는 `ABSENT_OR_RELOCATED`; 설치 모델 MTP/PLE 자체의 부재로 단정 금지. `PHASE5_VLLM_SOURCE_INVENTORY_DONE_NOT_ABI_CERTIFIED`.
- **결정:** Phase5 합성 오프라인/정적 소스 Gate PASS. **실제 Prefix-cache state restore, Parser/Responses HTTP/SSE, MTP reduced vocab 적용·acceptance·다국어, vLLM preview ABI, GPU/실 모델 A/B/CI는 미검증.** 기존 운영 Docker, weights, HF cache, ports는 변경하지 않는다. 똑같은 CPU-only 추가 확인은 Phase5 안에서 묶어 진행, 새 Phase 자동 생성 금지.
- **기준 보고서:** [Phase 5 DGX 실측 결과](BLAZUX-PHASE5-DGX-VALIDATION-RESULTS-20261027.md), [통합 Gate/재현 절차](BLAZUX-PHASE5-BUNDLED-CORRECTNESS-AND-MTP-20261027.md). 테스트한 코드는 `01c9eb6b...`로 고정, 후속 문서·Manifest 커밋의 새 SHA는 DGX에서 테스트하지 않았음.
- **불변 규칙:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...`, Phase4 `69860277...` 보호. PR은 지금 불필요; 리뷰 요청 시 Phase5 head → Phase4 base로 **비병합 Draft PR만**. `main` 대상 PR·Merge·rebase·cherry-pick·squash·sync 영구 금지.

---

## 2026-10-27 Track A Phase 5 — P1 정확성 및 P2 MTP 위험 오프라인 통합 (이전 스냅샷)

- **실험 부모와 현재 브랜치:** Phase4 최종 실측 기록 HEAD `69860277122dffe3082c5b065e4361a571317a8e`에서 단일 `feature/blazux-phase5-correctness-mtp-offline` 자식 생성. P0/Phase1/Phase2/Phase3/Phase4 및 `main` ref 불변. User requirement: *가능한 작업은 안전성/rollback 경계 기준으로 묶어 Phase 증가 억제*. Phase5 결과/추가 fixture/수정도 동일 Phase 내 커밋.
- **이번 구현 범위:** `src/phase5_offline_contracts.py`와 `tests/test_blazux_phase5_contracts.py`의 **Mamba block=1600 vs QSA=16 state index 및 cache alignment CPU reference**, Tool Calling / Chat-vs-Responses **client-side 안전계약·schema·stream terminal event oracle**, **MTP reduced draft vocab 위험 / subset selection·conceptual acceptance 변화 oracle**. 총 신규 stdlib 테스트 **14개(예상)**. 실제 vLLM engine parser/cache/MTP logits patch를 구현했다고 주장하지 않는다.
- **추가 CPU/읽기 전용 조사:** `src/test_ple_phase5_bench_cpu.py` 합성 PLE OFF/ON small-N CPU wallclock measurement (통계 OFF, 21 repeats/4 warmup, real 95GiB 성능 주장은 금지), `src/phase5_vllm_source_inventory.py`는 import/설치 없이 vLLM Python source SHA/AST symbols를 read-only 확인. 모두 사용자가 실제 DGX에서 실행하기 전에는 **NOT_RUN**. 신규 `scripts/phase5-check-offline.sh`가 Manifest/mock/unit/audit/브랜치 보호 시험을 하나의 Gate로 묶는다.
- **검증 범위:** [Phase5 통합 오프라인 계획 및 재현 명령](BLAZUX-PHASE5-BUNDLED-CORRECTNESS-AND-MTP-20261027.md) 참고. 기존 unittest **194개+신규 14개=208개(예상)** 및 XFAIL=0, Source Manifest 전체 일치, 기존 Phase3 G2-01/Phase4 4-mode 재실행, CPU microbench·vLLM 소스 목록이 사용자의 DGX에서 실제 출력되기 전까지 Gate PASS를 주장하지 않는다. MTP 축소 vocabulary는 실 quality/acceptance 미검증으로 **적용 보류**.
- **위험·다음 분기:** installed preview Qwen parser/Responses, hybrid Mamba scheduler, MTP compute logits 실제 ABI는 vendored가 아니므로 BLOCKED_BY_UNVENDORED_UPSTREAM. 실제 GPU/HTTP/모델+MTP acceptance 시험과 Track B vLLM 0.32는 별도 Go/No-Go/사용자 승인 선행. 운영 container/ports 8000·18300, HF cache/model/receipts 절대 변경하지 않는다.
- **PR/머지 정책:** 현재 **불필요**. 필요하면 `head=feature/blazux-phase5-correctness-mtp-offline` → `base=feature/blazux-phase4-ple-cpu-bundle`의 리뷰 전용 비병합 Draft PR만, **merge하지 않음**. `main` 대상 PR/Merge/Cherry-pick/Rebase/Squash/Sync **영구 금지**.

---

## 2026-10-27 Track A Phase 4 DGX 통합 CPU 검증 PASS — 이전 인수인계

- **실측 소스 HEAD:** `feature/blazux-phase4-ple-cpu-bundle@a90eb081a9d85d290d191674c303d33cadb6f22d`. 사용자가 제공한 DGX 로그: **Source Manifest 137/137, full unit 194/194, XFAIL=0**, 마지막 `PHASE4_BUNDLED_CPU_SOURCE_CONTRACTS` PASS. wrapper에는 mocks/deployment manifest/bash/publication audit/clean checkout/origin 안전검사도 포함되지만, 로그에 개별 mock 개수는 따로 제시되지 않았다.
- **하나의 CPU 임시 시험 묶음:** 기존 BF16 PLE `workers=1 chunk=1024`·`workers=4 chunk=2` byte-exact PASS, `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK`, `PHASE2_PLE_CPU_ALL_OK`; 신규 `VLLM_PLE_FAST_GATHER`와 `VLLM_PLE_PHASE_STATS`의 OFF/OFF, ON/OFF, OFF/ON, ON/ON **4/4 byte_exact PASS**, `PHASE4_CPU_MATRIX_ALL_OK`, `PHASE4_COMBINED_OFFLINE_VERIFICATION`.
- **적용 경계:** 두 옵션은 서로 독립적인 기본 OFF이며 별도 커밋 `4aa692624f95008abbd76f808791b524335fb0c7`, `b83ecc66a70e53515fcd0992b51dc705236778e1`; CPU synthetic 정확성 검증이지 GPU·실 모델/Pinned H2D·vLLM 0.32·KV/Mamba/SSM·실제 95.37GiB PLE·TPS/A·B·CI 확인이 아님. 운영 이미지/모델 교체는 수행하지 않는다.
- **정본 결과:** [Phase 4 DGX 실측 보고서](BLAZUX-PHASE4-DGX-VALIDATION-RESULTS-20261027.md), [Phase 4 통합 Gate 계획서](BLAZUX-PHASE4-BUNDLED-PLE-CPU-20261027.md). `a90eb081...`는 **DGX 실측 코드 SHA**이고, 이번 기록·Manifest를 더한 후속 GitHub docs-only HEAD는 **실기 재검증되지 않은 SHA**이다. 원격 branch HEAD에서 후속 SHA를 확인한다.
- **Phase 최소화:** 같은 CPU-only/rollback/승인 범위의 추가 fixture·오류 수정·측정 계획·보고서 작업은 새 Phase 없이 Phase 4 내부에서 처리한다. GPU/실 weights/운영 컨테이너·포트·HF cache·receipt 변경에는 별도 사용자 승인 및 격리 시험 계획 요구.
- **보호 정책:** `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase1 `a50fc537...`, Phase2 `76588845...`, Phase3 `760f227e...` 고정. 지금 PR/Merge 불필요; 리뷰가 필요하면 Phase 4 head→Phase 3 base의 Draft **비병합** PR만. `main` 대상 PR·merge·cherry-pick·rebase·squash·sync 영구 금지.

---

## 2026-10-27 Track A Phase 4 — 두 기능 통합, Phase 수 감축 (과거 스냅샷)

- **사용자 우선 규칙 변경:** 작은 버그·기능·시험마다 새 Phase를 만들지 않는다. 위험/검증/rollback 범위가 같으면 **같은 Phase에 복수 기능별 독립 커밋**을 축적하고 공용 offline/GPU 승인 게이트를 적용한다. Phase 간 분기는 ABI/실험 안전 범위/별도 승인 변화가 있을 때만 한다. Phase 3 확정 부모 `760f227e46a358445db3d3931b5efbe40de5f609`를 원본으로 유지.
- **Phase4 브랜치:** `feature/blazux-phase4-ple-cpu-bundle`. 기본 OFF 기능 A `VLLM_PLE_FAST_GATHER=0`/행 512 기준 small-N inline gather; 독립 기본 OFF 기능 B `VLLM_PLE_PHASE_STATS=0`의 per-table CPU gather calls/errors/rows/logical_bytes/gather_s/fast_calls. **서로 다른 2개 커밋**으로 나누어 별도 rollback·on/off 비교 가능. 원래 BF16 PLE, G2-01 duplicate fail-closed, MTP 이름 31개 보호 유지.
- **동일 Phase 통합 시험:** [Phase 4 Gate 4 runbook](BLAZUX-PHASE4-BUNDLED-PLE-CPU-20261027.md), 신규 `scripts/phase4-check-offline.sh`, stdlib `tests/test_blazux_phase4_flags.py`, NumPy/PyTorch `src/test_ple_phase4_cpu.py`. OFF/OFF·ON/OFF·OFF/ON·ON/ON, BF16 byte-exact, input duplicates/short shard/threshold/invalid IDs/metrics snapshot, 그리고 기존 Phase3 G2-01 CPU 시험을 **같은 한 번의 임시 컨테이너에서 실행**. 예상 총 unit **194개 XFAIL=0** (실기 전 결과 아님).
- **검증 상태:** Phase 4 source/manifest는 GitHub 커밋 뒤 path/mode/blob 1:1 재확인. **실제 DGX Phase 4 및 GPU/CI/A·B 성능시험은 아직 NOT_RUN/NOT_VERIFIED**; 성공·속도 향상 주장 불가. 원본 이미지·모델/컨테이너/HF cache/ports은 변경하지 않는다.
- **PR/merge:** 현 단계 불필요. 필요하다면 `base=feature/blazux-phase3-ple-duplicate-shard-guard`, `head=feature/blazux-phase4-ple-cpu-bundle`의 **비병합 리뷰 전용 Draft PR**만 제안; 그 PR도 merge하지 않는다. `main`으로 향하는 어떠한 변경/PR/merge/cherry-pick/squash/rebase/sync도 **영구 금지**. P0/P1/P2/P3 고정.

---
## 2026-10-27 Track A Phase 3 DGX 시험 완료 — 과거 최신 인수인계

- **검증 완료:** 사용자 제공 DGX Phase 3 오프라인 wrapper 로그: 정확한 소스 HEAD `cb1de387b09786d6be35fec838c6549a78e5417c`, `PASS_SOURCE_ONLY` **132/132**, Python **189 tests OK, XFAIL=0**, 최종 `PASS: PHASE3_G2_01_OFFLINE_CONTRACTS_XFAIL_0`. 기존 phase3 runner의 branch/origin/clean/source/deployment manifest/Mock/Bash audit 검증 체인을 통과했으나 사용자 마지막 출력에는 별도 세부 test 수치 전부가 포함되지는 않음.
- **실제 PyTorch PLE CPU 후속 출력:** `workers=1 chunk=1024` 및 `workers=4 chunk=2`에서 **BF16 mmap gather/forward byte-exact PASS**, `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK`, `PHASE2_PLE_CPU_ALL_OK`. **G2-01은 작은 합성 CPU 회귀시험 범위에서 CLOSED**, 배포/실 모델/GPU inference·CUDA graph/QSA TopK 성능 확인과는 구분.
- **정본:** [Phase 3 DGX 실측 보고서](BLAZUX-PHASE3-DGX-VALIDATION-RESULTS-20261027.md), [Phase 3 Gate 3 수정 및 실행 문서](BLAZUX-PHASE3-G2-01-DUPLICATE-SHARD-GUARD-20261027.md). 사용자 실측 소스 SHA `cb1de387...`를 보존하며, 보고서/handoff/source manifest만 갱신된 docs-only 커밋은 DGX에서 재시험된 것으로 주장하지 않는다.
- **열린 범위:** 손상 index/JSON duplicate key/모델 전체 신뢰성, 95GiB 실제 PLE, MTP 실제 로더, vLLM 0.32 이식, 성능 A/B, GPU/CI는 미검증. 기존 서비스를 stop/restart/update하지 않는다.
- **GitHub 불변 정책:** 보호 `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf...`, Phase 1 `a50fc537...`, Phase 2 `76588845...` 영구 보호. Phase 3 확정 문서 SHA 이후에만 후속 Phase 자식 브랜치. PR이 필요하면 Phase 3→Phase 2로 리뷰 전용 Draft PR만, **merge하지 않음**. **어떠한 실험도 `main`으로 PR/merge/rebase/cherry-pick/squash/sync 금지**.

---
## 2026-10-27 Track A Phase 3 — 중복 PLE shard 인덱스 Fail-Closed 구현 (과거 스냅샷)

- **출처/계보:** 개인 Fork Phase 2 최종 docs HEAD `76588845d7742703475ae1f49d5e8f5c174bb77a`에서 **Phase 3 전용 브랜치 `feature/blazux-phase3-ple-duplicate-shard-guard`** 생성. Phase 1/P0/main 불변. Phase 2 실기 검증 정본은 `fd9d8cf...`(코드)와 `765888...`(증거 docs) 구분.
- **G2-01 수정:** `src/vllm_ple_mmap.py::_find_shards`에서 한 레이어의 중복 PLE shard index가 여러 scanned safetensors header에서 발견되면 `ValueError`로 중단. 정상 경로는 변경 없이 유지. Phase 2의 XFAIL decorator 제거, no-index 기존 회귀 및 indexed second-file 신규 음성 시험, 실제 PyTorch CPU module의 duplicate 입력 시험을 추가. [Phase 3 Gate 3 문서](BLAZUX-PHASE3-G2-01-DUPLICATE-SHARD-GUARD-20261027.md) 참조.
- **검증 경계:** 브랜치 커밋 GitHub tree/Manifest 대조는 실제 수정 후 확인. **사용자 DGX의 Phase 3 unittest/CPU/GPU/CI는 아직 NOT_RUN/NOT_VERIFIED**. 목표 unittest 189개 / XFAIL=0, `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK` 및 기존 PLE CPU byte-exact PASS를 제출받아야 Gate 종료. Source Header JSON 중복 키 같은 다른 리스크까지 해결한 것이 아님.
- **브랜치/PR 규칙:** 이전 Phase는 영구 불변. 필요할 때만 `base=feature/blazux-phase2-offline-fixtures`, `head=feature/blazux-phase3-ple-duplicate-shard-guard`의 **리뷰 전용 비병합 Draft PR** 검토. PR을 만들든 말든 Merge 금지. `main` 대상 PR/merge/rebase/cherry-pick/squash/sync는 어떤 경우도 허용하지 않음. GPU/서비스·HF cache/receipt/port는 조작하지 않는다.

---
## 2026-10-27 Track A Phase 2 DGX 검증 완료 — 과거 최신 스냅샷

- **실측 HEAD:** `feature/blazux-phase2-offline-fixtures@fd9d8cfb6938b82ae979c9804386ffbe084cc81d`. 사용자 DGX offline wrapper 로그: Source Manifest **129/129(2회)**, deployment manifest 4 targets, Wizard mock **38/38**, full unittest **188개 실행 / expected failure 1개**, Bash syntax·publication audit PASS.
- **신규 PyTorch PLE fixture:** 사용자 후속 stdout에서 기존 production PLE BF16 mmap gather와 torch forward 바이트 일치 `workers=1 chunk=1024` 및 `workers=4 chunk=2` **PASS**, 종료 `PHASE2_PLE_CPU_ALL_OK`. GPU·vLLM 런타임 추론·성능/품질 A/B, blazux 패치 도입은 시험하지 않았고 CI는 계속 `NOT_VERIFIED`.
- **미해결 G2-01:** `_find_shards`는 중복 PLE shard index를 덮어쓸 수 있어 fail-closed 보장되지 않는다. unittest의 `@expectedFailure`는 **1건 XFAIL(OPEN)**이며 결함 해결 PASS로 해석 금지. Phase 2 완료는 *계획된 오프라인 테스트 실행 완료*를 의미할 뿐 전체 안전성/운영 승인 아님.
- **정본 결과:** [Phase 2 DGX 검증 보고서](BLAZUX-PHASE2-DGX-VALIDATION-RESULTS-20261027.md), [Gate 2 문서](BLAZUX-PHASE2-GATE2-OFFLINE-20261027.md), 사용자가 시험한 원본 SHA `fd9d8cfb...`. 이 영구 기록만 추가하는 docs-only commit의 새 HEAD는 **실측한 Git SHA가 아니다**.
- **다음 우선순위/브랜치:** 현재 Phase 2의 알려진 XFAIL 위험을 후속 독립 실험 Phase에서 fail-closed로 수정하고 regression으로 검증할지 Gate 리뷰에서 판단한다. 새 Phase는 Phase 2 확정 docs HEAD에서만 자식 분기하며, 부모·P0·`main`은 불변. `main`으로 향하는 PR/merge/cherry-pick/squash/rebase/sync **절대 금지**. Phase 간 PR은 필요할 때 review-only/draft, **merge도 금지**.

---
## 2026-10-27 Track A Phase 2 — 합성 BF16/CPU Gate 2 구현 진행 (과거 스냅샷)

- **정확한 계보:** P0 `feature/blazux-vllm032-evaluation-20261027@966ec7cf0741734b844b1cea938d56678a756469` → Phase 1 최종 `feature/blazux-phase1-source-compare@a50fc53721f3d23325dca44eb799f0f388d65951` → **Phase 2 `feature/blazux-phase2-offline-fixtures`**, 그 SHA로 신규 생성. Phase 1의 실제 DGX 테스트 대상은 `8555a0a5...`; Phase 1 docs-only 확정 HEAD는 `a50fc537...`.
- **Phase 2 코드:** 표준 라이브러리 기반 합성 BF16 safetensors 13×7/4 shards, 원본 PLE parser/layout AST 함수의 오프라인 회귀, 실제 PyTorch/NumPy PLE mmap gather+forward byte-by-byte CPU fixture, MTP 31/31 guard, QSA *독립* CPU TopK oracle, 독립 브랜치/원격/Manifest fail-closed 검증 wrapper. [Gate 2 계획·실행·위험 보고서](BLAZUX-PHASE2-GATE2-OFFLINE-20261027.md). 기존 모델/serving 코드/설치/운영 컨테이너는 변경하지 않는다.
- **검증 경계:** GitHub에서 코드 및 Source Manifest blob/path/mode가 일치해도 **DGX Phase 2 Python 테스트 실행은 아직 NOT_RUN**. 실제 테스트 결과를 받기 전 PASS 숫자나 완성 판정 금지. Stdlib suite에는 중복 PLE shard 인덱스 기존 덮어쓰기 결함을 드러낸 `@unittest.expectedFailure`가 **1개 예상**되며 이를 보호 기능 PASS로 주장하지 않는다. GPU, API/ABI, vLLM parser, MTP real tensor shape, 실제 95GiB PLE 성능, CI는 NOT_RUN.
- **PR/merge 알림 규칙:** Phase 2 DGX 결과 수집·문서 검토 후 필요하면 `base=feature/blazux-phase1-source-compare`, `head=feature/blazux-phase2-offline-fixtures` **리뷰 전용 draft PR만** 제안. Phase 1 immutable branch를 보호하기 위해 해당 PR도 **merge하지 않는다**. 후속 Phase 3는 검증된 Phase 2 최종 HEAD에서 새로운 자식 branch. `main` 대상 PR/merge/cherry-pick/squash/rebase/sync는 상황 무관 **영구 금지**.
- **현재 GitHub 인증 상태:** Phase 2 실험 브랜치 커밋 후 최신 SHA와 Manifest 및 `main`, P0, Phase 1 불변 여부를 다시 검증할 것. GitHub Actions CI 체크 기록 0이며 `CI_NOT_VERIFIED`.

---
## 2026-10-27 Phase 1 DGX 오프라인 검증 PASS — 과거 최신 스냅샷

- **실제 DGX 검증 출처:** 사용자 제공 terminal transcript, `feature/blazux-phase1-source-compare` **정확한 실측 HEAD `8555a0a5a73d6bf390eeeb3495a01257c0ca3327`**. [Phase 1 DGX 검증 보고서](BLAZUX-PHASE1-DGX-VALIDATION-RESULTS-20261027.md)를 최우선으로 확인한다.
- **실기 결과:** `PASS_SOURCE_ONLY` 122/122 (시작·종료 2회), deployment manifest 4 target OK, Wizard fake/mock **38/38**, 전체 repo **172/172**, bash syntax 및 publication audit PASS. 기존 이미지의 격리 CPU 컨테이너에서 기존 PLE FP8/BF16 synthetic fixture **ALL OK**; Python test `torch=2.13.0+cu130`, `numpy=2.2.6`. 기존 main `66051cd`에서의 과거 172/172이 아니라 **새 Phase 1 실측**이다.
- **판정:** Phase 1 Gate 1 정적 소스 비교 + 사용자 DGX 오프라인 회귀 시험 완료. GPU/실 모델 추론, blazux 최적화 코드 포팅, 성능 A/B, vLLM 0.32 ABI/Parser, GitHub CI **NOT_RUN/NOT_VERIFIED**. 기존 컨테이너를 stop/restart/replace하지 않았다. 결과만으로 실시간 운영 헬스/모델 품질 주장 금지.
- **SHA 구분:** 사용자가 검증한 `8555a0a5...`는 변경 전 *테스트 대상*이다. 이 보고서·인수인계·Source Manifest만 추가한 GitHub docs-only commit은 새 HEAD이고, 사용자의 DGX에서 재시험한 SHA가 아니다. 최종 SHA는 본 커밋의 GitHub branch HEAD에서 확인. Manifest 재계산·정확한 트리 Blob/모드는 commit 이후 GitHub에서 확인한다.
- **다음 분기:** Phase 1 확정 문서 커밋 HEAD에서 Phase 2 `feature/blazux-phase2-offline-fixtures` 분기. Phase 1 추가 코드 변경 금지, `main` 및 P0 불변, Track B 승인 전 미생성.

---

## 2026-10-27 Phase 1 DGX 검증 준비 보강 — 작성 당시 스냅샷

- Phase 1 Gate 1은 static-only 소스 계약 보고서 작성 완료. 이번 보강으로 [실기 DGX 격리 clone/pull 및 소스+오프라인 시험 방법](BLAZUX-PHASE1-DGX-READONLY-VERIFY-20261027.md)을 추가했다. **Phase 1 blazux serving 패치 구현/성능 실측은 수행하지 않음**.
- `scripts/verify-source-state.sh --strict`와 `scripts/verify-main-readonly.sh`는 각각 기존 release-branch allowlist 및 main 전용이라 **Phase 1 브랜치에서 실행 금지**. Phase 1 소스 검증은 별도 checkout에서 `scripts/verify-source-state.sh` (non-strict) + 명시적 branch/HEAD/remote 보호 확인을 사용. Manifest의 strict 허용 목록을 확대하지 않는다.
- 사용자 DGX 운영 checkout·Docker·포트·HF cache·receipts를 보호한다. 새로운 Phase 1 읽기 전용 source 검증 명령은 사용자가 실제 실행하기 전까지 **NOT_RUN**이며 이전 Wizard 172/172 기록을 승계하지 않는다.
- 다음 Phase 진입: Phase 1 실기 오프라인 시험 결과 검토 → Phase 1 확정 HEAD에서 신규 Phase 2 자식 브랜치 생성 → BF16 synthetic safetensors 등 Phase 2 fixture 작성. **blazux→main 영구 금지**.

---
## 2026-10-27 Phase 1 추가 스냅샷 (아래 P0 기록보다 최신)

- Track A Phase 1 브랜치: `feature/blazux-phase1-source-compare`; 분기 부모 `966ec7cf0741734b844b1cea938d56678a756469` (P0 루트). GitHub 소스 기준 외부 SHA `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`.
- Gate 1 정적 분석은 [Phase 1 함수/데이터 비교표](BLAZUX-PHASE1-GATE1-SOURCE-COMPARE-20261027.md)에 영구 보존한다. PLE BF16 offset/width/128 shard 및 MTP 31/31은 KEEP; PLE 계측·small batch 최적화는 선택적 PORT/ADAPT 후보; vLLM 0.32 constructor/graph/parser 직접 복사는 DEFER_TO_TRACK_B; NVFP4 MTP graft는 현 운영 계보에 REJECT.
- 이번 Phase 1에서는 새로운 Python 단위시험, GPU, Docker 및 CI를 실행하지 않았다. 수행한 것은 GitHub tree/Manifest 대조와 정적 코드/이름 목록 검증이다. **Phase 1 HEAD는 아래 결과 문서·Manifest의 커밋을 다시 읽어 확정한다.**
- 다음 단계는 Phase 1 HEAD 확정 후 신규 Phase 2 자식 브랜치에서 **작은 BF16 synthetic safetensors** 및 순수 CPU fixture 작성/실행이다. 위 Wizard/P0 구간의 과거 브랜치 미생성 서술은 당시 스냅샷이며 이 최신 기록을 우선한다.
- blazux 관련 커밋은 어떤 상황에서도 main에 PR/merge/cherry-pick/rebase/squash/sync 하지 않는다. DGX/운영 서비스는 변경하지 않는다.

---
## 현재 진행 상태 및 새 세션 우선 읽기 — 2026-10-27

> **현재 작업을 이어받을 때 이 절을 가장 먼저 적용한다.** 2026-10-26 Wizard 검증은 과거 시험이다. **2026-10-27 새 불변 정책:** blazux 관련 모든 브랜치/Phase의 변경을 `main`에 PR·머지·스쿼시·체리픽·리베이스·동기화하지 않는다. 각 Phase는 직전 확정 Phase의 HEAD에서 새 자식 브랜치를 만들어, 실험을 전부 폐기해도 `main`이 달라지지 않게 한다.

| 항목 | 최신 확인된 기준 | 다음 세션의 해석 |
| --- | --- | --- |
| 개인 GitHub `main` | **2847e39b4131eb8aff78bf86ffce98892401722a** | 2026-10-27 조회한 PR #5 병합 커밋. 새 세션에서 HEAD 재조회 |
| 현재 개발 브랜치 | **`feature/blazux-vllm032-evaluation-20261027`** | P0 실험 루트. 정책 반영 전 HEAD **`d877fc7197f3888bb80be2edc7fb20698e0d8316`**; 본 갱신 후 정확한 HEAD를 재조회하여 Phase 1 부모로 고정. 후속 새 Phase 브랜치 미생성 |
| 기록된 설계 보강 커밋 | **0e9b25d93eb533b1936930c77bf7f7b874ec0b60** | 2026-10-27 설계서 보강 기준. **본 핸드오프 갱신 커밋 자체의 SHA 아님** |
| 신규 PR | **없음** (2026-10-27 조회) | blazux→`main` PR **금지**; 필요하면 Phase 간 GitHub Compare/미병합 리뷰만 진행 |
| 실험 원본 blazux | **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa** | [외부 기술 참조](https://github.com/blazux/qwen3.8-Flash-DGX); 원본 저장소 전체 merge·serve.sh 실행 금지 |
| 성능 Baseline | PR **#5 MERGED**, 정식 **12조건 × 각 3회 = 36회** | [보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md) 및 원본 JSON·해시가 `main`에 보존됨 |
| Benchmark helper | `scripts/benchmark/run-llama-benchy.sh` | PR #5에 포함됐으나 **신규 wrapper 자체의 DGX 실행은 NOT_RUN** |
| Wizard DGX 검증 | `main=66051cdcd4b2c5766de55421579867c195fe4084` | 2026-10-26 source **114/114**, mock **38/38**, unit **172/172**, legacy Health PASS; **이후 소스 SHA로 승격 금지** |
| Source Manifest | 현 기능 브랜치의 `files[]` **120개 + Manifest 자체 1개** | 새 변경시 Git 트리 path/mode/blob SHA와 모두 일치시켜 **같은 커밋**에 저장 |
| GitHub CI / branch protection | Actions run **0** → `CI_NOT_VERIFIED`; `main.protected=false` | CI 정상화는 사용자 요청으로 보류. `main`의 PR 리뷰 보호는 **운영 정책**, 강제된 GitHub 보호 설정이 아님 |
| 엔진·GPU 실기기 | blazux 구현/이미지 빌드/A/B 시험 **NOT_STARTED** | 기존 레거시 컨테이너·모델·포트·영수증은 변경 금지 |

**두 개발 트랙은 섞지 않는다.** Track A는 P0 루트 아래에서 Phase별 자식 브랜치를 계단식으로 생성한다. Track B `feature/vllm032-bf16ple-port`는 별도 Go/No-Go 뒤 **P0 고정 HEAD에서 형제 브랜치로 분기**하며, `main`에서 새로 분기하거나 Track A의 검증되지 않은 코드를 자동 상속하지 않는다. 현재 Track B와 Track A Phase 1 브랜치는 미생성이다.

**최우선 다음 단계:** P0 브랜치 최신 HEAD와 Source Manifest 확인 → P0에서 **새 `feature/blazux-phase1-source-compare` 자식 브랜치 생성** → pinned blazux SHA와 현 preview의 PLE mmap/BF16 gather, MTP 31텐서/가드, QSA, SSM Prefix cache, Parser/Responses를 **Gate 1 함수·텐서 단위 1:1 비교**. 근거별 KEEP/PORT/ADAPT/DEFER_TO_TRACK_B/REJECT를 기록하고 실기기 Docker/GPU 작업은 하지 않는다.

---

## 2026-10-26 Wizard 검증 기준: DGX `main` 읽기 전용 실측 (PR #3 이후; 과거 이력)

> **Wizard 운영·시험에 한정된 당시 최신 기준.** 아래 오래된 PR #1/기능 브랜치 시험 및 보류 목록은
> 작성 당시의 **과거 이력**이다. 현재 진행 상태는 맨 위의 **2026-10-27 작업 요약**이 우선하며, 항목이 충돌하면 현재 GitHub 소스/새 DGX 로그를 대조한다.
> **이 문서를 포함한 다음 docs-only 머지 커밋은 DGX에서 다시 실행한 것이 아니다.**

- 최종 검증 대상: GitHub [PR #3](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/3)
  **MERGED**, `main=66051cdcd4b2c5766de55421579867c195fe4084`.
- 사용자가 **실 DGX**의 `main`에서 `scripts/verify-main-readonly.sh` 실행 완료:
  `SOURCE_HEAD`가 위 SHA 및 로컬 `origin/main`과 일치, 마지막
  `PASS: local source/tests/observations; real new deployment NOT_TESTED` 출력.
- Source `--strict` **PASS_SOURCE_ONLY 114 tracked files**,
  deployment manifest PASS **4 targets**, wizard fake/mock **38/38 PASS**,
  전체 unit **172/172 PASS**. 쉘 구문과 publication audit도 읽기 전용
  일괄 스크립트가 오류 없이 통과했으나 별도 검사 로그는 분리되어 있지 않음.
- 기존 YSLAB 레거시: 컨테이너 **running**, 설치 식별 **PASS**, API Health·모델 목록
  **PASS/PASS**, Health **PASS**, **OBSERVE_ONLY**. Snapshot `GIT_CHANGED`
  (설치 정체성 0 / 서비스 변경 0 / Git HEAD 1): stored
  `3522190192da605c17709bede32a0df98d0ed406` →
  `66051cdcd4b2c5766de55421579867c195fe4084`.
  캐시·recipe-view 저장 여유 각 **539.74 GiB**, MemAvailable 약 **14.24~14.30 GiB**.
- PR #3: 기능 브랜치 `feature/ci-wizard-isolation-main-readonly-20261026`에서
  **2 commits**, 19 files changed, 일반 merge SHA 위의 `66051cdc...`.
  신규 Wizard 전용 `qwen38-wizard-<target>` 이름, 전용 ownership label,
  엄격한 영수증/ID 검증, 레거시 running 시 단일 GB10 동시 GPU 기동 차단.
  해당 소스의 모의 회귀시험은 위 최신 DGX 172/172에 포함된다.
- **P0-3 완료:** DGX 로컬 `main` 전환 및 병합 소스 검증 확인.
  **P0-2 코드/모의 검증 완료, 실 신규 배포/제거 미시험.**
  **P0-1 GitHub Actions 정상화는 사용자의 명시적인 결정으로 연기.**
  GitHub Actions **run=0 / check run=0** (최신 조회 시점),
  `CI_NOT_VERIFIED`; 원인 조사, 워크플로 수정, 설정 변경 및 재실행을
  이번 문서 동기화 PR에서 진행하지 않는다.
- 그 외 미완료: 신규 Wizard 이미지 빌드/가중치 준비/활성화/소유 자산 제거,
  실패 rollback, 중복 다운로드 회피, 레거시→Wizard 소유권 이전, 단일 GB10
  신규 GPU 및 240K/MTP 성능·안정성 실기기 검증. **현재 서비스 정지/교체 금지.**
- **향후 우선순위:** 운영 자산 보호 → 원격 최신 HEAD/로컬 clean·Health 관찰 →
  안전한 offline mock·rollback 설계 → 중복 다운로드 방지 설계 →
  실기기 신규 배포는 별도 명시 승인. CI는 사용자가 재개를 요청할 때 다룬다.

자세한 명령·로그별 구분: [2026-10-26 검증 증거](../scripts/VALIDATION-RESULTS-20261026.md).

---

## 0. 새 세션에서 사용할 최상위 지시

당신은 **단일 NVIDIA DGX Spark(GB10)**에서 실행하는 Qwen3.8-Flash-Next NVFP4/BF16 PLE + BF16 MTP 레시피의 **개인 Fork 운영·위자드 유지보수 및 blazux 선택적 최적화 검토 프로젝트**를 이어받은 엔지니어링 보조자다. **한국어**로 기술 분석, 코드, 설명, 보고를 작성한다. 현재 실행 과제는 **Track A의 Gate 1 함수별 소스 계약 비교**이며, 신규 위자드 실배포 또는 vLLM 0.32 포팅이 아니다.

**제1원칙은 현재 운영 중인 기존 YSLAB 서비스, Docker 이미지/컨테이너, HF 캐시, recipe views, 모델 가중치, 로컬 상태 파일, 포트 8000, 다른 Ollama/OpenWebUI 및 네트워크 서비스를 변경하지 않는 것이다.** GitHub 소스 변경과 운영 서버에 대한 변경은 서로 다르다.

연결된 **GitHub 플러그인/앱 도구**를 활용하면 저장소 파일 조회, 코드/문서 수정, 신규 스크립트 생성, blob/tree/commit 생성, 브랜치/PR 생성, diff 리뷰, PR 머지와 결과 재검증을 **직접 수행할 수 있다**. 사용자에게 불필요하게 수동 UI 작업을 시키지 말라. 단, 실제 연결 가능 여부를 매 세션 확인하고, 실행하지 않은 작업을 완료했다고 주장하지 말라. GitHub 작업 권한이 있다고 해서 실제 DGX Docker 서비스 변경 권한이 생기는 것은 아니다.

**실제 코드와 최신 GitHub `main`을 진실의 기준으로 삼는다.** 과거 계획서의 '미구현', 오래된 README의 'NOT TESTED' 표기는 나중에 수집된 DGX 로그·Git HEAD와 대조한다. 모순은 시점/출처를 밝혀 해결하고 문서에 반영한다. 이전 채팅이 끊겨도 이 문서의 우선순위/검증 방법을 따르도록 한다.

### 다음 세션 시작용 사용자 메시지 예시

> 개인 GitHub 저장소 `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`의 `main`과 `feature/blazux-vllm032-evaluation-20261027` 최신 HEAD를 **둘 다 먼저 확인**하고, 기능 브랜치의 `docs/SESSION-HANDOFF-PROMPT.md`와 `docs/BLAZUX-VLLM032-ADOPTION-PLAN.md`를 읽으세요. PR #5 Baseline 원본은 `main`에 병합됐고, 현재는 **Track A Gate 1 blazux↔현 preview 함수/텐서 계약 1:1 비교** 단계입니다. P1→P2→P3 우선순위, 별도 Track B `feature/vllm032-bf16ple-port` 미생성 상태, DGX 레거시/위자드 보호 규칙을 준수하세요. 필요한 변경만 문서·테스트·Source Manifest와 함께 기능 브랜치에 커밋하고, PR/머지는 사용자 요청과 리뷰 범위 안에서 직접 수행하세요. 테스트 미실행/CI 부재는 명시하고 Docker·모델 파일은 변경하지 마세요.

---

## 1. 프로젝트 및 확정된 Git 이력

| 대상 | 확인한 사실 |
| --- | --- |
| 개인 Fork | `https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| YSLAB 원본 upstream | `https://github.com/YSLAB-ai/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| 원본 PIN | `9492b78c6bc04638587b42f2ffeb0680b0fcb3ef` |
| 기능 브랜치 | `feature/install-uninstall-wizard-20261026` |
| 마지막 기능 브랜치 SHA | `25949fd7fb16ff62f8c6bdfc6f9fe9ab74fd0f8a` |
| [PR #1](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/1) | **MERGED / CLOSED**, 일반 merge commit(8개 기능 커밋 유지) |
| PR #1 merge SHA | `bdc84eae28b7ce49ea2dde3c3923cfdf60382cf6` |
| 인수인계 문서 작업 시작 직전 `main` | `bdc84eae28b7ce49ea2dde3c3923cfdf60382cf6` |
| PR #1 병합 후 Git tree | `78ced78bb0c4381d3dd52c84b8d0f7f1082b3e9d` |
| 당시 Source Manifest | 111개 추적 파일 + Manifest 자체 blob SHA 일치 |
| GitHub Actions | 마지막 조회에서 workflow run/check run **0건**(CI PASS라고 주장 금지) |
| 이 문서 반영 이후 | **새 commit/PR가 생길 수 있으므로 반드시 원격 HEAD를 다시 확인** |

**이 단락은 PR #1 직후의 과거 기록이다.** 당시 개인 Fork `main`과 기능 브랜치의 Git tree 동일성을 GitHub 도구로 확인했다. 당시 사용자 DGX 로그는 기능 HEAD `25949fd7...`였지만 **이후 2026-10-26 사용자 DGX 로그에서 `main=66051cdc...` 전환·114/114, 38/38, 172/172 PASS가 확인되었다.** 현 원격 `main=2847e39...` 또는 blazux 기능 브랜치의 새 문서 커밋에 대해 DGX에서 재시험한 증거는 없다. GitHub PR 머지는 DGX 컨테이너를 재실행하거나 가중치를 변경하지 않는다.

---

## 2. 운영 중인 DGX — 바뀌면 안 되는 자산

사용자는 단일 NVIDIA DGX Spark를 운영하고 있다. 원래 YSLAB 설치로 모델을 실행했지만 설치 당시 repo 경로의 현재 Git origin이 **개인 Fork로 변경**되었다. **디렉터리 이름이 'yslab'이라고 해서 Git origin이 YSLAB이라고 판단하지 않는다.**

| 구분 | 사용자 DGX 로그에서 확인한 상태 |
| --- | --- |
| 호스트 checkout | `$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark` |
| 원격 origin | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git` |
| 레거시 Docker 이미지 | `yslab-qwen38-bf16ple:9492b78c` |
| 레거시 컨테이너 | `qwen38-flash-orca-uncensored-bf16-mtp` — `running` |
| API 바인딩 | `0.0.0.0:8000`; 방화벽/외부 접근 정책 보존 |
| 모델 alias | `qwen3.8-flash-next-orca-uncensored-bf16-mtp` |
| 모델 context 보고값 | `262144` — API 메타데이터, 최신 회차 장문 추론 시험은 아님 |
| 캐시 mount | `$REPO_DIR/hf-cache` → `/recipe/hf-cache` |
| Recipe View mount | `$REPO_DIR/recipe-views` → `/recipe/recipe-views` |
| 레거시 receipt | `~/.local/state/yslab-qwen38-bf16ple/{paths,image-id,container-id}` |
| 새 wizard receipt | `~/.local/state/qwen38-flash-dgx/deployment-state.json` (XDG_STATE_HOME 등 오버라이드 가능) |
| Legacy adoption | `scripts/adopt-legacy.sh` 성공; `recorded_legacy`는 등록된 과거 관찰 객체 |
| 관리 권한 | `read_only=true`, `management_authority=OBSERVE_ONLY` |

로컬 영수증에서 container/image **실제 전체 ID**를 대조했으며 일치했다. 그러나 이 값들은 **Git/공개 문서에 전체를 복사하지 않는다**. 유효성 확인에 필요하면 현 호스트에서 직접 읽어 비교한다.

**실 DGX의 마지막 읽기 전용 출력:** legacy identity **6/6 PASS**, API `/health`·`/v1/models` PASS, 컨테이너 running, Health PASS, 저장 당시와 현재의 차이 `GIT_CHANGED`(Git HEAD 1건), identity 변경 0/health 변경 0; 당시 disk 여유 약 539.75 GiB, MemAvailable 약 14.35 GiB. 이는 **2026-10-26 시점 관찰**이지 항상 유효한 실시간 상태가 아니다.

### 레거시 검사 의미

- `legacy.identity_verified=true` 또는 `legacy.verified=true`는 저장된 paths, container/image ID, labels, published port, 모델 cache/view mounts 등 **6개 설치 식별 근거 일치**. 삭제·정지 소유권 아님.
- `checkout_warnings`의 origin/HEAD 불일치는 설치 이력 변화이며 Docker 배포 손상의 증거가 아니다.
- `api.health/models=PASS`는 HTTP 조회 성공. full 생성 추론, throughput, 240K-long-context 평가와 다르다.
- `adopt-legacy`는 wizard의 별도 상태 파일에 읽기 전용 스냅샷만 저장. 레거시 원래 receipt에는 쓰지 않는다.
- `recorded_legacy`는 등록 당시 기록이므로 `status`/`doctor`/`compare-state` 수행 시 덮어쓰지 않는다.

**경고:** API가 `0.0.0.0:8000`에 열려 있어 방화벽에 따라 다른 호스트에서 접근할 수 있다. 네트워크/방화벽을 임의 변경하지 말고 보안 감사에서 별도 다룬다.

---

## 3. 구현·파일 구조·Manifest 계약

### 3.1 정책과 실행 구조

| 경로 | 역할 |
| --- | --- |
| `compatibility.json` | 대상 checkpoint·pinned revision·BF16 PLE/MTP tensor 계약 및 모델 무결성 기준 |
| `scripts/deployment-manifest.json` | 위자드 선언형 정책: 서비스 프로파일, legacy fingerprint, 소유권/보존 규칙 |
| `scripts/source-state-manifest.json` | Git 추적 파일의 path/mode/blob SHA-1 스냅샷; 자기 자신은 제외 |
| `scripts/verify-source-state.py` / `.sh` | Git HEAD, working-tree blob/mode, 개인 origin, 승인 브랜치 검증. `PASS_SOURCE_ONLY`는 모델 검증이 아님 |
| `scripts/wizard/model.py` | Manifest/target 정책 검증 |
| `scripts/wizard/probe.py` | Docker/Git/legacy/API 읽기 전용 관찰 및 엄격한 ID/label 검사 |
| `scripts/wizard/state.py` | 신규 자산 영수증, 권한 0600, atomic save 및 경로 안전 검사 |
| `scripts/wizard/engine.py` | build/prepare/activate/status/adoption 및 소유권 receipt를 확인하는 stop/remove |
| `scripts/wizard/cli.py` | 한글 지향 명령/대화형 메뉴/CLI 옵션 |
| `scripts/wizard/monitor.py` | saved-vs-current diff, 간결 상태, HTTP/API/디스크/메모리 Health |
| `scripts/qwen38-dgx-spark` 및 `src/recipe/*` | 실제 모델 download, audit, serve의 기존 runtime 구현 |
| `tests/test_wizard_monitor.py` / `test_wizard_safety.py` | 모의 Docker/Git/HTTP 및 소유권 안전 시험 |
| `tests/test_source_state_release_branches.py` | main/feature strict 허용, 다른 브랜치 거부, merge SHA·blob 변조 회귀 시험 |
| `.github/workflows/test.yml` | CI workflow 정의. 구성 파일 존재만으로 CI 성공 아님 |

주요 진입점: `scripts/{install,uninstall,prepare,activate,stop,adopt-legacy,status,compare-state,health,doctor,manifest,run-mock-tests}.sh`. 실제 실행 전에 최신 Git 파일 및 `--help`로 옵션을 확인한다.

### 3.2 신규 위자드 기본 설정 (실기기 신규 설치 검증은 별도)

- 추천 `target=orca-uncensored-bf16-mtp`, `MTP=2`.
- context `262144`, sequences `8`, GPU memory fraction `0.8`.
- 이미지 tag `kjlee-qwen38-bf16ple-wizard:9492b78c` (레거시 tag와 다름).
- 권장 새 호스트 endpoint `127.0.0.1:18300`.
- **PR #3 이후 이름 분리 완료:** 레거시는 `qwen38-flash-<target>`, 신규 Wizard는 `qwen38-wizard-<target>` 및 전용 소유권 라벨. 다만 단일 GB10에서 기존 레거시가 실행 중이면 새 GPU 활성화는 거부하고, 실기기 신규 설치·제거 검증은 별도로 필요하다.
- `--replace`, 자동 legacy takeover, HF 캐시 공유/이동, 가중치 purge는 지원하지 않는다.

### 3.3 상태 및 Health 출력

- `scripts/status.sh`: 간결한 한글 상태; `--json`으로 전체 기록/현재상태.
- `scripts/compare-state.sh`: 과거 vs 현재의 `identity`/`health`/`git` 차이.
- `scripts/health.sh`: 현재 컨테이너, API/모델 목록, cache/view 여유 공간, MemAvailable 읽기 전용 확인.
- `scripts/doctor.sh`: Manifest 검증 + 상태/Health/변경 내역.
- Snapshot 결과: `UNCHANGED`, `CHANGED`, `HEALTH_CHANGED`, `GIT_CHANGED`, `UNREGISTERED`, `UNKNOWN`. 저장 공간 경고 기본 임계값 `100 GiB`. UNKNOWN을 변경/실패로 단정하거나 기록을 자동 수정하지 않는다.

### 3.4 Source Manifest를 수정할 때 반드시 지켜야 할 점

PR #1 구현 당시 `scripts/verify-source-state.py --strict`의 허용 브랜치는 정확히
`feature/install-uninstall-wizard-20261026`과 `main` 두 개다.
Manifest `allowed_branches`와 소스 검증기 `RELEASE_BRANCHES`가 정확히 일치해야 한다.

**새 추적 파일 추가·기존 파일 수정·삭제·모드 변경 시 전체 tracked Git tree의 path/mode/blob SHA를 `scripts/source-state-manifest.json`에 재계산해 반드시 같은 커밋에 반영한다.** 파일 개수·SHA를 임의 생성하지 않는다. Manifest 자체는 순환 참조를 피하기 위해 `files[]`에서 제외하고, HEAD에서 Manifest 자기 blob SHA를 별도로 대조한다.

Git merge commit은 SHA가 달라질 수 있지만 **모든 tracked blob/mode와 Manifest가 일치하면** 소스 PASS 조건이다. 반대로 merge로 파일을 수정하면 Manifest를 재생성해야 한다.

**새 임시 PR 브랜치는 현재 strict 허용 목록 밖이다.** `--strict` 실패를 정상으로 포장하지 말고, PR 브랜치에서는 Git tree와 Manifest SHA를 별도로 대조하고 해당 오프라인 단위 시험을 수행한 뒤 **머지된 main에서 strict**를 재검증한다. 미래에는 이 제한을 해결하는 CI/브랜치 검증 설계를 별도 검토할 수 있으나 안전 검사 전체를 무조건 우회/무력화하지 않는다.

---

## 4. 확정된 시험 결과 및 미완료 작업

### 4.1 사용자 제공 DGX 실제 로그

| 항목 | 검증 결과 |
| --- | --- |
| Feature HEAD `25949fd7fb16ff62f8c6bdfc6f9fe9ab74fd0f8a` | 사용자 최종 재검증 기준 |
| Source Manifest | `PASS_SOURCE_ONLY: 111 tracked file(s)` |
| Deployment Manifest | PASS, 4 targets |
| main/feature 호환 회귀 시험 | **7/7 PASS** |
| 위자드 fake/mock 시험 | **36/36 PASS** |
| 전체 저장소 unit tests | **163/163 PASS** |
| Bash 구문 / publication audit | 출력된 오류·진단 없음; 명시적인 exit-code 기록 없음 |
| 실 DGX 레거시 identity | **6/6 PASS**, 컨테이너 running |
| API health/models | **PASS/PASS** |
| Snapshot diff | `GIT_CHANGED` 단독 1건, identity/health 변경 0 |
| Read-only Health | **PASS** |
| PR #1 GitHub merge 결과 | `main`에 **merged=true**, tree 동일, Manifest 111 entries 일치 |
| GitHub CI | 실행 기록 없음; **CI 미검증** |

위 결과는 **사용자가 DGX 터미널에서 실행한 로그**와 연결된 GitHub 조회에 근거한다. 보조자가 DGX에 접속한 것은 아니다. 새 코드/문서 커밋 후의 시험 결과로 **과거 163/163 수치를 자동 승계하지 않는다**.

### 4.2 보류·미시험·차단 과제

1. **완료(2026-10-26): DGX 현지 `main` 및 post-merge strict 검증.** 사용자 최신 로그에서 `main=66051cdc...`, source 114/114, mock 38/38, 전체 unit 172/172, 기존 Health PASS. 향후 신규 커밋은 별도 검증 필요.
2. **신규 위자드 실제 Docker 이미지 build, 모델 prepare/audit, 새 컨테이너 activate, chat inference, 신규 자산 stop/remove/image remove 미시험.** Mock PASS ≠ 실기기 성공.
3. **이름/소유권 격리 코드 및 mock 검증 완료(PR #3).** 신규 `qwen38-wizard-<target>`·전용 라벨/영수증 검사, 레거시 running 상태의 GPU 기동 차단은 구현. 독립 컨테이너 실제 기동·중단·GPU 영향·rollback은 **미시험**; 레거시 강제 삭제 금지.
4. **Legacy→신규 관리 migration** 미구현. 기존 ownership 이전, 모델 cache 재사용/링크/복사 정책은 무단 적용 금지.
5. **중복 가중치 다운로드 방지** 전략 미확정. 새 checkout과 기존 cache의 분리/경로/해시/마운트 검증 후 결정.
6. **실패 복구 및 rollback** 미완성: 준비 실패·부분 파일·readiness timeout 이후 안전한 상태 보존/정리를 설계. 자동 cleanup보다 자산 보존 우선.
7. **GitHub Actions 체크 0건 원인 조사/CI 정상화는 사용자 결정으로 보류.** 워크플로 소스 보완은 PR #3에 반영됐으나 run/check 0건이며 `CI_NOT_VERIFIED`. 재개 지시 전 설정/워크플로 변경하지 않는다.
8. **오래된 계획서·안내의 '미구현/NOT TESTED' 표현**: 현재 구현 vs 당시 시험 계획으로 나누어 점진적 갱신. 과거 기록은 삭제하지 않는다.
9. **GPU/성능/240K context/MTP 안정성·동시성**: 새 위자드 실행 경로의 실제 장시간 검증은 별도.
10. 인수인계 문서 추가로 변경된 Git HEAD/Manifest를 다음 세션에서 재확인하고 최종 로컬 소스 시험을 반복.

현재 권장 순서: **GitHub 최신 HEAD/Manifest 및 DGX read-only 상태 확인 → 모의시험과 실패 복구·중복 다운로드 설계 → 승인된 신규 자산만 별도 실기기 검증**. CI 정상화는 사용자 재개 지시 전 보류.

---

## 5. 운영 자산 보호 — 절대 규칙

1. 기존 `qwen38-flash-orca-uncensored-bf16-mtp`에 대해 `docker stop/rm/rename`, 교체/restart, `docker image rm`, prune, daemon/firewall/포트 설정 변경을 자동 실행하지 않는다.
2. 기존 모델 `hf-cache`, `recipe-views`, NVMe checkpoint, HF 인증, 원본 설치 receipt를 덮어쓰거나 삭제하지 않는다. `rm -rf`, `git reset --hard`, `git clean -fd`, `--purge-*` 등을 상태 복구용으로 사용하지 않는다.
3. `~/.local/state/yslab-qwen38-bf16ple/*`는 **레거시 소유권 증거**이므로 읽기 전용. 신규 위자드는 `~/.local/state/qwen38-flash-dgx/deployment-state.json`의 **자기 상태만** 기록할 수 있다.
4. `legacy.adoption`은 `OBSERVE_ONLY`이다. 실제 삭제/정지 권한은 **새 위자드가 생성한 자산의 정확한 영수증 ID, image ID, label 및 Docker 실제 정보가 일치할 때만** 고려한다.
5. 현 컨테이너의 전체 ID, HF access token, 인증 파일, 계정 비밀, 내부 환경변수/비공개 인프라를 공개 Git에 저장하지 않는다. 유출 위험 문서는 publication audit를 통과해야 한다.
6. `--yes`는 사용자가 특정한 **신규 자산 생성/작업을 명시적으로 요청한 경우**에만 적절히 사용하고, `--replace`/`sudo`/유해한 cleanup을 자동 추정하지 않는다. 실제 운영 자산 변경은 별도 안전 설계/승인 필요.
7. 기존 서비스가 돌아가므로 데이터 보존이 우선이다. 실패 시 `STOP/FAIL/UNKNOWN`을 사실 그대로 보고하고 읽기 전용 조사로 전환.
8. `0.0.0.0:8000` 노출 API의 방화벽 접근 제한을 유지. 다른 Ollama, OpenWebUI, Docker, 네트워크 서비스 영향 없이 작업.
9. Docker 이름/포트만으로 안전을 판단하지 말고 단일 GB10 자원과 모델 중복 데이터·GPU 점유를 확인한다.
10. **GitHub 소스 PR 머지와 DGX 운영 배포/서비스 전환을 혼동하지 않는다.**

---

## 6. GitHub 플러그인으로 직접 작업하는 표준 절차

### 6.1 도구 활용/권한 원칙

연결된 GitHub 앱이 있는 세션에서는 파일/branch/PR/commit/merge를 **직접 수행**한다.
새 세션에서는 지원 도구와 권한을 확인하되, 필요한 기능을 사용할 수 있는데도 "사용자가 직접 GitHub UI에서 하라"는 말만 하지 않는다.

전형적인 GitHub 연결 함수 이름(지원 목록을 실제 도구에서 발견한 뒤 사용):
- `fetch` / `fetch_file` / `compare_commits` / `get_pr_info` / `fetch_pr` / PR diff/review 조회.
- `create_branch`, `create_blob`, `create_tree`, `create_commit`, `update_ref`.
- `create_pull_request`, `merge_pull_request`.
- workflow run/check/status 조회(지원되지 않으면 접근 불가 사유를 명시).

### 6.2 수정 → 커밋 → PR → 머지

1. 최신 `main` HEAD/tree, 변경 대상 파일과 보호 정책, PR 상태를 먼저 조회한다.
2. 변경 사항을 작은 단위로 설계하고 필요한 기존 소스·테스트·Manifest/문서까지 함께 검토한다.
3. 새 기능/반복 작업은 재사용 가능한 `scripts/`와 `tests/`로 만든다. 필요한 변경만 새 Git blob으로 생성한다.
4. 추적 파일 **전부**의 최신 path/mode/Git blob SHA를 계산해 `scripts/source-state-manifest.json`을 다시 작성한다. 자기 자신은 파일 목록에서 제외.
5. 정확한 base tree로 tree 생성 후 부모 commit SHA 지정 커밋. branch ref 갱신 시 **예상 HEAD lease**를 사용해 경합 방지. 강제 push 금지.
6. **일반 Wizard/비-blazux 작업에만:** 승인된 PR의 diff/CI/리뷰를 검토하고 안전하게 merge한 뒤 검증한다. **blazux 예외:** 본 작업에서는 `main` PR/병합 및 모든 형태의 실험 코드 반입이 금지되어 있으며, Phase별 새 브랜치 커밋과 비교·미병합 리뷰만 허용한다.
7. 체크가 없는 경우 CI PASS라고 부르지 말고, 사용자 DGX 로그(163/163 등)와 GitHub checks(없는 상태)를 분리해 기록한다.
8. 새 PR 임시 branch는 기존 strict allowlist에 포함되지 않으므로, **그 브랜치에서 무조건 strict PASS를 기대하지 않는다**. 전체 blob/mode/Manifest 파일 inventory 대조 및 모의 테스트로 사전 검증하고, 머지된 main에서 strict를 실행한다.
9. PR #1은 이미 머지된 과거 이력이다. 새 작업은 별도 PR로 기록한다. 상위 YSLAB-ai 저장소, 기존 legacy checkout state 또는 실제 Docker를 Github source 변경에 묶어 수정하지 않는다.
10. 승인된 범위 내에서 연결된 GitHub 도구로 결과를 영구 기록한다. **blazux는 Phase별 브랜치 커밋까지만 수행**하며 일반 PR merge 관례를 적용하지 않는다. 오류·경합·CI 불명 상태는 사실대로 표시한다.

### 6.3 스크립트 생성/업데이트/사용 규칙

- 단순 반복 명령보다 **상시 유지보수 가능한 Bash wrapper + Python 모듈**을 선호한다. 기존 코드를 축약해 기능을 빠뜨리지 말고 backward compatibility와 안전 불변조건을 검토한다.
- Bash: `set -Eeuo pipefail`, 모든 경로/인자 quoting, 안전한 exit code, dry-run/읽기 전용 분리. 실제 파괴적 명령은 precise ID+영수증 검증 없이 실행하지 않는다.
- Python: `snake_case`, type hints, what/why/how docstrings, 중요 로직에 **한국어 주석**. 변형할 때 예외 처리를 fail-closed로 유지하고 실제 Docker/네트워크는 모킹된 단위시험을 우선한다.
- 새/수정 함수마다 정상·실패·경계·idempotency·불일치 테스트를 추가한다. 테스트가 실제로 실행되지 않았으면 `NOT_RUN`을 표시한다.
- 새 운영 절차가 확정되면 단발 채팅으로 끝내지 말고 `docs/` 또는 `scripts/*.md`에 영구 기록하고, 이 인수인계 문서도 필요 시 업데이트한다.
- 모든 커밋에 Manifest 및 문서 링크/README/HF 카드 미러 일치 검증을 포함. 공개/비밀 파일 `python3 tools/audit_publication.py` 감사 필요.
- Bash script/CLI 실행 비트는 `100755`, 문서/JSON/일반 테스트는 `100644`. 소스 Manifest에 tracked file mode까지 반영한다.
- 임의 SHA/시험 횟수/서비스 상태/커밋 결과를 절대 창작하지 않는다. 사용자에게 있던 기존 로그가 새 커밋을 증명하지 않음을 기록한다.

### 6.4 커뮤니케이션/보고

- 처음에는 **완료된 사실 / 미완료 / 위험 / 다음 작업**을 명료하게 요약한다. 이미 제공된 답을 반복 질문하지 않는다.
- 코드와 데이터 근거는 현재 GitHub 파일, 과거 사용자 로그, 추론을 분리한다.
- 작업 중엔 필요시 짧게 진척·차단을 알려 주고, 완료 시 변경 파일, 해시/브랜치, 테스트 결과, PR 링크, merge SHA를 확인해 보고한다.
- 실패한 부분은 숨기지 말고, 완료되지 않은 것은 명확히 `NOT_TESTED` 또는 `UNVERIFIED`로 표현한다.

---

## 7. 다음 세션에서 바로 수행할 확인 작업

### 7.1 GitHub 읽기 전용

1. **`main`과 현재 blazux 기능 브랜치의 양쪽 HEAD/트리·PR #5 병합·후속 PR·CI 현황을 먼저 확인**하고 맨 위 2026-10-27 상태 요약과 대조한다. 아래 과거 Wizard 관련 파일도 역사적 보호 규칙을 확인하는 용도로 읽는다.
2. **이 문서, `README.md`, `scripts/deployment-manifest.json`, `scripts/source-state-manifest.json`, `scripts/verify-source-state.py`, `scripts/wizard/*`**의 최신 버전을 조회.
3. Source Manifest와 HEAD tree의 **전체** SHA/mode/경로 대조, README와 `huggingface/README.md` 미러 확인.
4. GitHub Actions run/check를 조회하고, run=0이라면 `CI_NOT_VERIFIED`라고 표기.
5. **현재 개발의 필수 참조:** [blazux 계획서](BLAZUX-VLLM032-ADOPTION-PLAN.md), [Baseline 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), [Benchmark 재실행 wrapper](../scripts/benchmark/run-llama-benchy.sh)(실행 시험 NOT_RUN), [첨부된 원본 Benchmark 결과](../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json). 
6. Wizard 운영 역사 확인: [Legacy 설치 보호](../scripts/LEGACY-INSTALLATION.md), [DGX 관찰](../scripts/LEGACY-OBSERVATION-20261026.md), [안전·복구](../scripts/SAFETY-AND-RECOVERY.md), [작업 순서](../scripts/OPERATIONS.md), [시험 계획](../scripts/TEST-PLAN.md), [테스트 증거](../scripts/VALIDATION-RESULTS-20261026.md), [Health 비교](../scripts/STATUS-COMPARE-AND-HEALTH.md), [Manifest 계약](../scripts/MANIFEST-SCHEMA.md), [Git Pull](../scripts/VERIFY-FROM-GIT-PULL.md), [역사적 개발 계획](../scripts/INSTALL-UNINSTALL-WIZARD-PLAN.md).

### 7.2 DGX 사용자가 실행할 수 있는 **읽기 전용 중심** 명령

> 아래 코드 블록에 포함된 `git fetch/switch/pull`은 **조회만 하는 명령이 아니라 checkout/remote-tracking refs를 변경할 수 있다**. 현재 진행 중인 기능 브랜치·로컬 변경을 먼저 확인하고, 명시적으로 로컬 동기화할 때만 사용한다. 단순 소스 검토에는 GitHub 읽기 전용 조회가 우선이며, 승인 없는 DGX 명령 실행은 금지한다.

과거에는 기능 브랜치였으나 **2026-10-26 사용자 제공 최신 로그에서 `main=66051cdc...` 확인**. 향후 재실행 시에도 원격 origin/로컬 수정을 다시 확인한다.

```bash
cd "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark"
pwd
git remote get-url origin
git status --short

# origin이 개인 Fork이고 로컬 변경이 없는 경우에만
git fetch origin main
git switch main
git pull --ff-only origin main

git rev-parse HEAD
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py
scripts/status.sh
scripts/compare-state.sh
scripts/health.sh
scripts/doctor.sh
```

위 수동 절차는 참고용이다. 사용자 DGX는 `66051cdc...`에서 새 wrapper를 실제 실행하여 PASS를 제공했다. **다음 문서 커밋/머지는 별개 Git HEAD**이므로 새 HEAD의 DGX 실행 결과라고 주장하지 않는다. 로컬 수정·remote 차이·에러 시 reset/clean 금지; Source PASS는 ignored cache/가중치/Docker를 검증하지 않는다.

---

## 8. 완료 판단과 향후 세션 종료 시 갱신해야 할 항목

작업 종료 전에 다음을 **GitHub 영구 문서**와 답변에 반영한다.

- 최종 브랜치, `main` HEAD, 수행한 GitHub commit/PR/merge SHA/URL.
- 이전 기준 대비 실제 변경 파일과 source Manifest 최신 tracked 파일 수.
- 수행한 테스트: **실행 환경(DGX/모의/CI), 명령, 총 건수, 실패 수, 미시험**, 독립적인 runtime health 증거.
- 실제 기존 이미지/컨테이너/cache/API/state를 변경하지 않았는지와 보호 검증.
- 해결되지 않은 blocker, 디자인 선택/위험, 사용자 승인이 필요한 실제 배포 작업.
- 이 문서 `docs/SESSION-HANDOFF-PROMPT.md`, 관련 `scripts/*.md`와 README의 최신 정합성.

**과거 작업 시작 전 기록(최신 상태 아님):**
PR #1 MERGED, `main=bdc84eae28b7ce49ea2dde3c3923cfdf60382cf6`, 사용자 DGX 기능 HEAD에서 전체 테스트 **163/163 PASS**, 모의 36/36, release-branch 7/7, legacy 6/6 및 API PASS, 운영 `OBSERVE_ONLY`. **실제 신규 배포·제거/rollback 미시험, DGX main 전환 로그 없음, GitHub Actions CI 실행 증거 없음.** 문서 신규 커밋/머지에 따른 `main`의 다음 HEAD는 새 세션에서 다시 조회한다.

---

## 9. 후속 P0: CI, 컨테이너 격리 및 DGX main 읽기 전용 검증

> 후속 기능 브랜치: `feature/ci-wizard-isolation-main-readonly-20261026`.
> 작업 시작 기준 `main=8ab88bc13aee6400e32b488af65f0a43c1c34b05`.
> 실제 새로운 merge SHA/CI 결과는 매 세션 **GitHub에서 새로 조회**해야 한다.
> GitHub 코드 변경·PR 병합은 DGX 배포가 아니며 기존 Docker 서비스에 접근하지 않았다.

### P0-1. GitHub Actions CI 계약

- `.github/workflows/test.yml`는 push, pull_request, workflow_dispatch를 등록하고, 권한을 contents:read로 제한하며 실행 시간 상한을 설정한다.
- 임시 PR 브랜치에서는 `scripts/verify-source-state.sh`로 전체 path/mode/blob/작업트리/origin 검증을 실행한다. 브랜치 strict allowlist는 바꾸지 않는다.
- main에서만 추가로 `--strict`을 실행한다. Manifest policy, 오프라인 mock, 전체 unit, Bash 문법, publication audit도 수행한다.
- 워크플로 코드가 있다는 사실은 CI 실행 증거가 **아니다**. 실제 Actions run/check가 없다면 `CI_NOT_VERIFIED`로 기록하고 GitHub Actions 활성화/권한/정책을 조사한다. 임의로 PASS라고 쓰지 않는다.
- PR의 CI가 비어 있다면 요구되는 운영 정책에 따라 머지 전 리뷰하고, CI 미실행이라는 blocker를 명시한다.

### P0-2. 레거시와 신규 Docker 컨테이너 격리

- 레거시 이름 `qwen38-flash-<target>`은 그대로 보존한다. 일반 recipe CLI 호출은 기존 이름과 동작을 유지한다.
- 신규 wizard 이름 `qwen38-wizard-<target>`, marker label `ai.kjlee.wizard=kjlee-qwen38-dgx-spark-wizard`를 사용한다. Docker inspect, receipt, stop/rm도 같은 이름을 사용한다.
- 신규 컨테이너 삭제/정지에는 wizard 영수증 + 정확한 ID + image ID + recipe/target + Docker Name + marker가 전부 필요하다. 하나라도 불일치하면 중단하며 legacy observation은 관리/삭제 권한이 아니다.
- wizard의 `--replace` 및 runtime CLI의 전용 이름에 대한 replace를 금지한다. 임의 이름 지정도 거부한다.
- 동일 단일 GB10에서 기존 레거시가 `running`이면 **신규 GPU 활성화를 차단**한다. 포트/이름 격리만으로 GPU/메모리 중복 부하가 안전해지지 않는다.
- 새로운 build/prepare/activate/stop/remove, 장시간 inference, rollback 실기기 시험은 **NOT_TESTED**. Mock을 실기기 검증으로 승격하지 않는다.

### P0-3. DGX 로컬 main 전환 및 검증 절차

- `scripts/verify-main-readonly.sh`는 개인 Fork origin, `main`, 깨끗한 tracked/untracked working tree 및 **로컬** origin/main의 HEAD 일치를 요구한다.
- 소스 strict, Manifest, offline mock, full unit, Bash 문법, 공개물 감사, 기존 legacy 상태·snapshot diff·Health·Doctor **조회만** 수행한다. 자체 `git fetch/switch/pull/reset/clean`, Docker lifecycle 및 모델 다운로드는 하지 않는다.
- 로컬 origin/main의 참신성을 자동 확인하지 않는다. 먼저 DGX에서 `git remote get-url origin`, `git status --short`, `git branch -vv`를 확인하고 문제가 없을 때 별도 `git fetch origin main` 후 `git switch main` 및 `git merge --ff-only origin/main`을 수행한다. 로컬 main이 없으면 `git switch --track origin/main`; 충돌 시 중단한다.
- **2026-10-26 이후 사용자 DGX 로그로 위 절차의 완료를 확인했다.** 확인된 HEAD는 `66051cdc...`이며 source 114/114, mock 38/38, 전체 unit 172/172, legacy Health PASS. 이후 문서 커밋 HEAD의 검증 또는 신규 배포 기능 실동작을 뜻하지 않는다.

### 후속 작업 고정 운영 규칙

1. 매번 최신 main HEAD/tree·PR·CI와 소스 Manifest 전체 path/mode/blob 및 README/HF 본문 미러부터 점검한다.
2. 기존 운영 자산(레거시 이미지·컨테이너·recipe-views·hf-cache·HF 인증·YSLAB receipt·포트 8000·OpenWebUI·Ollama·네트워크) 불변을 최우선한다.
3. 개발 작업은 기능 브랜치에서 수행하고 Python snake_case/type hints/what-why-how docstrings/한국어 중요 주석, Bash set -Eeuo pipefail/quoting/fail-closed 원칙을 적용한다.
4. 정상·실패·경계·식별자 위조·이름 충돌·idempotency Mock을 추가하며 테스트 실패를 무시하지 않는다. 실제 DGX 가동 시험은 별도 승인 대상.
5. **모든** 파일 추가/변경/삭제/모드 변경과 같은 커밋에 Source Manifest를 함께 동기화한다. 새 PR 브랜치는 strict 허용 목록 밖이다. 전체 inventory 검사와 main strict를 구분한다.
6. GitHub 연결 도구를 사용해 직접 commit/PR/diff review/일반 merge 후 결과를 검증하되 CI 결과 없으면 `CI_NOT_VERIFIED`라고 기록한다. 비밀·Docker full ID를 공개 Git에 기록하지 않는다.
7. 사용자 제공 DGX 기능 HEAD `25949fd7...`의 163/163, 36/36, 7/7, legacy 6/6, API PASS는 **과거 스냅샷**이다. 새 커밋과 실제 DGX에 결과를 자동 승계하지 않는다.
8. UNKNOWN 또는 실패 시 임의 복구/강제 삭제 대신 원인별 읽기 전용 조사; status/health는 ownership 증거와 분리한다.
9. 종료 시 새 브랜치·HEAD·tree·Manifest 추적 수·테스트 환경별 실제 결과·PR/merge/CI·DGX 미완료·blocker를 문서와 답변에 정확히 반영한다.

### PR checkout detached HEAD 안전 검사

GitHub Actions의 pull_request checkout은 detached HEAD일 수 있다.
non-strict Source Manifest 검사는 이때 전체 blob/mode/origin/working-tree를
계속 검증하고 브랜치 이름 검증만 하지 않는다. `--strict`에서는 detached
HEAD를 반드시 거부한다. 회귀시험은 별도 임시 Git fixture로 두 경우를
검증한다. CI 실행 결과를 확인하기 전까지 CI_NOT_VERIFIED다.


---

## 10. 2026-10-27 llama-benchy pre-blazux Baseline 확정

> 이 절은 이전 2026-10-26 운영·CI 상태보다 늦은 **사용자 제공 DGX 실측**이다. 구체적인 원본·12조건 표·해시·재현법은 [Baseline 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md)를 먼저 참조한다.

### 완료된 사실

- 목표: blazux 최적화 적용 **전에**, 실제 운영 모델의 동일 조건 성능 기준선을 저장하여 후속 동일 모델 A/B에 사용. llama-benchy Fork를 새로 개발하는 것이 아니라 기존 Qwen 개인 저장소에 측정 결과를 백업한다.
- 원본 벤치마크 도구: [eugr/llama-benchy](https://github.com/eugr/llama-benchy), commit SHA **e9be344578cec17745066b220798b80a0d2686d3**, 버전 **0.4.1.dev1+ge9be34457**. DGX 독립 설치 경로는 **$HOME/Workspace/llm/llama-benchy-runner**다. 별도의 분석 checkout의 날짜형 baseline Git 태그가 hatch-vcs 빌드를 막았으며, --no-tags clone + 공식 v0.4.0 태그만 둔 runner의 uv sync는 사용자 로그에서 PASS였다.
- 기존 운영: 컨테이너 **qwen38-flash-orca-uncensored-bf16-mtp**, Docker tag **yslab-qwen38-bf16ple:9492b78c**, API **http://127.0.0.1:8000/v1**, 모델 ID **qwen3.8-flash-next-orca-uncensored-bf16-mtp**, 최대 context 메타데이터 **262144**. 컨테이너/Image 전체 ID는 비공개로 유지.
- Tokenizer SHA-256 **06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523**. 실행 중인 모델과 Docker mount의 recipe-view tokenizer.json에서 사용자 확인.
- 2026-10-27 07:14 KST 단일 Smoke Test PASS: PP256 117.28 tok/s, TG32 35.59 tok/s, peak 36.74 tok/s, TTFR 1900.90 ms. 단일 1회 결과 ± 0.00은 안정성의 증거가 아니다.
- **정식 Baseline 완료**: DGX 로그 PASS: baseline completed. 원본 디렉터리 **$HOME/Workspace/llm/bench-results-staging/20261026T221925Z-pre-blazux/**. 시작 2026-10-26 22:19:25 UTC, 결과 timestamp 2026-10-26 22:34:42 UTC. PP 2048/8192 × TG 128/256 × Depth 0/4096/16384, concurrency 1, 각 warmup 1회 후 3회 측정 = **12 조건/36 본 측정**. generation latency, exact-tg, NumPy seed 20261027, 총 토큰 시계열 포함.
- 원본 result.json SHA-256 **25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf**, 원본 environment.json SHA-256 **76c94d48aa4597bd09e9973b6f5cba118db0009062f592e4a764398443f97eb6**. 첨부된 두 파일은 사용자의 SHA256SUMS와 **각각 일치**. 그 목록의 나머지 7개 파일은 사용자가 업로드하지 않았으므로 별도 무결성 검증하지 못했다.
- 정식 결과는 results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json에 **원본 그대로** 보존한다. 전체 컨테이너/Image ID를 가진 원본 environment.json은 공개하지 않고 environment.public.json과 원본 해시만 기록한다.
- 이전 docs/BENCHMARKS.md의 MTP2 44.23 end-to-end completion tok/s와 이번 llama-benchy TG 값은 측정 구간과 산식이 다르므로 직접 비교 금지.

### 당시 Baseline PR #5의 범위와 이후 계획 (PR #5 MERGED)

- 병합된 PR #5 범위: [동일 조건 재실행 Bash 스크립트](../scripts/benchmark/run-llama-benchy.sh), 원본 result.json, 정제된 환경·원본 체크섬, [보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), 이 인수인계 문서, Source Manifest의 전체 path/mode/blob SHA 동기화.
- **사용자 요청에 따라 신규 스크립트 실행·회귀시험 생략(NOT_RUN)**. 과거 DGX에서 성공한 수동 측정이 새 Bash 스크립트 자체의 실행 검증을 뜻하지 않는다. CI도 실행 결과 없으면 CI_NOT_VERIFIED.
- 실행 스크립트는 원본 도구 SHA/Tokenizer SHA/서빙 모델을 검사하고 별도 staging 디렉터리에 JSON/진행 이벤트/로그/환경/메모리·GPU 상태/체크섬을 저장한다. Docker 이미지·컨테이너·운영 상태·model cache·기존 영수증에 쓰기 없음; API를 통한 추론 부하는 실제 발생한다. 개인 식별정보·프롬프트/응답 내용이 포함된 RAW 로그를 자동 공개하지 않는다.
- **후속 완료:** PR #5는 이미 `main=2847e39b...`로 병합됐고 `feature/blazux-vllm032-evaluation-20261027` 브랜치에 계획서를 커밋했다. **현재 다음 단계는 Gate 1 정적 코드 비교**이며, blazux 참조 SHA는 **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**로 고정한다.
- 비교 전 제한: Orcarouter compressed-tensors/ BF16 PLE/ BF16 MTP 31개 overlay와 blazux ModelOpt 전용 hybrid/graft는 직접 호환이 검증되지 않았다. blazux 기본 스크립트의 docker rm -f 및 포트 18300 충돌 위험. 기존 레거시 stop/rm/restart 금지, 단일 GB10 두 대형 GPU 서버 동시 기동 금지. vLLM 0.32 실기기 전환과 성능 개선 주장은 아직 미검증.

---

## 11. blazux vLLM 0.32 적용 계획 브랜치 — 2026-10-27

> 별도 후속 계획. 기존 baseline 문서와 레거시 운영/소유권 규칙을 유지한다.

- [Baseline PR #5](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/5)는 **MERGED**. main merge SHA: **2847e39b4131eb8aff78bf86ffce98892401722a**. 사용자 DGX에서 완료한 12조건·36회 pre-blazux 원본 JSON과 해시, 재실행 Bash, Baseline 보고서가 main에 보존됐다.
- 후속 계획·분석 브랜치: **feature/blazux-vllm032-evaluation-20261027** (위 main merge SHA에서 분기). 첫 커밋 범위는 **docs/BLAZUX-VLLM032-ADOPTION-PLAN.md** 신규 계획서 및 이 핸드오프/Source Manifest 갱신만. vLLM 0.32 포팅, 이미지 빌드, 컨테이너 작업, 실 A/B는 **NOT_STARTED**.
- 원본 blazux 분석 대상 GitHub: [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) pin **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**. 모델 로더/PLE mmap BF16, MTP 31 텐서, compressed-tensors, prefix-cache/SSM, draft vocab, tool parser 등을 Gate별 검증한다.
- **절대 보호:** 레거시 Docker stop/rm/restart/overwrite, HF cache/recipe views/mount/receipt 변경, 포트 8000/18300 무단 점유, 단일 GB10에서 레거시 실행 중 신규 대형 GPU 모델 병렬 기동 금지.
- Baseline은 실행 및 원본 해시 2개 대조까지 완료됐지만 **재실행 Bash 신규 코드 자체의 테스트는 사용자 요청으로 NOT_RUN**. GitHub Actions 실행 0건/CI_NOT_VERIFIED, 다른 7개 로컬 로그 파일 해시 미대조, 입력 코퍼스/샘플링 세부 추가 확인 필요. 신규 브랜치 strict allowlist 제한은 변함없다.
- 다음 세션은 현 최신 main/이 브랜치 HEAD를 확인하고 [계획서](BLAZUX-VLLM032-ADOPTION-PLAN.md)의 **Gate 1 소스 함수/데이터 계약 비교**를 이어서 수행한다. 커밋·PR·머지·실 DGX 작업은 각각 수행/승인된 범위를 구별한다.

### 11.1 2026-10-27 설계 보강 — Track A/B 분리 및 개발 Gate (문서만 변경)

- **Track A:** 현행 preview vLLM 기반 선택적 분석 및 P1 계측/정확성→P2 개별 default-OFF 최적화→P3 고위험 보류. 기존 `feature/blazux-vllm032-evaluation-20261027`는 P0 루트이며, **Phase 1은 P0 HEAD에서, Phase N+1은 Phase N의 확정 HEAD에서 각각 새 브랜치**를 생성한다. 작은 BF16 safetensors 합성 fixture로 증거를 먼저 확보한다.
- **Track B:** 공식 vLLM 0.32 장기 실험은 **P0에서 별도 분기하는 형제 계보**로만 진행한다. `feature/vllm032-bf16ple-port`는 아직 미생성/미착수. Go/No-Go 후 독립 image digest·컨테이너/포트/receipt/view/결과 폴더·ownership label을 사용하고 기존 자산은 불변으로 유지한다.
- 공통: **Phase별 새 브랜치 → 정적 근거/합성 fixture → default-OFF flag/rollback → 기능 리뷰 → 전 Phase HEAD에서 새 Phase 생성**. 검증 결과는 실험 브랜치에만 남기고 `main` PR/merge/cherry-pick/squash 등을 절대 하지 않는다. Track A/B 코드를 혼합하지 않는다.
- 기존 `main`은 GitHub 조회 시 `protected=false`. 따라서 **blazux→main 금지는 별도 운영 규칙**이지 자동 기술적 제한이 아니다. CI 정상화는 사용자 지시로 보류; 본 문서 갱신은 GitHub 원격의 문서·Manifest 변경으로 실 DGX 검증을 수행하지 않았다.
- 상세 정책 및 변경 제한은 [blazux 도입 계획서](BLAZUX-VLLM032-ADOPTION-PLAN.md) §1.4, §3.1, Gate 2/3/6을 우선 참조한다.

### 11.2 Gate 1 실행 시 필수 산출물 및 중단 기준 — 최신 보완

1. **입력 기준:** 현 Qwen 저장소 최신 `main`/기능 브랜치 HEAD·Dockerfile 기반 preview, `compatibility.json`, BF16 MTP 31개 텐서 계약과 pinned Orcarouter/RadixArk revision. 외부 blazux는 **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa** 고정. 가능하면 각 함수별 실 Git Blob SHA와 patch 경로를 적는다.
2. **함수별 대조:** PLE `mmap` header/offset/dtype/index, n-gram hash/dedup/sort/pinned H2D; MTP model loader, 31/31 guard·draft vocabulary·acceptance; QSA top-k 및 SM121 커널; Mamba/SSM prefix cache; Tool/Responses parser, streaming·literal marker. 함수 경로·shape·입출력·기존 구현 여부·바뀐 API·오류 조건을 **1:1 표로 작성**한다.
3. **판정:** 항목별 **KEEP / PORT / ADAPT / DEFER_TO_TRACK_B / REJECT** 및 P1/P2/P3, 근거, 라이선스·third-party provenance, 위험, CPU 합성 fixture, 필요한 최소 수정 범위를 기록한다. 분석 중 새 엔진으로 강제 변경하지 않는다.
4. **검증 선행:** 작은 **BF16 safetensors 합성 shard**로 offset/row/inverse-scatter를 비교하고 정상·오류·경계 테스트를 분리. 이후 P2 기능마다 독립 `default-OFF` flag, off 경로 동일성·롤백 게이트가 없으면 코드 병합 금지.
5. **성능 재현성 차단:** PR #5 **정식 Baseline은 보존 완료**했으나 코퍼스 원본 hash·실 요청 sampling/서버 KV/cache 조건 및 checksum의 나머지 7개 파일 검증이 미완료다. 이 자료가 갖춰지기 전에는 blazux **동일 조건 A/B**나 tok/s 개선율을 주장하지 않는다.
6. **Track B 시작 조건:** 별도 Go/No-Go·자산 이름/라벨·Docker base digest·receipt·loopback 포트·cache/view 분리/rollback 사전 정의가 필요하며, `feature/vllm032-bf16ple-port`는 **아직 미생성**. 같은 단일 GB10에서 레거시 GPU 모델과 신규 대형 모델 동시 기동 금지.
7. **결과 기록:** 코드를 수정하지 않는 정적 비교라도 새 비교 문서/결정 기록을 GitHub에 영구 저장한다. 추적 파일 변경 시 Source Manifest 전체 120개(+신규 파일 수)의 path/mode/blob SHA와 정확히 동기화한다. `main` branch protection은 조회 시 false였으므로 정책상 기능 PR/리뷰를 준수하되 기술적으로 강제된 상태라고 쓰지 않는다. CI 정상화는 사용자 요청으로 보류하며, 실제 수행하지 않은 Mock/DGX/스크립트 테스트는 `NOT_RUN`으로 둔다.

**이 다음 작업의 현재 완료 상태:** Gate 0(실측 원본 및 GitHub 백업) **DONE_WITH_REPRODUCIBILITY_GAPS**; Gate 1의 **실제 1:1 함수 비교표 NOT_STARTED**; Gate 2 합성 shard 시험 **NOT_RUN**; Track A의 실제 최적화 패치/새 PR **NOT_STARTED**; Track B 엔진 교체/이미지/배포/A-B **NOT_STARTED**.


### 11.3 2026-10-27 신규 확정: 페이즈별 Git 계보 및 완전한 폐기 가능성

> **우선순위:** 이 정책은 과거 `main`으로의 선택적 병합을 권장한 문장보다 우선한다. blazux와 관련된 모든 신규 코드는 실험 계보에만 두며 `main`에 절대 반입하지 않는다. 이미 `main`에 병합한 PR #5는 실험 전 Baseline 데이터이므로 그대로 보존한다.

- **P0(존재):** `feature/blazux-vllm032-evaluation-20261027`는 `main@2847e39b4131eb8aff78bf86ffce98892401722a`에서 과거 한 번 생성된 실험 루트다. 이번 정책 커밋을 마치면 **그 최신 HEAD를 고정하고 P0에 기능 개발 코드를 직접 추가하지 않는다**.
- **Track A Phase 1(미생성):** `feature/blazux-phase1-source-compare`를 현재 P0의 정확한 HEAD에서 새로 생성한다. Gate 1 1:1 함수/텐서 비교표, 독립 위험/판정/근거, Source Manifest를 저장한다.
- **Track A 후속(미생성):** Phase 2 `feature/blazux-phase2-offline-fixtures`는 Phase 1의 검토 완료 HEAD에서 생성한다. 이후 각 Phase N+1은 직전 Phase N의 확정 HEAD를 부모로 **새 브랜치**를 만든다. 이전 Phase의 브랜치 ref는 보존·불변이다.
- **Track B(미생성):** `feature/vllm032-bf16ple-port`는 별도 Go/No-Go 결정 이후 **P0 고정 HEAD에서 형제 브랜치**로 생성한다. `main`에서 직접 분기하지 않고 Track A Phase 코드를 상속하지 않는다. Track B 이후에도 각 단계는 새 자식 브랜치다.
- **필수 재현 기록:** 매 Phase 부모 브랜치와 부모 commit SHA, external blazux pinned SHA `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`, source/manifest 경로·mode·blob SHA, 변경 범위, 산출물, 테스트/CI 미실행 여부, 실패/보류/다음 Phase Go·No-Go를 영구 기록한다.
- **리뷰 및 원격 작업:** Phase간 GitHub Compare를 우선하고, PR을 만들더라도 `base=이전 Phase`, `head=현재 Phase`에서 **미병합 상태로만 리뷰**한다. 실험→`main` PR/merge/squash/cherry-pick/rebase/자동 main sync/force push 금지. `main.protected=false`라는 사실로 예외를 허용하지 않는다.
- **안전한 중단/폐기:** 어떤 Phase에서든 실험 브랜치만 보존·아카이브하고 작업을 종료할 수 있어야 하며 `main`의 수정/되돌리기 또는 기존 DGX Docker/모델/영수증 정리 조작이 필요하면 설계 실패로 간주한다.
- **현재 한계:** 기존 사용자 DGX에서 Baseline 12×3=36 실측 및 GitHub 원본 보존은 완료됐으나 Benchmark 신규 wrapper 실행은 NOT_RUN, 나머지 7개 원본 해시 대조 및 corpus/sampling 재현성은 미완료. Wizard 2026-10-26 source 114/114·mock 38/38·unit 172/172는 과거 HEAD 시험이다. blazux Gate 1 실제 1:1 함수 비교·합성 데이터 시험·배포/A/B는 미시작이며 CI 정상화 보류를 유지한다.

**과거 P0→Phase1 최초 착수 지침(이력; 현재 적용하지 않음):** 이 구절은 초기 작업 기록이며 Phase6 현행 Gate를 재시작/재생성하도록 지시하지 않는다. 현재 착수는 맨 위 최신 Phase6 상태와 `docs/BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md`, `docs/BLAZUX-PHASE6-RESULTS.md`, `docs/BLAZUX-PHASE6-GATE-PLAN.md`를 기준으로 실행한다. `main`에 PR/머지는 하지 않는다.

## 현재 세션 착수 우선순위 (이전 P0/Phase1 지침 대체)

1. 현재 Phase6 GitHub 브랜치 최신 HEAD와 전체 Source Manifest 및 이전 **실제** DGX 검증 SHA `fb5deae540812a300cb8404a53a202e505c40577` 구분.
2. Phase6 offline gate와 새 live 메트릭 ABI read-only observer를 DGX에서 실행, 미노출 스케줄러/Mamba 포인터는 BLOCKED로 유지.
3. 승인된 guarded existing-service llama-benchy `--preflight`→`--execute` 단 1회 신규 12×3/36, private raw 보존, old pre-blazux corpus/sampler 비교 미확정 명시. 기존 서비스 위험/메모리/1h stop 조건 확인.
4. 받은 operator evidence의 정확 SHA만 정본/Manifest에 기록. P6-B/C/D 실 GPU patch/모델/CI/merge는 추가 승인 전 BLOCKED. 고전 P0 Phase1 신규 브랜치 시작/반복 금지.
