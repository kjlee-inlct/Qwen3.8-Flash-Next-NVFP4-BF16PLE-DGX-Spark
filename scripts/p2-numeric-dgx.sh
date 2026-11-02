#!/usr/bin/env bash
# DGX entrypoint after git pull; source tests and optional private source stage only.
# Does NOT run or build a model, stop/start/exec Docker or query inference HTTP.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
usage() {
  printf 'Usage: bash scripts/p2-numeric-dgx.sh --check | --stage\n' >&2
  exit 2
}
[[ "$#" -eq 1 ]] || usage
case "$1" in
  --check|--stage) MODE="$1" ;;
  *) usage ;;
esac
HEAD="$(git rev-parse HEAD)"
export PYTHONDONTWRITEBYTECODE=1
# The original release-only --strict branch allowlist is NOT valid for P2.
# qsa.preflight checks the exact P2 branch, clean source manifest and fork.
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 -m unittest -v \
  tests.test_p2_numeric_boundary \
  tests.test_p2_numeric_sampler_witness \
  tests.test_p2_numeric_dgx_prepare
if [[ "$MODE" == --stage ]]; then
  # Pre-pinned original ID. The Python stage checks actual ID, image,
  # StartedAt and pinned Sampler SHA before writing to a NEW private /tmp dir.
  python3 -m src.p2_numeric_dgx_prepare \
    --expected-head "$HEAD" \
    --confirm-original-id "3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45" \
    --stage
fi
printf 'P2_DGX_SOURCE_ONLY_DONE mode=%s HEAD=%s (no GPU/API/build/service change)\n' "$MODE" "$HEAD"
