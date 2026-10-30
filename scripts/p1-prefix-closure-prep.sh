#!/usr/bin/env bash
# P1 one-shot closure preparation (CPU/read-only only).
# Explicitly does NOT launch GPU, stop/start production, mutate Stage or relax oracle.
set -Eeuo pipefail
umask 077

usage() {
  printf '%s\n' 'Usage: scripts/p1-prefix-closure-prep.sh --expected-head SHA [--show-source]'
}
HEAD=''
SHOW_SOURCE=0
while (($#)); do
  case "$1" in
    --expected-head) [[ $# -ge 2 ]] || { usage; exit 2; }; HEAD="$2"; shift 2 ;;
    --show-source) SHOW_SOURCE=1; shift ;;
    *) usage; exit 2 ;;
  esac
done
[[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] || { usage; exit 2; }

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO"
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] || {
  echo "P1_PREP_BLOCKED_WRONG_BRANCH"; exit 2;
}
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || {
  echo "P1_PREP_BLOCKED_HEAD_MISMATCH"; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P1_PREP_BLOCKED_DIRTY_TREE"; exit 2;
}

export PYTHONDONTWRITEBYTECODE=1

echo "=== TARGETED CPU REGRESSIONS ==="
for pat in \
  test_blazux_phase6_prefix_gpu_window.py \
  test_blazux_phase6_prefix_live_observer.py \
  test_blazux_phase6_prefix_state_reuse_contract.py \
  test_blazux_phase6_prefix_copy_region_contract.py \
  test_blazux_phase6_prefix_state_snapshot.py \
  test_blazux_phase6_prefix_offline_evidence.py \
  test_blazux_phase6_prefix_mamba_utils_probe.py \
  test_blazux_phase6_prefix_closure_prep.py
do
  python3 -m unittest discover -s tests -p "$pat" -q
done
echo "P1_PREP_CPU_REGRESSIONS_PASS"

echo "=== SOURCE MANIFEST / READ-ONLY HOST PREFLIGHT ==="
python3 scripts/verify-source-state.py
bash scripts/p1-prefix-gpu-window.sh --expected-head "$HEAD" --preflight

echo "=== INSTALLED PREVIEW COPY-ABI SOURCE (NO GPU) ==="
LOG="$(mktemp /tmp/p1-closure-abi.XXXXXXXX.log)"
if [[ "$SHOW_SOURCE" == 1 ]]; then
  if ! python3 -m src.p1_prefix_mamba_utils_probe \
      --inspect-image --show-source >"$LOG" 2>&1; then
    cat "$LOG"; echo "P1_PREP_ABI_BLOCKED_NO_GPU"; exit 2
  fi
else
  if ! python3 -m src.p1_prefix_mamba_utils_probe \
      --inspect-image >"$LOG" 2>&1; then
    cat "$LOG"; echo "P1_PREP_ABI_BLOCKED_NO_GPU"; exit 2
  fi
fi
python3 - "$LOG" <<'PY'
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
lines = p.read_text(errors="replace").splitlines()
result = next((json.loads(x) for x in lines if x.startswith('{"')), None)
if not isinstance(result, dict):
    raise SystemExit("P1_PREP_ABI_RESULT_MISSING")
print("P1_PREP_SOURCE_SHA256=" + str(result.get("installed_source_sha256")))
print("P1_PREP_COPY_SOURCE_EVIDENCE=" +
      json.dumps(result.get("copy_path_source_evidence", {}),
                 sort_keys=True))
for line in lines:
    if line.startswith("=== ") or line.startswith(
            "P1_PINNED_IMAGE_MAMBA_UTILS_CPU_SOURCE_ONLY_PASS_NO_GPU"):
        print(line)
PY
echo "P1_PREP_ABI_LOG=$LOG"
echo "=== PINNED STAGE SAVE/RESTORE SOURCE (NO GPU) ==="
STAGE_LOG="$(mktemp /tmp/p1-closure-stage.XXXXXXXX.log)"
if ! python3 -m src.p1_prefix_state_reuse_contract --inspect-stage >"$STAGE_LOG" 2>&1; then
  cat "$STAGE_LOG"
  echo "P1_PREP_STAGE_SOURCE_BLOCKED_NO_GPU"
  exit 2
fi
echo "P1_PREP_STAGE_SOURCE_LOG=$STAGE_LOG"
grep '^P1_PINNED_STAGE_RESTORE_SOURCE_ONLY_PASS_NO_GPU' "$STAGE_LOG"

echo "P1_PREP_ONLY_NO_GPU_NO_SERVICE_MUTATION"
