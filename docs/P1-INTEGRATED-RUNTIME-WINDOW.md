# P1 integrated image: guarded GPU-window lifecycle

Exact integrated P1 image built by operator on DGX (2026-10-31):
kjlee-qwen38-p1-integrated:bf80867dc5be
sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d
Contains Prefix ON changes, QSA exact top-k experiment, Preview-native
Tool/Responses patch, and opt-in BF16 PLE phase stats (OFF by default).
Original full-ID service port 8000 remained running and HTTP healthy.

src/p1_integrated_runtime.py is distinct from the original two-file
scripts/p1-prefix-release.sh. Never mix these two release controllers.

READ-ONLY NEXT STEP, NO GPU ALLOCATION OR SERVICE MODIFICATION:
  HEAD=$(git rev-parse HEAD)
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_integrated_runtime
  PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_integrated_runtime --expected-head "$HEAD" --preflight

Independent BF16 PLE CPU fixture regression, using the existing restricted
one-shot Docker CPU-only runc test harness (does not enter legacy service):
  bash scripts/ple-phase-stats-cpu-container.sh --expected-head "$HEAD" --execute

FUTURE GPU SERVICE WINDOW: NOT AUTHORIZED by this implementation or image build.
After an explicitly approved maintenance window and pinned full original ID,
stop only via existing scripts/stop.sh --expected-head and --confirm-id --execute.
Only after original is verified EXITED may the integrated controller launch
with --launch --confirm-original-id FULL64. Launch uses port 127.0.0.1:18080
and preserved MTP2/Prefix ON, never binds port 8000 or stops original.
To clean up, use --restore --confirm-original-id FULL64
--confirm-candidate-id FULL64 (the ID returned by launch). This removes
only the exact label-owned candidate and restores the same original ID
using scripts/start.sh, then verifies port-8000 health and model ID.
Launch failure attempts owned cleanup before original recovery; uncertain
ownership or cleanup fails closed to avoid two models on the single GPU.

At future runtime: verify Chat/Responses/API, tool calls and streaming;
cold/hit HIT telemetry + MTP acceptance, strict logprob absolute 1e-4
without relaxation, and GDN/PLE full-state evidence separately. The
un-instrumented integrated release does not by itself prove full state reuse.
Do not auto-promote to production, alter P2/P3, PR/merge or main.
