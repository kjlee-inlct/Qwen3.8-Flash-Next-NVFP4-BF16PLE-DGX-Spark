#!/usr/bin/env bash
# Phase6 B1a: passive deployment/host/NVML feasibility. No GPU execution or model startup.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ $# -eq 0 ]] || { echo "BLOCKED: B1a accepts no flags" >&2; exit 2; }
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "BLOCKED: wrong feature branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "BLOCKED: dirty Phase6 checkout" >&2; exit 2;
}
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_b1_readonly_feasibility.py --observe
echo "PHASE6_B1A_READONLY_METADATA_CHECK_COMPLETED_NOT_GPU_PASS"
