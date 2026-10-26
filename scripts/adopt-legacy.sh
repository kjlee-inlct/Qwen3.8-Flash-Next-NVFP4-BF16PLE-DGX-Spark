#!/usr/bin/env bash
# Records verified legacy installation for read-only monitoring; no ownership transfer.
set -Eeuo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" adopt-legacy "$@"
