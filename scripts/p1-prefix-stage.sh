#!/usr/bin/env bash
# CPU-only creation of two SHA-pinned vLLM Prefix source files; no GPU/model load.
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
BRANCH="feature/blazux-phase6-runtime-gates"
IMAGE="sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
LEGACY="qwen38-flash-orca-uncensored-bf16-mtp"
blocked() { echo "P1_PREFIX_STAGE_BLOCKED_$*" >&2; exit 2; }
[[ $# -eq 3 && "$1" == "--expected-head" && "$2" =~ ^[a-f0-9]{40}$ &&
   "$3" == "--execute" ]] || blocked "EXPECTED_HEAD_SHA_AND_EXECUTE_REQUIRED"
HEAD_PIN="$2"
cd "$ROOT"
[[ -d .git && ! -L .git ]] || blocked "INVALID_CHECKOUT"
[[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || blocked "WRONG_ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || blocked "WRONG_BRANCH"
[[ "$(git rev-parse HEAD)" == "$HEAD_PIN" ]] || blocked "HEAD_MISMATCH"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || blocked "DIRTY"
case "$(git remote get-url origin)" in
  https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark|\
  https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git|\
  git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark|\
  git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git) ;;
  *) blocked "WRONG_REMOTE" ;;
esac
for command in git python3 docker mktemp stat awk find; do
  command -v "$command" >/dev/null || blocked "MISSING_COMMAND"
done
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify-source-state.py ||
  blocked "MANIFEST_FAILED"
identity() {
  docker inspect --type container \
    --format '{{.State.Status}} {{.Image}} {{.Id}} {{.State.StartedAt}}' \
    "$LEGACY"
}
before="$(identity 2>/dev/null)" || blocked "LEGACY_MISSING"
[[ "$before" == "running $IMAGE "* ]] || blocked "LEGACY_NOT_RUNNING_OR_IMAGE_CHANGED"
[[ "$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null)" == "$IMAGE" ]] ||
  blocked "PINNED_IMAGE_MISSING"
available="$(awk '$1=="MemAvailable:" && $3=="kB" {print $2}' /proc/meminfo)"
[[ "$available" =~ ^[0-9]+$ ]] || blocked "RAM_UNKNOWN"
(( available >= 4194304 )) || blocked "RAM_BELOW_4G"
stage="$(mktemp -d /tmp/p1-prefix-stage.XXXXXXXX)" || blocked "STAGE_CREATE_FAILED"
[[ -d "$stage" && ! -L "$stage" && "$(stat -c %a "$stage")" == "700" ]] ||
  blocked "STAGE_NOT_PRIVATE"
success=0
cleanup() {
  if [[ "$success" == 0 && -d "$stage" && ! -L "$stage" ]]; then
    rm -f -- "$stage/mamba_hybrid.py" "$stage/scheduler.py"
    rmdir -- "$stage" 2>/dev/null || true
  fi
}
trap cleanup EXIT
docker run --rm --pull=never \
  --runtime=runc --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --cpus=1 --memory=512m --memory-swap=512m --pids-limit=64 \
  --user="$(id -u):$(id -g)" \
  --tmpfs '/tmp:rw,nosuid,nodev,size=64m,mode=1777' \
  --mount "type=bind,source=$ROOT,target=/phase6,readonly" \
  --mount "type=bind,source=$stage,target=/stage" \
  --workdir /phase6 \
  --env NVIDIA_VISIBLE_DEVICES=void \
  --env CUDA_VISIBLE_DEVICES=-1 \
  --env PYTHONPATH=/phase6 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONNOUSERSITE=1 \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --entrypoint python3 \
  "$IMAGE" /phase6/src/p1_prefix_stage_files.py --stage-files --output /stage ||
  blocked "ISOLATED_STAGE_FAILED"
[[ -f "$stage/mamba_hybrid.py" && -f "$stage/scheduler.py" &&
   ! -L "$stage/mamba_hybrid.py" && ! -L "$stage/scheduler.py" ]] ||
  blocked "STAGE_FILES_INVALID"
[[ "$(find "$stage" -maxdepth 1 -type f | wc -l)" -eq 2 ]] ||
  blocked "UNEXPECTED_STAGE_FILES"
after="$(identity 2>/dev/null)" || blocked "LEGACY_CHANGED"
[[ "$before" == "$after" ]] || blocked "LEGACY_STATE_CHANGED"
[[ "$(git rev-parse HEAD)" == "$HEAD_PIN" ]] || blocked "SOURCE_HEAD_CHANGED"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || blocked "SOURCE_CHANGED"
success=1
printf 'P1_PREFIX_STAGE_HOST_DIRECTORY=%s\n' "$stage"
echo "P1_PREFIX_STAGE_DGX_CPU_ONLY_READY_NOT_GPU_TESTED"
