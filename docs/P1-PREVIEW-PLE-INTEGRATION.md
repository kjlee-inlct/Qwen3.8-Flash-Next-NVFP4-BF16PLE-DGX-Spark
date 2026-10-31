# P1 integrated Preview image — BF16 PLE mmap and opt-in phase stats

Objective: keep Orcarouter BF16 PLE and MTP2 while integrating existing
Blazux P1 Prefix-cache, QSA exact top-k experiment, Preview-native
Tool/Responses patches, and an instrumentable PLE mmap module.

## Grounded PLE provenance

Existing original DGX image PLE SHA256 =
91f17b6203f402785279836c479ead347416da4394049850a47f0ba347649b48.
That is exactly the source at Git commit
9492b78c6bc04638587b42f2ffeb0680b0fcb3ef,
src/vllm_ple_mmap.py (matched via GitHub raw source SHA256).
Current feature implementation SHA256 =
9c13cf71001618838532ee9145443647a09a087f68ef82e2c3909028b893617e.
History adds BF16 shard duplicate fail-closed check, default-OFF Fast Gather,
per-table gather/forward CPU-phase stats. CPU timers do not measure
asynchronous H2D completion, GPU time, or physical NVMe bytes.

## Candidate construction

Parent pinned image: kjlee-qwen38-p1-tool-qsa:b89641b4fb52
ID: sha256:e01dffd7542432476d81635e38a706fd73942c7f0832d8eacab34e9d2518cc66.
New image adds only a single COPY of the feature-branch PLE Python module.
Exact original and new PLE SHA256 are checked before local CPU-only build.
Original running container must retain its receipt ID; source HEAD, branch,
clean tree, remote and full Source Manifest are verified.

VLLM_PLE_PHASE_STATS and VLLM_PLE_FAST_GATHER remain OFF by default.
Stats must be enabled only in a separately authorized runtime candidate.
The image does not activate, restart, stop, or mutate the operating service.

## After exact HEAD fast-forward on DGX

    cd ~/Workspace/llm/blazux-phase6-gates
    HEAD=$(git rev-parse HEAD)
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_preview_ple_integrated_image
    PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_preview_ple_integrated_image --expected-head "$HEAD" --build

Source CPU behavior regressions from src/test_ple_phase_stats_cpu.py,
src/test_ple_phase4_cpu.py and src/test_ple_mmap_cpu.py should also be run
using the existing isolated CPU-only test harness before GPU work.

Image build success means only CPU/source integration is ready.
GPU loading, PLE timing, actual Tool/Responses HTTP, Prefix-cache strict
1e-4 logprob and complete GDN/PLE state reuse are all NOT_VERIFIED.
Do NOT use the prior two-file Prefix release launcher with this image;
a separately reviewed same-ID restore workflow and explicit new GPU
maintenance authorization are required.
