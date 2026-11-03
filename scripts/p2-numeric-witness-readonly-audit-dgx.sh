#!/usr/bin/env bash
# Read-only Sampler provenance/branch audit after 2nd GPU witness absence.
# Only reads pinned private stage and original RUNNING container's sampler.py.
# No model HTTP, docker run/exec/start/stop, CUDA, or new image build.
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
if [[ $# -ne 2 || "$1" != "--audit" || "$2" != /tmp/p2-numeric-first-divergence-* ]]; then
  echo "P2_WITNESS_AUDIT_EXACT_STAGE_REQUIRED" >&2
  exit 2
fi
STAGE="$2"
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
HEAD="$(git rev-parse HEAD)"
python3 -m unittest -v tests.test_p2_numeric_witness_readonly_audit
python3 -m src.p2_numeric_witness_readonly_audit \
  --expected-head "$HEAD" --stage "$STAGE"
echo "P2_WITNESS_READ_ONLY_AUDIT_COMPLETE HEAD=$HEAD NO_GPU_NO_MODEL_HTTP_NO_DOCKER_MUTATION"
