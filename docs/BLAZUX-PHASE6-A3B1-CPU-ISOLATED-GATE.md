# P6-A3b-1 — explicitly approved isolated CPU-only pinned-source inspection

Status: USER_APPROVED_CPU_ONLY_ONCE / GITHUB_IMPLEMENTATION_PREPARED / DGX_NEW_SHA_NOT_RUN / ACTIVE_P6_A_BLOCKED. No approval for real Config/Scheduler construction, GPU, model load, HTTP, inference benchmark, CI, patch, PR or merge.

## Approval and verified prerequisite

- User explicitly replied `승인` after requesting a bounded P6-A3b-1 transient CPU-only container check. This approval covers **one** pinned-image ephemeral `docker run` to inspect source SHA/AST; it is not a general authorization for model/container experiments.
- Last DGX-measured Phase6 source HEAD `7dc77164447bdd272b3ff791341d8ec5379a1edd`: 45/45 offline tests PASS, 196/196 full tracked manifest PASS, synthetic CPU fixture group LCM=32/GCD=16, `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME`, `PHASE6_A3B0_DGX_PREPARATION_VERIFIED_NO_RUNTIME`. Synthetic block 16 vs 32 does **not** prove actual mismatch or runtime defect.
- Earlier A3a snapshot: host MemAvailable 14,085 MiB, SwapFree 8,735 MiB, GPU memory counters unavailable; this is not current memory or safe GPU/model concurrency evidence. Recheck current `/proc/meminfo` immediately before CPU-only invocation; STOP below 4 GiB available.
- Next code commit is distinct from DGX-tested `7dc771...` and must remain NOT_RUN until user supplies its terminal output.

## New tracked entrypoint

`scripts/phase6-a3b1-cpu-container-gate.sh --execute` requires the exact Phase6 branch, clean dedicated checkout and complete Source Manifest, then checks current host MemAvailable, the operational container's pinned running identity, and local immutable Docker image ID before any `docker run`.

Only one ephemeral container is started. It uses the existing pinned image **by image ID** `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`; `--pull=never --rm --runtime=runc --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges --cpus=1 --memory=512m --memory-swap=512m --pids-limit=64 --user=65534:65534`, a bounded `/tmp` tmpfs and **only** the clean dedicated Phase6 checkout bind-mounted read-only. No mounts for weights, HF cache, Docker socket, host process namespace or GPU devices; no `--gpus`, ports, privileged mode, pull, exec, stop or restart of legacy. HF/Transformers offline, CUDA/NVIDIA visible devices off, Python bytecode off. Docker incurs temporary daemon/container overhead; `--rm` removes this ephemeral container at normal exit.

The container executes **only** `src/phase6_a3b_cpu_config.py --installed-source-only` with stdlib import-free AST. It does not import vLLM, initialize CacheConfig or Scheduler, create real MambaSpecs, load checkpoint/GPU memory, perform inference or call HTTP. The probe compares **7 installed source file hashes** against previously captured Phase5 DGX SHA256 and checks **8 AST components** including the KV block-size resolver method (whose file SHA is **not pinned** by this probe). Class/function NAME anchors do not establish correct runtime branch binding.

`src/phase6_a3b1_evidence.py` independently requires the exact audit JSON schema, all eight components, seven pinned SHA matches, non-executed `vllm_modules_imported=false`, and the explicit sentinel. Raw container stdout is not echoed; Docker stderr is suppressed. `BLOCKED` on drift, missing image, missing permissions, unexpected output, or incomplete contract. No automatic root fallback or rerun.

The script checks the original legacy container's pinned running identity **again after** the disposable run, even if the probe failed. An unchanged identity is a necessary guard, not a proof that inference quality and availability were unaffected. A new container start or Docker daemon action does not happen under the original `scripts/phase6-a3b-container-preview.sh`: that preview remains inert.

## PASS/FAIL/BLOCKED classification

| Observed operator marker | Meaning |
| --- | --- |
| `PASS_SOURCE_ONLY: 200 tracked file(s)` | Expected new full source-tree integrity check at new SHA; not a runtime test |
| `Ran 57 tests` / `OK` | Expected previous 45 + 12 new synthetic/static tests, not yet DGX verified |
| `P6-A3B1_BEFORE=PINNED_LEGACY_RUNNING`, `P6-A3B1_AFTER=PINNED_LEGACY_RUNNING` | Legacy metadata identity preserved across the bounded probe |
| `status=PASS_PINNED_SOURCE_AST_ONLY` and 8 components / 7 historic hashes | Source SHA/AST probe PASS, **not** actual active Scheduler/Mamba/cache configuration |
| `PHASE6_A3B1_CPU_ISOLATED_PINNED_SOURCE_PASS_NOT_ACTIVE_RUNTIME` | The one approved isolated CPU inspection completed normally |
| `BLOCKED` or no final marker | Do **not** claim success or retry by weakening security; investigate read-only with operator evidence |

Strict active P6-A stays **BLOCKED** until real selected Scheduler class/CacheConfig, MambaSpec group blocks, live block-table and physical GPU tensor bounds have an approved independent observer. P6-B/C/D remain NOT_RUN/BLOCKED. The pre-blazux 12x3 baseline, historic corpus mismatch unknown, sampling/KV comparability and P6-D threshold approval are unchanged. CI, patch, PR/merge and main/P0/Phase1–5 are protected.

## Approved DGX execution sequence

Use exact new GitHub SHA (to be supplied after atomic commit) and the dedicated checkout only; check clean branch before `git pull --ff-only`. Run `bash scripts/phase6-gate.sh` once, then `bash scripts/phase6-a3b1-cpu-container-gate.sh --execute`. Never execute the old preview as if it were the approval-gated run.
