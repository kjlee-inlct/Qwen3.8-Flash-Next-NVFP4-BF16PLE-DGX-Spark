#!/usr/bin/env bash
# P6-A live API metadata observation only; never model inference/GPU/benchmark.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ "$#" == 0 ]] || { echo "BLOCKED: no flags accepted" >&2; exit 2; }
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "BLOCKED: wrong branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "BLOCKED: dirty source" >&2; exit 2;
}
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_a4_live_observer.py
