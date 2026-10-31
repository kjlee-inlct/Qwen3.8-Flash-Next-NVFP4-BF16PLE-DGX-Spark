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
