#!/usr/bin/env bash
# P1 dedicated legacy stop-only / same-container restart. Not Wizard scripts/stop.sh.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
BRANCH="feature/blazux-phase6-runtime-gates"
REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
blocked() { printf 'P1_LEGACY_WINDOW_BLOCKED_%s\n' "$*" >&2; exit 2; }
[[ $# -ge 3 && "$2" == "--expected-head" && "$3" =~ ^[a-f0-9]{40}$ ]] || blocked "ARGUMENTS"
case "$1" in
  --preflight) MODE=preflight ;;
  --pause) MODE=pause ;;
  --stop) MODE=stop ;;
  --start) MODE=start ;;
  *) blocked "UNKNOWN_ACTION" ;;
esac
HEAD_PIN="$3"
shift 3
if [[ "$MODE" == "preflight" ]]; then
  [[ $# -eq 0 ]] || blocked "PREFLIGHT_EXTRA_ARGUMENTS"
else
  [[ $# -eq 3 && "$1" == "--confirm-id" &&
    "$2" =~ ^[a-f0-9]{64}$ && "$3" == "--execute" ]] ||
      blocked "EXPLICIT_FULL_ID_AND_EXECUTE_REQUIRED"
fi
cd -- "$ROOT"
[[ -d .git && ! -L .git ]] || blocked "INVALID_CHECKOUT"
[[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || blocked "WRONG_REPO"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || blocked "WRONG_BRANCH"
[[ "$(git rev-parse HEAD)" == "$HEAD_PIN" ]] || blocked "WRONG_HEAD"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || blocked "DIRTY_TREE"
case "$(git remote get-url origin)" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git") ;;
  *) blocked "WRONG_ORIGIN" ;;
esac
python3 scripts/verify-source-state.py || blocked "SOURCE_MANIFEST_FAILED"
[[ "$(git rev-parse HEAD)" == "$HEAD_PIN" ]] || blocked "HEAD_CHANGED"
exec python3 src/p1_legacy_service_window.py --action "$MODE" "$@"
