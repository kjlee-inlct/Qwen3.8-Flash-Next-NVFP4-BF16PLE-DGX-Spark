# Phase6 B1a — single-DGX passive resource feasibility (2026-10-28)

## 2026-10-28 DGX P6-B1a 실제 무부하 관측 완료 — 147/224 PASS, GPU 미인증

- **정확한 DGX 테스트 소스 SHA:** `37b883793bdd33f8aa2d4810947a94fef3aa5c20`, `feature/blazux-phase6-runtime-gates`. 사용자 제공 전체 DGX 실행 로그에서 `git pull --ff-only`가 `이미 업데이트 상태`이며, 사용자 `git rev-parse HEAD` pin 검사 이후 종료 마커까지 성공했음을 확인.
- **Phase 6 오프라인 검증:** `Ran 147 tests in 0.018s` / `OK`; `PASS_SOURCE_ONLY: 224 tracked file(s)`를 `scripts/phase6-gate.sh` 및 B1a 래퍼에서 **2회**, 동일 HEAD에서 확인. `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- **B1a 실제 passive snapshot:** `status=PASSIVE_METADATA_COLLECTED_NOT_GPU_READY`, `pinned_legacy_identity_stable=true`, `reasons=[]`; `host_available_mib_before=14620`, `after=14609`, **8192 MiB는 읽기 전용 메타데이터 검사 보호 하한이지 GPU 할당 보증치가 아님**; `gpu_telemetry_scope=PARTIAL` (NVML 완전한 메모리 telemetry 미확보). `unified_memory_headroom_proven=false`, `second_model_feasible_proven=false`, `gpu_allocation_authorized=false`. 개인 컨테이너 ID/시작 시각·비공개 상태 원문은 기록하지 않음.
- **실제 종료 마커:** `PHASE6_B1A_PASSIVE_FEASIBILITY_DONE_NOT_GPU_APPROVAL` → `PHASE6_B1A_READONLY_METADATA_CHECK_COMPLETED_NOT_GPU_PASS` → `PHASE6_B1A_DGX_PASSIVE_OBSERVATION_FINISHED_NO_GPU`.
- **Gate 판정:** `P6_B0_CPU_SYNTHETIC=PASS_AT_PRIOR_SHA_3aa4029`, `P6_B1A_PASSIVE_METADATA=OBSERVED_AT_SHA_37b8837`; **`P6_A_ACTIVE_ABI=BLOCKED`, `P6_B1_REAL_GPU=NOT_RUN`, `P6_B_FORMAL=BLOCKED`, `P6_C_D=NOT_RUN`**. 이 관측은 CUDA/Triton kernel 실행, 모델 GPU 메모리 실측, 두 번째 모델 공존성, prefix/rollback/canary 정합성 검증이 아니다.
- **다음 결정:** 승인 없는 GPU 작업이나 두 번째 모델 기동을 금지한다. 다음에는 최소 메모리 사용량이 상한으로 고정된 synthetic CUDA/Triton copy + canary를 **GPU를 전혀 실행하지 않고 설계·소스 검증**할 수 있으나, 실제 실행에는 단일 DGX 서비스 간섭 위험·통합 메모리 할당 예산을 독립적으로 평가하고 사용자에게 정확한 GPU 실행 범위에 관한 **새 명시적 승인**을 받아야 한다. 이미 승인 소진된 PRE-B 36회 재실행 금지. 이 결과를 기록하는 후속 GitHub docs/Manifest 커밋은 DGX 미시험임.

---


**Goal:** continue after B0 124/124 unit + Source220/220 + targeted 25/25 DGX PASS at source SHA 3aa40292f96427d3592ebdba971b31484c2a6079 without bypassing P6-A active ABI BLOCKED or affecting the existing pinned service.

**Decision:** passive A3a-compatible resource/identity observation is allowed, **not GPU execution approval**. P6-B1 CUDA/Triton correctness remains NOT_RUN, P6-B formal BLOCKED, P6-C/D NOT_RUN. Source-prepared until exact-HEAD operator DGX evidence.

## B1a observation source and additional checks

- Reuse pure parsers parse_meminfo and parse_nvidia_smi from src/phase6_a3_readonly_resources.py. Read only /proc/meminfo, one nvidia-smi read-only query for memory/usage/temperature, and two bounded docker inspect --type container queries against the pinned existing legacy container. No Docker run/exec/stats, attach, model, CUDA, HTTP or benchmark.
- Compare opaque Docker ID, pinned image digest, StartedAt, and running status before/after. The identifiers stay private and are never printed or uploaded. Missing identity, changed image or stopped/restarted service -> BLOCKED.
- Both host MemAvailable snapshots must be valid and >=8192 MiB for this **metadata-only audit**. This is not a GPU allocation budget, proof of isolation, or CUDA authorization. Missing/low values -> BLOCKED; no memory allocation is performed.
- NVML N/A, unavailable or unsupported values remain UNKNOWN/PARTIAL, not zero; even full numeric values mean TELEMETRY_ONLY. DGX GB10 shared/unified GPU headroom is not established by NVML alone.
- Only successful status: PASSIVE_METADATA_COLLECTED_NOT_GPU_READY. Always report unified_memory_headroom_proven=false, second_model_feasible_proven=false, gpu_allocation_authorized=false, p6_a_active_abi=BLOCKED, p6_b1_gpu_runtime=NOT_RUN, p6_b_formal_gate=BLOCKED. There is no execute/CUDA flag.

Files: src/phase6_b1_readonly_feasibility.py, tests/test_blazux_phase6_b1_readonly_feasibility.py (23 new CPU stdlib tests), scripts/phase6-b1a-readonly-feasibility.sh. Expected Phase6 147 unit cases (prior 124 + 23), tracked Source Manifest 224 (prior 220 + four new files); expected counts are NOT actual DGX results.

## DGX operator-only, no-load verification

~~~bash
(
  set -Eeuo pipefail
  cd "$HOME/Workspace/llm/blazux-phase6-gates"
  test "$(git branch --show-current)" = "feature/blazux-phase6-runtime-gates"
  test -z "$(git status --porcelain=v1 --untracked-files=all)"
  git pull --ff-only
  test "$(git rev-parse HEAD)" = "REPLACE_WITH_COMMITTED_B1A_SHA"
  bash scripts/phase6-gate.sh
  bash scripts/phase6-b1a-readonly-feasibility.sh
  echo "PHASE6_B1A_DGX_PASSIVE_OBSERVATION_FINISHED_NO_GPU"
)
~~~

### Evidence and stop table

| Evidence | Accept | STOP/interpretation |
| --- | --- | --- |
| Exact feature branch and clean Source Manifest | 224/224 on exact SHA | Dirty/changed tree -> STOP |
| CPU Phase6 suite | Expected 147/147, await log | Failure -> STOP, no GPU |
| Docker running/ID/image/StartedAt | Same before/after | Missing/drift -> BLOCKED, do not restart |
| Host MemAvailable before/after | Two valid values >=8192 MiB | Unknown/low -> BLOCKED, no floor relaxation |
| NVML | PARTIAL, UNKNOWN, or TELEMETRY_ONLY | Never means GPU ready |
| Marker | PHASE6_B1A_READONLY_METADATA_CHECK_COMPLETED_NOT_GPU_PASS | Scope: passive only |

Keep raw Docker inspect, identifiers, host paths, environment and sensitive logs private. Export only the allowlisted status/numeric values and exact tested SHA. No automatic retries.

## Actual B1 GPU execution — still separately scoped and unauthorized

The previous A3a MemAvailable near 14085 MiB and NVML memory fields N/A cannot establish GPU coexistence safety on one DGX Spark.

For a later separately authorized experiment, consider **small bounded isolated synthetic CUDA/Triton copy with canary buffers, without loading a second language model**, before any full model GPU test. Even the smallest GPU test can contend with the operational service and needs independent maximum allocation budget, snapshot consistency, identity+health guards, isolation, stop-and-rollback plan and explicit operator approval. It cannot certify the active legacy P6-A ABI or all of P6-B.

An actual model/Mamba path test requires later resource-scoped maintenance-window authorization. No GPU tensor allocation, model startup, Docker run/exec/restart, port change, inference, benchmark or blazux patch is permitted by this B1a preflight. Formal P6-B remains BLOCKED pending actual A and GPU state evidence.
