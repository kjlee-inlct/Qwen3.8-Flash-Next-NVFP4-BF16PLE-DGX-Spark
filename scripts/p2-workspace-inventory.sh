#!/usr/bin/env bash
# Read-only workspace/Docker mount/Git inventory; no archiving or deletion.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/p2-workspace-inventory.py" "$@"
