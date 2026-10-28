# Phase 6 evidence ledger

## 2026-10-28 P1 native Qwen schema — 실제 DGX marker PASS 및 추가 Preview-native 포팅

- **정확한 operator DGX SHA:** `07c031e708cede07cd2842d1fd1e752336cbb567`. Phase6 **165/165 PASS**, Source **237/237 PASS**, PLE phase byte-exact/concurrency24/Phase4 four flags PASS, Phase5 synthetic 14/14 PASS. **네이티브 마커 코드의 임시 source patch/수정 메서드 CPU 5 사례 PASS**, `PREVIEW_P1_NATIVE_QWEN_MARKER_CPU_PASS_NOT_API_OR_DEPLOYED`, `PLE_PHASE_STATS_CPU_DGX_ISOLATED_VERIFIED_NO_GPU_NO_SERVICE_CHANGE`. 운영/GPU/model/HTTP unchanged.
- 다음 기능 코드: **`src/preview_p1_patches/qwen-preview-native-schema.patch`** — 실제 operator 제공 Preview source의 **marker 적용 후 preimage** 기준 6-file 독립 패치. 새 JSON schema validator `argument_validation.py`, Qwen3 strict Responses argument buffering + one-layer wrapper schema repair, incomplete/unoffered/invalid fail-closed, Chat incremental path 유지, parser adapter→Responses serving에 오류 상태 전달.
- **현재 작업 환경의 사용자 제공 원본 archive 검증**: 정확 9개 Python preimages; 원본 4-file marker patch와 새 schema patch 순차 `patch --batch --forward --fuzz=0 -p1` temp copy 적용, 변경 AST + 실제 Qwen3 메서드/validator CPU **12개 검사 PASS**. `src/preview_p1_native_schema_verify.py`는 설치 Preview 원본 SHA 확인 후 동일한 임시 사본 시험을 재현한다. **full vLLM parser/Responses API/실 모델/운영 검증이 아님**.
- 다음 DGX 1회 CPU-only mode: `scripts/ple-phase-stats-cpu-container.sh --expected-head <정확한 신규 SHA> --bundle p1-schema --execute`. 실행은 새로운 사용자 승인과 HEAD 필수. 신규 커밋은 `DGX_NOT_RUN`; v0.32 원본 패치 무차별 적용 금지, main/P0/Phase1–5/운영 Docker/GPU/PR/CI/merge 무변경.


## 2026-10-28 P1 Preview-native Qwen tool-marker port — uploaded real source archive

- 사용자 첨부 `preview-p1-source-vjEAFR9W.tar.gz`에서 **9개의 실제 설치 Preview 파일**을 검사, path/file과 sha256 확인(새 `argument_validation.py`는 원본에 존재하지 않아 9개가 정상). 내부 6개 핀과 일치, 추가 `nemotron_v3.py`는 sha256 `9d77b45debb4fb820cc448dfbeeccb53b384f8124b0ef6627ddba9777dcfa6df`.
- **실제 기능 코드:** `src/preview_p1_patches/qwen-preview-native-marker.patch` — vLLM v0.32용 원본을 맹목적으로 적용하는 대신, 사용자 **정확한 Preview 소스**에서 직접 생성한 native source diff. `parser_engine_config.py`, `streaming_parser_engine.py`, `qwen3.py`, `nemotron_v3.py` 네 파일 수정. tool wrapper preamble을 확인 전까지 보류하고, 인용/코드 펜스/중간 문장 도구 마커를 보호. EOF의 확정 안 된 preamble은 내용으로 돌려준다. 기본 Qwen3만 opt-in, Nemotron은 OFF.
- **현재 세션 로컬 독립 검사(운영 DGX 아님):** 업로드된 정확한 원본을 `patch --batch --fuzz=0 -p1`로 **임시 복사본 4개 파일에만** 적용했고 AST 유효성 PASS. 수정된 `StreamingParserEngine`의 실제 메서드 바디를 추출해 stdlib CPU mock으로 **5개 행동 반례 PASS** (mid-line bare function / fenced literal / 정상 tool wrapper / 잘못된 tool wrapper 내용 반환 / tilde fence). `CPU_VERIFIED_EXTRACTED_METHODS_ONLY` — **전체 vLLM Parser import/API/serving 검증 아님**.
- 새 도구 `src/preview_p1_native_marker_verify.py` 및 기존 CPU-only 1회용 컨테이너의 **새 독립 `--bundle p1-native-marker` 모드**로 4개 SHA 확인→읽기 전용 temp patch→AST→실제 메서드 CPU 검사. **신규 GitHub HEAD 자체는 DGX NOT_RUN**; 운영 컨테이너/모델/GPU/HTTP/CI/PR 변경 없고 새 기능 운영 적용=0.
- **남은 같은 P1 묶음:** `qwen-safe-output.patch` (Responses 실패/미완료/빈 stop)와 `qwen-tool-argument-schema.patch` (schema/JSON wrapper) 그리고 실제 API harness/Parser 통합. 기존 P6-A active block GPU 미해결은 그대로 별도.


## 2026-10-28 P1 Tool/Responses — 원본 패치 1 문맥 불일치 확인, 전체 Preview 소스 획득 필요

- 실제 사용자 DGX 소스 `10fc574ff60afb7d8a09728ef4e547c3a6774001`: Phase6 **159/159 PASS**, Source **233/233 PASS**, PLE byte-exact/Phase4 4 combinations PASS, Phase5 Tool/Responses/Prefix/MTP synthetic **14/14 PASS**.
- 6개 Preview source SHA256 검사 완료 후 blazux v0.32 **첫 번째** 패치에 진입했으나 `PREVIEW_PATCH_1_CONTEXT_MISMATCH:vllm/parser/engine/parser_engine_config.py:old_line_103`로 `BLOCKED_NOT_APPLIED` / `exit=2`. `installed_vllm_modified=false`, `model_gpu_api_run=false`. **Preview 코드의 103행 근처 실제 텍스트는 제공된 로그에 없으므로 임의의 위치·수정 내용을 단정하지 않음**.
- 다음 **실제 Preview-native 기능 포팅에 필요한 새 증거**: `scripts/preview-p1-source-export.sh`가 고정 이미지의 installed Preview에서 patch target `vllm/parser` 및 `vllm/entrypoints/openai/responses` Python 파일을 **한 번만** 수집하여 비공개 `$HOME/preview-p1-source-*.tar.gz`로 저장. 원본 SHA 확인/allowlist/읽기 전용/CPU-only/no-network/GPU-void/운영 컨테이너 identity 보호, `--execute` 명시. 새 소스 번들 제공 후 **네 패치**를 모두 native Preview source/ABI 기준으로 직접 구현하며, v0.32 patch를 반복해 맞춰보는 일은 중단.
- 이 새 source-export 경로는 포팅에 필요한 실제 파일 **내용 확보 도구**이며, 그 자체가 구현·호환성·runtime PASS가 아니다. 신규 HEAD DGX `NOT_RUN`, 운영 서비스 변경 없음.


## 2026-10-28 P1 Tool/Responses Preview stage 실제 DGX 중단 — SHA 4efed48

- 사용자 실행: exact `4efed48136278acb195231bb2b1a79a91ce62c5f`, `--bundle p1-tool-stage --execute`. Phase6 **157/157 PASS**, Source **233/233 PASS**, PLE byte-exact/동시성/Phase4 flag PASS, Phase5 Tool/Responses/Prefix/MTP 합성 **14/14 PASS** 및 Preview read-only AST 감사 완료.
- stage 결과: `{"status":"BLOCKED_NOT_APPLIED","reason":"PREVIEW_SHA_DRIFT","installed_vllm_modified":false,"model_gpu_api_run":false}`; 최종 CPU wrapper `exit=2`. 실제 패치는 복사본에도 적용되지 못했으며 Parser/API 실행·운영 적용 증거 없음.
- **진짜 원인:** `src/preview_p1_tool_responses_stage.py`의 `vllm/parser/qwen3.py` static SHA256 고정값이 **54자리 오기**. 이미 동일한 DGX 실행의 `phase5_preview_abi_audit.py`가 64자리 실제 관측 SHA `8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb`와 과거 값 일치를 확인. 이 결과를 **실제 Preview 코드 변경/드리프트로 오판 금지**.
- 다음 source-fix: 올바른 64자리 고정값으로 정정, 기존 감사의 4개 공통 SHA에 대한 일치 테스트 및 static pin 형식 테스트, temp patch context rejection에서 공개 상대경로/기대 라인만 보고. 새 commit에서 DGX 실제 patch apply 여부는 여전히 `NOT_RUN`; 운영 Docker/GPU/모델/HTTP 및 PR/CI 변경 없음.


## 2026-10-28 DGX P1 묶음 실제 PASS — SHA 3899031

- 사용자 DGX 전체 출력: `git pull --ff-only`가 `47c8aa8..3899031` fast-forward한 직후, `--bundle p1-offline --execute` 실행. **정확한 시험 SHA** `389903179f9ce81b2f846c657b877b190750e3c1`.
- Host Phase6 **147/147 PASS**, Source Manifest **227/227 PASS**. CPU-only disposable Docker의 PLE 계측/24-call 동시성/byte-exact PASS, Phase4 네 조합 PASS. 독립 Phase5 Tool/Responses/Prefix/MTP **14/14 합성 contract PASS**.
- Preview 소스 읽기 전용 분석 성공: parser engine/qwen3/streaming/Responses의 과거 SHA와 일치. 새로운 blazux 메서드가 아직 없는 것을 확인(예: `_normalize_tool_arguments`, `_marker_is_literal`, `_make_failed_response_event`). 이는 **패치 부재**의 소스 증거이며 Preview 서버가 실제 오작동한다는 증거가 아니다.
- synthetic warm CPU 중앙값 stats OFF **112.815 μs**, ON **131.456 μs**. 이전 `47c8aa8` 시험 값과 방향이 다르므로 실제 오버헤드/서비스 성능 추정에 사용하지 않는다.
- 마지막 마커 `PLE_PHASE_STATS_CPU_DGX_ISOLATED_VERIFIED_NO_GPU_NO_SERVICE_CHANGE`; **GPU/model/http/운영 적용은 수행하지 않음**. 새 SOURCE-only patch staging 커밋은 별도 DGX 실행 전 `NOT_RUN`.


## 2026-10-28 P1 PLE 단계별 계측 — 일회성 CPU Docker 실제 DGX PASS (정확한 SHA)

- **사용자가 제공한 실제 DGX 로그:** `feature/blazux-phase6-runtime-gates` 소스 `47c8aa819bcdca5c6938831a091190bea075610a`. `git pull --ff-only`로 `518e805..47c8aa8` fast-forward 후, `scripts/ple-phase-stats-cpu-container.sh --expected-head 47c8aa8... --execute` 실행 완료.
- **Host 표준 라이브러리:** Phase 6 **147/147 OK**, Source Manifest **227/227 PASS**, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- **독립 CPU-only 일회용 컨테이너:** `PLE_CPU_CONTAINER_PREFLIGHT_PASS`, `RUNC_CPU_ONLY_NETWORK_NONE_GPU_VOID_READONLY_MEMORY_1G`; 신규 단계별 계측 `PLE_PHASE_STATS_CPU_PASS byte_exact=1 concurrency=24`; Phase 4 FAST/STATS OFF/OFF, ON/OFF, OFF/ON, ON/ON 모두 `byte_exact=1`, `PHASE4_CPU_MATRIX_ALL_OK`; 최종 `PLE_PHASE_STATS_CPU_DGX_ISOLATED_VERIFIED_NO_GPU_NO_SERVICE_CHANGE`.
- **소형 warm synthetic CPU 샘플:** stats OFF median **116.606 μs**, stats ON median **114.607 μs**. 단기 측정 잡음/테스트 환경의 영향이 가능하며 **계측 ON 성능 향상·계측 오버헤드 0·운영 TPS 개선을 증명하지 않는다**.
- **기능별 판정:** P1 PLE 단계 계측 `CPU_VERIFIED_AT_SHA_47c8aa8`; 실제 운영 엔진 활성화 `NOT_APPLIED`, 실서비스 프로파일/인퍼런스/실 NVMe 성능/GPU H2D `NOT_RUN`. 그 밖의 7개 기능 구현 완료 근거로 계산하지 않는다. 이후 GitHub 문서/스크립트 HEAD는 별도 DGX 실행 전까지 `DGX_NOT_RUN`.


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

- **실제 DGX-tested SHA**: `d031d4196eab1f5f1603d6541eaf5a31b02192c0` (사용자 제공 콘솔 로그). `git pull --ff-only` 이후 `bash scripts/phase6-gate.sh`에서 **99/99 단위시험 PASS**, **Source Manifest 211/211 PASS**. 이 SHA에서 shell `bash -n` 점검도 이어서 성공했다.
- **후속 GitHub docs-only HEAD**: `13668e031992341dfde1d815ec553a6d97d29ecf` (212개 tracked file). 로그 당시 DGX checkout은 `d031d419...`이었으므로 **13668e0...의 Source212/212 및 단위시험은 DGX NOT_RUN**이다. 이후 증거/Manifest 문서 커밋 역시 DGX-tested로 간주하지 않는다.
- **P6-A live read-only 결과**: `PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA`, `/v1/models`의 고정 served model ID 일치, `/metrics` `vllm:cache_config_info` 1 series: `block_size=8`, `enable_prefix_caching=false`, `gpu_memory_utilization=0.8`; 관찰 전후 pinned legacy identity=true. 이 값은 노출된 시작시 cache 메타데이터만 증명한다. 실제 Scheduler class, effective scheduler/hash block size, 그룹별 MambaSpec, block-table row/stride, GPU tensor ptr/shape/stride/allocation은 전부 `NOT_OBSERVED`; **P6-A 활성 ABI=BLOCKED**.
- **PRE-B 무부하 preflight**: `READY_FOR_APPROVED_PROVISIONAL_BENCH`, runner SHA/current cached corpus SHA 검증, original baseline 12조건/36 반복 검증, pinned image/running=true, 당시 host MemAvailable=14058MiB. Bench 시작 watch 기록 14050MiB, 이후 minute 1~15의 관측 범위 14170~14746MiB (출력된 점검치); 이것은 전체 운영 무간섭이나 OOM 방지를 증명하지 않는다.
- **승인된 단 1회 신규 벤치 완료**: `PASS_PROVISIONAL_PRE_B_36`, **12 conditions × 3 measured = 36**, 기존 서비스 대상, 원본 Baseline과 별도 private staging에 보존. 신규 `result.json` 보고된 SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d`. 로그는 래퍼의 검증 완료 선언을 포함하지만 새 raw 파일 바이트의 독립 재해시는 이 GitHub 문서 갱신 과정에서 수행하지 않았다.
- **승인 소진**: 위 1회가 실행되었으므로 `scripts/phase6-ab-provisional-run.sh --execute` 및 레거시 benchmark 직접 호출을 **재실행하지 않는다**. 실패/재검증 명목으로 자동 추가 API/GPU 부하도 금지.
- **비교 범위**: 역사적 Gutenberg corpus 원본 SHA 및 sampling/KV/cache 동일성 미확정. 과거 pre-blazux↔금번 결과 strict A/B 성능 개선율/회귀율을 주장할 수 없다. 공식 **P6-D NOT_RUN**, **P6-B/C NOT_RUN/BLOCKED**. 결과 원본/비공개 environment/guard logs/개별 컨테이너 ID·로컬 절대경로를 공개 GitHub로 올리지 않는다.

### 기존 운영 모델 신규 PROVISIONAL PRE-B 공개용 12조건 요약

다음 숫자는 래퍼가 사용자 DGX 콘솔에 보고한 **조건별 평균/추정 요약**이다. 개별 36회 raw records는 GitHub에 올리지 않았고, 아래 수치를 과거 Baseline과 strict 개선율로 비교하지 않는다.

| Depth | PP | TG | PP 추정 tok/s | TG decode tok/s | E2E TTFT (ms) |
|---:|---:|---:|---:|---:|---:|
| 0 | 2048 | 128 | 667.173 | 32.778 | 3236.184 |
| 0 | 2048 | 256 | 668.434 | 30.946 | 3275.206 |
| 0 | 8192 | 128 | 1455.77 | 33.2 | 6572.308 |
| 0 | 8192 | 256 | 906.417 | 36.713 | 9204.701 |
| 4096 | 2048 | 128 | 826.221 | 31.563 | 7655.009 |
| 4096 | 2048 | 256 | 985.086 | 32.315 | 6512.844 |
| 4096 | 8192 | 128 | 876.705 | 33.689 | 14179.975 |
| 4096 | 8192 | 256 | 885.994 | 31.551 | 14132.565 |
| 16384 | 2048 | 128 | 852.802 | 30.726 | 21828.964 |
| 16384 | 2048 | 256 | 841.979 | 32.611 | 22053.947 |
| 16384 | 8192 | 128 | 935.012 | 32.378 | 26441.901 |
| 16384 | 8192 | 256 | 1013.813 | 30.996 | 24951.241 |

**승인된 1회 종료 마커**: `PHASE6_AB_NEW_12X3_BENCH_RECORDED_EXISTING_SERVICE_NOT_A_PASS`, `PHASE6_AB_LIVE_BENCH_EXECUTION_COMPLETED`. P6-A `BLOCKED`, 공식 P6-D `NOT_RUN`, 역사적 strict A/B `UNVERIFIED`. 영구 Baseline raw result 불변.

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


Prepared on Phase6 branch from Phase5 docs-only parent `11fd777e2c49c030eee671133ab0af3a3ca9c26d`.
Phase6 offline code now has DGX operator evidence on exact SHA `0513b118260047b9965e16b20bdadf690c112c5d` (15/15, Source186/186). No GPU, CI, model startup, serving/API inference, benchmark or patch execution.

| Item | Status | Evidence |
| --- | --- | --- |
| P6-A real active configuration | BLOCKED | A2 Docker metadata PASS at 0513b118; A3a passive resources OBSERVED_METADATA_ONLY at exact 100ffb3; A3b-0 synthetic prep NOT_RUN on new HEAD; active class/cache/Mamba group/pointers NOT_OBSERVED |
| P6-B GPU state/rollback/prefix | BLOCKED | GPU execution not approved; requires P6-A |
| P6-C MTP/tool/parser/Responses | BLOCKED | model/API execution not approved; requires P6-B |
| P6-D performance/stability | BLOCKED | benchmark not approved; requires all correctness gates |
| GitHub Actions | NOT_RUN | user prohibited CI |
| Phase6 DGX offline source/tests | PASS at exact DGX source | **57/57** unittest and **200/200** Source Manifest at SHA `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`; upcoming P6-AB planner code expected **70/204** remains NOT_RUN |
| Phase5 offline exit | PASS (historical) | exact DGX-tested SHA `780b780fc7572226a6a9ff2e52cd8e1921c8738b`, never attribute to Phase6 HEAD |

Record future runs with exact tested SHA, environment fingerprint, raw redacted evidence, each required oracle, failure/blocked reason, cleanup and final status. Do not overwrite history.

## Historical A3a execution checklist (fulfilled at 100ffb3)

- New exact-code SHA: resolve from GitHub after atomic manifest commit; do not copy 0513b118 test results to newer HEAD.
- Observed trace: 28/28 Phase6 unittest, Source 190/190 (actual DGX operator result at 100ffb3); `PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED` and final user shell marker only after execution.
- Record host MemAvailable/total and optional GPU telemetry availability as momentary passive observations. Do **not** infer safe model coexistence or activate GPU. P6-A real runtime BLOCKED regardless of passive outcome.

## P6-A3a evidence interpretation / candidate next Gate

`gpu_telemetry.status=PARTIAL` with total/free/used `null` does not imply error or zero available GPU bytes; 0.0% reported utilization is a point measurement, not resource isolation proof. `host_memory.mem_available_mib=14085` may change and cannot establish safety to allocate GPU unified memory. `deployment.explicit_container_memory_limit_mib=null` means no explicit Docker limit observed; it does not imply unlimited available RAM. No runtime Scheduler/CacheConfig/MambaSpec/physical state evidence was obtained. Therefore `P6-A runtime BLOCKED` is the required classification. Only prepare P6-A3b observer plan; do not run Docker exec/run, attach to service, start model, or run GPU/HTTP/benchmark/CI.

## Next Phase6 offline bundle status (expectation, NOT an execution result)

- New files: one pure stdlib fixture/group arithmetic projection, one synthetic fixture JSON, 17 new CPU-only unit tests, two Bash entrypoints (prepare + Docker preview-only), and A3b-0 runbook. The Phase6 next combined Gate expects 45 unittest cases and Source196 tracked files, subject to operator evidence. No Docker runtime execution path was enabled.
- A `SYNTHETIC_GEOMETRY_ONLY_NOT_RUNTIME` output is not P6-A PASS and no actual Scheduler, CacheConfig, MambaSpec constructor is invoked. P6-A real runtime, P6-B/C/D continue BLOCKED/NOT_RUN.

## P6-A3b-0 operator DGX result (2026-10-28)

- `git pull --ff-only` from 100ffb3 to exact `7dc77164447bdd272b3ff791341d8ec5379a1edd`, Bash syntax checks successful, `Ran 45 tests`, `OK`, `PASS_SOURCE_ONLY: 196 tracked file(s)` twice, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- CPU synthetic input output: 2 fake groups, Mamba group count1, naive LCM32/GCD16, artificial Mamba32/cache16, `SYNTHETIC_GEOMETRY_ONLY_NOT_RUNTIME` and `p6_a_runtime_status=BLOCKED`. No real scheduler/Mamba values or bug established.
- Preview-only `PHASE6_A3B_CPU_CONTAINER_PROPOSAL_ONLY_NOT_EXECUTED`, `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME`, final `PHASE6_A3B0_DGX_PREPARATION_VERIFIED_NO_RUNTIME`. No GPU/model, Docker CPU-run, CI or benchmark executed.

## Upcoming approved P6-A3b-1 run — NOT_RUN on new HEAD

- Approval strictly one 1CPU/512MiB locked image read-only source SHA/AST ephemeral container, host + Docker metadata guards. Expected Phase6 unit 57, Source200; do not claim actual PASS until DGX log. Mark source SHA/AST success `PASS_PINNED_SOURCE_AST_ONLY`, not P6-A active runtime.
- If pinned source drift/permissions/resource margin/runtime unavailable, report BLOCKED without retry or weakening isolation. P6-A real ABI/B/C/D stay BLOCKED.

## 2026-10-28 DGX P6-A3b-1 operator result (exact tested SHA)

- Dedicated Phase6 checkout fast-forward from 7dc771 to `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`; full phase6 unittest **57/57 OK**, Source Manifest **200/200 PASS**; `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- One approved ephemeral CPU-only source SHA/AST scan: `P6-A3B1_BEFORE=PINNED_LEGACY_RUNNING`, `P6-A3B1_AFTER=PINNED_LEGACY_RUNNING`, host MemAvailable **14064 MiB** observed, policy 1 CPU /512MiB memory+total swap/no-network/no-GPU/read-only, 8 AST components, 7 previously pinned source SHA checked, KV resolver AST anchor true but SHA not pinned; `PASS_PINNED_SOURCE_AST_ONLY`, `PHASE6_A3B1_CPU_ISOLATED_PINNED_SOURCE_PASS_NOT_ACTIVE_RUNTIME`, final `PHASE6_A3B1_DGX_SOURCE_PROBE_COMPLETED`. No model inference, actual config reconstruction, GPU, HTTP, benchmarking or operational changes are evidenced.
- **Actual P6-A remains BLOCKED**: Scheduler factory effective branch, `CacheConfig` and each `MambaSpec` block, live block tables and GPU tensor addresses not observed. P6-B/C/D remain NOT_RUN/BLOCKED.

## Intermediate P6-A→B performance checkpoint requested (PLAN_ONLY when originally prepared)

- User requests an additional pre-B performance reference. Existing raw baseline 12×3 36 measurements pre-blazux is already archived. New P6-AB-0 source-only `scripts/phase6-ab-benchmark-plan.sh` validates immutable baseline, original matrix and runner/tokenizer provenance; **not** a new benchmark.
- Planned fresh PRE-B 36 measured runs: after actual P6-A PASS plus **separate** target-specific inference/API/performance approval and isolation, before B changes. Preserve same input+corpus+sampler+cache/KV configuration and raw private artifacts. If missing historic corpus SHA/sampling, report strict old-vs-new comparability BLOCKED and compare fresh pre-B/post-B matched pair instead.
- **DGX operator verified** Phase6 offline **70/70** and Source Manifest **204/204** at exact SHA `fb5deae540812a300cb8404a53a202e505c40577` with a **no-load baseline plan**; no port8000 load or P6-B progression. [P6-AB runbook](BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md).

## Confirmed DGX P6-AB-0 result (exact tested source, not a new benchmark)

- DGX checkout and manifest at `fb5deae540812a300cb8404a53a202e505c40577`: `Ran 70 tests`, `OK`, `PASS_SOURCE_ONLY: 204 tracked file(s)` twice; final `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`.
- Verified existing `results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json`: `original_sha256_match=true`, `SOURCE_BASELINE_MATRIX_VALIDATED` (12×3=36), runner/tokenizer provenance match, PP/TG/depth/concurrency, warmup and 20261027 random seed aligned with published baseline metadata. The checker did not replay the old inputs or reconstruct sampling/KV/corpus.
- `status=PLAN_READY_NOT_EXECUTED`; `pre_b_checkpoint_run=NOT_RUN`, `performance_benchmark_authorized=false`, `p6_a_to_b_transition=BLOCKED_UNTIL_REAL_A_GATE`, `actual_p6_a_runtime_abi=BLOCKED`, `p6_b_runtime=NOT_RUN`, `p6_d_formal_regression=NOT_RUN`; `no_docker_http_gpu_model_or_benchmark_called=true` in planner output.
- Next acceptable evidence: approval-gated **real** active Scheduler/cache/Mamba/group physical state observation before classifying P6-A PASS, then separately authorized fresh PRE-B paired 12×3 measurement without touching historical baseline, legacy server/port or protected files. Historical corpus/sampling/KV gaps remain and no benchmark numeric thresholds are approved.

## P6-A live ABI attempt and provisional PRE-B run requested (new code not DGX run)

User approved actual P6-A attempt through existing loopback `/metrics` + `/v1/models` (only published cache configuration fields can be verified; no process attachment), and approved one resource/identity monitored **existing-service** new 12×3/36 inference workload specifically to validate `scripts/benchmark/run-llama-benchy.sh`. Direct use of old benchmark script is not the permitted entrypoint; use Phase6 guard script.

**Previous DGX-tested SHA** remains `fb5deae540812a300cb8404a53a202e505c40577` with 70/70 unit and 204/204 Source PASS, baseline-lock `PLAN_READY_NOT_EXECUTED`. New GitHub head expected offline 97 tests/211 Source files is **NOT_RUN** until DGX operator log. Running service actual ABI remains `BLOCKED` without Scheduler/Mamba group/GPU pointer evidence. The new live benchmark (when run) shall be tagged **PROVISIONAL_NOT_A_GATE_PASS** and store private raw 36 results in new `phase6-pre-b-provisional` directory; no numerical regression/improvement claims versus historic baseline because its corpus/sampling/KV parity is unresolved. No measured benchmark values exist yet. P6-B/C/D remain NOT_RUN/BLOCKED. [Current runbook](BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md).
