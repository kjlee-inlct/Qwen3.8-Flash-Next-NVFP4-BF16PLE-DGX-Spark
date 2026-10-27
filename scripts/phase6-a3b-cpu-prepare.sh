#!/usr/bin/env bash
# Phase6 A3b-0: pure host stdlib synthetic contract and Docker command preview.
# Never Docker run/exec, import vLLM, load model, access GPU or HTTP.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "BLOCKED: wrong checkout branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "BLOCKED: checkout not clean" >&2; exit 2;
}
python3 scripts/verify-source-state.py
PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_a3b_cpu_config.py \
  --fixture tests/fixtures/phase6_a3b_synthetic.json
bash scripts/phase6-a3b-container-preview.sh --preview
echo "PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME"
