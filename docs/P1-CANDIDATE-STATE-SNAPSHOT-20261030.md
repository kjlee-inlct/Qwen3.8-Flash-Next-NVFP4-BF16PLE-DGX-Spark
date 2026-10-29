# P1 Candidate-only Mamba state snapshot — 2026-10-30

## Source provenance

- User-uploaded exact DGX source bundle p1-final-source-37e8962562bd.tar.gz includes pinned Stage model-state methods and installed mamba_utils.py fused helper. Pinned source SHA256: 25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3.
- preprocess_state calls _ensure_align_ctx before fused state-advance/precopy and forward. The first safe source-confirmed sampling site is AFTER _ensure_align_ctx initializes the group tables and state context, and BEFORE the precopy/forward.
- postprocess_state updates accepted tokens and conditionally calls ctx.run_fused_postprocess_align. Sampling AFTER the method and explicitly synchronizing CUDA supplies a bounded postprocess state snapshot if the selected request has reached an exact Mamba-block token boundary.
- _copy_mamba_state_block uses group-indexed physical block table, state_base_addrs, state_block_strides, state_inner_sizes and state_conv_widths. Temporal copies natural tensor bytes (exclude page padding); conv SD/DS copies valid shifted windows. _memcpy_u64_tiled selects an aligned u64 head/body/tail or bytewise misaligned fallback. A kernel *launch* can fast-exit and is not proof a copy ran.

## New opt-in candidate-only hook

- src/p1_prefix_state_snapshot.py is copied to _p1_prefix_state_snapshot.py in the stopped, isolated candidate overlay and SHA-verified. Only this candidate receives the fixed P1_PREFIX_STATE_SNAPSHOT=1 opt-in env. Original container, image, mounted model data, and SHA-pinned Stage are not modified.
- The candidate wrapper samples (a) after _ensure_align_ctx, before precopy/forward, and (b) after postprocess_state. The target is the **previously observed 6400-token cache HIT boundary** (Mamba block size 1600, persistent column 3), even if the cold request has advanced to 9503 or more tokens. It refuses n < 6400 or incompatible Mamba block sizes. Every event preserves the actual observed computed count separately and does not claim Cold/HIT attribution.
- Each selected persistent GPU cache tensor physical block is converted to contiguous logical bytes, explicitly synchronized, SHA256-hashed on candidate CPU, and immediately discarded. Never log raw model values, GPU pointers, weights, prompts or request identifiers. Cap at 32 MiB per block tensor, 4 states/event, 8 events per phase.
- A first-layer sample is NOT full-model coverage; only states accessible via live copy_funcs are labeled conv/temporal. The candidate worker emits P1_PREFIX_STATE_SNAPSHOT_JSON with anonymous layer SHA prefix, physical block id, group id, boundary, state kind and state content hash.
- GPU oracle's candidate observer retains up to 16 filtered state snapshot records before candidate cleanup (otherwise Docker logs vanish). This is NOT a verified Cold-HIT pair: HTTP request attribution and cross-layer timing are not established. The flags physical_mapping_and_reuse_verified and candidate_state_snapshot_full_cold_hit_pair_verified stay false, and the strict 1e-4 logprob threshold is unchanged.

## Exit and recovery gates

1. DGX read-only closure prep must pass all existing CPU mocks plus the new candidate snapshot/parse regression cases; expected targeted total 96. Verify source manifest and original running status, Stage SHA, installed source SHA, and exact HEAD. A failure blocks GPU.
2. A single operator-approved exclusive GPU maintenance window uses the existing script scripts/p1-prefix-gpu-window.sh --expected-head SHA --execute --confirm-id ORIGINAL_RECEIPT_ID. It temporarily stops the original. The script must clean candidate and restore original same-ID, HTTP /health and /v1/models; no pause to release GPU.
3. Capture full candidate oracle JSON, active_candidate_abi.candidate_state_snapshot_records, the exit code, and original recovery proof. Nonzero exit remains inconclusive/failure even when restoration passes.
4. Correlate real Cold/HIT snapshots by actual request and block identity, verify all GDN/PLE states and timing, then address no-HIT strict numerical nondeterminism separately. No diagnostic HASH match alone may upgrade the final gate.

This commit is candidate-only GPU evidence preparation and is NOT final P1 PASS.
