#!/usr/bin/env bash
# Read-only one-shot CPU-only export of ten allowlisted installed Preview sources.
# This never enters or mutates the running serving container or model.
set -Eeuo pipefail
readonly BRANCH="feature/blazux-phase6-runtime-gates"
readonly LEGACY="qwen38-flash-orca-uncensored-bf16-mtp"
readonly IMAGE="sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
readonly ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
stop() { echo "STOP: $*" >&2; exit 2; }

[[ $# -eq 3 && "$1" == "--expected-head" && "$3" == "--execute" ]] ||
  stop "usage: bash scripts/preview-p1-source-export.sh --expected-head <40-char SHA> --execute"
readonly HEAD="$2"
[[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] || stop "invalid HEAD"
[[ -d "$ROOT/.git" && ! -L "$ROOT" ]] || stop "unsafe checkout root"
cd -- "$ROOT"
[[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || stop "wrong checkout root"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || stop "wrong branch"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || stop "wrong HEAD"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || stop "dirty checkout"
case "$(git remote get-url origin)" in
  https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark|\
  https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git|\
  git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark|\
  git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git) ;;
  *) stop "unexpected origin" ;;
esac
for cmd in git docker python3 awk mktemp base64; do
  command -v "$cmd" >/dev/null || stop "missing $cmd"
done
export PYTHONDONTWRITEBYTECODE=1
bash scripts/phase6-gate.sh >/dev/null 2>&1 || stop "source/Phase6 gate"
available() { awk '$1=="MemAvailable:" && $3=="kB" {print $2}' /proc/meminfo; }
before="$(available)"
[[ "$before" =~ ^[0-9]+$ ]] || stop "missing host MemAvailable"
(( before >= 8388608 )) || stop "host MemAvailable below 8 GiB"
legacy_identity() {
  docker inspect --type container \
    --format '{{.State.Running}} {{.Image}} {{.State.StartedAt}}' "$LEGACY"
}
original="$(legacy_identity)" || stop "missing legacy identity"
[[ "$original" == "true $IMAGE "* ]] || stop "legacy container drift"
[[ "$(docker image inspect --format '{{.Id}}' "$IMAGE")" == "$IMAGE" ]] ||
  stop "pinned image missing"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || stop "HEAD drift"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || stop "source drift"
[[ -d "$HOME" && ! -L "$HOME" ]] || stop "unsafe user home"
outfile="$(mktemp "$HOME/preview-p1-source-XXXXXXXX.tar.gz")"
cleanup() { rm -f -- "$outfile"; }
trap cleanup ERR INT TERM

docker run --rm --pull=never \
  --runtime=runc --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --cpus=1 --memory=1g --memory-swap=1g --pids-limit=64 \
  --user=65534:65534 \
  --tmpfs '/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777' \
  --mount "type=bind,source=$ROOT,target=/phase6,readonly" \
  --workdir /phase6 \
  --env NVIDIA_VISIBLE_DEVICES=void \
  --env CUDA_VISIBLE_DEVICES=-1 \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONNOUSERSITE=1 \
  --env HOME=/tmp \
  --entrypoint /bin/sh "$IMAGE" -c \
  'exec python3 src/preview_p1_tool_responses_stage.py --snapshot-preview-source-base64' |
  base64 --decode > "$outfile"

# Validate the archive using stdlib only; never extract it.
python3 - "$outfile" <<'PY'
import os
import sys
import tarfile
from pathlib import Path
p = Path(sys.argv[1])
if not 0 < p.stat().st_size <= 2_000_000:
    raise SystemExit("STOP: unexpected source archive size")
with tarfile.open(p, "r:gz") as tf:
    names = tf.getnames()
    if not 1 <= len(names) <= 10 or len(names) != len(set(names)):
        raise SystemExit("STOP: invalid source member count")
    for entry in tf.getmembers():
        if (not entry.isfile() or not entry.name.startswith("vllm/")
                or ".." in Path(entry.name).parts or not entry.name.endswith(".py")
                or entry.size > 2_000_000):
            raise SystemExit("STOP: unsafe member")
os.chmod(p, 0o600)
print(f"PREVIEW_P1_ALLOWLISTED_SOURCE_MEMBERS={len(names)}")
PY

[[ "$(legacy_identity)" == "$original" ]] || stop "legacy container drift"
after="$(available)"
[[ "$after" =~ ^[0-9]+$ ]] || stop "host MemAvailable missing after export"
(( after >= 4194304 )) || stop "host MemAvailable below 4 GiB after export"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || stop "HEAD changed"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || stop "checkout changed"
trap - ERR INT TERM
echo "PREVIEW_P1_SOURCE_EXPORTED_NO_GPU_NO_SERVICE_CHANGE"
printf 'SOURCE_ARCHIVE=%s\n' "$outfile"
