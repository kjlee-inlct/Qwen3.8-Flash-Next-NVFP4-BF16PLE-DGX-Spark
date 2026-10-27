#!/usr/bin/env bash
# Track A Phase 2: refuse wrong origin/branch or dirty state; never touch Docker.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase2-offline-fixtures"
ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git"|"ssh://git@github.com/$REPO"|"ssh://git@github.com/$REPO.git") ;;
  *) echo "STOP: not the personal fork" >&2; exit 2 ;;
esac

[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "STOP: expected the dedicated Phase 2 branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: checkout has modified/untracked files; never reset/clean" >&2; exit 2;
}
BASE="a50fc53721f3d23325dca44eb799f0f388d65951"
git merge-base --is-ancestor "$BASE" HEAD || {
  echo "STOP: Phase 1 finalized parent absent" >&2; exit 2;
}

export PYTHONDONTWRITEBYTECODE=1
echo "PHASE2_SOURCE_HEAD=$(git rev-parse HEAD)"
echo "Checking Git source inventory (no --strict for experimental branch)"
scripts/verify-source-state.sh
scripts/manifest.sh validate
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py

if [[ $# -eq 1 && "$1" == "--ple-cpu" ]]; then
  # Explicit opt-in for a host that already has NumPy+PyTorch.
  # No pip install or Docker execution; separate CPU-only container preferred.
  CUDA_VISIBLE_DEVICES=-1 python3 src/test_ple_phase2_cpu.py
elif [[ $# -gt 0 ]]; then
  echo "usage: scripts/phase2-check-offline.sh [--ple-cpu]" >&2
  exit 2
fi

scripts/verify-source-state.sh
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: test run modified checkout" >&2; exit 2;
}
echo "PASS: PHASE2_OFFLINE_SOURCE_AND_STDLIB_CONTRACTS"
echo "NOTE: PyTorch CPU fixture is separate unless --ple-cpu explicitly selected"
echo "NOT_RUN: GPU, blazux optimization, production vLLM, benchmark, CI"
