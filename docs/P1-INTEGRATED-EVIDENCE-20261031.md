# P1 integrated candidate DGX evidence — 2026-10-31

## 2026-11-02 통합 기능 최종 DGX 영수증 (아래 10-31 실험보다 최신)

**실제 실행 소스** `50fc65b65d10b36804c65e8a48d06d9bf3abecfe`; Source Manifest **327/327 PASS**, 최소 통합 런타임·정비창 CPU **10/10 + 10/10 PASS**, read-only functional preflight PASS. 승인된 단일 격리 GPU 창은 종료 코드 **0**, `P1_FUNCTIONAL_BOUNDED_EVIDENCE_PASS_NOT_RELEASE`, `functional_evidence_complete=true`, `primary_error=null`.

| P1 최소 기능 | 사용자 DGX 실측 | 범위 |
| --- | --- | --- |
| Tool/Responses | `tool_full_roundtrip=PASS`: forced named tool call ID/arguments → tool result → final answer. 기존 Responses nonstream/stream PASS 재사용 | Tool 왕복 PASS; 재시험 없음 |
| BF16 PLE phase stats | `ple_phase_stats_observed=true`, `calls=1`, `forward_calls=1`, `rows=131072`; CPU phase 값 수집 | DMA 완료시간/실 GPU kernel 시간은 미측정 (`gpu_dma_verified=false`) |
| Prefix ON + MTP2 | HIT `[0,6400,6400,6400]`, draft accepted +400, token IDs 동일, Cold→HIT 2·3·4의 선택 상태 각각 4/4 SHA 일치, 총 12/12, mismatch0 | `bounded_state_match=true`, `full_state_reuse_verified=false` |

**출시 판단은 독립:** `P1_FUNCTIONAL_VERIFIED=BOUNDED_PASS` (합의된 최소 검증 범위만), `P1_RELEASE_BLOCKED=TRUE`, `P1_FINAL_PASS=FALSE`, `DEPLOYED=FALSE`, `strict_numeric_release_pass=false`. 원본 Prefix OFF/No-MTP/first-token 및 Prefix ON에서 이전 strict logprob `1e-4` 초과 실측이 있어 출시 Gate는 여전히 미통과. 이 기능 창에서 strict no-HIT/numeric 재시험은 생략했으므로 기능 PASS가 숫자 Gate PASS는 아니다. 전 계층 실제 state/copy provenance와 CUDA H2D 완료 측정도 입증하지 않았다.

**운영 원복:** 후보 삭제, 원본 정확한 same-ID running·image unchanged·port 8000 `/health`·`/v1/models` PASS. 기존 통합 이미지는 그대로 사용했고 후보의 독립 writable layer에만 관측 코드를 복사했다. 실제 영수증과 이관 경계는 [Phase6 결과 장부](BLAZUX-PHASE6-RESULTS.md), [현재 인수인계](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md)를 우선한다. 승인된 단일 창은 소진됐다. 이후 새 정비창을 자동 실행하지 않는다.

### 이하: 2026-10-31 당시의 준비 및 이전 GPU 실행 기록 (역사 기록)


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
