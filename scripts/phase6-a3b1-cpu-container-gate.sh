#!/usr/bin/env bash
# P6-A3b-1: explicitly approved ONE bounded disposable CPU-only Docker run.
# No GPU/model/HTTP/CI/benchmark or operational Docker change.
set -Eeuo pipefail

readonly BRANCH="feature/blazux-phase6-runtime-gates"
readonly LEGACY="qwen38-flash-orca-uncensored-bf16-mtp"
readonly IMAGE="sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
readonly MIN_AVAILABLE_KIB=4194304   # 4 GiB host floor, NOT GPU proof.
readonly ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"

stop() {
  echo "BLOCKED: P6-A3b-1 CPU-only source audit; no active runtime certification" >&2
  return 2
}

legacy_identity_ok() {
  local identity
  identity="$(docker inspect --type container --format '{{.State.Running}} {{.Image}}' "$LEGACY" 2>/dev/null)" || return 1
  [[ "$identity" == "true $IMAGE" ]]
}

main() {
  [[ "$#" -eq 1 && "$1" == "--execute" ]] || {
    echo "STOP: only --execute is valid, under explicit CPU-only approval" >&2
    return 2
  }
  [[ -d "$ROOT/.git" && ! -L "$ROOT" ]] || { stop; return 2; }
  cd "$ROOT"
  [[ "$(git branch --show-current)" == "$BRANCH" ]] || { stop; return 2; }
  [[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || { stop; return 2; }
  [[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || { stop; return 2; }
  PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify-source-state.py || { stop; return 2; }
  for required in git python3 docker awk; do
    command -v "$required" >/dev/null 2>&1 || { stop; return 2; }
  done

  local mem_available
  mem_available="$(awk '$1=="MemAvailable:" && $3=="kB" {print $2}' /proc/meminfo)" || { stop; return 2; }
  [[ "$mem_available" =~ ^[0-9]+$ ]] || { stop; return 2; }
  if (( mem_available < MIN_AVAILABLE_KIB )); then
    echo "STOP: current host MemAvailable below 4 GiB, no Docker operation" >&2
    return 2
  fi

  # No raw Docker inspect JSON, env, mounts, IDs or argv are printed.
  legacy_identity_ok || { echo "STOP: pinned legacy deployment not running" >&2; return 2; }
  local local_image
  local_image="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null)" || { stop; return 2; }
  [[ "$local_image" == "$IMAGE" ]] || { stop; return 2; }

  echo "P6-A3B1_BEFORE=PINNED_LEGACY_RUNNING"
  echo "P6-A3B1_POLICY=RUNC_CPU_1_MEMORY_512M_SWAP_512M_NO_NETWORK_NO_GPU_READONLY"
  echo "P6-A3B1_HOST_AVAILABLE_MIB=$((mem_available / 1024))"

  # Keep raw stdout in RAM until independently checked for exact expected
  # schema/marker; suppress stderr (may include private Docker source paths).
  local raw="" rc=0
  raw="$(docker run --rm --pull=never \
    --runtime=runc --network=none --read-only \
    --cap-drop=ALL --security-opt=no-new-privileges \
    --cpus=1 --memory=512m --memory-swap=512m --pids-limit=64 \
    --user=65534:65534 \
    --tmpfs '/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777' \
    --mount "type=bind,source=$ROOT,target=/phase6,readonly" \
    --workdir /phase6 \
    --env NVIDIA_VISIBLE_DEVICES=void \
    --env CUDA_VISIBLE_DEVICES=-1 \
    --env HF_HUB_OFFLINE=1 \
    --env TRANSFORMERS_OFFLINE=1 \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --env PHASE6_A3B_CPU_INSPECTION_ONLY=1 \
    --entrypoint python3 "$IMAGE" \
    /phase6/src/phase6_a3b_cpu_config.py --installed-source-only \
    2>/dev/null)" || rc=$?

  # Always verify operational identity after the probe, even on probe failure.
  legacy_identity_ok || {
    echo "STOP: legacy container identity/running state changed" >&2
    return 2
  }
  echo "P6-A3B1_AFTER=PINNED_LEGACY_RUNNING"
  [[ "$rc" -eq 0 ]] || { stop; return 2; }

  local summary
  summary="$(PYTHONDONTWRITEBYTECODE=1 python3 src/phase6_a3b1_evidence.py <<< "$raw")" ||
    { stop; return 2; }
  printf '%s\n' "$summary"
  echo "PHASE6_A3B1_CPU_ISOLATED_PINNED_SOURCE_PASS_NOT_ACTIVE_RUNTIME"
}

main "$@"
