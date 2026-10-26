#!/usr/bin/env bash
# Read-only model API, Docker identity, cache/view disk and host memory.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" status --health "$@"
