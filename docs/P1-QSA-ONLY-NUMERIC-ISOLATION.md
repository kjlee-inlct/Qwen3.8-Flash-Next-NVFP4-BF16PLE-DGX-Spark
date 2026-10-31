# QSA-only numeric isolation candidate — experiment B

CPU-only, single-variable build for strict 1e-4 root-cause analysis.

## Confirmed operator GPU evidence

Original Prefix OFF + MTP2 + stock QSA ran four identical synthetic long
Chat requests, all 150 token IDs identical, all finish reasons identical.
Original source HEAD c9eaccbca557a5157c4134f963bcfdf3c1d57bb1.
Observed original maximum all-pairs logprob absolute delta:
0.00036634469870477915 (> 1e-4).
First-token reference max 0.00029654306126758456; only the first
token (index 0) exceeded strict relative to the first run.
Original stock path was numerically nonreproducible under the existing
criterion even with Prefix cache disabled. Do not assign cause to Prefix.

Previously integrated Prefix ON + MTP2 + exact QSA candidate also
exceeded strict: cold/HIT max 0.0001794818672351539 and no-HIT
max 0.00015837186947464943. Comparing these maxima does NOT
prove improvement or causality: different service windows, Prefix
behavior, image layering and scheduling.

## Exact A/B design

A = original image yslab-qwen38-bf16ple:9492b78c, original Prefix OFF,
MTP2, original BF16 PLE, original QSA stock. A measured above.
B = exact A parent + ONE patched QSA Python COPY and image ENV
VLLM_QSA_EXACT_TOPK=1, with Prefix OFF, MTP2, and original PLE.
Builder: src.p1_qsa_isolation_image --build --expected-head HEAD.
Checks SHA256-pinned original qsa.py and Python AST, one-copy
image ancestor, original unchanged after build, no other code changes.
Image build is CPU-only and does NOT run model or containers.

B has NOT undergone GPU runtime or strict numeric measurement. Future
GPU window needs a separate audited B-only service controller that
preserves the ORIGINAL Prefix OFF command; NEVER use the existing
P1 integrated runtime or Prefix-ON launcher for this B image.
Only after explicit permission to stop the original for a maintenance
window, compare four serialized requests with exactly the same
synthetic prompt/seed and token-level metrics, control load/order.
If B is strict-stable, investigate QSA stock selection as a major
contributor (still not definitive proof from one window). If B still
drifts, test MTP ON/OFF with only that variable changed next.
No strict threshold relaxation. Do not merge main or change service.

## DGX CPU build receipt and next B-only runtime (2026-10-31)

Actual operator CPU build ran at source HEAD
`c3d31b7f3ab30d91e3562acb87555df19385c1db`:
Source Manifest **307/307 PASS**, isolated builder unit tests **5/5 PASS**.
Pinned B image `kjlee-qwen38-p1-qsa-isolation:c3d31b7f3ab3`
has exact image ID
`sha256:3d1c21c8fea3ed57dafad2f97c4cd8af1c3bce1f3cb22897cd87901b021b9fe7`,
original base ID `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`,
patched QSA SHA256 `7cb6299c6b58dc051197d4a516c85a8d07552ecf81f29db21f900b8a44a2334f`.
Original same-ID Running and HTTP port 8000 PASS. No B GPU execution.

The next source-only feature implements a dedicated B-only lifecycle/numeric
controller at `src/p1_qsa_only_runtime.py`; see
[P1 QSA-only runtime](P1-QSA-ONLY-RUNTIME-WINDOW.md). That controller and
its tests are **GitHub source-only until actual DGX verification**. It keeps
the original exact Prefix-OFF command, requires fresh GPU-window approval,
and restores the same-ID original after B. Do not reuse the integrated
Prefix-ON controller or compare historical A maxima as matched A/B evidence.
