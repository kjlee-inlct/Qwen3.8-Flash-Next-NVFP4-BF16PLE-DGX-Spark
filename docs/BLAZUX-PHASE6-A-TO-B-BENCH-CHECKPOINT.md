# Phase6 A→B performance checkpoint — baseline freeze before GPU correctness gate

Status: CHECKPOINT_PLAN_PREPARED / NEW_BENCHMARK_NOT_RUN / ACTIVE_P6_A_BLOCKED / P6_B_NOT_RUN / P6_D_NOT_RUN. This document **adds a pre-B performance checkpoint, not a shortcut around A, B, or C correctness or P6-D**.

## Decision and role in the schedule

User requests a performance record between Phase6 P6-A and P6-B so later B/C/D development or fixes can be compared against **the exact pre-B code, model and environment**. Add a non-authoritative *performance checkpoint* in the dependency graph:

```text
                         PRE-B checkpoint (reference / no gate bypass)
 P6-A REAL ABI PASS ───────────┬──────────────→ P6-B GPU state PASS → P6-C MTP/API PASS → P6-D formal performance
                              │
                         collect 12 × 3 after separately approved model/API/benchmark scope
```

Existing A1/A2/A3a/A3b-0/A3b-1 source checks are **not** actual P6-A PASS: the active Scheduler class, resolved CacheConfig, each MambaSpec/group and physical block tables/state pointer/stride/allocations are missing. **A remains BLOCKED**. Preserve this dependency; do not start B or claim a performance Gate PASS on synthetic/source results.

## Level 0: immediately usable immutable record (no inference load)

- The original pre-blazux llama-benchy raw result is fixed at `results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json`, SHA256 `25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf` and pin runner `e9be344578cec17745066b220798b80a0d2686d3`.
- Baseline reference: Orcarouter NVFP4/BF16 PLE, MTP=2, served ID `qwen3.8-flash-next-orca-uncensored-bf16-mtp`; tokenizer SHA256 `06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523`.
- Freeze PP {2048,8192} × TG {128,256} × depth {0,4096,16384}, concurrency=1; 1 warm-up each, 3 measured repeats each, generation mode, `--exact-tg`, NumPy prompt seed 20261027. **36 measured runs**, no user-authored default of new seed or hidden sampling change.
- Baseline table metrics are arithmetic mean of 3 samples; keep originals and distinguish PP estimated throughput, generation TG throughput, TTFR, E2E TTFT and full end-to-end completion rate. Old MTP sweep 44.23 tok/s is a different metric.
- A2 DGX verified legacy baseline hash and bench runner HEAD. Current cached Gutenberg SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c` was observed, but historical 2026-10-26 corpus SHA was not retained; historical sampling/KV state not proven. **Do not label old-vs-new strict identical A/B** without filling this gap.
- New `src/phase6_ab_benchmark_plan.py` + `scripts/phase6-ab-benchmark-plan.sh` only validate the original baseline raw SHA, frozen 12×3 result structure, environment.public source pins and fixture consistency. No `docker`, `curl`, `nvidia-smi`, `llama-benchy`, GPU/model/HTTP or benchmark operations. End marker: `PHASE6_AB_BENCH_BASELINE_LOCKED_NEW_BENCH_NOT_RUN`.

## Level 1: PRE-B live performance capture (FUTURE APPROVAL REQUIRED)

**Only after** actual P6-A runtime ABI PASS and explicit approval for source model, inference API, exact endpoint/port and benchmark workload. If P6-A cannot safely be observed, it stays BLOCKED; an optional operator-approved *provisional* measurement, if ever run, must be labeled `PRE_A_RUNTIME_PROVISIONAL_NOT_GATE_PASS` rather than satisfying this A→B checkpoint.

Benchmark target priority: (1) separately isolated pre-B candidate with known exact image/config/serving API and proven non-interference; (2) an existing operational instance **only under separate explicit authorization**, resource/watchdog limits and an agreed maintenance/performance-impact window. On single DGX Spark, measured MemAvailable 14,085 MiB (earlier snapshot) and NVML GPU memory N/A do NOT prove concurrent candidate can be launched. No Docker restart, new model startup or port changes under this plan. **Never execute** legacy `scripts/benchmark/run-llama-benchy.sh` unmodified: it targets live `127.0.0.1:8000`.

Freeze before first load: Phase6 git SHA, exact installed vLLM image/source SHA, Orcarouter model/revisions, MTP2, BF16 PLE/overlay provenance, tokenizer, runner Git SHA, cached corpus **byte hash**, prompts/sampling effective config, precision, max model length, GPU utilization flag, cache config/prefix state, KV-cache initial state, test ordering, warmup, concurrency, host/GPU memory+temperature. Record whether model had already been warmed by previous requests. If historical data missing, pair this new pre-B capture with a **later equally controlled post-B/P6-D capture** and compare those as the paired baseline; historical pre-blazux 36-run data remains contextual rather than strict direct A/B.

## PRE-B outputs / classification

Private output directory on DGX: a newly created unique folder beneath `$HOME/Workspace/llm/bench-results-staging/`, labeled `phase6-pre-b-unmodified`, NOT inside a tracked checkout or prior baseline directory. Capture: raw result.json (all 12 combinations and 36 repeats), public redacted provenance projection and separate private environment, prompt/corpus SHA, run+warmup order, progress/timeseries/error log, model/runner/source image fingerprints, memory/thermal before+after, SHA256SUMS, any server interruption or failed row. Keep raw prompt/response content, credentials, private Docker identifiers and mount paths OUT of GitHub unless explicitly redacted/reviewed.

PASS only as `P6_AB_PERF_SNAPSHOT_CAPTURED` when complete 12×3 data and exact identity verified; this is **not P6-A/B correctness PASS** and not P6-D formal regression PASS. Failure/partial/missing input -> `BLOCKED` or `INCOMPLETE`. No thresholds yet approved; do not manufacture 'improved' or 'regressed' labels or numerical limits after seeing data.

## Gate and final comparison

- `P6-A` active runtime ABI verified first; `P6-AB` optional/recommended freeze; `P6-B` isolated GPU correctness (separate approval); `P6-C` real MTP/Tool/Responses (separate approval); `P6-D` final 12×3 perf/stability (new approval + numeric limits). Do not use a pre-B throughput PASS to enter B if A failed.
- Where possible, use the same candidate target pre-B and post-B. The old pre-blazux baseline and pre-B fresh capture must remain separate datasets, with exact dates/hashes recorded.
- A benchmark itself can prime cache and consume GPU/system memory, so finish it in an approved isolated scope and re-establish B-stage initial conditions before testing GPU rollback/prefix correctness. Do not claim that a prior benchmark left GPU state pristine.
- Publication/commit boundary: Phase6 docs, plan, tests and Source Manifest may be prepared now; **no benchmark, CI, model/API calls, Docker run or operation** is authorized by this document. When user later approves a live benchmark, introduce a separately validated execution command and preserve the original baseline bytes.

## Current latest DGX operator evidence (2026-10-28)

Exact source SHA `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`: Phase6 unittest **57/57 PASS**, full Source Manifest **200/200 PASS**, pinned-image disposable CPU-only probe `P6-A3B1_BEFORE/AFTER=PINNED_LEGACY_RUNNING`, fresh host MemAvailable=14064 MiB; allowlisted parser `PASS_PINNED_SOURCE_AST_ONLY`, 8 AST components, 7 historical hashes checked (KV resolver SHA **not pinned**). Final `PHASE6_A3B1_DGX_SOURCE_PROBE_COMPLETED`. No model inference, GPU workload or benchmark was run. Actual active Scheduler/CacheConfig/Mamba groups/physical GPU table/tensor pointers still not observed; P6-A runtime BLOCKED.
