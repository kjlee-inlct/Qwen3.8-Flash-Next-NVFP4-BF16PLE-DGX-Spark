# Phase 6 현재 진행 작업 전용 — 새 대화 인수인계 프롬프트 (2026-10-28)

## 2026-10-28 P6-B1a 무부하 격리·자원 관측기 준비

DGX에서 소스 3aa40292f96427d3592ebdba971b31484c2a6079의 Phase6 124/124, Source220/220 및 B0 독립 25/25 PASS를 확인했다. B0 CPU 합성 Gate는 완료됐으나 **활성 P6-A ABI=BLOCKED, 실제 B1 GPU=NOT_RUN, 정식 B=BLOCKED, P6-C/D=NOT_RUN**은 변하지 않는다.

신규 [P6-B1a 읽기 전용 자원·격리 가능성 검사 정본](BLAZUX-PHASE6-B1A-READONLY-FEASIBILITY-20261028.md)과 src/phase6_b1_readonly_feasibility.py, tests/test_blazux_phase6_b1_readonly_feasibility.py, scripts/phase6-b1a-readonly-feasibility.sh를 준비했다. 이전 A3a 파서를 재사용하여 Docker 고정 이미지·실행 식별자(ID/StartedAt) 전후 일치, 호스트 MemAvailable 2회 관측 시 각각 최소 8192 MiB(메타데이터 검사 보호 하한), NVML 읽기 전용 수치의 가용/부분 상태를 기록한다. 호스트 가용 메모리와 NVML 숫자는 실제 GB10 GPU 통합 메모리 할당 가능량을 인증하지 않는다. 성립해도 결과는 PASSIVE_METADATA_COLLECTED_NOT_GPU_READY뿐이며 GPU 승인·실행·정식 B PASS가 아니다.

신규 23개 오프라인 시험을 포함한 예상 전체 Phase6 147개, Manifest 224개는 신규 코드 DGX 실행 전 **예상값/NOT_RUN**이다. 실제 DGX 확인 명령은 B1a 정본에만 있으며 운영 Docker stop/restart/exec/run, 새 GPU 모델, torch/vLLM/CUDA 실행, 추론/벤치, 기존 PRE-B 재실행, CI·PR·merge, blazux patch를 수행하지 않는다. 정식 GPU 단계는 별도 리소스·격리 증거와 명시적 승인 필요.

---


## 2026-10-28 DGX B0 실제 전체 오프라인 PASS — SHA 고정 영수증

- **DGX 실행 소스 SHA**: `3aa40292f96427d3592ebdba971b31484c2a6079` (`feature/blazux-phase6-runtime-gates`), 사용자 제공 전체 터미널 로그에서 `6afade4..3aa4029` fast-forward 확인.
- `bash scripts/phase6-gate.sh`: **`Ran 124 tests in 0.017s`, `OK`**. `PASS_SOURCE_ONLY: 220 tracked file(s)` / `HEAD=3aa40292f96427d3592ebdba971b31484c2a6079`. 종료 `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- `bash scripts/phase6-b0-offline.sh`: Source Manifest **220/220 PASS를 한 번 더 확인**, **`Ran 25 tests in 0.001s`, `OK`**, 합성 `operations_checked=2`, `tables=2`, `states=2`, `status=CPU_SYNTHETIC_ONLY_NOT_GPU`. `PHASE6_B0_CPU_SYNTHETIC_REHEARSAL_NOT_GPU_PASS`, `PHASE6_B0_OFFLINE_PREPARATION_COMPLETE_NO_GPU_NO_ABI_PASS`, 사용자 최종 마커 `PHASE6_B0_DGX_OFFLINE_VALIDATION_DONE_NOT_GPU_PASS`.
- **판정**: `P6_B0_CPU_SYNTHETIC=PASS_AT_EXACT_SHA`; `P6_A_ACTIVE_ABI=BLOCKED_MISSING_IN_PROCESS_EVIDENCE`; `P6_B1_GPU=NOT_RUN`; 정식 `P6_B=BLOCKED`; `P6_C/D=NOT_RUN`. CPU 합성 복사·bounds 검증은 실제 CUDA/Triton, rollback, prefix, active physical GPU state 검증이 아니다. 운영 Docker, GPU/model, HTTP/inference, benchmark 또는 blazux patch 실행 증거 없음.
- 이 영수증의 **후속 GitHub 문서·Manifest 커밋 자체는 DGX에서 재시험되지 않았다**. 이전 PRE-B 벤치 1회 승인 소진 상태 유지; 재실행 금지. B1은 안전한 격리/GPU 자원 가용성과 별도의 명시적 실행 승인이 있기 전까지 설계 및 무부하 준비에 한정.

---


## 2026-10-28 사용자 결정 — A BLOCKED 유지, B0 CPU 독립 검증 착수

사용자는 P6-A의 실물 ABI가 안전하게 관측되지 않더라도 P6-B 작업을 진행하기로 결정했다. **이것은 준비·오프라인 검증의 선행 승인이지, 미검증 A Gate를 형식적으로 PASS 처리하거나 B의 운영 GPU 실행을 즉시 승인한 것이 아니다.** 실 B GPU Gate 선행조건 및 P6-C/D 의존성은 유지한다.

[Phase6 P6-B0 CPU physical-bounds / B1 GPU isolation 계획](BLAZUX-PHASE6-B0-BOUNDS-AND-B1-GPU-ISOLATION-20261028.md)을 추가하고, 순수 stdlib 코드 src/phase6_b0_cpu_bounds.py, 25개의 오프라인 회귀시험, scripts/phase6-b0-offline.sh를 기능 브랜치에 준비했다. 합성 multi-group block table의 int32 element stride, state byte stride, physical ID/할당 범위, 복사 길이, sentinel, alias, 보존 바이트·패딩·실패 원자성 등을 검사한다. **실 GPU/CUDA state copy·prefix/rollback·MTP나 실제 활성 ABI 증거는 전혀 제공하지 않음**. 현재 정식 P6-A는 BLOCKED_MISSING_IN_PROCESS_EVIDENCE, 정식 P6-B는 BLOCKED, B1 GPU NOT_RUN; B0 소스·CPU 검증은 **신규 HEAD에 대한 DGX 로그 수신 전 NOT_RUN**. 새 HEAD의 기대값 124 unit, Source220은 실측이 아니다.

DGX 운영 컨테이너·이미지·가중치·서빙 포트·GPU 모델·기존 PRE-B 36회 원본 불변. 이미 소진된 벤치마크 재실행 금지. 이번 단계의 실제 GPU/모델 배치, Docker exec/run, 운영 stop/restart, blazux patch, CI/PR/merge 금지. 별도 B1 자원·격리·검증 프로토콜을 확보하고 명시 승인받아야 GPU 시험을 시작할 수 있다.

---


## 2026-10-28 DGX A5 실제 오프라인 회귀 영수증 — 99/99·Source216/216 PASS

- **검증된 DGX checkout exact HEAD**: `6afade42bdf40f73c644f96ecbc17b4f3ad36f7f` (`feature/blazux-phase6-runtime-gates`), `git pull --ff-only`로 `882b590... → 6afade4...` fast-forward 확인. `bash scripts/phase6-gate.sh`: `Ran 99 tests in 0.016s`, `OK`; `PASS_SOURCE_ONLY: 216 tracked file(s)`와 동일 HEAD; 종료 마커 `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, 사용자 래퍼 `PHASE6_A5_OFFLINE_SOURCE_VALIDATION_COMPLETED`를 확인했다.
- **정확한 검증 범위**: Python 오프라인 회귀 및 Source Manifest의 tracked path/mode/blob 무결성만 검증했다. 로그에 Docker 내부 객체 관찰, GPU/모델 추론, 커널 실행 또는 실시간 ABI 결과는 없다. 이 영수증을 P6-A 활성 ABI 합격으로 승격하면 안 된다. **P6-A ACTIVE `BLOCKED_MISSING_IN_PROCESS_EVIDENCE`; P6-B/C/D `NOT_RUN`.**
- 사전 승인된 PRE-B 벤치 1회는 이미 소진되었으므로 재실행하지 않는다. 다음은 [P6-A5 관측 가능성 정본](BLAZUX-PHASE6-A5-ACTIVE-ABI-OBSERVABILITY-DECISION-20261028.md)의 별도 승인 필요 검증 경로만 유지한다. 이 로그를 기록한 **후속 문서·Manifest 커밋 자체는 DGX 미시험**으로 분리한다. 운영 Docker/기존 모델/포트/원본 결과 변경, PR/CI/merge 없음.

---


## 2026-10-28 P6-A5 BLOCKED 원인 및 안전한 후속 결정

[**P6-A5 실제 ABI 관측 가능성 결정서**](BLAZUX-PHASE6-A5-ACTIVE-ABI-OBSERVABILITY-DECISION-20261028.md)에 기존 `/metrics`가 시작 시 CacheConfig `block_size=8`만 보여 주며, **실제 선택된 Scheduler/Mamba 그룹·block-table·GPU state의 physical ID/stride/할당 경계를 노출하지 않는 구조적 증거 공백**을 명시했다. 이는 **관측 부족에 의한 `BLOCKED`이지 관측된 ABI `FAIL`이 아니다.** 기존 HTTP/기본 Docker metadata 반복은 Full P6-A를 PASS로 만들지 못한다.

**다음 단계**는 운영 서비스 비변경을 원칙으로 하는 별도 승인용 **향후 in-process attestation** 설계이며 현재 운영 프로세스에 코드를 삽입하거나 재시작/attach/exec하지 않는다. 대안인 격리 GPU/모델 ABI 검증도 별도 승인과 자원 판정이 있어야 하며 기존 활성 프로세스의 실측으로 승격할 수 없다. 승인 소진된 12×3 벤치 재실행 금지. 마지막 실제 DGX 오프라인 99/99·Source212/212 PASS는 `882b590119afcdadb06afe9938c7f3e10c866656`에만 적용되며, 이번 문서·Manifest 신규 HEAD는 DGX NOT_RUN. P6-A ACTIVE `BLOCKED`, P6-B/C/D `NOT_RUN`, patch/PR/merge/CI/운영 변경 없음.

---


## 2026-10-28 PRE-B 원본 36회 결과 Git 보관 완료

- [실제 DGX result.json 원본](../results/llama-benchy/phase6/pre-b-provisional/20261027T234639Z/result.json): **533,082바이트 원본 바이트 불변**, SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d`, Git Blob SHA1 `f963d6003f954bbc90c650a92104fddb34b38bbf` 독립 검증 일치. 12개 조합×3회 개별 PP/TG/TTFT 및 시계열 구조 검사 PASS. [공개 요약](../results/llama-benchy/phase6/pre-b-provisional/20261027T234639Z/summary.public.json) 12개 평균 수치도 원본과 12/12 일치.
- 기존 별도 비공개 환경/실행 로그/체크섬 장부와 운영 Docker 식별자는 공개하지 않음. 아래의 '원본 미수령' 단락은 이전 시점의 기록으로만 유지한다.
- DGX 오프라인 마지막 확인: `882b590119afcdadb06afe9938c7f3e10c866656` 99/99 tests, Source Manifest 212/212 PASS. 본 raw 등재 커밋의 DGX·CI는 별도 검증하지 않았다. PRE-B 벤치 신규 실행 승인은 소진됨: **재실행 금지**. P6-A ACTIVE ABI `BLOCKED`, P6-B/C/D `NOT_RUN`, strict 공식 성능 개선율 주장 금지.

---


## 2026-10-28 신규 PRE-B 결과 Git 보관 시작 (원본 raw 미수령)

- **구조화 공개 요약**: [Phase6 PRE-B summary.public.json](../results/llama-benchy/phase6/pre-b-provisional/20261027T234639Z/summary.public.json) / [공개·비공개 구분 README](../results/llama-benchy/phase6/pre-b-provisional/20261027T234639Z/README.md). DGX 콘솔에서 보고한 12개 조합의 평균값, 36회 검증 선언, 결과 원본의 보고된 SHA `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d`를 기록했다.
- **중요**: `result.json` 자체의 36회 원시 반복값·시계열 파일은 이 대화에 첨부되지 않았고 **Git에도 아직 없음**. 기존 비공개 staging 파일은 비공개로 유지한다. 정확한 원본을 제출받아 SHA 및 안전한 필드 구성을 검증한 뒤에만 별도 커밋한다. **벤치마크 재실행 금지**.
- **추가 DGX 확인**: 소스 `882b590119afcdadb06afe9938c7f3e10c866656`에서 Phase6 오프라인 99/99, Source Manifest 212/212 PASS (`PHASE6_POST_RECEIPT_OFFLINE_CHECK_COMPLETED`). 이 결과는 후속 공개 요약 커밋으로 자동 승계되지 않는다. P6-A ACTIVE ABI `BLOCKED`; P6-B/C/D `NOT_RUN`.

---


## 2026-10-28 DGX 실제 로그 반영 — P6-A 부분 관찰 / 신규 PRE-B 1회 완료

**현재 가장 우선하는 업데이트: 이미 신규 벤치 1회 완료. 본 문서 아래의 ‘실행’ 지시는 이 시점 이후 다시 사용할 수 없는 역사적 인수인계 명령이다.**

- **실제 DGX-tested SHA**: `d031d4196eab1f5f1603d6541eaf5a31b02192c0` (사용자 제공 콘솔 로그). `git pull --ff-only` 이후 `bash scripts/phase6-gate.sh`에서 **99/99 단위시험 PASS**, **Source Manifest 211/211 PASS**. 이 SHA에서 shell `bash -n` 점검도 이어서 성공했다.
- **후속 GitHub docs-only HEAD**: `13668e031992341dfde1d815ec553a6d97d29ecf` (212개 tracked file). 로그 당시 DGX checkout은 `d031d419...`이었으므로 **13668e0...의 Source212/212 및 단위시험은 DGX NOT_RUN**이다. 이후 증거/Manifest 문서 커밋 역시 DGX-tested로 간주하지 않는다.
- **P6-A live read-only 결과**: `PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA`, `/v1/models`의 고정 served model ID 일치, `/metrics` `vllm:cache_config_info` 1 series: `block_size=8`, `enable_prefix_caching=false`, `gpu_memory_utilization=0.8`; 관찰 전후 pinned legacy identity=true. 이 값은 노출된 시작시 cache 메타데이터만 증명한다. 실제 Scheduler class, effective scheduler/hash block size, 그룹별 MambaSpec, block-table row/stride, GPU tensor ptr/shape/stride/allocation은 전부 `NOT_OBSERVED`; **P6-A 활성 ABI=BLOCKED**.
- **PRE-B 무부하 preflight**: `READY_FOR_APPROVED_PROVISIONAL_BENCH`, runner SHA/current cached corpus SHA 검증, original baseline 12조건/36 반복 검증, pinned image/running=true, 당시 host MemAvailable=14058MiB. Bench 시작 watch 기록 14050MiB, 이후 minute 1~15의 관측 범위 14170~14746MiB (출력된 점검치); 이것은 전체 운영 무간섭이나 OOM 방지를 증명하지 않는다.
- **승인된 단 1회 신규 벤치 완료**: `PASS_PROVISIONAL_PRE_B_36`, **12 conditions × 3 measured = 36**, 기존 서비스 대상, 원본 Baseline과 별도 private staging에 보존. 신규 `result.json` 보고된 SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d`. 로그는 래퍼의 검증 완료 선언을 포함하지만 새 raw 파일 바이트의 독립 재해시는 이 GitHub 문서 갱신 과정에서 수행하지 않았다.
- **승인 소진**: 위 1회가 실행되었으므로 `scripts/phase6-ab-provisional-run.sh --execute` 및 레거시 benchmark 직접 호출을 **재실행하지 않는다**. 실패/재검증 명목으로 자동 추가 API/GPU 부하도 금지.
- **비교 범위**: 역사적 Gutenberg corpus 원본 SHA 및 sampling/KV/cache 동일성 미확정. 과거 pre-blazux↔금번 결과 strict A/B 성능 개선율/회귀율을 주장할 수 없다. 공식 **P6-D NOT_RUN**, **P6-B/C NOT_RUN/BLOCKED**. 결과 원본/비공개 environment/guard logs/개별 컨테이너 ID·로컬 절대경로를 공개 GitHub로 올리지 않는다.

**다음 작업**: 실제 Scheduler/MambaSpec/physical state를 서비스 비간섭 방식으로 관측할 수 있는 정식 인터페이스/소스 계약을 읽기 전용으로 검토하고, 부족하면 별도 승인 가능한 최소 실제 ABI oracle 설계안만 제출한다. 추가 운영 `docker exec/run`, attach, GPU/model start, inference/benchmark, patch, B/C/D Gate 진입 금지. 정확한 DGX 로그는 `d031d419...` 기준이며 후속 문서 커밋 테스트는 `NOT_RUN`이다.

---


> 이 파일은 **현재 진행 중인 작업만** 전달한다. 확정 사실·완료 이력·상시 운영 규칙·과거 Phase별 영수증은 정본을 참조하고 복제하지 않는다. 이 파일 작성 이후 GitHub 문서/Manifest 전용 커밋의 SHA는 실제 DGX 시험 SHA가 아니다.

## 새 대화에 그대로 입력할 프롬프트

당신은 `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`의 `feature/blazux-phase6-runtime-gates`에서 진행 중인 **Phase 6 P6-A 활성 ABI 증거 수집 + 사용자 승인된 기존 서비스 PRE-B 벤치마크 스크립트 실검증**을 인수인계한다. 설명/분석/지시/출력은 한글로 진행하라.

**먼저 반드시 GitHub에서 최신 버전의 아래 영구 문서를 직접 읽고, 이것이 현재 진행 상태에 우선하는 규칙/정본임을 확인하라.** 기존 완료 기록과 상시 규칙의 내용은 이 프롬프트에서 되풀이하지 않는다.

- `docs/SESSION-HANDOFF-PROMPT.md`: 실험 브랜치, P0/Phase 계보, 권한 경계, Source Manifest, 운영 서비스 비간섭, 인수인계 규칙
- `docs/BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md`: **현재 승인된 실행 범위** 및 위험·중지·evidence 구분
- `docs/BLAZUX-PHASE6-RESULTS.md` 및 `docs/BLAZUX-PHASE6-GATE-PLAN.md`: 현재 Phase 6 실측 및 Gate 상태
- `docs/BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md`, `docs/BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md`: Baseline/새 PRE-B/향후 P6-D 구분과 비교 가능성
- `docs/BLAZUX-VLLM032-ADOPTION-PLAN.md`, `docs/BLAZUX-PHASE5-MAMBA-GROUPED-EXIT-GATE-20261028.md`, `scripts/source-state-manifest.json`: 상시 보호 경계와 정확한 소스 검증 계보

### 지금 진행 중인 두 작업

1. **P6-A 실서비스 관찰 시도**: `scripts/phase6-a-live-observe.sh` / `src/phase6_a4_live_observer.py`가 기존 고정 Docker 컨테이너를 실행 전후 대조한 뒤 localhost `/v1/models`와 `/metrics`를 GET하여 **실제로 노출된** CacheConfig 숫자/불리언만 추출한다. 기존 메트릭의 값은 실제 Python Scheduler 객체, `MambaSpec` 그룹별 block sizes, block-table geometry, 물리 GPU state/tensor 주소/stride를 증명하지 않는다. **P6-A 실제 활성 ABI는 현재 BLOCKED**이고 이 관찰 실행만으로 PASS로 변경하면 안 된다.
2. **PRE-B 성능 스크립트 실측 — 1회 승인된 provisional run**: 기존 2026-10-26/27 pre-blazux Baseline이 있어도 사용자가 `llama-benchy` 런처 검증 목적으로 신규 측정을 승인했다. `scripts/phase6-ab-provisional-run.sh --preflight`를 먼저 실행하고 PASS 시에만 `--execute`를 **1회** 수행한다. 이는 기존 127.0.0.1:8000 운영 모델에 실제 generation inference를 보내는 **12 조건×3 측정=36회**이며, B 정식 진입/P6-D 성능 Gate가 아니라 `PASS_PROVISIONAL_PRE_B_36` 형식의 잠정 자료다. 이 요청 이후 작업을 바로 수행하는 동안에도 다른 운영 사용자가 받을 응답 지연 위험을 고려한다. 새로운 GPU 모델/컨테이너 기동은 없다.

### 정확한 실증 상태 (새 테스트 결과가 도착하면 덮어쓰지 말고 SHA별로 갱신)

- **마지막 DGX operator-tested 소스 SHA**: `fb5deae540812a300cb8404a53a202e505c40577` — `Ran 70 tests; OK`, `PASS_SOURCE_ONLY: 204 tracked file(s)`, 과거 원본 Baseline SHA와 runner/tokenizer/12×3 36-repeat 검사 PASS, `PLAN_READY_NOT_EXECUTED`, 최종 `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`. 이는 **신규 벤치 실측이 아님**.
- **신규 기능 구현 GitHub SHA**: `d031d4196eab1f5f1603d6541eaf5a31b02192c0` — loopback live observer 12개 테스트, 메모리/컨테이너 identity watchdog 포함한 provisional benchmark 17개 테스트, current runbook 및 오래된 Phase1/Baseline 문구 교정, 새 Source Manifest 211개. **DGX 미실행**. `99/99`와 `211/211`은 원 코드 커밋에서의 *기대치*일 뿐 아직 PASS 아니다. 이후 문서-only 인수인계 커밋은 파일 수가 증가하지만 코드는 그대로이며 HEAD 검증 전 기대 수를 재계산해야 한다.
- Github 상태 확인 시점 (2026-10-28): 이 구현 SHA는 `baf1d48...`에서 fast-forward된 1커밋; **Open PR=0**, combined commit statuses `[]`, 조회 가능한 PR-triggered workflow runs `[]`. 이는 **CI PASS가 아니라 CI evidence 없음**이며 PR/머지는 수행하지 않았다는 뜻이다. 새 문서-only HEAD에서도 상태를 재조회하라.
- 기존 레거시 Docker: `qwen38-flash-orca-uncensored-bf16-mtp`, pinned image ID `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`, 서비스 loopback `http://127.0.0.1:8000/v1`. **현재 시점 실가동 여부는 과거 관측값일 뿐** 새 operator log/체크로 확인한다.

### 미완료, 차단 요소, 해결 전에는 주장하면 안 되는 내용

- 실제 선택된 Scheduler 클래스와 CacheConfig/scheduler/hash group block-size, 각 `MambaSpec` 그룹·물리 block table/실 GPU state pointer·allocation/stride는 아직 독립적으로 관측되지 않음. HTTP 메트릭 일부 노출만으로 full P6-A PASS 금지. 추가 process attach, Docker exec/instrumentation 또는 격리 GPU probe는 **이번 승인 대상이 아니며 별도 승인**이 필요하다.
- 이전 Baseline의 **당시 실제 Gutenberg corpus SHA 및 sampler/KV/cache 동등성** 미확정. 신규 벤치의 current cache SHA는 별도 고정하되 2026-10-26/27 수치와 **strict A/B 개선율/회귀율, blazux 성능 개선을 주장하지 않는다**. 동일 조건의 신규 pre/post 쌍과 사전 정의한 임계값만 향후 비교한다.
- 신규 live observer/preflight/실제 벤치 새 SHA의 DGX 로그, 원본 결과 폴더/sha checksum, 사용 모델 메타데이터, 오류/중단 여부, bench PASS/PARTIAL 미확인. **P6-B/C/D는 NOT_RUN/BLOCKED**. No CI and no PR/merge evidence.

### 새 대화에서 진행할 우선순위

1. **GitHub 현황 확정**: 연결된 GitHub 도구로 포크 저장소 최신 Phase6 HEAD, `docs/SESSION-HANDOFF-PROMPT.md`와 위 정본, Source Manifest 전체 개수, 열린 PR, 최신 커밋 combined status 및 조회 가능한 Actions 실행 상태를 확인한다. 최신 문서-only 커밋은 DGX-tested SHA로 둔갑시키지 않는다. 과거 단순 목록/영구 규칙을 재작성하지 말고 링크만 사용한다.
2. **DGX 전용 clean checkout 갱신**: 사용자 DGX `$HOME/Workspace/llm/blazux-phase6-gates`에서 origin/branch/clean을 확인하고 `git pull --ff-only`, `git rev-parse HEAD`를 **실제로 GitHub에서 본 최신 HEAD**에 일치시킨다. Phase6 `bash scripts/phase6-gate.sh`, `bash -n`으로 두 신규 shell entrypoint 확인, `scripts/verify-source-state.py` 전체 manifest 검사. 새 문서 추가가 1개라면 **Source212개 기대**, 신규 코드 테스트 **99개 기대**, 모두 **LOG 도착 전 NOT_RUN**.
3. **P6-A 관찰**: `bash scripts/phase6-a-live-observe.sh`를 실행한다. GET한 engine metrics가 `PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA`면 허용 숫자만 기술하고 active P6-A는 BLOCKED; 메트릭 `ABI_METRICS_NOT_USABLE`인 경우에도 없는 값을 임의로 채우지 않는다. `docker inspect` 실행 전후 identity drift / 모델 ID 불일치면 STOP. 실제 GPU tensor/그룹의 관찰 계획은 결과에 따라 별도 작성한다.
4. **PRE-B 신규 스크립트 검증**: `bash scripts/phase6-ab-provisional-run.sh --preflight`가 `READY_FOR_APPROVED_PROVISIONAL_BENCH` 및 marker를 출력했는지 먼저 확인. 사전 검사: 원본 baseline hash, runner `e9be344578cec17745066b220798b80a0d2686d3`, 현재 cached Gutenberg SHA `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`, image ID/StartedAt, MemAvailable>=8GiB. 실패 시 자동 재시도/완화 없음.
5. **조건 만족 시 단 한 번 실제 벤치**: `bash scripts/phase6-ab-provisional-run.sh --execute` (실제 추론 부하 발생). 10초 주기 관측으로 MemAvailable<4GiB, Docker identity drift, 1시간 초과 시 벤치 자식 그룹만 중단하고 기존 서비스는 그대로 둔다. 한 번 성공·실패·중단 후 **승인을 자동으로 재사용하여 또 실행하지 않는다**. 현재 RAM/HW 상황과 중요한 사용자 트래픽을 반영하여 실행 여부를 판단하고, 문제 발생 시 STOP.
6. **증거·정본 갱신**: 실제 출력에 나타난 정확 SHA, unittest/Source PASS, metric 상태, PRE-B 12×3/36 raw result SHA256·private staging 위치 및 redacted 12-row PP/TG/TTFT 요약·SHA256SUMS, 전후 identity, stop/watchdog 여부를 GitHub 문서에 기록. 비공개 logs/environment/IDs/경로·토큰을 공개 repo로 업로드하지 않는다. Source Manifest의 모든 path/mode/blob sha를 최신 HEAD 파일 내용과 일치시킨 뒤 기능 브랜치에 **CAS expected_sha**, fast-forward 커밋한다. 후속 기록 커밋은 DGX-tested로 위장하지 않는다.
7. **후속 정확성 설계**: 현재 관찰로 P6-A active ABI가 해결되지 않으면 group별 실제 state oracle 확보 방법을 소스·리스크·승인 경계로 쪼개서 다음 별도 검증 제안만 준비한다. B 실 GPU/C API/최종 D 벤치/patch는 자동 진행하지 않는다.

### 이번 작업에만 적용되는 STOP/금지

- **원본 2026-10-26/27 pre-blazux 12×3 결과 절대 덮어쓰지 않음**. 실제 새 36회 결과는 홈의 private `bench-results-staging`의 `phase6-pre-b-provisional` 새 하위 폴더에만 보존. 직접 `scripts/benchmark/run-llama-benchy.sh` 실행 금지(운영 API에 guard 없이 부하 가능).
- P6-A active runtime, P6-B, P6-C, P6-D의 정확성/개선 주장은 미관측 상태에서 금지. 실제 사용자 요청에 근거해 provisional benchmark만 승인 범위 내 1회 허용; 이미 실행된 로그가 있다면 중복 벤치 금지.
- 이 작업에서 운영 Docker stop/restart/exec/run, ptrace, instrumentation, 새 모델 로딩, GPU 전용 stress/추론 실험, 가중치·cache·port·receipt 변경, 기본 image 변경을 금지한다. 벤치 자체가 기존 모델 GPU 연산을 발생시키는 것은 명시 승인됐으나 새 GPU 모델 기동 권한은 아님.
- **지금은 Phase6 브랜치만 수정**. `main`, P0, Phase1–5, 원본 Bench/PR#5 불변. PR 작성/리뷰가 필요하면 영구 문서의 **이전 Phase base→현재 Phase head, 미병합 리뷰 전용** 정책부터 확인한다. **main PR·merge/squash/cherry-pick/rebase/force push 금지**; 이 인수인계 문서나 시험 미완료 기능을 `main`으로 머지하지 않는다. CI 미실행은 PASS가 아니다.

이제 실제 GitHub 최신 HEAD와 위 정본부터 확인하고, DGX 증거가 아직 없으면 절대 실행되었다고 주장하지 말고, 가장 안전한 다음 실행 명령/검증 기준을 제시하라.

