#!/usr/bin/env bash
# P6-A→B checkpoint plan-only; validates immutable baseline without load.
# NEVER calls Docker, nvidia-smi, CUDA, HTTP, llama-benchy, or a model.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "BLOCKED: unexpected Phase6 branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "BLOCKED: dirty dedicated checkout" >&2; exit 2;
}
[[ "$#" -eq 0 ]] || {
  echo "BLOCKED: this is a plan-only runner, no --execute accepted" >&2; exit 2;
}
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_ab_benchmark_plan.py
echo "PHASE6_AB_BENCH_BASELINE_LOCKED_NEW_BENCH_NOT_RUN"
