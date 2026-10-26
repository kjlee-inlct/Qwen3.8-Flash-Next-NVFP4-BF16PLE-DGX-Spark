#!/usr/bin/env bash
# Safe removal wizard. Default preserves all checkpoints and legacy installs.
set -Eeuo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" uninstall "$@"
