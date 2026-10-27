# Phase6 P6-D frozen benchmark rules (PLAN_ONLY; no benchmark authorized)

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
