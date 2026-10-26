#!/usr/bin/env bash
# Safe deployment wizard. Existing YSLAB installs are never modified automatically.
set -Eeuo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" install "$@"
