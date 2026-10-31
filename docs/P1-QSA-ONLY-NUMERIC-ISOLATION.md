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

## Actual same-window A/B result (operator DGX, 2026-10-31)

Exact execution source HEAD `5f3eb29eece1470090c0623a4890161a42a7f342`:
source Manifest **312/312 PASS**, targeted CPU **18/18 PASS**,
both B and integrated read-only preflight PASS.
A and B used the SAME shared long synthetic payload (seed=42) and four
serial requests each. Each arm returned identical 150 token IDs and
finish reasons. **A stock QSA / Prefix OFF / MTP2** all-pairs max
`0.00022305361926555634`, exceed token indices `[0,2]`;
**B exact QSA / Prefix OFF / MTP2** all-pairs max
`0.00031112757278606296`, exceed indices `[0,148]`.
Both exceed **strict 0.0001**. Corresponding A-vs-B max
`0.00026372616412118077`, exceed index `[0]`;
same-index A/B token IDs and finishes matched. No causal effect estimated
from the ratio of observed sample maxima.

B candidate ID `d5fee689d47637e26b6b2d64d0d7278fcfe19535c0c5f4d0867476cd953482d2`
was launched and removed by the owner-checked lifecycle; receipt:
`B_CLEANED_ORIGINAL_SAME_ID_HTTP_PASS`. Conditional integrated arm was
**SKIPPED_B_NOT_STRICT_OR_DISABLED**, exactly as programmed. Bundle exit=2
indicates numerical failure, not a service-restore failure. DGX local full
log: `/tmp/p1-qsa-ab-window.ZT1Kzy9d.log` (not a GitHub attachment).

**Inference:** QSA Exact Top-K alone is insufficient to restore strict
repeatability. It remains possible that QSA changes numerical behavior;
these four-request arm-wise maxima do not determine that. Prefix-enabled
cache is also unnecessary for the strict error. Next isolate common
MTP2 speculative decoding from non-MTP numerical nondeterminism.

## Next C-arm: MTP OFF, stock QSA, original image, Prefix OFF

A new source-only one-window controller
`src/p1_mtp_off_numeric_isolation.py` (CPU tests in
`tests/test_p1_mtp_off_numeric_isolation.py`) prepares **C** by using
the original exact Docker image and runtime settings, but removing the
single `--speculative-config {"method":"mtp","num_speculative_tokens":2}`
CLI pair. No candidate image build, QSA patch, Prefix ON, BF16 PLE
change or model-view edit. Dedicated 127.0.0.1:18080 container and
existing strict baseline `1e-4` oracle. It verifies the live candidate
Docker Cmd lacks the speculative flag and checks accepted-draft-token
counter delta (expected zero), while making no claim of GPU execution
until operator evidence is received. A fresh 4-request stock/MTP2
baseline is sampled before stopping the original; C runs four matching
requests; ownership-checked cleanup and same-ID original HTTP restore
are mandatory independent of numeric result.

This **next** GPU maintenance window has NOT been approved or run.
After exact Git HEAD checkout, operator may run read-only source/CPU
tests and `--preflight`. Actual `--execute` is forbidden until the
operator explicitly approves a new original-service outage and GPU
load. A successful C strict result suggests investigating MTP2 but
cannot by itself establish causal exclusivity or P1 PASS. If C fails,
the next target is non-MTP common GPU/PLE/sampling reproducibility,
not another speculative QSA conclusion. No strict relaxation.
