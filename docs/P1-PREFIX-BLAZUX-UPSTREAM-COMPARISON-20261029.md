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
