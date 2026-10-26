---
title: Qwen3.8-Flash-Next BF16 PLE DGX Spark recipe
library_name: vllm
license: apache-2.0
tags:
  - qwen
  - vllm
  - dgx-spark
  - nvme
---

# Qwen3.8-Flash-Next BF16 PLE recipe for DGX Spark

A recipe to run NVFP4 Qwen3.8-Flash-Next with its full-precision BF16 PLE memory-mapped from NVMe on a single NVIDIA DGX Spark (GB10).

## Fork-specific installation and management wizards (NOT TESTED)

### Read-only state comparison, compact status and host Health (2026-10-26)

After successful legacy observation registration on the DGX Spark, the feature
branch now includes snapshot-versus-live comparisons, concise Korean status
output, host disk/memory advisories, and offline mock-based protection tests.
The saved legacy receipt is **never changed by status, compare or health**.

```bash
# Only after safe git pull --ff-only in the existing personal-fork checkout
scripts/status.sh                    # compact
scripts/status.sh --json             # full JSON and diff
scripts/compare-state.sh             # saved vs current changes
scripts/health.sh                    # Docker/API/model/disk/memory (read-only)
scripts/doctor.sh                    # policy + comparison + health
```

[Detailed guide](scripts/STATUS-COMPARE-AND-HEALTH.md) ·
[Saved legacy adoption evidence](scripts/LEGACY-OBSERVATION-20261026.md).

**Testing scope:** offline unit tests with simulated Docker/Git/HTTP;
no actual DGX install/uninstall, Docker build, data cleanup or inference
evaluation is part of this change. CI results must be checked independently.

### Existing YSLAB deployment: same checkout, changed Git history

The operator's 2026-10-26 DGX outputs show that an existing legacy YSLAB
model is still running from the **same** directory now tracking the personal
fork's feature branch. Image/container receipt IDs, target labels, port
`0.0.0.0:8000`, and Docker mounts for `hf-cache` and `recipe-views`
matched the original deployment record. The old pinned source commit still
exists as a Git object. `/health` and `/v1/models` responded, but no
new generation inference test was performed.

The updated wizard separates `legacy.identity_verified` (strict recorded
Docker IDs, labels, port and both mount sources) from Git origin/HEAD drift
(`legacy.checkout_warnings`). **Existing Docker resources remain
observation-only: no automatic takeover, stop, remove or replace.**
See [DGX evidence and limits](scripts/LEGACY-OBSERVATION-20261026.md).
The code change itself has not been exercised on the DGX or through tests.

### Pull and verify the exact source snapshot (read-only)

After checking out the personal fork's `feature/install-uninstall-wizard-20261026`
branch, follow the complete, safety-guarded commands in
[Git pull to verification](scripts/VERIFY-FROM-GIT-PULL.md).
The tracked code/data/docs state is captured by
[`scripts/source-state-manifest.json`](scripts/source-state-manifest.json);
`scripts/verify-source-state.sh --strict` compares every tracked file's
Git blob ID, working-tree bytes, file mode, expected branch and fork origin.
It does not modify Docker, HF cache, either state directory or the running API.

```bash
# Run ONLY from the correct personal-fork checkout, AFTER a safe fast-forward pull:
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
scripts/status.sh                   # read-only; real host evidence is separate
```

`PASS_SOURCE_ONLY` is **not** a test result for the wizard or its model.
Do not run deployment/removal on the production Spark on the strength of
a source integrity check alone.

> **Existing YSLAB installations are protected.** This fork contains new, untested
> wizard tooling. It must not be used to forcibly replace or uninstall an existing
> model on a production DGX Spark. There has been **no actual DGX or CI test** of
> the new wizard implementation in this change.

The repository provides two distinct manifests:
`compatibility.json` pins model/checkpoint revisions and PLE/MTP identities;
`scripts/deployment-manifest.json` defines the wizard's deployment defaults,
read-only legacy fingerprint, and safety policies. The wizard's Docker IDs and
legacy observation are stored separately in a private local receipt and never in Git.

**Already installed using the YSLAB reference scripts?** Keep its model cache,
image, container, port `8000`, and legacy `~/.local/state/yslab-qwen38-bf16ple`
untouched. From this **fork checkout**, inspect it first:

```bash
scripts/manifest.sh validate
scripts/status.sh
scripts/doctor.sh
scripts/install.sh --dry-run
```

When a read-only legacy fingerprint is fully verified, the wizard can record it
with `scripts/adopt-legacy.sh --confirm-container-id FULL_ID --yes`. Adoption
**does not grant stop/remove permission** and does not alter legacy state.
The upstream runtime uses the *same Docker container name* for the same target,
so a new wizard activation will deliberately refuse to replace the legacy container
even if the new service port is different.

For a **new, separate** wizard-managed deployment, `scripts/install.sh` and
`scripts/uninstall.sh` present a TTY menu; `--prepare-only`,
`--activate-only`, `--build-only`, `--dry-run`, and explicit managed
stop/removal modes are available for automation. The new default port is
`127.0.0.1:18300`, not the reference script's host `0.0.0.0:8000`.
No automatic `git clone`, model cache migration/purge, legacy takeover,
or destructive `--replace` is implemented.

**Documentation:** [Wizard guide](scripts/README-WIZARDS.md) ·
[Legacy installation protection](scripts/LEGACY-INSTALLATION.md) ·
[Manifest and ownership model](scripts/MANIFEST-SCHEMA.md) ·
[Operations](scripts/OPERATIONS.md) ·
[Safety and recovery](scripts/SAFETY-AND-RECOVERY.md) ·
[Unexecuted test plan](scripts/TEST-PLAN.md) ·
[Original implementation plan](scripts/INSTALL-UNINSTALL-WIZARD-PLAN.md).

The original upstream recipe instructions below are preserved for reference.
They do **not** automatically adopt your existing deployment.

## What this recipe does

The Parameter Lookup Embedding (PLE) is a lookup table. This recipe keeps the
complete 95.37 GiB BF16 PLE in its checkpoint on NVMe and memory-maps it, gathering
only the rows needed by each request. The NVFP4 compute trunk stays in unified
memory while the full table remains file-backed. The runtime uses PIECEWISE CUDA
graphs and a BF16 KV cache.

For the qualified Orcarouter target, the recipe can also build a deterministic
overlay containing the 31 native BF16 MTP tensors from a pinned RadixArk checkpoint.
The original gated Orcarouter files are not modified or redistributed.

## Measured results - Orcarouter checkpoint only

These results apply only to
[`orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4`](docs/COMPATIBILITY.md) revision
`3a3b63161c0745390e5270179af42e46efc70799` plus the documented BF16 MTP overlay,
on one DGX Spark. They do not describe Inferact or RadixArk runtime performance.

- The MTP load guard verified 31/31 expected tensors. The compact BF16 MTP file is
  4.86 GiB.
- A single-stream MTP depth sweep selected `MTP=2`: 44.23 tok/s end-to-end,
  including hidden reasoning and first-visible latency, versus 27.26 tok/s
  at `MTP=0`, a 62.2% increase. Its separately measured visible-answer phase was
  46.15 tok/s, with 1.324s to first visible content.
- Native 262,144-token startup used 76.21 GiB for model loading and exposed 17.37
  GiB of BF16 KV, enough for 627,960 cached tokens (2.40 concurrent native windows).
- Exact retrieval passed at 240,051 prompt tokens, with 116.80s TTFT and 2,055.17
  prompt tok/s.

See [Benchmarks](docs/BENCHMARKS.md) for the full MTP sweep, sampling parameters,
baseline concurrency results, and caveats. A separate
[three-instance SWE-bench pilot](docs/SWE-BENCH-PILOT.md) records an agent-level
comparison against the installed UD-Q4_K_XL GGUF runtime.

## Compatibility matrix

| Checkpoint recipe | PLE arrangement | Runtime status |
| --- | --- | --- |
| Orcarouter | Direct BF16 PLE; optional BF16 MTP overlay | runtime validated |
| Inferact | Direct BF16 PLE | runtime unvalidated |
| RadixArk | Hybrid BF16 PLE | runtime unvalidated |

The matrix describes tooling compatibility, not equivalent model behavior. See
[Compatibility](docs/COMPATIBILITY.md) for pinned revisions and boundaries.

## Requirements

- One NVIDIA DGX Spark (GB10), with NVMe storage available to the recipe.
- At least 100 GiB free disk space before download; the command checks this gate.
- A Hugging Face account that has accepted the Orcarouter checkpoint's access
  conditions. Open the
  [`orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` page](https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4),
  sign in, and accept the request to share your contact information. A read token
  cannot grant gated access until this browser step is complete.
- Docker with NVIDIA runtime support.

## Quick start: qualified BF16 MTP profile

```bash
git clone https://github.com/YSLAB-ai/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git
cd Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark
docker build -t qwen38-flash-dgx .
scripts/qwen38-dgx-spark login
scripts/qwen38-dgx-spark prepare orca-uncensored-bf16-mtp
scripts/qwen38-dgx-spark serve orca-uncensored-bf16-mtp --mtp 2
```

The interactive login stores the token in the same recipe cache used by the
downloader. Before the large transfer, the downloader requests only `config.json`
so gated-access problems fail early. Preparation then downloads the pinned
Orcarouter checkpoint, only the three pinned source shards containing the 31 MTP
tensors, and writes an audited local overlay.

The qualified profile is loopback-only, native 262,144-token context, eight maximum
sequences, PIECEWISE capture, BF16 KV, no PLE prewarm, and `MTP=2`. The runtime
unloads an existing recipe-labelled container before a guarded replacement.

## Recommended thinking sampler

The MTP sweep used thinking mode with medium reasoning effort and:

```text
temperature=1.0 top_p=0.95 top_k=20 min_p=0.0
presence_penalty=0.0 repetition_penalty=1.0
```

Reasoning effort is a request/client setting; it is not baked into the weights.

## Limitations

- This repository is a recipe only and does not distribute model weights.
- Runtime qualification covers only the pinned Orcarouter checkpoint and its
  documented RadixArk-sourced BF16 MTP overlay. Inferact and RadixArk remain runtime
  unvalidated.
- The overlay assumes matching Qwen3.8-Flash-Next architecture and exact pinned
  tensor identities. It is audited rather than treated as a generic plug-in.
- Measurements are point-in-time observations, not capacity guarantees.

## License

The recipe code is licensed under [Apache-2.0](LICENSE). Model use remains subject
to the licenses and access terms of the referenced repositories. See
[NOTICE](NOTICE) for attribution.

## Credits

- blazux originated the FP8 PLE mmap work.
- YSLAB-ai added BF16 PLE support, DGX Spark compatibility fixes, checkpoint-aware
  preparation, the guarded BF16 MTP overlay, and runtime qualification.
- Qwen and vLLM provide the model architecture and serving foundation.
