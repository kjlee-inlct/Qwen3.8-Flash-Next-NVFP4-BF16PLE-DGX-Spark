#!/usr/bin/env bash
# Prepare pinned model using new wizard image/cache; does NOT touch legacy install.
set -Eeuo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/install.sh" --prepare-only "$@"
