#!/usr/bin/env bash
# Verify policy, then read-only saved-vs-current diff, API/host capacity probe.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/wizard/cli.py" manifest validate
exec python3 "$script_dir/wizard/cli.py" status --health --compare "$@"
