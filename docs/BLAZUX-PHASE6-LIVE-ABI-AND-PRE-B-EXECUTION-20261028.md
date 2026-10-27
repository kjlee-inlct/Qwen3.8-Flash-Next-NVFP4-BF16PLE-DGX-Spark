# Phase6 live P6-A ABI observation and provisional PRE-B benchmark on existing service

Status: USER_APPROVED / GITHUB_SOURCE_PREPARED / NEW_DGX_HEAD_NOT_RUN / ACTUAL_P6_A_ABI_NOT_PROVEN. The user explicitly requested actual P6-A ABI verification and a fresh benchmark even though an archived baseline exists, to validate the benchmark script. This approval covers the existing pinned model's read-only HTTP metadata probe and one bounded 12×3 generation benchmark through its existing loopback API. It does NOT authorize server stop/restart, image/model changes, Docker exec, process attach, ptrace, patch, new GPU model, CI, PR or merge.

## Actual evidence already verified

- Most recent **operator-tested exact source SHA** `fb5deae540812a300cb8404a53a202e505c40577`: 70/70 Phase6 offline unit tests, Source204/204, immutable historic 12×3 raw result SHA/runner/tokenizer and 36 repeats verified. Marker `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`; absolutely **no fresh benchmark was conducted** at that SHA.
- Earlier `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`: one approved CPU-only pinned image source scan passed (7 historical file SHA, 8 AST component anchors), operating legacy container same pinned state before/after. Source/AST is not proof of effective live runtime Scheduler or GPU state.
- The original baseline source `results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json` is immutable, SHA256 `25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf`.

## 1. P6-A true live observation: possible and impossible with currently exposed interfaces

`scripts/phase6-a-live-observe.sh` checks clean dedicated Phase6 branch, Source Manifest, immutable image and running legacy identity BEFORE/AFTER. Requests only the existing fixed loopback `GET /v1/models` and `GET /metrics`. Restricts HTTP response bytes/time and forbids redirects, stderr/environment/log/id leaks. vLLM 0.32 may expose `vllm:cache_config_info{block_size="...", enable_prefix_caching="...", gpu_memory_utilization="..."}`; output copies **only** validated numeric/boolean allowlisted fields. This metric is startup-advertised engine cache metadata; it does not resolve actual Python object pointers. If missing, report `ABI_METRICS_NOT_USABLE` or `NOT_EXPOSED`, NOT a fabricated default.

Crucially, no ordinary HTTP/Prometheus metric can certify the active selected Scheduler class, effective scheduler/hash/group MambaSpec block sizes, real block-table geometry, physical pointer/stride/tensor allocation, kernel bounds or G1–G8 correctness. Those remain `NOT_OBSERVED` and real P6-A ABI `BLOCKED` even if cache info is observed. No in-process debug hook, `docker exec`, ptrace, instrumented code or second GPU model is authorized by this workflow. A full P6-A PASS would require a separately implemented safe live observer or proven isolated GPU/ABI evidence; no such observer has been run. The read-only check is an **actual attempt**, not an assertion that full ABI was verified.

## 2. Approved fresh performance measurement despite still-BLOCKED P6-A

`scripts/phase6-ab-provisional-run.sh --preflight` does **no inference**; `--execute` is the user's explicitly authorized one bounded run of `scripts/benchmark/run-llama-benchy.sh` against the already running `http://127.0.0.1:8000/v1` model. Use the checkout's version of that legacy launcher but **never invoke it directly** (it omits independent guard and can default to `pre-blazux` output label). This test is `PHASE6_AB_PROVISIONAL_ON_EXISTING_SERVICE`, strictly **not** gate-qualified `P6_AB_PERF_SNAPSHOT_CAPTURED`, not P6-A PASS, not final P6-D regression.

- Preflight: historical raw baseline source SHA/provenance pass, separate llama-benchy git pin `e9be344578cec17745066b220798b80a0d2686d3`, runner virtualenv present, unchanged local Gutenberg cache SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`, exact pinned running Docker `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`, dedicated private staging root, and **fresh host MemAvailable≥8192 MiB**. No duplicate wrapper via advisory lock.
- Load: original runner, no source/model modification, PP[2048,8192] × TG[128,256] × depth[0,4096,16384], concurrency 1, 1 warmup and 3 measured repeats each = 12×3 = 36 measured, generation latency mode, exact-TG and NumPy seed 20261027, progress log and throughput time series. Normal inference changes the running service's transient scheduler/cache state and may contend with other clients: benchmark **may temporarily reduce service responsiveness**. No service health/zero-interference guarantee is claimed; the user approved this bounded load.
- Watchdog: monitor current `MemAvailable` every 10 sec and STOP benchmark child process group only if below **4096 MiB**, if the exact running Docker ID+image+start timestamp drifts, or if one hour passes. Existing operational server is **never** signaled/killed/restarted/stopped or reconfigured. Container identity also checked after the bench. The monitoring floor reduces risk but is not an OOM or no-interference guarantee; on abnormal memory condition stop and keep partial private files.
- Private output: new unique directories under `$HOME/Workspace/llm/bench-results-staging/` with `phase6-pre-b-provisional` label; separate `phase6-ab-guard-*` user-only control log. Never overwrite the old pre-blazux Git-tracked 36-run result. The source runner's `environment.private.json` may contain full Docker IDs/model-view details; raw logs must not go to GitHub. On completion, independently verify output matrix + all 36 repeats, private provenance including cached corpus SHA, SHA256SUMS for all nine original raw files, then emit sanitized 12-condition mean PP estimate / TG decode / E2E TTFT and independent new `result.json` SHA. `P6_AB_BENCH_STATUS=RUNNING_APPROVED_EXISTING_SERVICE_LOAD`, final `PHASE6_AB_NEW_12X3_BENCH_RECORDED_EXISTING_SERVICE_NOT_A_PASS` only on complete success.
- Warning: the archived **2026-10-26/27** original corpus byte SHA and exact sampler/KV/cache conditions were not proven. Even if candidate ran identical static flags, declare strict old-vs-new improvement `UNVERIFIED`; use fresh matched pre-B/post-B later, and predefine regression thresholds prior to formal P6-D. The new run is for runner-validation and provisional reference, **not** for numerical blazux gain claims.

## Gate/status and stop conditions

| Component | PASS evidence | Missing / blocked |
| --- | --- | --- |
| Phase6 offline sources | New branch-specific unittest and Source Manifest PASS at exact tested SHA | New code is NOT_RUN until DGX operator log |
| P6-A live exposed metric | `PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA` if published, otherwise `ABI_METRICS_NOT_USABLE` | Actual Scheduler/Mamba/group/table/GPU pointers always NOT_OBSERVED, P6-A `BLOCKED` |
| 12×3 script validation | `PASS_PROVISIONAL_PRE_B_36` with 36 measurements, 9 files SHA ledger + immutable baseline separate | Timeout, low RAM, identity drift, results incomplete = `INCOMPLETE` or `BLOCKED`, no automatic retry |
| P6-A→B official transition | **NOT** advanced by this run | Real P6-A ABI proof missing -> B `BLOCKED` |
| P6-D formal comparison | NOT_RUN | historic corpus/sampling/KV and accuracy/stability gates unresolved |

## Required DGX execution order (no remote access by assistant)

1. Pull `feature/blazux-phase6-runtime-gates` in dedicated clean `$HOME/Workspace/llm/blazux-phase6-gates` checkout; verify exact GitHub SHA (supplied after commit), source manifest and shell syntax.
2. `bash scripts/phase6-gate.sh` — CPU/offline regression only.
3. `bash scripts/phase6-a-live-observe.sh` — GET metadata only; its full A verdict stays BLOCKED, but must verify pinned identity and served ID.
4. `bash scripts/phase6-ab-provisional-run.sh --preflight` — no inference, verifies local baseline/runner/corpus/deployment/memory and staging.
5. `bash scripts/phase6-ab-provisional-run.sh --execute` — one approved bounded live 12×3 run. This sends real inference requests to the existing server, monitored, and never modifies container configuration.

Do not run under external client traffic or when operator knows service is under deadline/production load. Once stage 4 or stage 5 returns BLOCKED/INCOMPLETE, STOP and inspect only private local staged evidence. Never loosen guards silently, repeat failed runs automatically, delete partials, or publish unreviewed private files. Leave main/P0/Phase1–5 and all original benchmark inputs/results intact.
