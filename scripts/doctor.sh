#!/usr/bin/env bash
# Read-only policy verification and inventory. Does not run inference or modify Docker.
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/wizard/cli.py" manifest validate
exec python3 "$script_dir/wizard/cli.py" status "$@"
