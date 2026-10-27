#!/usr/bin/env bash
# Read-only: verify tracked tree, Docker inspect, and benchmark provenance.
# No docker exec/run, GPU, HTTP, model load, CI, patch, benchmark or service change.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
test "$(git branch --show-current)" = "feature/blazux-phase6-runtime-gates" || {
  echo "BLOCKED: wrong branch"; exit 2;
}
test -z "$(git status --porcelain=v1 --untracked-files=all)" || {
  echo "BLOCKED: dirty checkout"; exit 2;
}
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_readonly_preflight.py
