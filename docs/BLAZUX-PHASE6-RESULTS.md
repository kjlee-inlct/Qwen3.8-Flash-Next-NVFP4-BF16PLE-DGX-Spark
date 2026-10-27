# Phase 6 evidence ledger

## 2026-10-28 Phase6 A1 result and A2 read-only gate (current)

- **DGX measured exact Phase6 code SHA** `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`: dedicated `~/Workspace/llm/blazux-phase6-gates` clean checkout, 7/7 Phase6 unittest PASS, 182/182 Source Manifest PASS, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, final `PHASE6_DGX_OFFLINE_GATE_COMPLETED`. The same SHA operator's **A1 source-only** log ended `PHASE6_A1_READONLY_SOURCE_INVENTORY_COMPLETED`; image tag `yslab-qwen38-bf16ple:9492b78c`, image ID short `b0984c4b724b`; `P6_A_RUNTIME_STATUS=BLOCKED`. Do not attribute these DGX results to the newer GitHub commit.
- **Next bundled step** on dedicated DGX checkout after `git pull --ff-only`: `bash scripts/phase6-gate.sh` (new offline unit suite+manifest) followed by `bash scripts/phase6-readonly-preflight.sh` (Docker `inspect` metadata ONLY + fixed pre-blazux result SHA, bench runner SHA, cached current Gutenberg corpus hash and optional historical private corpus SHA, no private raw data output). The latter prints `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED`. Its deployment `PASS` is solely pin/running metadata, not active Scheduler, MambaSpec/group, tensor pointer/stride, actual GPU address, or active config correctness. P6-A overall stays **BLOCKED**.
- [Frozen Phase6 benchmark comparison rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md) require original 12×3 immutable raw Baseline, runner and tokenizer/seed, corpus and sampler parity, equivalent cache/KV/environment, correctness P6-A/B/C, and preapproved regression thresholds. Legacy `scripts/benchmark/run-llama-benchy.sh` targets production port 8000 and has NOT_RUN wrapper status: **do not execute** for Phase6 without separate benchmark/isolation approval.
- User has not authorized DGX GPU, real model loading, HTTP/benchmark, CI, operational change, any blazux runtime patch, PR, or merge. A2 is explicit user-operated read-only observation, NOT permission to launch new compute; all new Phase6 code on the fresh commit is NOT_RUN until operator log. Main/P0/Phase1–5 remain untouched. Update these canonical docs and entire Source Manifest together.


Prepared on Phase6 branch from Phase5 docs-only parent `11fd777e2c49c030eee671133ab0af3a3ca9c26d`.
This commit implements **offline scaffolding only**. No DGX, GPU, CI, model, serving, API, benchmark or patch execution.

| Item | Status | Evidence |
| --- | --- | --- |
| P6-A real active configuration | BLOCKED | DGX read-only access not approved; supplied JSON contract tests are not active runtime evidence |
| P6-B GPU state/rollback/prefix | BLOCKED | GPU execution not approved; requires P6-A |
| P6-C MTP/tool/parser/Responses | BLOCKED | model/API execution not approved; requires P6-B |
| P6-D performance/stability | BLOCKED | benchmark not approved; requires all correctness gates |
| GitHub Actions | NOT_RUN | user prohibited CI |
| New Phase6 DGX source tests | NOT_RUN | user prohibited DGX |
| Phase5 offline exit | PASS (historical) | exact DGX-tested SHA `780b780fc7572226a6a9ff2e52cd8e1921c8738b`, never attribute to Phase6 HEAD |

Record future runs with exact tested SHA, environment fingerprint, raw redacted evidence, each required oracle, failure/blocked reason, cleanup and final status. Do not overwrite history.
