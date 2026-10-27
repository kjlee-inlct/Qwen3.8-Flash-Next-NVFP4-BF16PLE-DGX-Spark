#!/usr/bin/env bash
# Track A Phase 3: narrow G2-01 fail-closed guard / offline regressions only.
# No Docker, HF cache, model, GPU, or running service mutations.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase3-ple-duplicate-shard-guard"
BASE="76588845d7742703475ae1f49d5e8f5c174bb77a"

ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git"|"ssh://git@github.com/$REPO"|"ssh://git@github.com/$REPO.git") ;;
  *) echo "STOP: not the approved personal fork" >&2; exit 2 ;;
esac

[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "STOP: expected isolated Phase 3 branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: checkout has local modifications/untracked files" >&2; exit 2;
}
git merge-base --is-ancestor "$BASE" HEAD || {
  echo "STOP: finalized Phase 2 parent is not in ancestry" >&2; exit 2;
}
if [[ $# -gt 1 ]] || { [[ $# -eq 1 ]] && [[ "$1" != "--ple-cpu" ]]; }; then
  echo "usage: scripts/phase3-check-offline.sh [--ple-cpu]" >&2
  exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
echo "PHASE3_SOURCE_HEAD=$(git rev-parse HEAD)"
scripts/verify-source-state.sh
scripts/manifest.sh validate
scripts/run-mock-tests.sh

# Do not permit expected failures: the Phase 2 G2-01 XFAIL must now PASS.
PYTHONPATH=src:. python3 - <<'PY'
import unittest

suite = unittest.TestLoader().discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit("FAIL: unit tests did not pass")
if result.expectedFailures:
    raise SystemExit("FAIL: remaining XFAIL, Phase 3 G2-01 is not closed")
if result.unexpectedSuccesses:
    raise SystemExit("FAIL: unexpectedSuccesses require explicit review")
print(f"PHASE3_UNIT_PASS={result.testsRun}; XFAIL=0")
PY

bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py

if [[ $# -eq 1 ]]; then
  # Only in an isolated Python environment where torch+numpy already exist.
  # Prefer a CPU-only disposable Docker container invoked OUTSIDE this script.
  CUDA_VISIBLE_DEVICES=-1 python3 src/test_ple_phase2_cpu.py
fi

scripts/verify-source-state.sh
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: source tree changed after test" >&2; exit 2;
}
echo "PASS: PHASE3_G2_01_OFFLINE_CONTRACTS_XFAIL_0"
echo "NOT_RUN: GPU inference, vLLM integration, runtime throughput, CI"
