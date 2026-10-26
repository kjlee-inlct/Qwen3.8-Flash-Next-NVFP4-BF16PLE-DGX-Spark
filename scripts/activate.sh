#!/usr/bin/env bash
# Activate already-prepared new wizard deployment; never downloads or builds.
set -Eeuo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/install.sh" --activate-only "$@"
