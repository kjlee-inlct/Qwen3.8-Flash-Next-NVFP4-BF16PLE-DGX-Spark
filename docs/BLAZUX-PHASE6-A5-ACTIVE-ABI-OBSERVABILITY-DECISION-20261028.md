# Phase 6 P6-A5: active ABI observability decision (2026-10-28)

## 2026-10-28 DGX A5 실제 오프라인 회귀 영수증 — 99/99·Source216/216 PASS

- **검증된 DGX checkout exact HEAD**: `6afade42bdf40f73c644f96ecbc17b4f3ad36f7f` (`feature/blazux-phase6-runtime-gates`), `git pull --ff-only`로 `882b590... → 6afade4...` fast-forward 확인. `bash scripts/phase6-gate.sh`: `Ran 99 tests in 0.016s`, `OK`; `PASS_SOURCE_ONLY: 216 tracked file(s)`와 동일 HEAD; 종료 마커 `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, 사용자 래퍼 `PHASE6_A5_OFFLINE_SOURCE_VALIDATION_COMPLETED`를 확인했다.
- **정확한 검증 범위**: Python 오프라인 회귀 및 Source Manifest의 tracked path/mode/blob 무결성만 검증했다. 로그에 Docker 내부 객체 관찰, GPU/모델 추론, 커널 실행 또는 실시간 ABI 결과는 없다. 이 영수증을 P6-A 활성 ABI 합격으로 승격하면 안 된다. **P6-A ACTIVE `BLOCKED_MISSING_IN_PROCESS_EVIDENCE`; P6-B/C/D `NOT_RUN`.**
- 사전 승인된 PRE-B 벤치 1회는 이미 소진되었으므로 재실행하지 않는다. 다음은 [P6-A5 관측 가능성 정본](BLAZUX-PHASE6-A5-ACTIVE-ABI-OBSERVABILITY-DECISION-20261028.md)의 별도 승인 필요 검증 경로만 유지한다. 이 로그를 기록한 **후속 문서·Manifest 커밋 자체는 DGX 미시험**으로 분리한다. 운영 Docker/기존 모델/포트/원본 결과 변경, PR/CI/merge 없음.

---


**Decision**: `P6_A_ACTIVE_ABI=BLOCKED_MISSING_IN_PROCESS_EVIDENCE`. Not an observed ABI failure, not a benchmark failure, and not an approval to change or restart the operational vLLM service. Current GitHub source checkout and archived PRE-B results do **not** change this gate verdict.

## 1. Exact evidence already obtained

- Exact DGX-observed implementation SHA `d031d4196eab1f5f1603d6541eaf5a31b02192c0`: Phase6 unit `99/99`, source manifest `211/211`. Fixed running Docker image/StartedAt/ID before/after and served model ID matched. Existing read-only `GET /metrics` returned a single `vllm:cache_config_info` startup series with `block_size=8`, `enable_prefix_caching=false`, `gpu_memory_utilization=0.8`. This is **published cache configuration metadata**, NOT direct evidence of the active Python Scheduler or state buffers.
- Exact separate DGX-tested docs SHA `882b590119afcdadb06afe9938c7f3e10c866656`: offline Phase6 `99/99`, Source Manifest `212/212` PASS. The later benchmark archival HEAD `72153391313dc56014512605545868ea12a36559` was verified on the GitHub side (manifest `215/215`), **not** on DGX. Test evidence is SHA-specific.
- The one operator-authorized PRE-B benchmark completed once, `12 conditions × 3 measured=36`. Its byte-identical `result.json` is archived under `results/llama-benchy/phase6/pre-b-provisional/20261027T234639Z/` with independently verified SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d`. **The authorization is consumed; never re-run under this approval.** It is a provisional existing-service result, not formal P6-D or actual P6-A state proof.

## 2. Why the active ABI is still blocked

The source proves *possible implementation paths*, but not which path the running worker took. Existing allowed endpoints `GET /v1/models` and `GET /metrics` do not expose the following live process-owned state:

| Required real-world oracle evidence | Source/producer candidate (from prior installed-image source AST/body audits) | Current state |
| --- | --- | --- |
| Selected Scheduler class, resolved factory branch, actual scheduler/hash/cache block units | `config/scheduler.py:SchedulerConfig.get_scheduler_cls`; `v1/engine/core.py`; `v1/core/kv_cache_utils.py:resolve_kv_cache_block_sizes`; `v1/core/sched/scheduler.py` | `NOT_OBSERVED` |
| Actual grouped KV/Mamba specs, per-group `block_size`, group mapping and DCP/hash handling | Resolved `kv_cache_config.kv_cache_groups`, each group's `kv_cache_spec` and `MambaSpec` | `NOT_OBSERVED` |
| Real block-table group/row/column layout, int32 dtype, per-row element stride, logical→physical IDs including sentinel/unused IDs | `v1/worker/mamba_utils.py:MambaSpecDecodeGPUContext._populate_metadata`, and actual live table allocations | `NOT_OBSERVED` |
| Real state tensor device, dtype/element size, shape, per-dimension strides, storage base/capacity, state→group map and block stride **bytes** | `_populate_metadata` uses `state.data_ptr()`, `state.stride(0)*state.element_size()`, `state.numel()`, and `state_group_indices` | `NOT_OBSERVED` |
| Real token→logical column→physical ID→byte address window bounded by allocation for each applicable state/layout, including copy widths and token bias | `_copy_mamba_state_block` reads `block_table_base+column`, then calculates `state_base_addr + physical_id * state_block_stride` | `NOT_OBSERVED` |

Do not assume `cache_config.block_size == scheduler_block_size == hash_block_size == MambaSpec.block_size`; differing units may be valid depending on resolver/factory/group rules. The observed startup `block_size=8` cannot be propagated into unobserved group/scheduler values.

For each **valid, in-use** physical ID and state, a future independent oracle must prove, in consistent byte units, at least `0 <= physical_id < physical_blocks`, `0 < payload_bytes <= block_stride_bytes`, and `physical_id * block_stride_bytes + payload_bytes <= allocated_bytes`; also check group-local mapping, logical column bounds, row-stride/dtype, layout-specific offsets, token bias, zero-length and sentinel paths. Checking numeric inequalities on synthetic fixtures is not live attestation. Raw pointer addresses, user prompts and all container secrets must stay private; a trustworthy in-process observer may report verified invariants and redacted type/shape/stride counts with scope/provenance, instead of raw pointer values.

**Critical limitations:** Actual block-table contents and occupied rows may be request-dependent. An idle service or startup metric cannot prove real copy bounds under active hybrid/MTP processing. A proposed future observer cannot silently create synthetic request rows or send model inference just to turn an unknown into a PASS.

## 3. Exhausted current safe observability surface

- **Allowed and already exercised:** exact pinned `docker inspect` metadata, checked-in installed-source SHA/AST/body audits, source-manifest and CPU-only tests, `GET /v1/models` and `GET /metrics`. All are read-only and may affirm deployment/source provenance, but cannot inspect Python heap-owned Scheduler/Mamba/GPU tensor state.
- **No available retroactive interface verified:** neither current source-only results nor the allowed HTTP output establishes a pre-existing process-internal ABI snapshot API. Searching more Prometheus counters is not equivalent to state introspection; process memory/ptrace/attach/`docker exec` is prohibited.
- **Approved source/CPU inspection cannot certify this:** earlier one-shot CPU-only isolated SHA/AST probe verified the pinned image source but did not import or construct active Scheduler/Mamba or execute GPU kernels.

Therefore **no amount of repeated passive metadata polling can itself produce a full P6-A PASS** under the existing approval.

## 4. Next real verification paths — separate explicit scope required

**Preferred for protecting the current operational service: deferred, maintenance-window, in-process attestation.** At a separately authorized *future* deployment, prepare a version-pinned, minimal, read-only diagnostic **inside the actual EngineCore/worker lifetime**. It must capture the selected factory/class, effective cache/scheduler/hash/Mamba group values, table metadata and relevant live physical indices, GPU state shape/strides/storage range, calculate index/byte bounds without copying user token/state data, and produce a signed-or-hashed redacted local artifact. Instrumentation itself and any restart/new container are **not authorized in this phase**. The current service should remain untouched.

**Alternative, with a separately approved and resource-assessed isolated GPU/model run:** reproduce the pinned candidate in an isolated environment, capture real grouped-state/tensor geometry using the same independent ABI oracle, and gate it as **ISOLATED_CANDIDATE_ABI** only. This cannot establish the historical running legacy process's actual selection/state and cannot be silently promoted to its `ACTIVE_LEGACY_ABI` PASS. No current GPU memory headroom or safe co-residency is certified on the single DGX Spark; do not launch an additional model under current authority.

**Not an acceptable workaround:** manually fabricating a JSON snapshot for `src/phase6_gate.py --snapshot`; its `PASS` applies only to an operator-supplied snapshot's numeric contract, not its origin or active DGX run. Similarly do not downgrade P6-A to a config-only Gate to let P6-B/C/D proceed.

## 5. Acceptance/stop conditions for later explicit approval

1. Identify the target whose ABI is asserted (unchanged **active legacy** versus an explicitly segregated **isolated candidate**), exact image/source/config/observer provenance, and selected scheduler branch.
2. Securely collect the *actual*, same-process group/block table/tensor geometry with snapshot consistency, and separately identify missing values and idle/unused/sentinel rows; reject stale, simulated or cross-process evidence.
3. Implement an independent, version-pinned CPU arithmetic/bounds oracle (not the same function-under-test), with multi-group, Mamba Conv DS/SD, temporal, padded strides, prefix, token-bias and physical-ID boundary cases. Treat missing dynamic exercise as `BLOCKED` rather than PASS.
4. Keep all private addresses and host/worker IDs/redacted raw state local; export only allowlisted evidence, aggregate counts, provenance hashes and pass/fail indicators. Confirm no service identity drift and no unapproved inference.
5. If the observer does not exist or any required field/group/bounds is inaccessible: `BLOCKED`. On an independently reproduced impossible index/range: `FAIL`. Only complete target-specific actual evidence with every applicable bound validated permits `PASS`; then, and only after separate approvals, consider P6-B.

## 6. Immediate no-load operator action (optional)

For the current, unmodified Phase6 checkout, `bash scripts/phase6-gate.sh` is an **offline regression only**. It must not be interpreted as P6-A actual runtime attestation. An ordinary `bash scripts/phase6-a-live-observe.sh` is a separate, strictly passive metadata observation and will correctly continue to say `P6-A=BLOCKED` unless a genuine new in-process channel exists. **Do not run the historical benchmark again.** A new Phase6 docs/Manifest Git HEAD receives no new DGX PASS until the operator executes the offline gate and returns the exact SHA-specific result.

**Current decision**: finish the current-safe P6-A observability feasibility analysis; retain `P6-A ACTIVE=BLOCKED`, `P6-B/C/D=NOT_RUN`, `NO_PATCH_OR_NEW_MODEL_OR_BENCH`, and require separately explicit approval before any live hook, process attach, container restart or isolated GPU run.
