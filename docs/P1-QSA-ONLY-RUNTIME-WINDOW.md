# P1 QSA-only B runtime: isolated GPU candidate (NOT EXECUTED)

The operator-built one-COPY image is already present on DGX. Do not rebuild
the P1 integrated Prefix-ON image or confuse it with this B-only image.

- DGX-tested builder HEAD: `c3d31b7f3ab30d91e3562acb87555df19385c1db`.
- Source Manifest 307/307, builder unit tests 5/5: operator PASS.
- B image: `kjlee-qwen38-p1-qsa-isolation:c3d31b7f3ab3`.
- Exact image ID: `sha256:3d1c21c8fea3ed57dafad2f97c4cd8af1c3bce1f3cb22897cd87901b021b9fe7`.
- Base ID: `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`.
- Patched QSA SHA256: `7cb6299c6b58dc051197d4a516c85a8d07552ecf81f29db21f900b8a44a2334f`.
- Original same-ID Running and port 8000 HTTP health: operator PASS.
- **B GPU and strict logprob: NOT_RUN.** Runtime code in this document is
  GitHub SOURCE_ONLY until independently executed on DGX.

Independent runtime: `python3 -m src.p1_qsa_only_runtime`. It pins the
already-built image, checks the one-file ancestor and expected labels, and
validates the original Prefix OFF/MTP2 command *without replacing it*. The
integrated runtime's Prefix-ON command MUST NOT be reused. Loopback
`127.0.0.1:18080` only, read-only HF model/cache mounts; independent
candidate name and labels. It never installs/patches any original resource.

## Before any new maintenance authorization: read-only only

From clean `~/Workspace/llm/blazux-phase6-gates` checkout:
```bash
git pull --ff-only origin feature/blazux-phase6-runtime-gates
HEAD="$(git rev-parse HEAD)"
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_qsa_only_runtime
PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_qsa_only_runtime --expected-head "$HEAD" --preflight
```
Preflight does not start containers, allocate GPU, send inference, stop or
restart the original service. If image or original container identity differs,
STOP and diagnose without auto-building or replacing assets.

## Future service-window lifecycle — commands are illustrative, NOT approved

Obtain **fresh, explicit operator approval** for original A inference, its
maintenance stop, B launch/GPU inference and original same-ID restore.
PIN_IMAGE_ID above and original 64-char container ID must be recorded.
Perform A original numeric probe only if explicitly authorized, using
`src.p1_original_numeric_baseline` with exact seed/prompt/request settings.
The old original measurement is a reference, NOT a same-window A result.

After an approved P1 `scripts/stop.sh` stop-only action has verified the
original is EXITED, invoke `--launch --confirm-original-id FULL64
--confirm-image-id sha256:3d1c21c8fea3ed57dafad2f97c4cd8af1c3bce1f3cb22897cd87901b021b9fe7`.
Capture the returned `candidate_id` and verify it before any probe. Only
then invoke `--numeric` with both confirmed IDs, exact image ID, and
`--expected-head HEAD`. This sends **four serialized synthetic GPU requests**
to B on loopback port 18080, with the original baseline payload/seed and
unchanged strict `1e-4` per-token logprob comparison. Tokens, prompt text and
logprob vectors are never printed. A numeric FAIL is a *completed negative
measurement*, not a P1 acceptance; incomplete evidence exits nonzero.

**Always run an independent `--restore` with both confirmed IDs even if
`--numeric` fails.** Cleanup removes only the exact label/image/ID-owned
candidate; original same-ID `scripts/start.sh` plus HTTP readiness is checked.
No success-only `&&` chain or `set -e` trap that skips restore after
probe failure. If ownership is uncertain, recovery fails closed rather than
starting two models simultaneously. Power interruption requires manual
inspection of the exact candidate/original ID before restoration.

Interpretation: B's repeated-requests numeric reproducibility is compared with
a strictly matched same-window A, not an unrelated historical maximum. Even
a B PASS is evidence of a QSA contribution only after controlled repeats;
it does not prove cache correctness or full GDN/PLE state reuse. B strict
failure motivates separately approved MTP2 ON/OFF isolation. No relaxation
of 1e-4, deployment, PR, main merge or P1 final PASS.

## 2026-10-31 operator-authorized single-window bundle — execution source only

The operator explicitly approved A 4-request baseline, original stop, B 4
requests, same-ID restore, and batching toward the P1 integrated checks.
The bundle adds NO new Docker image, GPU kernel code, model payload or service
configuration. It automates the existing pinned controllers.

New entry point `src.p1_qsa_window_bundle` has an explicit `--execute`
switch and must be called with the new exact Git HEAD and **both** the pinned
original container ID and pinned B image ID. It fails closed if checks drift.
Under one top-level invocation:

1. Before stop, verify B image/original and, if requested, integrated image;
   measure A **exactly four** sequential same-payload Chat requests to the
   current original (Prefix OFF/MTP2/stock QSA). If incomplete, abort before
   stop. Pre-existing original work/other external traffic may confound A.
2. Stop the original only through `scripts/stop.sh` with exact ID. Launch B
   at 127.0.0.1:18080 (Prefix OFF/MTP2/exact QSA) and issue **exactly four**
   synthetic Chat requests. Compute A and B within-arm pairwise strict
   logprob maxima and, only when IDs match, aligned cross-arm drift. All
   prompts/seed/temperature/max_tokens are from **one shared payload**,
   never exposed in output.
3. In `finally`, independently inspect and remove ONLY exact owned B,
   restore the ORIGINAL same container ID (start.sh) and check port8000
   /health + /v1/models. A measurement FAIL or model exception must not
   bypass attempted restoration.
4. **Optional** `--include-integrated-if-b-strict`: only when B has
   measured within 1e-4, attempt a *second* stop/launch/restore cycle
   in the same authorized operator invocation, using the exact existing
   integrated image. Run corrected forced-tool roundtrip + Responses smoke
   and integrated Prefix HIT/MTP/no-HIT-control strict oracle. Independent
   label-owned cleanup/restore is still mandatory after failed probes.
   If B exceeds strict, **skip integrated**: isolate MTP next rather than
   consuming GPU on an already nonreproducible baseline. No automatic
   MTP-off launch or new image is created.
5. On terminal SIGINT/SIGTERM, try to unwind with finally; repeated signals
   are ignored during recovery. SIGKILL, Docker daemon crash, host reboot
   or ambiguous candidate ownership cannot guarantee automatic recovery.
   In ambiguous ownership, do NOT force-start production alongside a
   possible live GPU candidate: inspect IDs and recover manually.
6. Print sanitized numeric summaries and recovery markers. Never claim
   a strict result from source/CPU tests, never report P1 completed just
   because numeric, tools or Prefix checks pass: **entire GDN/PLE live state
   provenance and PLE GPU phase stats remain separately unproven**.
   A/B order (A then B), maintenance interruption and scheduling may
   confound causal inference even in a single approved window.

One DGX operator command after pulling this source HEAD (exact SHA will be
provided with the commit):
```bash
export PYTHONDONTWRITEBYTECODE=1
python3 -m src.p1_qsa_window_bundle \
  --expected-head "$HEAD" \
  --confirm-original-id "3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45" \
  --confirm-b-image-id "sha256:3d1c21c8fea3ed57dafad2f97c4cd8af1c3bce1f3cb22897cd87901b021b9fe7" \
  --include-integrated-if-b-strict --execute
```
Do not add extra manual `start.sh` when the original same ID is already
running/HTTP PASS. If the bundle exits 2, read its last restoration marker,
then inspect original/B/integrated container identity before any manual
action. Log output is the user's DGX local receipt; GitHub documents only
summaries provided by the operator after execution.
