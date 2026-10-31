# P1 original service Prefix-OFF/MTP2 numeric baseline

Why: The P1 integrated QSA-exact/Prefix-ON candidate already failed
strict 1e-4 not only in cold/HIT (max 0.0001794818672351539)
but also in verified no-HIT controls (max 0.00015837186947464943).
Before attributing that to Prefix-cache, characterize numeric
reproducibility of the **unchanged original** Prefix-OFF + MTP2 + stock QSA.

Tool: src/p1_original_numeric_baseline.py, explicit --probe-original.
It verifies the exact running original ID and protected original CLI
(Prefix OFF, MTP2, model name, utilization) before sending any requests.
Four sequential synthetic long-prompt Chat requests are sent only to
127.0.0.1:8000; inputs match the original Prefix GPU oracle.
Maximum logprob delta vs first and all-pairs are reported, plus up to
16 zero-based exceeding token positions. No model text, raw token IDs,
logprob vectors or original paths are printed. Recheck the original
identity after each request. This uses inference GPU time and may add
temporary latency to the live service. It does NOT stop/restart,
edit Docker/image/model, enable Prefix or alter runtime settings.

Run *only* when a few production test inference requests are acceptable:

    HEAD=$(git rev-parse HEAD)
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_original_numeric_baseline
    PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_original_numeric_baseline --expected-head "$HEAD" --probe-original

Interpretation:
- If original original-Prefix-OFF drifts above 1e-4, nondeterminism
  predates candidate-only Prefix reuse; investigate common QSA/MTP/GPU
  effects. It does not exonerate the cache pathway.
- If original is strict stable, compare candidate no-HIT and MTP/QSA
  controlled runs during an authorized future GPU service window.
- Neither outcome alone is P1 PASS. Different QSA, Prefix, and
  scheduling configurations prevent a single-variable causal proof.

Grounded prior P1 GPU image: sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d.
Original same ID was restored and HTTP healthy. This instrument never
creates any GPU service window, Docker container or attached observer.

## Actual DGX original measurement (2026-10-31)

Original Prefix OFF + MTP2 + stock QSA (no service interruption), four
identical synthetic long requests, 150 identical token IDs per request
and identical finish reasons. Exact original measurements:
- all_pairs_max_abs_delta=0.00036634469870477915
- reference_to_repeats_max_abs_delta=0.00029654306126758456
- first_token_max_abs_delta=0.00029654306126758456
- strict_exceed_positions_0_based_first16=[0]
- strict_abs_tolerance=0.0001, status=ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT
- synthetic_prompt_sha256=1b6782fe5048cf43e979a741a4d699f6866fefd0a6306b31b6b9c690e407f439.

Interpretation: strict numeric nonreproducibility exists before any
candidate-only Prefix-cache. A cache-specific numerical bug is neither
proven nor disproven. Existing integrated GPU result must not be
attributed to Prefix ON based on Cold/HIT max values alone.
For a more controlled variable isolation see
docs/P1-QSA-ONLY-NUMERIC-ISOLATION.md. No GPU candidate was run here.
