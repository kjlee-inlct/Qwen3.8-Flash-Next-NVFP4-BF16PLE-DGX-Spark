# Phase6 A→B performance checkpoint — baseline freeze before GPU correctness gate

## 2026-10-28 P6-AB-0 DGX 검증 확정 — 최신 체크포인트

- **DGX operator-tested exact source SHA** `fb5deae540812a300cb8404a53a202e505c40577`: dedicated Phase6 checkout (`~/Workspace/llm/blazux-phase6-gates`) `git pull --ff-only` from `0ad5e62...`, Phase6 unittest **70/70 PASS** (`Ran 70 tests`, `OK`), `PASS_SOURCE_ONLY: 204 tracked file(s)` **204/204 PASS**. Offline marker `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`; P6-AB stdout marker `PHASE6_AB_BENCH_CHECKPOINT_PLAN_ONLY_NO_LOAD`, `PHASE6_AB_BENCH_BASELINE_LOCKED_NEW_BENCH_NOT_RUN`, final `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`.
- **검증된 기록 범위**: 기존 pre-blazux `result.json` **원본 SHA256 match=true**, `environment.public.json` runner SHA/tokenizer SHA/매트릭스 provenance match=true, **12 conditions × 3 measured repeats = 36 raw measurements** (`generation`, concurrency=1, PP[2048,8192], TG[128,256], context depth[0,4096,16384], warmup=1, NumPy seed=20261027). **지금 새 36회 벤치를 실행한 것이 아님**: P6-AB 상태 `PLAN_READY_NOT_EXECUTED`, `pre_b_checkpoint_run=NOT_RUN`, `performance_benchmark_authorized=false`.
- **여전히 미해결**: 2026-10-26/27 역사적 실제 Gutenberg corpus SHA 없음, sampling/KV 정확한 동등성 `UNVERIFIED` → 과거 기준선과 엄밀한 동일조건 비교 `BLOCKED`. Active Scheduler class/CacheConfig/그룹별 MambaSpec/block tables/GPU state 주소 미관측 → **P6-A 실제 ABI BLOCKED**, P6-A→B 진행 `BLOCKED_UNTIL_REAL_A_GATE`, P6-B/C/D NOT_RUN/BLOCKED. 기존 운영 port 8000 대상 `scripts/benchmark/run-llama-benchy.sh`는 사용자로부터 별도 부하 승인받지 않았으므로 **실행 금지**.
- **향후 분리 절차**: A 실런타임 정확성에 대한 독립적 증거와 PASS 선행, 그 다음 target-specific serving/HTTP/모델 GPU 작업 및 벤치마크를 별도 승인받아 정확히 12×3 새 `phase6-pre-b-unmodified` private staging 작성 → B 단계를 마친 후 동일 조건 `post-B` 대조. P6-AB fresh run은 계획이며 P6-D 공식 회귀/안정성 시험과 구분; 임계값 사전 승인·코퍼스/샘플링/KV 일치를 먼저 확보. [P6-A→B 체크포인트 정본](BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md).
- 이 DGX 통합 로그는 정확히 `fb5deae...` 코드만 시험한 증거임. 다음 문서·Source Manifest 증거 커밋은 **DGX 미시험 docs-only SHA**. `main`/P0/Phase1–5/기존 원본 benchmark/Docker/weights/port/cache 불변, CI/PR/merge/패치/GPU/모델/API/신규 벤치 수행 없음.


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

## DGX result after creation — P6-AB-0 baseline lock verified

Exact DGX executed source SHA `fb5deae540812a300cb8404a53a202e505c40577`, Phase6 stdlib unit tests **70/70 OK** and full Source Manifest **204/204 PASS**. Read-only `scripts/phase6-ab-benchmark-plan.sh` reported `SOURCE_BASELINE_MATRIX_VALIDATED`, `original_sha256_match=true`, `runner_sha_match=true`, `tokenizer_sha_match=true`, `provenance_matrix_match=true`, 12 configurations and 36 three-repeat measurements. Plan-only status `PLAN_READY_NOT_EXECUTED`; both `PHASE6_AB_BENCH_CHECKPOINT_PLAN_ONLY_NO_LOAD` and `PHASE6_AB_BENCH_BASELINE_LOCKED_NEW_BENCH_NOT_RUN` emitted; final `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD` observed. The existing baseline dataset was neither overwritten nor supplemented by new measurements. 

The actual active Scheduler/CacheConfig/MambaSpec/physical state ABI is still `BLOCKED`, and the 2026-10-26/27 old corpus/sampler/KV fingerprint is still incomplete. No real PRE-B or P6-D benchmark authorized or run. The future 36-run capture must stay behind actual P6-A PASS and separate approval for workload target, model/API and service interference. A documentation-only GitHub receipt commit must not inherit 70/204 DGX-test status.
