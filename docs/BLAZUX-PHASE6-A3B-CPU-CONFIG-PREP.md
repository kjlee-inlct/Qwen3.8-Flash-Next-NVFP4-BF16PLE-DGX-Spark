# Phase6 A3b-0 CPU-only configuration-reproduction preparation (no execution approval)

Status: HOST_STDLIB_PREPARATION_ONLY / CONTAINER_CPU_PROPOSAL_ONLY / P6-A_ACTIVE_RUNTIME_BLOCKED / GPU_MODEL_HTTP_BENCH_CI_NOT_RUN.

## Why this is a preparatory Gate

- DGX A3a measured `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`: Phase6 28/28 unittest, Source190/190; image running and pinned; host MemAvailable 14,085 MiB; NVML memory total/free/used unavailable; GPU utilization 0%, temperature 35°C at one moment. These **do not establish extra GPU memory headroom**.
- Historical baseline runner/result SHA PASS, but corpus historical SHA, sampler and KV/cache parity remain unknown; P6-D stays BLOCKED.
- Previous DGX Phase5 inspected pinned preview source and Scheduler/Mamba contract. Its source SHA pins are reused; new image import-free AST probe is a *future* drift check, not active configuration recovery.

## Files and safe host run

- `src/phase6_a3b_cpu_config.py --fixture tests/fixtures/phase6_a3b_synthetic.json`: bounded strict-schema stdlib CPU arithmetic. Computes naive group LCM/GCD and flags conditional Mamba/CacheConfig block-size sensitivity. **The actual vLLM resolver has conditional early returns, group-specific DCP/hash/prefix rules**; the naive numbers are diagnostics, NOT predictions or expected runtime values. Synthetic fixture cannot prove the real running Scheduler class or block size.
- `scripts/phase6-a3b-cpu-prepare.sh`: exact Phase6 branch/clean checkout, Source Manifest, synthetic contract, safe Docker command preview. Never starts Docker/model/GPU.
- `scripts/phase6-a3b-container-preview.sh --preview`: **prints only** bounded proposed isolation. `--execute` or other flags fail CLOSED; there is no `docker run` execution path in the script. No user approval has been given for Docker CPU container execution.
- `tests/test_blazux_phase6_a3b_cpu.py`: strict/fail-closed synthetic fixture, missing data, mismatches, size bounds, symlinks, pinned source guard, and no-active-certification regressions.
- `src/phase6_a3b_cpu_config.py --installed-source-only`: prepared for a later separately approved CPU-only container. Uses Python stdlib `importlib.util.find_spec('vllm')` (does not import vLLM), source SHA256 and AST class/function anchors only. Never constructs CacheConfig, Scheduler, MambaSpec or GPU tensor. **It is not, by itself, a genuine config-construction reproducer.**

## Proposed separate CPU-only container authorization

Even CPU-only `docker run` can consume DGX RAM and interact with daemon state. Do **not** execute it under current approval. Only after user explicitly approves CPU-only ephemeral container within the single DGX, prepare a separately reviewed execution script with:

- `--runtime=runc`, `--pull=never`, immutable locally pinned digest, `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--user=65534:65534`.
- `--cpus=1`, `--memory=512m`, `--memory-swap=512m`, `--pids-limit=64`, temp writable tmpfs (max 64 MiB), **only** dedicated Phase6 checkout mounted read-only; no weights, GPU, HF cache, Docker socket, host process mount, privileged mode or operating ports.
- `CUDA_VISIBLE_DEVICES=-1`, `NVIDIA_VISIBLE_DEVICES=void`, offline HF/Transformers, Python bytecode off and explicit `PHASE6_A3B_CPU_INSPECTION_ONLY=1`. Run only allowlisted source SHA/AST verification, no imports or model constructors; on source drift/exception, BLOCKED.
- Verify existing legacy container still running with exact digest before and after future probe, and stop if free system memory, service health, isolation controls or source pins drift. Do not guess a safe allocation based on old A3a telemetry.

## What would be required for actual CPU config-constructor reconstruction?

Separately: full launch/config provenance (including custom Scheduler override and model-dependent grouped KV specs); inspect installed constructor/dependency side effects before importing vLLM or building configs; guarantee offline no HF model reads/writes and bounded host memory; compare default/AsyncScheduler factory branch, CacheConfig and per-group MambaSpec exact values with independent oracle. If input or constructor branches are incomplete, STOP/BLOCKED. A reconstructed CPU config from a different process is **not** evidence of the active legacy process or real GPU group tables and pointers. P6-A itself cannot PASS until those actual runtime values and block/state bounds are independently observed.

## Stop and evidence classification

Host synthetic output marker `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME` is only prep completion. Image source marker `PHASE6_A3B_CPU_PREPARATION_ONLY_NOT_ACTIVE_CONFIG_VERIFIED` (future run, if approved) means pinned source anchor audit only. Neither constitutes `P6-A PASS` or approval for P6-B/C/D, patch, benchmark, CI, PR or merge. Source drift, missing fixture, wrong branch, dirty tree, or any attempt to run Docker without approval must STOP. Keep `main`, P0, Phase1–5 and pre-blazux baseline unchanged.
