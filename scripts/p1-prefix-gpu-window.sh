#!/usr/bin/env bash
# Exclusive single-DGX P1 window. All real Docker transitions require --execute + same-ID.
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
blocked() { echo "P1_PREFIX_GPU_WRAPPER_BLOCKED_$*" >&2; exit 2; }
[[ $# -ge 3 && "$1" == "--expected-head" &&
   "$2" =~ ^[a-f0-9]{40}$ ]] || blocked "EXPECTED_SHA_REQUIRED"
HEAD="$2"
shift 2
[[ "$1" == "--preflight" || "$1" == "--execute" || "$1" == "--recover" ]] ||
  blocked "INVALID_ACTION"
ACTION="$1"
shift
if [[ "$ACTION" == "--preflight" ]]; then
  [[ $# -eq 0 ]] || blocked "PREFLIGHT_EXTRA_ARGS"
else
  [[ $# -eq 2 && "$1" == "--confirm-id" && "$2" =~ ^[a-f0-9]{64}$ ]] ||
    blocked "EXACT_CONTAINER_ID_REQUIRED"
fi
cd "$ROOT"
[[ -d .git && ! -L .git && "$(git rev-parse --show-toplevel)" == "$ROOT" ]] ||
  blocked "INVALID_CHECKOUT"
[[ "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" ]] ||
  blocked "WRONG_BRANCH"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || blocked "WRONG_HEAD"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || blocked "DIRTY_TREE"
case "$(git remote get-url origin)" in
  "https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"|  "https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git"|  "git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"|  "git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git") ;;
  *) blocked "WRONG_ORIGIN" ;;
esac
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify-source-state.py ||
  blocked "SOURCE_MANIFEST_FAILED"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || blocked "HEAD_CHANGED"
PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1 python3   -m src.p1_prefix_gpu_window "$ACTION" "$@"
