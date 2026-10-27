# Phase6 P6-D frozen benchmark rules (PLAN_ONLY; no benchmark authorized)

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


## 2026-10-28 confirmed A2 provenance

On DGX Phase6 exact source SHA `0513b118260047b9965e16b20bdadf690c112c5d`, baseline raw SHA256 and runner SHA matched. Current cached Gutenberg SHA256 = `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`. Historical corpus SHA **not available**; `historical_corpus_matches_current=null` (not true or false); sampling/KV `UNVERIFIED`; performance benchmark `NOT_RUN`. Running pinned image and selected startup numeric flags are deployment metadata only. Strict A/B comparability and numeric regression thresholds remain BLOCKED pending explicit approval.


Historical immutable [pre-blazux baseline](benchmark/LLAMA-BENCHY-BASELINE-20261027.md):
original result SHA256 `25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf`; pinned eugr/llama-benchy commit `e9be344578cec17745066b220798b80a0d2686d3`. Same Orcarouter NVFP4/BF16 PLE/31 BF16 MTP tensors (MTP=2), tokenizer, inputs and sampler needed for strict A/B.

**Frozen matrix:** PP {2048,8192} × TG {128,256} × context depth {0,4096,16384} × concurrency 1 = 12 conditions, 1 warm-up and 3 measured runs per condition = 36 runs, `--exact-tg`, generation-latency mode, seed 20261027.

## Mandatory gates
- P6-A active Scheduler/CacheConfig/Mamba/group/address safety, P6-B isolated GPU rollback and prefix-cache correctness, P6-C MTP/Tool Parser/Responses HTTP correctness must PASS **before P6-D**. Source-only PASS is insufficient.
- Pin runner SHA, served model/checkpoint/PLE/MTP overlay, tokenizer, corpus bytes/SHA, input corpus selection, sampling, cache/KV, concurrency, image/GPU memory and launch options. The published old environment file omits exact historical corpus SHA and sampling/KV details; missing parity means **BLOCKED for strict improvement claims**.
- Preserve original 36 raw repeats and provenance; compare arithmetic mean with arithmetic mean. If deriving median/p95, compute identically from both raw sets. PP throughput (estimated), TG decode interval, peak, TTFR and E2E TTFT are distinct; do NOT compare MTP prior 44.23 tok/s end-to-end to llama-benchy TG tok/s.
- Predeclare TG/PP latency, p95, memory, error/stability/startup regression thresholds **before measuring**. No numerical limits have yet been authorized. Without thresholds P6-D is BLOCKED.
- Baseline wrapper `scripts/benchmark/run-llama-benchy.sh` targets the existing production service on 127.0.0.1:8000, and newly written script itself has NOT_RUN status. Never run it unmodified against either operational server or Phase6 candidate. Separate isolation, model/HTTP and benchmark authorization required.
- Source `results/orcarouter/stability-2h.json` covers **904 seconds, not 2 hours**. Separate 8159s uptime/11 health checks do not establish 2-hour stress.
- Raw evidence (repeats, configuration fingerprints, GPU/host memory and thermals, sampling/input digest, errors, hashes) remains **private and locally staged**. Publish only reviewed redacted projections; no secret or full Docker identifiers.
- `scripts/phase6-readonly-preflight.sh` reads only metadata/hash and cannot prove active runtime state or recreate missing historical A/B conditions. No HTTP, Docker exec/run, GPU, model start, benchmark, CI or patches.

Decision: P6-D NOT_RUN/BLOCKED until correctness, provenance comparability, isolation, explicit benchmark approval and predetermined thresholds.

## P6-A3a additional capacity observation (NOT benchmark authorization)

DGX exact SHA `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`: host MemAvailable=14085 MiB, but NVML total/free/used GPU bytes all unavailable; GPU 0% and 35°C are instantaneous. This snapshot **does not prove isolated candidate capacity**, let alone baseline-equivalent KV/cache conditions. Previously captured raw baseline checksum, runner SHA, current corpus SHA remain as documented; missing original corpus and sampler/KV equivalence plus unapproved quantitative regression thresholds keep P6-D BLOCKED. No 12×3 benchmark was run.
