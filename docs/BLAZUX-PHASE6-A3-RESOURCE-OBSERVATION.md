# Phase6 P6-A3 passive resource observation and active-runtime decision

Status: A3a SCRIPT_PREPARED_NOT_DGX_TESTED; active P6-A remains BLOCKED; GPU/model/CI/operational changes/patch/PR/merge NOT_APPROVED.

## Completed prerequisites (exact operator-tested SHA)

- Dedicated DGX Phase6 checkout at `0513b118260047b9965e16b20bdadf690c112c5d`: offline 15/15, Source186/186 PASS. A2 Docker inspect pinned image running PASS; original baseline result and benchmark-runner Git SHA PASS.
- Current cached Gutenberg corpus SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; historical corpus checksum unavailable, sampler/KV parity unverified. Performance comparisons BLOCKED.
- Previous documentation-only `be7a463274765627d0fd0da3a9d70907c5f0cf83` records this tested SHA. New A3a code is NOT_RUN until user-operated DGX execution.

## A3a scope: metadata and passive telemetry only

Tracked entrypoint: `scripts/phase6-a3-readonly-resources.sh`.

Prerequisites: correct personal fork, exact Phase6 branch/HEAD, clean dedicated checkout, complete manifest. Run Phase6 offline regression once first.

Read-only inputs:
- `/proc/meminfo`: host `MemTotal`, `MemAvailable`, optional swap, in MiB. This is a point-in-time estimate of general memory, **not** free allocatable CUDA/GB10 capacity.
- `docker inspect --type container qwen38-flash-orca-uncensored-bf16-mtp`: only pinned image/running identity and explicit Docker memory limit (if any). No Docker exec, run, stats stream, stop, restart, mount or environment/config disclosure.
- `nvidia-smi --query-gpu=memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits`: optional read-only NVML query. Missing/unsupported/N/A values -> UNAVAILABLE/PARTIAL, **not zero memory, proof of failure, or evidence that a second model will fit**.

All stdout/stderr from tools is suppressed except allowlisted status and numeric fields; never publish full Docker inspect, process command line, container IDs, mounts, keys or model/tokenizer paths.

A3a success requires pinned running Docker identity and valid MemAvailable observation. GPU telemetry may be PARTIAL/UNAVAILABLE on DGX Spark without changing this **metadata-only** observation result. Output marker `PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED`, status `OBSERVED_METADATA_ONLY`, `p6_a_runtime_status=BLOCKED`.

FAIL/BLOCKED: wrong branch/HEAD/origin/dirty tree, manifest mismatch, missing or drifted image identity, inconsistent memory values. Stop; no rollback necessary because no resources were modified. Retain exact DGX tested HEAD; new docs-only commits do not inherit tests.

## Mandatory A3b approval decision

A3a CANNOT observe the active Python Scheduler factory result, real `CacheConfig.block_size`, group-specific `MambaSpec.block_size`, effective block tables, GPU state tensor allocations or physical pointer/stride ranges. Source AST or Docker launch flags cannot substitute.

Options for a later independently approved plan:

1. **Non-intrusive existing observability**: only if current system already exposes safe, authenticated and documented effective runtime configuration; no speculative live HTTP probes, ptrace, `docker exec`, process memory scraping, debug attachment or instrumentation without explicit approval. If required fields are absent, mark BLOCKED.
2. **Isolated configuration reproducer**: after separately approving CPU-only container execution, create a bounded no-GPU configuration-construction probe using pinned image/source and same public config. Even if it reconstructs group/spec values, it **does not certify active operational process objects or GPU pointers**. Prove all environment inputs and factory branches equivalent.
3. **Isolated GPU runtime**: only after separately approving GPU/model start and an explicit memory budget or maintenance window. This is required for actual state tensor pointers/strides, physical block-table index bounds and guarded CUDA/Triton correctness. Single DGX Spark / unified memory means no independent guarantee of non-interference from a snapshot. Never stop/replace legacy service or assume free memory based on NVML.
4. P6-B GPU state correctness, P6-C model/API MTP/Tool/Responses, and P6-D immutable 12×3 performance require their own authorization and prior correctness PASS. Predeclared regression limits and baseline corpus/sampler parity are still missing.

### Evidence recording

Record operator-provided terminal output, exact tested commit, host memory snapshot, GPU telemetry availability and non-certification boundaries. Do not report A3a as P6-A PASS; do not claim memory measurements authorize GPU compute.
