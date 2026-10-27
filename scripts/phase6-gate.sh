#!/usr/bin/env bash
# Phase6: safe local offline contract harness. Never starts DGX, GPU, CI, Docker or model.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || { echo "BLOCKED: wrong branch"; exit 2; }
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || { echo "BLOCKED: dirty checkout"; exit 2; }
python3 -m unittest discover -s tests -p 'test_blazux_phase6_*.py' -v
python3 scripts/verify-source-state.py
echo "PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN"
# No automatic runtime execution; explicitly supplied snapshot is evaluated as data only.
if [[ "${1:-}" == "--snapshot" && -n "${2:-}" ]]; then
  exec python3 src/phase6_gate.py --gate P6-A --snapshot "$2"
fi
[[ $# -eq 0 ]] || { echo "BLOCKED: unsupported arguments"; exit 2; }
