# Phase 6 evidence ledger

## 2026-10-28 Phase6 A2 DGX verified — CURRENT STATUS (scope-limited)

- **Exact DGX operator-tested SHA** `0513b118260047b9965e16b20bdadf690c112c5d`, dedicated `~/Workspace/llm/blazux-phase6-gates` checkout, ff-only fast-forward from `c7f4ca7`. Bash syntax passed; Phase6 unittest **15/15 PASS**; `PASS_SOURCE_ONLY: 186 tracked file(s)` at exact SHA, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`. Read-only preflight ended `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED` and user shell `PHASE6_A2_PREFLIGHT_DGX_COMPLETED`.
- **Observed deployment-only evidence**: pinned image digest match=true, running=true; allowlisted launch flags `--gpu-memory-utilization=0.8`, `--max-model-len=262144`, `--max-num-batched-tokens=8192`, `--max-num-seqs=8`. `deployment.status=PASS` applies solely to Docker metadata; it does **not** verify process-selected Scheduler class/CacheConfig, MambaSpec blocks/groups or physical GPU state.
- **Benchmark evidence**: baseline raw result SHA256 match=true; pinned llama-benchy runner Git SHA match=true; cached Gutenberg corpus SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`, but **historical corpus SHA not available** and `historical_corpus_matches_current=null`; sampling/KV equivalence `UNVERIFIED`. The cached bytes' current hash does not prove what was used during the historical 2026-10-26/27 baseline. No P6-D comparison, benchmark execution, regression thresholds, or throughput claim authorized. [Benchmark rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md).
- **Gate classification**: `P6-A2 passive preflight=COMPLETED` with deployment PASS and benchmark PARTIAL, but `P6-A REAL ACTIVE RUNTIME=BLOCKED`; `P6-B/C/D=NOT_RUN/BLOCKED`. Next decision: distinguish (A3a) non-intrusive source/launch metadata, which cannot certify active Python objects, from (A3b) active Scheduler/Mamba/group/pointer observation that requires a separately authorized, safe and feasible observer/isolated GPU plan. Do not attach/deploy/instrument the running service or invoke Docker exec/run, live model, GPU, HTTP, CI or benchmark under existing approval.
- Historical Phase5 DGX-tested code SHA remains `780b780fc7572226a6a9ff2e52cd8e1921c8738b`; previous Phase6 offline exact SHA `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`. This follow-up **documentation/manifest commit is not DGX-tested**; a new HEAD does not inherit the 15/15 run. main/P0/Phase1–5 protected; no patch/PR/merge.


## 2026-10-28 Phase6 A1 result and A2 read-only gate (current)

- **DGX measured exact Phase6 code SHA** `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`: dedicated `~/Workspace/llm/blazux-phase6-gates` clean checkout, 7/7 Phase6 unittest PASS, 182/182 Source Manifest PASS, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, final `PHASE6_DGX_OFFLINE_GATE_COMPLETED`. The same SHA operator's **A1 source-only** log ended `PHASE6_A1_READONLY_SOURCE_INVENTORY_COMPLETED`; image tag `yslab-qwen38-bf16ple:9492b78c`, image ID short `b0984c4b724b`; `P6_A_RUNTIME_STATUS=BLOCKED`. Do not attribute these DGX results to the newer GitHub commit.
- **Next bundled step** on dedicated DGX checkout after `git pull --ff-only`: `bash scripts/phase6-gate.sh` (new offline unit suite+manifest) followed by `bash scripts/phase6-readonly-preflight.sh` (Docker `inspect` metadata ONLY + fixed pre-blazux result SHA, bench runner SHA, cached current Gutenberg corpus hash and optional historical private corpus SHA, no private raw data output). The latter prints `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED`. Its deployment `PASS` is solely pin/running metadata, not active Scheduler, MambaSpec/group, tensor pointer/stride, actual GPU address, or active config correctness. P6-A overall stays **BLOCKED**.
- [Frozen Phase6 benchmark comparison rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md) require original 12×3 immutable raw Baseline, runner and tokenizer/seed, corpus and sampler parity, equivalent cache/KV/environment, correctness P6-A/B/C, and preapproved regression thresholds. Legacy `scripts/benchmark/run-llama-benchy.sh` targets production port 8000 and has NOT_RUN wrapper status: **do not execute** for Phase6 without separate benchmark/isolation approval.
- User has not authorized DGX GPU, real model loading, HTTP/benchmark, CI, operational change, any blazux runtime patch, PR, or merge. A2 is explicit user-operated read-only observation, NOT permission to launch new compute; all new Phase6 code on the fresh commit is NOT_RUN until operator log. Main/P0/Phase1–5 remain untouched. Update these canonical docs and entire Source Manifest together.


Prepared on Phase6 branch from Phase5 docs-only parent `11fd777e2c49c030eee671133ab0af3a3ca9c26d`.
Phase6 offline code now has DGX operator evidence on exact SHA `0513b118260047b9965e16b20bdadf690c112c5d` (15/15, Source186/186). No GPU, CI, model startup, serving/API inference, benchmark or patch execution.

| Item | Status | Evidence |
| --- | --- | --- |
| P6-A real active configuration | BLOCKED | DGX passive metadata PASS at 0513b118; active class/cache/Mamba group/tensor pointers NOT_OBSERVED |
| P6-B GPU state/rollback/prefix | BLOCKED | GPU execution not approved; requires P6-A |
| P6-C MTP/tool/parser/Responses | BLOCKED | model/API execution not approved; requires P6-B |
| P6-D performance/stability | BLOCKED | benchmark not approved; requires all correctness gates |
| GitHub Actions | NOT_RUN | user prohibited CI |
| Phase6 DGX offline source/tests | PASS (bounded) | 15/15 unittest and 186/186 Source Manifest at exact tested SHA 0513b118 only |
| Phase5 offline exit | PASS (historical) | exact DGX-tested SHA `780b780fc7572226a6a9ff2e52cd8e1921c8738b`, never attribute to Phase6 HEAD |

Record future runs with exact tested SHA, environment fingerprint, raw redacted evidence, each required oracle, failure/blocked reason, cleanup and final status. Do not overwrite history.
