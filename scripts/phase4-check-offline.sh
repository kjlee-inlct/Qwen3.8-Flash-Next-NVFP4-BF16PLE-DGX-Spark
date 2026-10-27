#!/usr/bin/env bash
# Phase 4 bundled CPU-only gate: two independent OFF-by-default PLE features.
# No Docker operation, model download, GPU, HF cache, or running service changes.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase4-ple-cpu-bundle"
BASE="760f227e46a358445db3d3931b5efbe40de5f609"
ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git"|"ssh://git@github.com/$REPO"|"ssh://git@github.com/$REPO.git") ;;
  *) echo "STOP: unexpected Git origin; personal fork required" >&2; exit 2 ;;
esac

[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "STOP: wrong branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: dirty checkout; no reset or cleanup will be performed" >&2; exit 2;
}
git merge-base --is-ancestor "$BASE" HEAD || {
  echo "STOP: finalized Phase 3 parent not found" >&2; exit 2;
}
if [[ $# -gt 1 ]] || { [[ $# -eq 1 ]] && [[ "$1" != "--ple-cpu" ]]; }; then
  echo "usage: scripts/phase4-check-offline.sh [--ple-cpu]" >&2
  exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
echo "PHASE4_SOURCE_HEAD=$(git rev-parse HEAD)"

# Experimental Phase 4 is not allowlisted for release --strict mode.
scripts/verify-source-state.sh
scripts/manifest.sh validate
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 - <<'PY'
import unittest
suite = unittest.TestLoader().discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit("FAIL: repository unittest returned errors/failures")
if result.expectedFailures or result.unexpectedSuccesses:
    raise SystemExit("FAIL: Phase4 cannot accept XFAIL or XPASS")
print(f"PHASE4_UNIT_PASS={result.testsRun}; XFAIL=0")
PY
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py

if [[ $# -eq 1 ]]; then
  # Only in a dedicated environment that already has NumPy+PyTorch.
  # Prefer a disposable CPU-only Docker container invoked separately.
  CUDA_VISIBLE_DEVICES=-1 python3 src/test_ple_phase2_cpu.py
  CUDA_VISIBLE_DEVICES=-1 python3 src/test_ple_phase4_cpu.py
fi

scripts/verify-source-state.sh
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: test run modified checkout" >&2; exit 2;
}
echo "PASS: PHASE4_BUNDLED_CPU_SOURCE_CONTRACTS"
echo "NOTE: phase4 CPU flag matrix runs only with --ple-cpu or in isolated container"
echo "NOT_RUN: GPU inference, serving image, KV/Mamba, pinned H2D, TPS benchmark, CI"
