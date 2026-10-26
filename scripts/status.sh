#!/usr/bin/env bash
# Read-only deployment and legacy inventory.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" status "$@"
