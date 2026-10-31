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

## 2026-10-31 readiness fixes before any GPU window

- The first integration API smoke only checked tool_call generation. It now
  sends one more Chat request with the exact emitted tool_call_id and a
  fictional tool result, then requires a nonempty final assistant message.
  This measures a complete nonstream Tool roundtrip (not comprehensive tool API).
- Numeric report now distinguishes Cold/HIT strict, no-HIT control-to-control
  reproducibility, and cold-reference-to-no-HIT reproducibility. The combined
  strict_numeric_pass requires all three under the unmodified 1e-4 threshold.
  A no-HIT control API/telemetry failure is INCONCLUSIVE, not PASS.
- Even if combined strict_numeric_pass is true, full_state_reuse_verified and
  p1_final_pass remain false until separate candidate-only full-state evidence.
- Existing integrated image SHA and original container are unchanged.

## Actual DGX P1 GPU service-window result (2026-10-31)

User approved the GPU window at feature HEAD
6c1397d78433b1fa2082047367b042b6e372a431. Operator report:
result log /tmp/p1-integrated-gpu.NImgD957.log (DGX local only).
The original same-ID container was restored and port 8000 HTTP passed.
Integrated candidate started, responded to Responses API, produced cache
HIT deltas [0, 6400, 6400, 6400], MTP accepted tokens +400, identical
output token IDs; NO P1 final pass.

The first forced named ToolCall passed callable name/JSON/ID checks, but
the P1 smoke returned TOOL_FINISH_REASON_INVALID before the tool-result
roundtrip. This was an overly strict client expectation: vLLM's named,
forced tool_choice may legitimately use finish_reason="stop" while
auto/required tool selection uses "tool_calls". Corrected only the
client checker to allow both "stop" and "tool_calls" *after* verifying
actual function name, arguments and call ID, with the full result
roundtrip still mandatory. The real finish_reason value was not printed
in the prior log, so the next live API test must verify this hypothesis.

Observed strict numerical results from integrated image:
- cold/HIT max token logprob absolute delta 0.0001794818672351539;
- cold/HIT exceedance positions (zero-based) 0, 145, 148;
- no-HIT control/control absolute max 0.00015837186947464943;
- cold-reference/no-HIT absolute max 0.00024062054581008852;
- repeated HIT/HIT maxima 0.00028819357976317406,
  0.0003216628101654351.
All exceed unchanged 1e-4 tolerance in at least one comparison.
The no-HIT reproducibility failure means **cache-specific numerical
fault is unproven**, even after QSA exact top-k was selected.
No global GDN/PLE state reuse or PLE GPU phase stats were verified.
Do not turn an API smoke correction into numerical or full P1 PASS.

The follow-up code change affects the API verification client and
regression tests ONLY. The immutable integrated Docker image is unchanged,
as are production model, MTP2, Prefix cache setting, and QSA implementation.
Do not initiate another GPU service window without explicit approval.
