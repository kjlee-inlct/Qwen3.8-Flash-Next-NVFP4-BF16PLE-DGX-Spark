# Phase 6 현재 진행 작업 전용 — 새 대화 인수인계 프롬프트 (2026-10-28)

## 2026-10-28 중요 교정 — 검증 활동이 실제 blazux 기능 적용 목표를 대체하지 않도록 할 것

**사용자 지적 및 어시스턴트 작업 관리 실패:** Phase 4에서 PLE 옵션을 이미 오프라인 구현한 이후, Phase 5·6에서 소스/CPU 합성 시험, 하위 Gate, 문서/Manifest를 과도하게 늘린 반면, 사용자가 원했던 신규 blazux 기능의 실제 엔진 적용·통합 성과는 증명하지 못했다. 147/147 tests, Source224/224, B0/B1a PASS는 각 검증 범위의 성과일 뿐 **8개 기능의 운영 적용 실적은 0개**이다. 실제 ABI BLOCKED를 재조사와 Gate 증식으로 해결할 수 있다는 인상을 주지 말 것.

**새 대화의 최우선 규칙:** [실수 원인 및 재발 방지 정본](BLAZUX-DELIVERY-DRIFT-POSTMORTEM-AND-GUARDRAILS-20261028.md)을 먼저 읽고 (1) 사용자 기능 가치 (2) 실제 코드 변경 (3) 최소 반증 가능 검증 (4) 남는 실제 실행 장애를 밝힌 뒤 작업한다. 독립적인 소스/CPU P1 기능 구현(PLE 단계별 계측 완성, Tool/Responses Preview Parser 호환 준비)을 우선 후보로 하고, 새 A/B 하위 Gate·반복 메타데이터 조사·시험 개수 증가는 목적이 아니라 필요할 때만 수행한다. **동일 근거에서 전진이 없는 연속 작업은 STOP 및 재우선순위.** 과거 계획의 PRE-B --execute 지시와 이전 예상 테스트 수는 역사적 기록이며 재실행하지 않는다.

**권한과 근거 불변:** 운영 Docker/GPU/model/HTTP/벤치/패치/CI/PR/merge 무승인 실행 금지, main/P0/Phase1–5 및 baseline 불변. P6-A 활성 ABI BLOCKED, B0 합성 PASS, B1a read-only 관측 완료, B1 실제 GPU NOT_RUN, P6-B 정식 BLOCKED, C/D NOT_RUN. 사용자 제공 마지막 DGX-tested source 37b883793bdd33f8aa2d4810947a94fef3aa5c20의 147 unit 및 Source224 PASS와 이후 문서-only GitHub 커밋을 반드시 구분. **이번 수정은 핸드오프 재발 방지 기록만이며 기능 적용·DGX 실행이 아니다.**

---


## 2026-10-28 DGX P6-B1a 실제 무부하 관측 완료 — 147/224 PASS, GPU 미인증

- **정확한 DGX 테스트 소스 SHA:** `37b883793bdd33f8aa2d4810947a94fef3aa5c20`, `feature/blazux-phase6-runtime-gates`. 사용자 제공 전체 DGX 실행 로그에서 `git pull --ff-only`가 `이미 업데이트 상태`이며, 사용자 `git rev-parse HEAD` pin 검사 이후 종료 마커까지 성공했음을 확인.
- **Phase 6 오프라인 검증:** `Ran 147 tests in 0.018s` / `OK`; `PASS_SOURCE_ONLY: 224 tracked file(s)`를 `scripts/phase6-gate.sh` 및 B1a 래퍼에서 **2회**, 동일 HEAD에서 확인. `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- **B1a 실제 passive snapshot:** `status=PASSIVE_METADATA_COLLECTED_NOT_GPU_READY`, `pinned_legacy_identity_stable=true`, `reasons=[]`; `host_available_mib_before=14620`, `after=14609`, **8192 MiB는 읽기 전용 메타데이터 검사 보호 하한이지 GPU 할당 보증치가 아님**; `gpu_telemetry_scope=PARTIAL` (NVML 완전한 메모리 telemetry 미확보). `unified_memory_headroom_proven=false`, `second_model_feasible_proven=false`, `gpu_allocation_authorized=false`. 개인 컨테이너 ID/시작 시각·비공개 상태 원문은 기록하지 않음.
- **실제 종료 마커:** `PHASE6_B1A_PASSIVE_FEASIBILITY_DONE_NOT_GPU_APPROVAL` → `PHASE6_B1A_READONLY_METADATA_CHECK_COMPLETED_NOT_GPU_PASS` → `PHASE6_B1A_DGX_PASSIVE_OBSERVATION_FINISHED_NO_GPU`.
- **Gate 판정:** `P6_B0_CPU_SYNTHETIC=PASS_AT_PRIOR_SHA_3aa4029`, `P6_B1A_PASSIVE_METADATA=OBSERVED_AT_SHA_37b8837`; **`P6_A_ACTIVE_ABI=BLOCKED`, `P6_B1_REAL_GPU=NOT_RUN`, `P6_B_FORMAL=BLOCKED`, `P6_C_D=NOT_RUN`**. 이 관측은 CUDA/Triton kernel 실행, 모델 GPU 메모리 실측, 두 번째 모델 공존성, prefix/rollback/canary 정합성 검증이 아니다.
- **다음 결정:** 승인 없는 GPU 작업이나 두 번째 모델 기동을 금지한다. 다음에는 최소 메모리 사용량이 상한으로 고정된 synthetic CUDA/Triton copy + canary를 **GPU를 전혀 실행하지 않고 설계·소스 검증**할 수 있으나, 실제 실행에는 단일 DGX 서비스 간섭 위험·통합 메모리 할당 예산을 독립적으로 평가하고 사용자에게 정확한 GPU 실행 범위에 관한 **새 명시적 승인**을 받아야 한다. 이미 승인 소진된 PRE-B 36회 재실행 금지. 이 결과를 기록하는 후속 GitHub docs/Manifest 커밋은 DGX 미시험임.

---


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

## 새 대화에 그대로 입력할 프롬프트 — 최신 (기존 2026-10-28 초기 계획 대체)

당신은 저장소 kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark의 feature/blazux-phase6-runtime-gates를 인수인계한다. 사용자 목표는 **실제 유용한 blazux 기능 구현과 검증**이다. Phase/Gate 수 증가 자체가 아니다. 한국어로 진행한다.

**첫 필독**: docs/SESSION-HANDOFF-PROMPT.md, docs/BLAZUX-DELIVERY-DRIFT-POSTMORTEM-AND-GUARDRAILS-20261028.md, docs/BLAZUX-VLLM032-ADOPTION-PLAN.md, docs/BLAZUX-PHASE6-RESULTS.md, docs/BLAZUX-PHASE6-GATE-PLAN.md, scripts/source-state-manifest.json. 완료 이력은 각 정본에 남겨 중복해서 복제하지 않는다. 이 섹션보다 위의 날짜가 같은 교정 규칙이 다음 작업에 우선한다.

### 현재 정확한 실증

- B0 CPU 합성 DGX PASS: source 3aa40292f96427d3592ebdba971b31484c2a6079, Phase6 124/124, Source220/220, 별도 25/25.
- B1a 비간섭 관측 DGX PASS: source 37b883793bdd33f8aa2d4810947a94fef3aa5c20, Phase6 147/147, Source224/224 (2회), pinned legacy container stable, host MemAvailable 14620→14609 MiB, NVML PARTIAL. 결과는 PASSIVE_METADATA_COLLECTED_NOT_GPU_READY로 GPU 가용성 증거가 아님.
- P6-A active Scheduler/Mamba state ABI BLOCKED_MISSING_IN_PROCESS_EVIDENCE; B1 실제 CUDA/Triton NOT_RUN, 정식 B BLOCKED, C/D NOT_RUN. 사용자 승인됐던 PRE-B 12조건×3회=36회는 이미 정확히 한 번 수행·보관되었고, 해당 승인은 소진됐다. 재벤치 금지.
- Phase4 PLE CPU Fast Gather/Stats default-OFF 구현 및 CPU byte-exact PASS; Phase5 Prefix/Mamba·Tool/Responses·MTP reduced-vocab **합성/source** 위험 검증 PASS; 신규 blazux 기능 중 **운영 적용 실증 0개**. 합성 테스트와 실제 엔진 적용을 혼동하지 않는다.
- GitHub HEAD는 다음 대화가 커넥터로 직접 재조회한다. 마지막 DGX-tested SHA와 docs/manifest-only 후속 HEAD를 구분한다. CI는 별도 실행증거 없으면 NOT_RUN/NO_EVIDENCE.

### 미완료 및 사용자 가치 중심 우선순위

1. 기능 표(P1 PLE 단계별 계측 / Prefix-cache / Tool Calling·Responses; P2 reduced MTP vocab / PLE Gather / 별도 vLLM 0.32; P3 YaRN 500K / Hybrid FP8)를 기준으로 **실제 구현되는 최소 사용자 가치 1개**부터 고른다. 다음 제안의 우선 후보는 현재 옵션을 기반으로 한 PLE wait/dedup/gather/stage 단계별 계측의 누락 코드 구현 및 CPU 독립 검증, 또는 Pi Agent를 위한 실제 Preview Parser 호환성 소스/모의 API 정확성 구현이다. GPU/서빙 실행 승인을 임의로 포함하지 않는다.
2. P6-A 실물 ABI 공백과 B1 GPU 실행 위험은 원인·필요 증거·별도 승인 조건을 문서에 기록한 채 **DEFERRED_BY_EVIDENCE**로 유지한다. 승인·관측 수단의 변화 없이 B1b, B1c 같은 CPU-only 세부 Gate나 동일 자원 관측을 자동 추가하지 않는다.
3. 작업 착수 전 반드시 기능의 실제 변화, 파일/함수, 실패 가능한 최소 검증, 실사용까지 남은 blocker, 적용 상태를 명시한다. 결과 보고에서 SOURCE_REVIEWED / IMPLEMENTED_OFFLINE / CPU_VERIFIED / GPU_VERIFIED / API_VERIFIED / DEPLOYED_VERIFIED를 명확하게 구분하고, 테스트 수·Manifest 개수·Phase 완료·임의 퍼센트를 제품 진행률처럼 사용하지 않는다.
4. 코드·문서 변경은 승인된 Phase6 feature branch에만, 정확한 GitHub HEAD CAS 및 전체 path/mode/blob manifest 동기화 후 수행한다. 파일·스크립트를 만든 뒤 DGX 미실행이면 NOT_RUN으로 남긴다.

### 절대 보호 경계

운영 중인 pinned Docker/모델/이미지/포트, 사용자 HF cache, 벤치 원본, main/P0/Phase1–5 refs 변경 금지. 승인 없는 운영 Docker exec/run/stop/restart/attach, GPU model/kernel execution, 추론/HTTP/벤치, blazux runtime patch 적용, CI/PR/merge 금지. 실 모델·GPU/서빙 적용 검증은 새 증거와 사용자 별도 명시적 승인이 필요하다. 그 대신 독립적인 옵션 기본 OFF CPU 기능 구현은 불필요하게 미루지 않는다.

**다음 대화에서 먼저 수행할 일:** GitHub 최신 상태와 실수 교정 정본을 읽고, P1 기능 중 하나에 대한 **실제 코드 구현 및 검증 계획**을 제시한다. 사용자가 해당 구현을 요청하면 그때 구현한다. 불필요한 신규 Gate로 시작하지 않는다.
