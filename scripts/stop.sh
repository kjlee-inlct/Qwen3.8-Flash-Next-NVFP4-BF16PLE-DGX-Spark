#!/usr/bin/env bash
# Stop ONLY the new wizard-owned container with matching recorded ID and labels.
set -Eeuo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/uninstall.sh" --stop-only "$@"
