#!/usr/bin/env bash
# A3a read-only metadata + host/GPU telemetry, NO GPU compute/model/API.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
test "$(git branch --show-current)" = "feature/blazux-phase6-runtime-gates" || {
  echo "BLOCKED: unexpected branch" >&2; exit 2;
}
test -z "$(git status --porcelain=v1 --untracked-files=all)" || {
  echo "BLOCKED: dirty dedicated checkout" >&2; exit 2;
}
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_a3_readonly_resources.py
