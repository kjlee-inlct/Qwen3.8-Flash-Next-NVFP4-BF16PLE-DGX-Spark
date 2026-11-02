#!/usr/bin/env bash
# P2 exact DGX four-COPY stage -> one-COPY Numeric-only diagnostic candidate.
# --preflight metadata only, --prepare private /tmp source context only.
# NO docker build/run/stop/start/exec, HTTP, GPU, model, or API.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
[[ "$#" -eq 2 && ( "$1" == "--preflight" || "$1" == "--prepare" ) ]] || {
  echo "P2_NUMERIC_MINIMAL_USAGE: --preflight|--prepare /tmp/p2-functional-bundle-<id>" >&2; exit 2;
}
MODE="$1"
STAGE="$2"
[[ "$STAGE" == /tmp/p2-functional-bundle-* ]] || {
  echo "P2_NUMERIC_MINIMAL_EXPECTS_PRIOR_FOUR_COPY_STAGE" >&2; exit 2;
}
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
HEAD="$(git rev-parse HEAD)"
# Ten NEW focused contract tests; prior 29/29 real DGX results are retained.
python3 -m unittest -v tests.test_p2_numeric_minimal_candidate
python3 -m src.p2_numeric_minimal_candidate --expected-head "$HEAD" \
    --stage-dir "$STAGE" "$MODE"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || {
  echo "P2_NUMERIC_MINIMAL_HEAD_CHANGED" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P2_NUMERIC_MINIMAL_SOURCE_DIRTY" >&2; exit 2;
}
echo "P2_NUMERIC_MINIMAL_SOURCE_COMPLETE HEAD=$HEAD MODE=$MODE NO_DOCKER_BUILD_NO_GPU_NO_HTTP"
