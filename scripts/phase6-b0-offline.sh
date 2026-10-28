#!/usr/bin/env bash
# P6-B0 synthetic CPU-only copy/bounds rehearsal; no GPU, model, Docker or HTTP.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ "$#" -eq 0 ]] || { echo "BLOCKED: no flags accepted" >&2; exit 2; }
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "BLOCKED: wrong branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "BLOCKED: dirty checkout" >&2; exit 2;
}
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests \
  -p 'test_blazux_phase6_b0_cpu_bounds.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_b0_cpu_bounds.py --demo
echo "PHASE6_B0_OFFLINE_PREPARATION_COMPLETE_NO_GPU_NO_ABI_PASS"
