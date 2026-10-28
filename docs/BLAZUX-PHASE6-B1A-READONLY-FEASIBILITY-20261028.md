# Phase6 B1a — single-DGX passive resource feasibility (2026-10-28)

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
