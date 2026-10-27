#!/usr/bin/env bash
# Track A Phase 5 bundled stdlib-only correctness gate. No service/GPU/Docker.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase5-correctness-mtp-offline"
BASE="69860277122dffe3082c5b065e4361a571317a8e"
ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git"|"ssh://git@github.com/$REPO"|"ssh://git@github.com:$REPO.git") ;;
  *) echo "STOP: origin is not the approved personal fork" >&2; exit 2 ;;
esac

[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "STOP: wrong experiment branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: checkout has modifications or untracked files" >&2; exit 2;
}
git merge-base --is-ancestor "$BASE" HEAD || {
  echo "STOP: finalized Phase 4 parent not in ancestry" >&2; exit 2;
}
[[ $# == 0 ]] || {
  echo "usage: scripts/phase5-check-offline.sh" >&2; exit 2;
}

export PYTHONDONTWRITEBYTECODE=1
echo "PHASE5_SOURCE_HEAD=$(git rev-parse HEAD)"
scripts/verify-source-state.sh
scripts/manifest.sh validate
scripts/run-mock-tests.sh

PYTHONPATH=src:. python3 - <<'PY'
import unittest
suite = unittest.TestLoader().discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit("FAIL: Phase5 unittest suite failed")
if result.expectedFailures or result.unexpectedSuccesses:
    raise SystemExit("FAIL: outstanding XFAIL/XPASS not accepted")
print(f"PHASE5_UNIT_PASS={result.testsRun}; XFAIL=0")
PY

# Source-only AST check: no py_compile side effects, no dependency downloads.
python3 - <<'PY'
import ast
from pathlib import Path
for name in (
    "src/phase5_offline_contracts.py",
    "src/phase5_vllm_source_inventory.py",
    "src/phase5_preview_abi_audit.py",
    "src/phase5_patch_readiness.py",
    "src/phase5_dependency_trace.py",
    "src/phase5_scheduler_provenance.py",
    "src/test_ple_phase5_bench_cpu.py",
    "tests/test_blazux_phase5_contracts.py",
    "tests/test_blazux_phase5_preview_abi_audit.py",
    "tests/test_blazux_phase5_patch_readiness.py",
    "tests/test_blazux_phase5_dependency_trace.py",
    "tests/test_blazux_phase5_scheduler_provenance.py",
):
    ast.parse(Path(name).read_text(encoding="utf-8"), filename=name)
print("PHASE5_SOURCE_AST_OK")
PY

bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py
scripts/verify-source-state.sh
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: tests modified checkout" >&2; exit 2;
}
echo "PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS"
echo "NOTE: Scheduler ctor block-size source provenance runs in isolated CPU-only image"
echo "NOTE: focused source dependency trace runs separately in isolated CPU-only image"
echo "NOTE: source patch preflight runs separately in isolated CPU-only image"
echo "NOTE: preview ABI triage script is separate; must run in isolated CPU image"
echo "NOT_VERIFIED: installed vLLM parser/cache ABI, real prefix hit, HTTP APIs,"
echo "NOT_VERIFIED: MTP acceptance, real PLE throughput, GPU/serving, CI"
