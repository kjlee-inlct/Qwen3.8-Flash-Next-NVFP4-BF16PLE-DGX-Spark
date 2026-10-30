# P1 Prefix ON deployable image — feature branch, 2026-10-30

## Scope: build the feature, not more synthetic validation

The P1 Preview Prefix-cache fixes are already proven to cause real cache HITs
with BF16 PLE and MTP=2: Mamba seed divisor uses
`self.cache_config.mamba_block_size`; scheduler split uses `self.block_size`.
Do not change the pinned `/tmp/p1-prefix-stage.2dSPVPR6` files or the
currently running Prefix-OFF legacy service merely to build the release.

This new path produces a **persistent local Docker release image with just
two SHA-pinned Python overlay files** copied into the exact imported vLLM
package paths, derived from pinned YSLAB original image.
No observer, snapshot hooks, model weights, host Stage mounts or release
Dockerfiles containing a CUDA RUN step are included. After an image is built,
the **runtime no longer depends on the /tmp Stage directory**.

Feature branch files:
- `src/p1_prefix_release.py`: CPU-only local image builder plus an isolated
  opt-in runtime launcher and controlled same-ID rollback.
- `scripts/p1-prefix-release.sh`: HEAD, branch, clean checkout, origin,
  source manifest and explicit action gate.
- `tests/test_blazux_phase6_prefix_release.py`: 9 narrowly scoped release
  safety tests (no GPU/candidate creation from tests).

Pinned base image ID:
`sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`.
Pinned patched sources:
- `mamba_hybrid.py`: `1dfb7b5566c8e683afff6640b1764c774c27daaa817437862fd465e63da9f381`
- `scheduler.py`: `0501cec135d23a21f988c67371f8f1dbf97cc63726c9c44b89e350c8887178d7`

## Phase A — real persistent image build, original keeps running

First run targeted offline/source preflight at the exact feature HEAD:

```bash
HEAD="$(git rev-parse HEAD)"
bash scripts/p1-prefix-closure-prep.sh --expected-head "$HEAD"
```

Then build **locally without GPU/CUDA execution**:

```bash
bash scripts/p1-prefix-release.sh --expected-head "$HEAD" --build
```

The builder refuses changed/missing host Stage SHA, changed original image ID,
unexpected imported vLLM directory, foreign pre-existing release image tag,
unknown original container state and unreviewed source checkout. It requires
the original `running` and checks that it stays the **same running container
ID** at the end. Docker BuildKit gets no network (`--network=none`), no
remote pull (`--pull=false`) and executes **COPY statements only**. The
output is a persistent, independent local image:

`kjlee-qwen38-p1-prefix:<12-character feature HEAD prefix>`

Image labels bind exact full feature HEAD, local base-image SHA256, the two
Stage source SHA256s, vLLM package path, and `observer=absent`. RootFS
ancestry must be exactly original base layers + 2 COPY layers. This is an
**image build result, not runtime correctness / strict logprob PASS**.

## Phase B — OPTIONAL future service window, NOT authorized by image build

This phase interrupts the existing port-8000 service. **Do not perform it
without an approved exclusive GPU service window.**

1. Independently verify original full 64-character receipt container ID and
   original `/health`, `/v1/models`, original still `running`.
2. Use **only** the existing P1 service-window `scripts/stop.sh
   --expected-head "$HEAD" --confirm-id "$ORIGINAL_ID" --execute` to stop
   the original. A pause cannot free GPU memory; never use it here.
3. Start the built release image *without touching port 8000*:

   ```bash
   bash scripts/p1-prefix-release.sh --expected-head "$HEAD" \
     --launch --confirm-original-id "$ORIGINAL_ID"
   ```

   The launcher **does not stop the original**: it strictly requires
   the original exact ID already in the `exited` state and no existing release
   container or debug candidate. It uses read-only model mounts, MTP=2
   unchanged, Prefix ON and `127.0.0.1:18080` only; readiness checks use
   both `/health` and `/v1/models`. It logs the release container full ID.
   This is the actual deployable implementation and does not install any
   candidate diagnostic instrumentation.
4. After explicitly reviewing the running release, restore the original:

   ```bash
   bash scripts/p1-prefix-release.sh --expected-head "$HEAD" \
     --stop-and-restore --confirm-original-id "$ORIGINAL_ID" \
     --confirm-release-id "$RELEASE_ID"
   ```

   This verifies release container label, image ID and full 64-hex ID before
   removing **only** the release container, then delegates original same-ID
   restart to existing P1 `scripts/start.sh`, checks original same ID and
   port-8000 HTTP readiness. No automatic port migration or production
   configuration changes are provided. If any cleanup/identity check fails,
   do **not** start the legacy service while the GPU release might still run.
   Use an operator-reviewed recovery window.

If release launch fails after creating an owned candidate, the controller
attempts owned cleanup **before** restoring the original same-ID container.
On uncertain ownership or cleanup failure it fails closed and can leave the
original stopped rather than risk two models using the single GPU. The caller
must inspect the exact reported failure marker before any recovery.

## Known unfinished functionality

Release image build does not resolve numeric parity: recent actual GPU
Candidate Cold/HIT logprob maximum `0.0003418332780711353`, Cold-reference
versus no-HIT salt controls `0.0002452267217449844`, no-HIT
control/control `0.00005613901885226369`. The strict acceptance threshold
remains `0.0001`, **P1 final PASS is not claimed**. The selected state
sha256 Cold-to-HIT 12/12 are actual bounded comparisons across requests 2–4,
not full-layer GDN/PLE coverage or a proof of copy execution.

No main/PR/merge, model weights, original Docker/image, immutable host Stage
or production port 8000 changes are allowed by this feature branch.
