#!/usr/bin/env bash
# P1 PLE: one-shot CPU-only BF16 fixture tests in the pinned existing vLLM image.
# Does NOT enter, restart, alter or benchmark the running serving container.
# Requires a fresh, explicit operator decision to run a disposable Docker container.
set -Eeuo pipefail

readonly BRANCH="feature/blazux-phase6-runtime-gates"
readonly LEGACY="qwen38-flash-orca-uncensored-bf16-mtp"
readonly IMAGE="sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly MIN_AVAILABLE_KIB=8388608  # 8 GiB preflight, host RAM only.
readonly MIN_AFTER_KIB=4194304     # 4 GiB after, NOT GPU headroom.

stop() { echo "STOP: $*" >&2; exit 2; }

# Allow exactly the old two-test PLE invocation, or a fixed CPU-only
# P1 synthetic/source bundle. No arbitrary command/profile injection.
readonly USAGE="usage: scripts/ple-phase-stats-cpu-container.sh --expected-head <40-char SHA> [--bundle p1-offline|p1-tool-stage|p1-native-marker|p1-schema] --execute"
BUNDLE="ple"
if [[ $# -eq 3 && "${1:-}" == "--expected-head" && "${3:-}" == "--execute" ]]; then
  :
elif [[ $# -eq 5 && "${1:-}" == "--expected-head" &&
        "${3:-}" == "--bundle" && ( "${4:-}" == "p1-offline" || "${4:-}" == "p1-tool-stage" || ( "${4:-}" == "p1-native-marker" || "${4:-}" == "p1-schema" ) ) &&
        "${5:-}" == "--execute" ]]; then
  BUNDLE="$4"
else
  stop "$USAGE"
fi
readonly EXPECTED_HEAD="$2"
readonly BUNDLE
[[ "$EXPECTED_HEAD" =~ ^[0-9a-f]{40}$ ]] || stop "invalid expected HEAD"
[[ -d "$ROOT/.git" && ! -L "$ROOT" ]] || stop "not a regular repository checkout"
cd -- "$ROOT"
[[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || stop "checkout mismatch"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || stop "wrong branch"
[[ "$(git rev-parse HEAD)" == "$EXPECTED_HEAD" ]] || stop "HEAD mismatch"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || stop "dirty checkout"
case "$(git remote get-url origin)" in
  https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark|\
  https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git|\
  git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark|\
  git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git)
    ;;
  *) stop "unexpected origin" ;;
esac
for cmd in git python3 docker awk; do
  command -v "$cmd" >/dev/null 2>&1 || stop "missing $cmd"
done

available_kib() {
  awk '$1=="MemAvailable:" && $3=="kB" {print $2}' /proc/meminfo
}
before_mem="$(available_kib)"
[[ "$before_mem" =~ ^[0-9]+$ ]] || stop "cannot determine host available RAM"
(( before_mem >= MIN_AVAILABLE_KIB )) || stop "host available RAM below 8 GiB"

legacy_identity() {
  docker inspect --type container \
    --format '{{.State.Running}} {{.Image}} {{.State.StartedAt}}' \
    "$LEGACY"
}
legacy_before="$(legacy_identity 2>/dev/null)" || stop "running legacy container not found"
[[ "$legacy_before" == "true $IMAGE "* ]] || stop "legacy image/state is not pinned"
local_image="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null)" ||
  stop "pinned image missing locally (never pull)"
[[ "$local_image" == "$IMAGE" ]] || stop "unexpected pinned image identity"

export PYTHONDONTWRITEBYTECODE=1
bash scripts/phase6-gate.sh
[[ "$(git rev-parse HEAD)" == "$EXPECTED_HEAD" ]] || stop "HEAD changed before CPU test"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || stop "checkout changed"

echo "PLE_CPU_CONTAINER_PREFLIGHT_PASS"
echo "PLE_CPU_CONTAINER_POLICY=RUNC_CPU_ONLY_NETWORK_NONE_GPU_VOID_READONLY_MEMORY_1G"
echo "PLE_CPU_CONTAINER_BUNDLE=$BUNDLE"
rc=0
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
  --env XDG_CACHE_HOME=/tmp/ple-cache \
  --env OMP_NUM_THREADS=1 \
  --env OPENBLAS_NUM_THREADS=1 \
  --env MKL_NUM_THREADS=1 \
  --env PLE_CPU_TEST_BUNDLE="$BUNDLE" \
  --entrypoint /bin/sh "$IMAGE" -c '
    set -eu
    python3 src/test_ple_phase_stats_cpu.py
    python3 src/test_ple_phase4_cpu.py
    echo PLE_CPU_CONTAINER_TESTS_PASS
    if [ "$PLE_CPU_TEST_BUNDLE" = "p1-offline" ] || [ "$PLE_CPU_TEST_BUNDLE" = "p1-tool-stage" ] || [ "$PLE_CPU_TEST_BUNDLE" = "p1-native-marker" ] || [ "$PLE_CPU_TEST_BUNDLE" = "p1-schema" ]; then
      # Existing independent synthetic client oracles: NOT the real parser.
      PYTHONPATH=.:src python3 -m unittest discover \
        -s tests -p "test_blazux_phase5_contracts.py" -v
      echo P1_TOOL_RESPONSES_PREFIX_MTP_SYNTHETIC_CONTRACTS_PASS_ONLY
      # Read-only installed vLLM source AST/hash triage, never imports vLLM.
      python3 src/phase5_preview_abi_audit.py
      echo P1_PREVIEW_PARSER_SOURCE_TRIAGE_DONE_NOT_API_VERIFIED
      if [ "$PLE_CPU_TEST_BUNDLE" = "p1-tool-stage" ]; then
        # Real upstream source patches: apply only to ephemeral copied vLLM source.
        # Expected Preview drift must fail without patching the installed package.
        python3 src/preview_p1_tool_responses_stage.py --stage-preview-source-only
      fi
      if [ "$PLE_CPU_TEST_BUNDLE" = "p1-native-marker" ]; then
        # Stages ACTUAL pinned Preview-native code against a temporary copy and
        # executes extracted parser methods under stdlib CPU fakes, not vLLM.
        PYTHONPATH=.:src python3 src/preview_p1_native_marker_verify.py --verify-installed
      fi
      if [ "$PLE_CPU_TEST_BUNDLE" = "p1-schema" ]; then
        # Actual Preview parser/Responses source patched only in temporary copies.
        # Marker -> schema dependency order, no model/GPU/service/API invocation.
        PYTHONPATH=.:src python3 src/preview_p1_native_schema_verify.py --verify-installed
      fi
    fi
  ' || rc=$?

legacy_after="$(legacy_identity 2>/dev/null)" ||
  stop "legacy identity unavailable after CPU test"
[[ "$legacy_before" == "$legacy_after" ]] ||
  stop "legacy container identity/running state changed"
after_mem="$(available_kib)"
[[ "$after_mem" =~ ^[0-9]+$ ]] || stop "cannot determine host RAM after CPU test"
(( after_mem >= MIN_AFTER_KIB )) || stop "host available RAM below 4 GiB after run"
[[ "$(git rev-parse HEAD)" == "$EXPECTED_HEAD" ]] || stop "HEAD changed after test"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || stop "source checkout changed"
[[ "$rc" -eq 0 ]] || stop "isolated CPU test failed (exit=$rc)"
echo "PLE_PHASE_STATS_CPU_DGX_ISOLATED_VERIFIED_NO_GPU_NO_SERVICE_CHANGE"
