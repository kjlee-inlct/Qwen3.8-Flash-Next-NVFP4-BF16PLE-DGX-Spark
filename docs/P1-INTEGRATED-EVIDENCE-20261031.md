# P1 integrated candidate DGX evidence — 2026-10-31

Observed on DGX, feature branch HEAD 0ac95dbbccbeec2e261979886e120190608e20a8.
User-provided exact source/test/preflight log, no runtime inference.

- PASS_SOURCE_ONLY: 295 tracked files.
- Runtime safety tests: 7/7 PASS.
- Phase6 offline regression: 346/346 PASS.
- CPU runc one-shot: network none, GPU void, read-only, memory 1 GiB.
- PLE byte_exact=1, concurrency=24, synthetic warm CPU timing
  off_median_us=91.840, on_median_us=106.863.
- Phase4 fast_gather x stats CPU flag matrix: 4/4 byte exact PASS.
- Integrated image preflight PASS_NO_GPU_NO_MUTATION; original state running.
- Integrated image sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d.
- Original same ID: 3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45.
- No GPU inference / Responses / tools / strict numeric or full GDN/PLE
  state reuse of the integrated image was performed.

Candidate-only API verification code: src/p1_integrated_api_check.py.
Only after explicit operator-approved GPU maintenance stop + guarded launch:
  python3 -m src.p1_integrated_api_check --expected-head "$HEAD" --confirm-candidate-id "$CID" --api-smoke
  python3 -m src.p1_integrated_api_check --expected-head "$HEAD" --confirm-candidate-id "$CID" --prefix-oracle

These two actions only send synthetic inference to 127.0.0.1:18080,
require original exited and exact running label-owned candidate ID,
and produce bounded metadata. Prefix oracle retains strict 1e-4 and
collects no-HIT controls; full physical GDN/PLE state reuse is not proven.
Even if any API probe exits nonzero, the independently guarded
src.p1_integrated_runtime --restore step MUST still be performed using
the exact original and candidate IDs. Do not put restore only after
a success-only shell chain. Existing original stays running until
separately authorized stop; no P1 final PASS or production promotion.
