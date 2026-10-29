# P1 Prefix-cache ↔ Blazux 원본 소스/검증 비교 (2026-10-29)

## 고정 비교 대상 및 증거 등급

- **Blazux GitHub `main`:** [`blazux/qwen3.8-Flash-DGX`](https://github.com/blazux/qwen3.8-Flash-DGX) exact HEAD `7e63dbe5761448ea833ed28781c1d32ce0d56f4c`. `Dockerfile`은 공식 `vllm/vllm-openai:v0.32.0` 기반에서 `src/patch_mamba_block_size.py`를 이미지 빌드 중 적용한다. `README.md`/`docs/HOW-IT-WORKS.md`에 **당시 Blazux GB10 실측** 및 버그 원인 기록이 있다.
- **현재 P1:** [`kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark) 작업 브랜치 `feature/blazux-phase6-runtime-gates` 증거 시작 HEAD `eefa476779703964c0e0e87c6c79858862e28806`; 마지막 DGX 실제 GPU 실행은 `f5bcbbfee72a0d8212eb40a786fa1321e5d01efa`였다. P1 고정 Preview `0.1.dev20073+g8e685d198`, pinned source SHA256을 사용한다. `src/preview_p1_prefix_candidate.py`의 `UPSTREAM_PIN`은 Blazux HEAD `7e63dbe5761448ea833ed28781c1d32ce0d56f4c`와 동일하다.
- 두 저장소는 **동일한 오류와 수정 대상**을 공유하지만 같은 vLLM 런타임 코드가 아니다. upstream v0.32 수정/관측 hook/커널을 Preview에 그대로 복사하는 것은 ABI 및 GPU 안전성을 검증하지 않은 작업이다.

## 핵심 구현 차이

| 항목 | Blazux 원본 (source) | 현재 P1 (실 DGX) | 판단 |
|---|---|---|---|
| 근본 원인 | EngineCore가 KV group 최소 block size(8)를 `cache_config.block_size`로 설정하므로 Mamba 1600과 달라짐 | 실제 `cache_config.block_size=8`, `mamba_block_size=1600`, Scheduler effective 1600 | 같은 버그 경로 |
| Mamba seed fix | worker `add_request`: `mamba_block_size` 우선, 예전 소스 fallback `or cache_config.block_size` | SHA-검증 Stage에서 `self.cache_config.mamba_block_size`로 나눗셈 | 의미 동등, 미설정 처리 다름 |
| Scheduler fix | `_mamba_block_aligned_split`: `self.block_size` | 동일 `self.block_size` | 일치 |
| Runtime 검증 | GDN layer-0 + PLE short-conv **Cold 저장 상태 ↔ HIT 복구 상태 체크섬**; 이전 zero restore와 `has_initial_state=True` 불일치 발견 | `idx_mapping → state slot → physical block` 40 *표본* 추출, 실제 버퍼 내용 미비교 | **핵심 누락: 상태 내용 동일성** |
| 출력 정합성 | Blazux 문서상 32/32 greedy completions 동일, 최초 top-5 logprobs 4th decimal 동일, guard counter 0/100 동시 request | 150 token IDs 동일 4회, cache HIT 3회, MTP accepted +400, 수치 gate 1e-4 미달 | 시험환경·정확도 기준이 달라 직접 동일 PASS 불가 |
| 수치 결정성 | v0.32 이미지에 `patch_qsadet.py`의 deterministic persistent_topk와 `patch_qsa_exact_topk.py`를 포함 (실제 적용 확인은 원본 빌드 계약에 근거) | 무 HIT cold control끼리 logprob delta 0.0003318255 > 1e-4; HIT 경로 max delta 0.0004462341 | 캐시 유일 원인 미입증; sampler/수치환경 별도 확인 |
| 운영 | Blazux `./flash`/Docker 이미지 patch, default Prefix ON | 기존 Prefix OFF 서비스 보존, 후보 Docker writable overlay와 port 18080로만 Prefix ON 시험 | P1 서비스 보존 요구 강함 |

## Blazux가 실제로 사용한 결정적 증거

- [`docs/HOW-IT-WORKS.md#prefix-caching-the-root-cause-and-the-fix`](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/docs/HOW-IT-WORKS.md#prefix-caching-the-root-cause-and-the-fix): 수정 전 5,150-token Cold state와 cache-hit의 **상태 체크섬 불일치** 및 `has_initial_state=True`인데 0으로 복구되는 문제를 진단. 수정 후 3,200-token boundary의 cache restore state 체크섬 4.149867426e3가 Cold 저장 상태와 맞았다고 보고. 32/32 동일 출력과 100-request guard counter 0도 기록. **이 값은 P1 실측값이 아니다.**
- [`src/patch_mamba_block_size.py`](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/src/patch_mamba_block_size.py): 실제 2개 코드 포인트를 패치한다. P1 Preview는 기존 Stage 두 파일이 이미 고정 SHA 검증되고 후보 Overlay에만 적용된다는 점을 보존한다.
- [`scripts/smoke-test.sh`](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/scripts/smoke-test.sh)는 간단한 한 토큰 prefill/hit + greedy first-token logprob 비교다. P1 150-token live oracle/무 HIT 대조군을 대체하지 않는다.

## P1 마지막 GPU 결과와 strict 수치 기준

- P1 시험 `f5bcbbfee72a0d8212eb40a786fa1321e5d01efa`: Prefix HIT deltas `[0,6400,6400,6400]`, 150 output token IDs 동일, MTP accepted +400, `batch_row_to_state_slot` 10회, physical entries 40개, `physical_mapping_observed_partial=true`. 원본 동일 Docker ID 및 HTTP 복구 성공.
- Cold↔HIT 최대 logprob 절대차 `0.0004462340730242431`, HIT↔HIT `0.0004495693719945848`, **No-HIT control↔No-HIT control `0.000331825518514961`**; 모두 strict `0.0001` 초과. 따라서 `1e-4`가 현재 모든 비캐시 반복 추론에서도 달성 가능한 기준인지 근거가 부족하다. 이 문서에서 threshold를 완화하거나 GPU PASS로 변경하지 않는다.

## 이번 CPU-only 묶음 작업

1. `src/p1_prefix_state_reuse_contract.py`에 **2종 필수 state (GDN, PLE conv)의 full-state capture/restore, cached block identity, source timing, has_initial_state, 실제 GPU provenance**를 검사하는 fail-closed 계약을 정의했다. **CPU synthetic 자료만으로 `verified=True`를 반환하지 않는다.**
2. `tests/test_blazux_phase6_prefix_state_reuse_contract.py`에서 단절된 증거·없는 HIT·잘못된 block ID·미관측 copy·부분 scalar·cold/hit state hash 불일치 등의 반례를 검증하도록 작성했다. 이 변경 자체는 DGX CPU/GPU **NOT_RUN**.
3. `python3 src/p1_prefix_state_reuse_contract.py --inspect-stage` 는 고정 SHA256인 Stage `mamba_hybrid.py`에서 `add_request`, `_ensure_align_ctx`, `preprocess_state`, `postprocess_state` 코드를 AST로 읽기만 해 저장·복구 직전/직후 실제 ABI 위치를 파악한다. Docker/GPU/모델/원본 파일을 변경하지 않는다.

## P1 종료까지 남은 기술 과제와 허용되는 순서

- **A — Stage 소스 증거:** CPU-only inspector 출력에서 실제 state 저장/복구 전후 함수와 context/Mamba fused-copy 연계를 찾는다. native context가 Stage 이외의 경로에 있다면 정확한 설치 패키지 경로·SHA를 먼저 CPU-only로 확인한다. 공개 Blazux v0.32 경로를 Preview에 추측으로 이식 금지.
- **B — 관측 GPU hook:** 후보에만 bounded **full-state bytes** checksum 계측을 도입한다. Cold state **캐시 저장 완료 직후**와 HIT state **원본 running state에 복사 완료 직후**를 같은 synthetic prompt, Mamba group, physical cached block boundary와 연결한다. GDN/PLE 각각 checksum이 동일해야 하며 `has_initial_state`, cache HIT telemetry, copy timing을 함께 확인한다. 실제 GPU checksum readback 오버헤드와 주소/모델 자료 누출 제한을 사전 검토한다.
- **C — 수치 판단:** 기존 strict `1e-4`는 유지. 같은 후보 GPU 환경의 캐시 없는 반복 추론도 1e-4를 넘으므로 P1 캐시 오류 원인을 분리할 deterministic/FP rounding control을 CPU 설계 → 별도 승인 GPU 창에서 시험. logprob 차이와 토큰 동일성을 분리한다.
- **D — 상태:** `read_candidate_observer().physical_mapping_and_reuse_verified=false`는 계속 유지. 계약 코드에서 형식상 checksum match가 나와도 actual runtime hook audit 및 조건 충족 없이는 이 flag를 True로 올리지 않는다. 새로운 GPU 창, prod stop/start, main/PR/merge, Stage 수정은 별도 승인이 없으며 실행하지 않았다.

## 2026-10-29 DGX Stage 복구 호출 확인과 정확한 운영 이미지 context ABI 검사 준비

- **직전 사용자 DGX 실측:** `c9351e8af2620b4037cf319989f1e37c0cfad1e1`에서 CPU 28+14+13=**55/55 PASS**, Source Manifest **268/268 PASS**, 기존 서비스 `running`, 실제 Stage SHA/read-only preflight PASS, 신규 GPU 없음. `add_request`의 state seed는 `self.cache_config.mamba_block_size` 나눗셈. 다음 실측은 **CPU-only** ABI 검사로 한정.
- **실제 Stage 호출:** `preprocess_state()`의 `preprocess_mamba_align_fused_kernel[grid]` 다음 `ctx.run_fused_precopy(..., input_batch.idx_mapping)` (177~224행). `postprocess_state()`는 Align + `num_computed_tokens` + ctx 조건에서 `ctx.run_fused_postprocess_align(..., idx_mapping)` (306~345행). `_ensure_align_ctx`는 `MambaSpecDecodeGPUContext.create` 후 `initialize_from_forward_context(...,[block_tables[gid] ...])` 호출. **pre-copy는 블록 경계를 넘지 않으면 per-request fast-exit**하므로 이 메서드 호출/HTTP HIT 자체는 실제 `cold_capture→hit_restore` state checksum 증거가 아니다.
- **공개 코드와 실제 이미지 구분:** 공개 vLLM `v0.32.0` `vllm/v1/worker/mamba_utils.py`의 `MambaSpecDecodeGPUContext`는 `state_base_addrs/state_block_strides`를 포인터·stride 메타데이터로 관리하며 `forward_context[layer].kv_cache`에서 state tensor를 조회하고 fused precopy/postprocess Triton kernel을 사용한다. **이 공개 v0.32 구조는 P1의 고정 Preview `0.1.dev20073+g8e685d198`와 동일함이 아직 입증되지 않음**. 따라서 공개 코드의 포인터/텐서 형태를 근거로 GPU hook을 무단 설치하지 않는다.
- 신규 `src/p1_prefix_mamba_utils_probe.py`는 **고정된 원본 Docker image digest**에서 정확히 `v1/worker/mamba_utils.py` 한 소스를 GPU 없이 읽고 SHA256 + AST 메서드/커널 호출·인자·원문을 분석한다. 기존 read-only P1 preflight와 원본 source SHA probe를 선행한다. Docker 플래그 `--pull=never --network=none --read-only --runtime=runc --cap-drop=ALL`, `NVIDIA_VISIBLE_DEVICES=void`, `CUDA_VISIBLE_DEVICES=-1`; model, 운영 Docker container, Stage 변경 없음. `--show-source`는 선택한 7개 함수를 줄번호 포함으로 기록한다. Preview 구현의 클래스·kernel API가 다르면 **fail closed**, 현재의 `physical_mapping_and_reuse_verified=False` 및 strict 1e-4 유지.
- 추가 CPU mock **5개**는 Docker CPU isolation/원본 image pin, AST symbol drift, Triton bracket-call, SHA tamper, 실제 Docker 경로가 mock임을 검증한다. 이는 로컬 격리 mock 5/5 통과 후 GitHub에 반영한 코드이며 **신규 DGX CPU·GPU NOT_RUN**. 다음은 해당 HEAD의 DGX CPU 60/60 및 image source probe 결과를 확보한 뒤 Preview 고유 state-buffer layout/Cold-save/HIT-restore 바이트 캡처 지점 확정. 실제 GPU 정비창 추가 승인 없음.

### GDN/PLE conv window shift 반례 처리 — 후속 CPU 계약 보강

공개 vLLM fused-copy의 convolution 경로에는 `token_bias=num_accepted-1`을 적용해 source window를 shift하는 경우가 있다. state buffer의 원시 바이트가 다르더라도 올바른 복사일 수 있으므로, 현재 CPU full-state checksum 계약은 `token_bias == 0`이고 `copy_semantics == FULL_BLOCK_EXACT`가 실제 evidence로 입증된 경우만 같은 전체 바이트 digest를 직접 비교한다. 바이어스가 0이 아니거나 의미가 unknown이면 `INCONCLUSIVE_WINDOW_SHIFT_OR_COPY_SEMANTICS`으로 보류한다. 이 규칙은 공개 v0.32로부터 얻은 보수적 반례 대비이며, 실제 Preview에서 `MambaSpecDecodeGPUContext` ABI를 검증하기 전까지의 추가 사전 조건일 뿐이다. 후속 Stage runtime hook 감사 없이 live GPU PASS로 승격하지 않는다.

### 2026-10-29 직접 실행 import 실패 원인과 수정

- DGX 검증 HEAD 01d6e7af382815b6fea18a8bed0b8556bbdcb6ab: CPU 61/61 PASS, source 270/270 PASS, Stage/원본 running preflight PASS. 직후 직접 python3 src/p1_prefix_mamba_utils_probe.py --inspect-image --show-source 호출 시 ModuleNotFoundError: No module named 'src'. Mamba utils ABI 분석은 미시작, GPU 및 기존 서비스 변경 없음.
- 신규 수정: 직접 실행 때 repo root 모듈 경로를 설정하며 window.Blocked는 bounded BLOCKED_NO_GPU로 처리. Docker를 호출할 수 없는 PATH에서 직접 실행을 검증하는 CPU 테스트와 blocked preflight 반례 2개 추가. 총 CPU 63개 정의, 새 HEAD DGX_NOT_RUN.
- 권장 호출: python3 -m src.p1_prefix_mamba_utils_probe --inspect-image --show-source. 직접 실행 CLI도 정상 모듈 경로를 확보하도록 수정. 오직 고정 원본 이미지 digest의 GPU 없는 read-only CPU probe만 허용한다.

### 2026-10-29 DGX CPU 62/63 실패 교정: 분리된 legacy.Blocked

- DGX HEAD `ac3830f4d603a9a0ad6f721020d10a9b4a780816`에서 이미지 검사기 CPU **6/7 PASS**, 통합 사전검사 이후 이미지를 읽기 전에 단위시험 `test_direct_script_invocation_imports_project_package_without_docker` 실패. traceback: `window.preflight() → p1_legacy_service_window.inspect() → p1_legacy_service_window.Blocked("DOCKER_INSPECT_FAILED")`, 기존 검사기는 `window.Blocked`만 포착. 이는 **원본 Docker 실패 처리 반례**이며 실제 DGX Docker나 Mamba fused-copy 오류가 아님; 해당 통합 실행은 CPU-only 이후 중단, GPU 미실행.
- 수정: 두 타입 `window.Blocked`, `window.legacy.Blocked` 모두 catch 후 `PINNED_IMAGE_CPU_PREFLIGHT_OR_PROBE_BLOCKED`로 bounded 종료 코드 2. 기존 직접실행 PATH-empty 반례를 유지하고 별도 legacy exception mocking test 추가. 신규 HEAD의 검사기 unit test **8개 정의, DGX_NOT_RUN**. P1 최종 게이트 및 원본 서비스/Stage 변경 없음.
