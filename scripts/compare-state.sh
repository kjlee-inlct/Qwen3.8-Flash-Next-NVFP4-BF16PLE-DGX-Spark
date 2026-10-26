#!/usr/bin/env bash
# Saved legacy observation vs current live probes; no local state writes.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" status --compare "$@"
