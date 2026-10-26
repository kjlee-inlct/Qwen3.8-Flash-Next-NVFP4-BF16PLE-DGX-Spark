#!/usr/bin/env bash
# Show or validate declarative deployment manifest (not checkpoint compatibility).
set -Eeuo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/wizard/cli.py" manifest "${1:-show}"
