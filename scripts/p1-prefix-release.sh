#!/usr/bin/env bash
# P1 isolated Prefix ON release. --build is CPU-only; launch requires
# original ALREADY stopped via P1 legacy service-window authorization.
set -Eeuo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
blocked() { printf 'P1_RELEASE_WRAPPER_BLOCKED_%s\n' "$*" >&2; exit 2; }
[[ $# -ge 3 && "$1" == "--expected-head" &&
   "$2" =~ ^[0-9a-f]{40}$ ]] || blocked "EXPECTED_HEAD_REQUIRED"
HEAD="$2"
shift 2
ACTION="$1"
shift
case "$ACTION" in
  --build) [[ $# -eq 0 ]] || blocked "BUILD_EXTRA_ARGS" ;;
  --launch)
    [[ $# -eq 2 && "$1" == "--confirm-original-id" &&
       "$2" =~ ^[0-9a-f]{64}$ ]] || blocked "LAUNCH_EXACT_ID_REQUIRED" ;;
  --stop-and-restore)
    [[ $# -eq 4 && "$1" == "--confirm-original-id" &&
       "$2" =~ ^[0-9a-f]{64}$ && "$3" == "--confirm-release-id" &&
       "$4" =~ ^[0-9a-f]{64}$ ]] ||
      blocked "STOP_BOTH_EXACT_IDS_REQUIRED" ;;
  *) blocked "UNKNOWN_ACTION" ;;
esac
cd "$ROOT"
[[ -d .git && ! -L .git &&
   "$(git rev-parse --show-toplevel)" == "$ROOT" ]] ||
  blocked "WRONG_CHECKOUT"
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] ||
  blocked "WRONG_BRANCH"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || blocked "HEAD_MISMATCH"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] ||
  blocked "DIRTY_TREE"
case "$(git remote get-url origin)" in
  "https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"|  "https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git"|  "git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"|  "git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git") ;;
  *) blocked "WRONG_REMOTE" ;;
esac
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify-source-state.py ||
  blocked "SOURCE_MANIFEST_FAILED"

export PYTHONDONTWRITEBYTECODE=1
exec python3 -m src.p1_prefix_release --expected-head "$HEAD" "$ACTION" "$@"
