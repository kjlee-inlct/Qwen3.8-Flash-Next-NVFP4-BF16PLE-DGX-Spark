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
