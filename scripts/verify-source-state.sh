#!/usr/bin/env bash
# Read-only source snapshot integrity check. No Docker/weights/state modifications.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/verify-source-state.py" "$@"
