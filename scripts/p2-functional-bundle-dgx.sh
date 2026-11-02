#!/usr/bin/env bash
# P2 one-turn DGX operator entrypoint: source tests + combined candidate stage.
# --check: stdlib source tests only. --stage: read-only Docker inspect/cp and
# private /tmp stage; NEVER docker build/run/exec/stop/start, GPU, HTTP.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
[[ "$#" -eq 1 && ( "$1" == "--check" || "$1" == "--stage" || "$1" == "--stage-mtp" ) ]] || {
  echo "P2_BUNDLE_USAGE: --check|--stage|--stage-mtp" >&2; exit 2;
}
HEAD="$(git rev-parse HEAD)"
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1

# Same exact HEAD/fork/branch/clean-manifest checks for both modes.
python3 -m src.p2_functional_bundle --expected-head "$HEAD" --check
# Only the NEW tests are needed; the previous 40/40 CPU receipt is preserved.
python3 -m unittest -v tests.test_p2_functional_bundle tests.test_p2_mtp_candidate_overlay
if [[ "$1" == "--stage" || "$1" == "--stage-mtp" ]]; then
  # Exact pinned original ID is a read-only access acknowledgement; no service
  # interruption is permitted by this or any sub-command.
  python3 -m src.p2_functional_bundle \
    --expected-head "$HEAD" \
    --confirm-original-id '3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45' \
    "$1"
fi
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || {
  echo "P2_BUNDLE_HEAD_CHANGED" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P2_BUNDLE_REPOSITORY_DIRTY" >&2; exit 2;
}
echo "P2_BUNDLE_SOURCE_COMPLETE HEAD=$HEAD MODE=$1 NO_BUILD_NO_GPU_NO_API"
