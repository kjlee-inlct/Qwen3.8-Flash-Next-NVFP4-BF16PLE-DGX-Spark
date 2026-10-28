# Phase 6 P6-B0: CPU bounds rehearsal / P6-B1 GPU isolation gate

## 2026-10-28 DGX B0 실제 전체 오프라인 PASS — SHA 고정 영수증

- **DGX 실행 소스 SHA**: `3aa40292f96427d3592ebdba971b31484c2a6079` (`feature/blazux-phase6-runtime-gates`), 사용자 제공 전체 터미널 로그에서 `6afade4..3aa4029` fast-forward 확인.
- `bash scripts/phase6-gate.sh`: **`Ran 124 tests in 0.017s`, `OK`**. `PASS_SOURCE_ONLY: 220 tracked file(s)` / `HEAD=3aa40292f96427d3592ebdba971b31484c2a6079`. 종료 `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`.
- `bash scripts/phase6-b0-offline.sh`: Source Manifest **220/220 PASS를 한 번 더 확인**, **`Ran 25 tests in 0.001s`, `OK`**, 합성 `operations_checked=2`, `tables=2`, `states=2`, `status=CPU_SYNTHETIC_ONLY_NOT_GPU`. `PHASE6_B0_CPU_SYNTHETIC_REHEARSAL_NOT_GPU_PASS`, `PHASE6_B0_OFFLINE_PREPARATION_COMPLETE_NO_GPU_NO_ABI_PASS`, 사용자 최종 마커 `PHASE6_B0_DGX_OFFLINE_VALIDATION_DONE_NOT_GPU_PASS`.
- **판정**: `P6_B0_CPU_SYNTHETIC=PASS_AT_EXACT_SHA`; `P6_A_ACTIVE_ABI=BLOCKED_MISSING_IN_PROCESS_EVIDENCE`; `P6_B1_GPU=NOT_RUN`; 정식 `P6_B=BLOCKED`; `P6_C/D=NOT_RUN`. CPU 합성 복사·bounds 검증은 실제 CUDA/Triton, rollback, prefix, active physical GPU state 검증이 아니다. 운영 Docker, GPU/model, HTTP/inference, benchmark 또는 blazux patch 실행 증거 없음.
- 이 영수증의 **후속 GitHub 문서·Manifest 커밋 자체는 DGX에서 재시험되지 않았다**. 이전 PRE-B 벤치 1회 승인 소진 상태 유지; 재실행 금지. B1은 안전한 격리/GPU 자원 가용성과 별도의 명시적 실행 승인이 있기 전까지 설계 및 무부하 준비에 한정.

---


Date: 2026-10-28 (KST). Branch: feature/blazux-phase6-runtime-gates.

## Decision: begin B preparation while A remains BLOCKED

The user requests progressing Phase 6 B despite unresolved active legacy ABI. This changes **work scheduling**, not correctness acceptance. The actual active P6-A remains BLOCKED_MISSING_IN_PROCESS_EVIDENCE; **formal P6-B GPU PASS, promotion to P6-C and official P6-D remain forbidden**. The current approval covers independent B preparation and CPU-only synthetic validation. It does not authorize operating-service attach/exec/restart/stop, a second GPU model, live inference, benchmark, blazux patch, CI or merge.

Record independent classifications: **P6-B0 CPU_SYNTHETIC** can PASS on its own evidence, but **P6-B1 GPU_RUNTIME=NOT_RUN** and **P6-B FORMAL_GATE=BLOCKED_UNTIL_A_AND_REAL_GPU_EVIDENCE**. Do not change src/phase6_gate.py P6-B's fail-closed default or fabricate P6-A snapshot provenance.

## Prior evidence and why B0 is different

- Phase5 exact DGX-tested SHA 780b780fc7572226a6a9ff2e52cd8e1921c8738b passed 310/310 offline unit, Source177/177, G1–G8 source and synthetic CPU oracles. The 25,528 embedded checks were NOT independent GPU tests. CUDA execution, real grouped GPU state and prefix/rollback correctness remained unverified.
- Last Phase6 DGX-tested SHA 6afade42bdf40f73c644f96ecbc17b4f3ad36f7f: 99/99 unit and Source216/216 PASS. Subsequent documentation-only SHA 419ab608626b0c0b8e79eeb754abed99ee558368 had GitHub manifest verification but not DGX operator tests.
- Previously observed read-only /metrics startup cache block_size=8 is not selected Scheduler/Mamba group or physical state evidence. Existing pre-B benchmark 12×3 was completed ONCE and cannot be rerun.
- **New B0** contributes independent, pure Python synthetic physical-block copy bounds testing. It does not duplicate Phase5 source scans and does not assert any real CUDA kernel result.

## B0 implementation and exact synthetic scope

- src/phase6_b0_cpu_bounds.py: strict bounded Python dict schema for 1–8 int32 group tables, logical columns and row_stride_elements, physical IDs with unused -1 sentinel, 1–64 physical block states labeled Conv-SD/Conv-DS/temporal, byte block strides/payloads and up to 64 KiB synthetic backing storage per state, 1–128 explicit byte-range copy operations.
- Validate whole transaction before writing: false bool-as-int, negative/unallocated physical IDs, selected -1, state allocation underflow, wrong table dtype/row width/stride, payload or backing storage overrun, ambiguous alias overlap, excess/unknown fields -> reject. Copy only cloned buffers and report aggregate counts, not synthetic contents.
- tests/test_blazux_phase6_b0_cpu_bounds.py: 25 CPU-only regressions for multiple groups, distinct table row/request slot, byte vs int32 element stride, padding and guards, Conv-SD/Conv-DS labels, temporal synthetic payload copy, sentinel/OOB, exact alias no-op, overlap rejection, zero length, fail-atomic input preservation and forbidden runtime imports.
- scripts/phase6-b0-offline.sh: fail-closed exact Phase6 clean branch + complete Source Manifest, only targeted 25 unit tests + synthetic demo. Existing scripts/phase6-gate.sh naturally runs all Phase6 test files, including these 25.
- **Critical limits:** state kind labels are not active Conv/temporal shape reconstruction. Explicit byte offsets do not prove token bias or Triton aligned/misaligned tile partitions. Synthetic copy and checks do not prove GPU rollback/prefix/cancel, active physical pointers, memory races or correctness of installed kernels. B0 status is not formal B.

## Safe DGX offline validation (no model, Docker, GPU or HTTP)

Use the dedicated checkout and insert the exact resulting GitHub B0 SHA in the expected pin before running:

~~~bash
(
  set -Eeuo pipefail
  cd "$HOME/Workspace/llm/blazux-phase6-gates"
  test "$(git branch --show-current)" = "feature/blazux-phase6-runtime-gates"
  test -z "$(git status --porcelain=v1 --untracked-files=all)"
  git pull --ff-only
  test "$(git rev-parse HEAD)" = "REPLACE_WITH_COMMITTED_PHASE6_B0_SHA"
  bash scripts/phase6-gate.sh
  bash scripts/phase6-b0-offline.sh
  echo "PHASE6_B0_DGX_OFFLINE_VALIDATION_DONE_NOT_GPU_PASS"
)
~~~

**Expected**, not yet DGX-verified: full Phase6 124 tests (= prior 99 + 25); Source Manifest 220 entries (= prior 216 + four new tracked files: B0 code, test, wrapper, this runbook). B0 wrapper separately re-runs the targeted 25 CPU unit tests plus synthetic demo. It does not touch live inference or execute GPU.

## P6-B1 isolated GPU correctness — NOT AUTHORIZED / NOT_RUN

**Current feasibility STOP:** one DGX Spark is already serving the pinned model; earlier host MemAvailable near 14 GiB while GPU NVML reported memory total/free/used N/A. These values do NOT certify safe unified-memory headroom to launch a second model. No parallel GPU model or container is allowed at present.

Required eventual B1 steps, each separately authorized:

1. **Preflight**: explicit isolated target, pinned source/image/weights/cache, verified unified/host memory headroom and model allocation budget, unique namespace/port, private result path, operating service health, stop/rollback conditions. Never silently stop or replace the operating model.
2. **Evidence provenance**: isolated candidate observation is not actual running legacy P6-A. B1 experimental GPU evidence remains EXPERIMENTAL_ISOLATED until required real target-specific P6-A evidence exists; it cannot become formal B automatically.
3. **Independent CPU reference**: model Conv SD/DS, temporal, multi-group, V1/V2 batch-row vs request-slot, padding/sentinel, unequal cache vs Mamba block sizes, token bias and uint64 tiled/byte fallback. Use prior Phase5 G1–G8 as source/fixture baseline; compare true GPU implementation against independent byte-exact expected results, never same implementation twice.
4. **Guarded GPU run**: guarded canary/neighbor allocations, physical ID/table/stride/storage provenance, pre/post hashes, request isolation, deterministic repeat, alias and rollback invariants, OOB/CUDA error observation. Prefix-hit, cancellation and MTP accepted-token cases require distinct live-workload/observer authorization. No raw GPU pointer or prompt data on public Git.
5. **Stop**: any resource shortfall, service identity drift, canary violation, CUDA error, physical index OOB, source/config mismatch or operating interference -> abort only isolated experiment, keep private evidence, no automatic retry.

| Scope | Allowed classification |
| --- | --- |
| B0 synthetic/offline tests on exact DGX SHA | B0 CPU_SYNTHETIC PASS only |
| B1 independently approved isolated CUDA/model run | B1 EXPERIMENTAL_ISOLATED, not active legacy A |
| Formal B after real A evidence + real GPU correctness | P6-B formal PASS may be considered, never automatic |

**No blazux runtime patch, operational change, main/P0/Phase1–5 edit, history baseline overwrite, PR/CI/merge, or benchmark rerun in B0.**
