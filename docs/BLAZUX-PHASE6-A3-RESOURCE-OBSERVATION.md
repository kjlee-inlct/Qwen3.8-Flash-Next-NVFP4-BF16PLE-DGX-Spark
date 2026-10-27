# Phase6 P6-A3 passive resource observation and active-runtime decision

## 2026-10-28 Phase6 P6-A3a DGX 실측 및 다음 진입 경계 — 최신

- **DGX 사용자가 실제 실행한 SHA**: `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`; 전용 `~/Workspace/llm/blazux-phase6-gates` checkout fast-forward 후 Phase6 unittest **28/28 PASS**, Source Manifest **190/190 PASS**, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`. 읽기 전용 자원 관찰 결과 `PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED`, 최종 `PHASE6_A3A_DGX_OBSERVATION_COMPLETED`.
- **A3a 관측값 (snapshot)**: 운영 컨테이너 running=true, pinned image digest match=true, Docker 명시적 memory limit 없음(`null`); 호스트 `MemTotal=124543 MiB`, `MemAvailable=14085 MiB`, `SwapTotal=16383 MiB`, `SwapFree=8735 MiB`. GPU NVML은 단일 device에서 `utilization=0.0%`, `temperature=35°C`, `memory.total/free/used=N/A`여서 GPU telemetry `PARTIAL`. 순간적으로 관측한 숫자이며 별도 GPU/모델을 띄울 수 있는 용량·운영 간섭 부재를 증명하지 않음. `explicit_container_memory_limit_mib=null`은 무제한 물리 GPU 메모리 증거가 아님.
- **정확한 상태 구분**: P6-A3a `OBSERVED_METADATA_ONLY`, P6-A 활성 Scheduler/CacheConfig/MambaSpec/physical block-table/state pointers **NOT_OBSERVED/BLOCKED**; P6-B/C/D `NOT_RUN/BLOCKED`; 기존 운영 서비스 변경, GPU 계산, 신규 모델 load, HTTP, CI, benchmark, blazux patch/PR/merge **실행하지 않음**. 이전 A2 baseline raw result/runner SHA PASS, 기존 Gutenberg cache SHA `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; baseline 당시 corpus SHA·sampling/KV 동일성 여전히 미확정 → P6-D 차단.
- **다음은 P6-A3b 관찰 방법 승인 설계**: 기존 비침습 인터페이스로 활성 객체를 노출하는지 먼저 확인(관측 가능한 부분만); 불가능하면 PIN된 이미지를 사용한 격리 CPU-only 구성 재현은 별도 `docker run` 승인과 자원 제한 필요(재현된 구성은 운영 프로세스 실측이 아님). 실제 block-table/tensor ptr·stride는 별도 GPU/model 실행 또는 지원되는 관측기 없이는 검증 불가. 이번 메모리 snapshot만으로 단일 DGX에서 GPU 모델 동시 실행 승인 금지; 기존 서비스에 attach/ptrace/debug/exec 금지. [A3 관찰 및 승인 결정](BLAZUX-PHASE6-A3-RESOURCE-OBSERVATION.md).
- 이번 후속 정본/Manifest 커밋은 **문서 전용, DGX 신규 시험 NOT_RUN**. **28/28·190/190은 오직 위 정확한 소스 SHA에 귀속**. `main`/P0/Phase1–5 및 PR#5 벤치 원본 불변; 신규 PR/Merge/CI 없음.


Status: A3a DGX_VERIFIED_28_190_AT_100FFB3 / RESOURCE_OBSERVED_METADATA_ONLY; active P6-A remains BLOCKED; GPU/model/CI/operational changes/patch/PR/merge NOT_APPROVED.

## Earlier prerequisites and preparation evidence (historical)

- Dedicated DGX Phase6 checkout at `0513b118260047b9965e16b20bdadf690c112c5d`: offline 15/15, Source186/186 PASS. A2 Docker inspect pinned image running PASS; original baseline result and benchmark-runner Git SHA PASS.
- Current cached Gutenberg corpus SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; historical corpus checksum unavailable, sampler/KV parity unverified. Performance comparisons BLOCKED.
- Previous documentation-only `be7a463274765627d0fd0da3a9d70907c5f0cf83` records this tested SHA. At the time this section was written A3a had not run; it is now verified at exact DGX SHA 100ffb3, as recorded above.

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

## A3a final observed DGX status (2026-10-28)

- Tested exact SHA: `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`, 28/28 offline unit tests and tracked Source Manifest 190/190. Operator final marker: `PHASE6_A3A_DGX_OBSERVATION_COMPLETED`.
- Running legacy fixed image identity passed. Explicit container memory limit absent (`null`); not a guarantee of no memory constraints.
- Host MemTotal=124543 MiB, MemAvailable=14085 MiB, SwapTotal=16383 MiB, SwapFree=8735 MiB. No inference about the safe memory cost of the existing model versus an additional model is supported.
- NVML one GPU: utilization 0.0%, temperature 35°C. NVML memory total/used/free=`null`, `gpu_telemetry.status=PARTIAL`; unknown unified-memory allocation availability.
- P6-A3a result `OBSERVED_METADATA_ONLY`; active Scheduler, cache/Mamba group block size, GPU table/state pointers `NOT_OBSERVED`; P6-A real ABI remains BLOCKED. No GPU/model/HTTP/benchmark/CI/patch/operational action occurred in observed script.

## A3b planning decision — stop and approval boundaries

| Candidate | Allowed result if independently approved | Remaining limitation | Decision now |
| --- | --- | --- | --- |
| Existing passive in-process telemetry/API | Only values already exposed without new instrumentation, if authorized and provenance-matched | Current read-only Docker/NVML metadata does not expose actual object/class/group/table state; unknown observability surface | BLOCKED pending discovery; no speculative HTTP/ptrace/exec |
| Isolated CPU-only config-construction process, pinned image, no GPU | Reproduced constructor/factory and group/spec values for equivalent supplied config with all inputs hashed; stop on drift | Not the active legacy process, not real GPU table/tensor allocation | PLAN_ONLY; requires separate bounded Docker-run approval |
| Isolated GPU or genuine in-process inspection | Potential actual per-group table/tensor address and guarded index oracle if safe isolated model and instrumentation exist | GB10 single-device memory pressure and no GPU memory telemetry; current 14,085 MiB host availability is insufficient evidence of noninterference | NO_GO until explicit GPU/model, memory budget and maintenance/isolation permission |

No A3b runtime or GPU operation has been executed. Prefer designing/fail-closed reviewing a CPU-only reproducer before requesting separate execution approval; if the reproduced config diverges, report BLOCKED and do not progress. Real P6-A certification cannot be inferred from that reproducer alone. P6-B/C/D stay BLOCKED.
