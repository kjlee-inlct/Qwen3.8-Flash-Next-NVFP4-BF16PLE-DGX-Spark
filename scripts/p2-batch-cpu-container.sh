#!/usr/bin/env bash
# P2: one explicit disposable CPU-only container for the full 40-test bundle.
# Reuses the pinned original IMAGE only. NEVER enters/stops/modifies original.
set -Eeuo pipefail

readonly ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
readonly BRANCH="feature/blazux-phase6-runtime-gates"
readonly LEGACY="qwen38-flash-orca-uncensored-bf16-mtp"
readonly LEGACY_ID="3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45"
readonly IMAGE="sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
readonly MIN_BEFORE_KIB=8388608  # Host MemAvailable >= 8 GiB
readonly MIN_AFTER_KIB=4194304   # Host MemAvailable >= 4 GiB
fail() { echo "P2_BATCH_CPU_CONTAINER_BLOCKED: $*" >&2; exit 2; }

[[ "$#" -eq 1 && "$1" == "--execute" ]] ||
  fail "explicit --execute required; no Docker command has run"
[[ ! -L "$ROOT" && -d "$ROOT/.git" ]] || fail "unexpected checkout"
cd -- "$ROOT"
for cmd in git python3 docker awk; do
  command -v "$cmd" >/dev/null 2>&1 || fail "missing required command"
done
readonly HEAD="$(git rev-parse HEAD)"
[[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] || fail "invalid HEAD"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "wrong branch"
[[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || fail "wrong repository root"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] ||
  fail "dirty source checkout"
export PYTHONDONTWRITEBYTECODE=1
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check ||
  fail "source-state/fork/branch/HEAD preflight failed"

available_kib() {
  awk '$1=="MemAvailable:" && $3=="kB" {print $2}' /proc/meminfo
}
before_ram="$(available_kib)"
[[ "$before_ram" =~ ^[0-9]+$ ]] || fail "host MemAvailable not readable"
(( before_ram >= MIN_BEFORE_KIB )) || fail "host RAM below 8 GiB protection floor"

legacy_identity() {
  docker inspect --type container \
    --format '{{.Id}} {{.State.Running}} {{.Image}} {{.State.StartedAt}}' \
    "$LEGACY"
}
legacy_before="$(legacy_identity 2>/dev/null)" || fail "original container unavailable"
[[ "$legacy_before" == "$LEGACY_ID true $IMAGE "* ]] ||
  fail "original ID/running/image mismatch (do not restart)"
local_image="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null)" ||
  fail "immutable original image not available locally; never pull"
[[ "$local_image" == "$IMAGE" ]] || fail "immutable image ID mismatch"

# One disposable process, no model/weights/cache/Docker socket/GPU mount.
# CPU 2, RAM/swap 2 GiB, read-only source/root, nonroot and no network.
echo "P2_BATCH_ISOLATED_CPU_PREFLIGHT_PASS HEAD=$HEAD"
echo "P2_BATCH_ISOLATED_CPU_POLICY=RUNC_NO_GPU_NO_NETWORK_2CPU_2G_READONLY"
rc=0
docker run --rm -i --pull=never \
  --runtime=runc --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --cpus=2 --memory=2g --memory-swap=2g --pids-limit=96 \
  --user=65534:65534 \
  --tmpfs '/tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777' \
  --mount "type=bind,source=$ROOT,target=/p2,readonly" \
  --workdir /p2 \
  --env NVIDIA_VISIBLE_DEVICES=void \
  --env CUDA_VISIBLE_DEVICES=-1 \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONNOUSERSITE=1 \
  --env PYTHONPATH=/p2 \
  --env HOME=/tmp \
  --env XDG_CACHE_HOME=/tmp/p2-cache \
  --env OMP_NUM_THREADS=1 \
  --env OPENBLAS_NUM_THREADS=1 \
  --env MKL_NUM_THREADS=1 \
  --entrypoint python3 "$IMAGE" -B - <<'PYCODE' || rc=$?
import sys
import unittest
import numpy as np
import torch

if torch.cuda.is_available():
    raise SystemExit("P2_CPU_ONLY_BLOCKED_CUDA_AVAILABLE")

names = [
    "tests.test_p2_numeric_boundary",
    "tests.test_p2_numeric_sampler_witness",
    "tests.test_p2_numeric_dgx_prepare",
    "tests.test_p2_mtp_draft_vocab",
    "tests.test_p2_numeric_report",
    "tests.test_p2_ple_unique_h2d",
]
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(f"P2_BATCH_CPU_DEPENDENCIES numpy={np.__version__} torch={torch.__version__}")
print(f"P2_BATCH_CPU_COUNTS tests={result.testsRun} skipped={len(result.skipped)}")
if (not result.wasSuccessful() or result.testsRun != 40 or result.skipped
        or result.expectedFailures or result.unexpectedSuccesses):
    raise SystemExit("P2_BATCH_CPU_INCOMPLETE_OR_FAILED")
print("P2_BATCH_ISOLATED_CPU_40_OF_40_PASS_NO_SKIPS")
PYCODE

legacy_after="$(legacy_identity 2>/dev/null)" ||
  fail "cannot verify original identity after disposable container"
[[ "$legacy_before" == "$legacy_after" ]] ||
  fail "original ID/image/running/StartedAt changed"
after_ram="$(available_kib)"
[[ "$after_ram" =~ ^[0-9]+$ ]] || fail "host MemAvailable after run not readable"
(( after_ram >= MIN_AFTER_KIB )) || fail "host RAM below 4 GiB after run"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || fail "source HEAD drift"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] ||
  fail "source checkout changed"
[[ "$rc" -eq 0 ]] || fail "CPU tests failed in isolated container (exit=$rc)"
echo "P2_BATCH_DGX_CPU_COMPLETE_HEAD=$HEAD ORIGINAL_UNCHANGED_NO_GPU_API"
