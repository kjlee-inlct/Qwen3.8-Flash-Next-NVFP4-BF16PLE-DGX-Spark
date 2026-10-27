# Phase 6 evidence ledger

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
| P6-A real active configuration | BLOCKED | A2 Docker metadata PASS at 0513b118; A3a passive resources OBSERVED_METADATA_ONLY at exact 100ffb3; active class/cache/Mamba group/pointers NOT_OBSERVED |
| P6-B GPU state/rollback/prefix | BLOCKED | GPU execution not approved; requires P6-A |
| P6-C MTP/tool/parser/Responses | BLOCKED | model/API execution not approved; requires P6-B |
| P6-D performance/stability | BLOCKED | benchmark not approved; requires all correctness gates |
| GitHub Actions | NOT_RUN | user prohibited CI |
| Phase6 DGX offline source/tests | PASS | 28/28 unittest and 190/190 Source Manifest at exact DGX tested SHA 100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1; earlier 15/15 at 0513b118 |
| Phase5 offline exit | PASS (historical) | exact DGX-tested SHA `780b780fc7572226a6a9ff2e52cd8e1921c8738b`, never attribute to Phase6 HEAD |

Record future runs with exact tested SHA, environment fingerprint, raw redacted evidence, each required oracle, failure/blocked reason, cleanup and final status. Do not overwrite history.

## Historical A3a execution checklist (fulfilled at 100ffb3)

- New exact-code SHA: resolve from GitHub after atomic manifest commit; do not copy 0513b118 test results to newer HEAD.
- Observed trace: 28/28 Phase6 unittest, Source 190/190 (actual DGX operator result at 100ffb3); `PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED` and final user shell marker only after execution.
- Record host MemAvailable/total and optional GPU telemetry availability as momentary passive observations. Do **not** infer safe model coexistence or activate GPU. P6-A real runtime BLOCKED regardless of passive outcome.

## P6-A3a evidence interpretation / candidate next Gate

`gpu_telemetry.status=PARTIAL` with total/free/used `null` does not imply error or zero available GPU bytes; 0.0% reported utilization is a point measurement, not resource isolation proof. `host_memory.mem_available_mib=14085` may change and cannot establish safety to allocate GPU unified memory. `deployment.explicit_container_memory_limit_mib=null` means no explicit Docker limit observed; it does not imply unlimited available RAM. No runtime Scheduler/CacheConfig/MambaSpec/physical state evidence was obtained. Therefore `P6-A runtime BLOCKED` is the required classification. Only prepare P6-A3b observer plan; do not run Docker exec/run, attach to service, start model, or run GPU/HTTP/benchmark/CI.
