#!/usr/bin/env bash
# P2 owner-checked Numeric-only GPU window. User-approved exclusive maintenance.
# --preflight: read-only, --build: offline image build without service stop,
# --execute: original same-ID stop -> diagnostic -> candidate cleanup -> restore.
# --recover: exact owner/pins checked restoration only (never remove original).
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
if [[ "$#" -lt 1 ]]; then
  echo "P2_NUMERIC_GPU_USAGE: --preflight|--build|--execute|--recover" >&2
  exit 2
fi
MODE="$1"; shift
case "$MODE" in
  --preflight|--build)
    [[ "$#" -eq 1 && "$1" == /tmp/p2-numeric-first-divergence-* ]] || {
      echo "P2_NUMERIC_GPU_EXACT_MINIMAL_STAGE_REQUIRED" >&2; exit 2;
    }
    STAGE="$1"; shift
    ;;
  --execute)
    [[ "$#" -eq 3 && "$1" == /tmp/p2-numeric-first-divergence-*
      && "$2" =~ ^[0-9a-f]{64}$ && "$3" =~ ^sha256:[0-9a-f]{64}$ ]] || {
      echo "P2_NUMERIC_GPU_STAGE_AND_FULL_ORIGINAL_PINS_REQUIRED" >&2; exit 2;
    }
    STAGE="$1"; ORIGINAL_ID="$2"; ORIGINAL_IMAGE="$3"; shift 3
    ;;
  --recover)
    [[ "$#" -eq 2 && "$1" =~ ^[0-9a-f]{64}$ && "$2" =~ ^sha256:[0-9a-f]{64}$ ]] || {
      echo "P2_NUMERIC_GPU_FULL_RECOVERY_PINS_REQUIRED" >&2; exit 2;
    }
    ORIGINAL_ID="$1"; ORIGINAL_IMAGE="$2"; shift 2
    ;;
  *) echo "P2_NUMERIC_GPU_MODE_INVALID" >&2; exit 2;;
esac
[[ "$#" -eq 0 ]] || { echo "P2_NUMERIC_GPU_EXTRA_ARGS" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1
HEAD="$(git rev-parse HEAD)"
case "$MODE" in
  --preflight)
    python3 -m unittest -v tests.test_p2_numeric_first_divergence_window
    python3 -m src.p2_numeric_first_divergence_window --expected-head "$HEAD" \
      --preflight --stage "$STAGE"
    ;;
  --build)
    python3 -m src.p2_numeric_first_divergence_window --expected-head "$HEAD" \
      --build --stage "$STAGE"
    ;;
  --execute)
    # Independent best-effort shell recovery after a failed/killed Python
    # controller. Python also restores in its own finally. Both are idempotent
    # and ownership-checked. Never attempt a second GPU launch.
    _recover_on_failure() {
      local exit_code=$?
      if (( exit_code != 0 )); then
        echo "P2_NUMERIC_GPU_WRAPPER_ATTEMPTING_SAME_ID_RECOVERY" >&2
        if ! python3 -m src.p2_numeric_first_divergence_window \
            --expected-head "$HEAD" --recover \
            --confirm-original-id "$ORIGINAL_ID" \
            --confirm-original-image "$ORIGINAL_IMAGE"; then
          echo "P2_NUMERIC_GPU_RECOVERY_UNCONFIRMED_MANUAL_ATTENTION_REQUIRED" >&2
        fi
      fi
      return 0
    }
    trap _recover_on_failure EXIT
    python3 -m src.p2_numeric_first_divergence_window --expected-head "$HEAD" \
      --execute --stage "$STAGE" \
      --confirm-original-id "$ORIGINAL_ID" --confirm-original-image "$ORIGINAL_IMAGE"
    trap - EXIT
    ;;
  --recover)
    python3 -m src.p2_numeric_first_divergence_window --expected-head "$HEAD" \
      --recover \
      --confirm-original-id "$ORIGINAL_ID" --confirm-original-image "$ORIGINAL_IMAGE"
    ;;
esac
echo "P2_NUMERIC_GPU_WINDOW_COMMAND_COMPLETE HEAD=$HEAD MODE=$MODE"
