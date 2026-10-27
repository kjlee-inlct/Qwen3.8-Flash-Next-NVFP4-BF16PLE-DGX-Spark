#!/usr/bin/env bash
# User-authorized existing-service single 12x3 bench; not P6-A/B/D gate PASS.
# --preflight is no-load. --execute sends real workload to 127.0.0.1:8000.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ "$#" == 1 && ( "$1" == "--preflight" || "$1" == "--execute" ) ]] || {
  echo "BLOCKED: specify --preflight or explicitly approved --execute" >&2; exit 2;
}
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "BLOCKED: wrong Phase6 branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "BLOCKED: dirty dedicated checkout" >&2; exit 2;
}
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_ab_provisional_bench.py "$1"
