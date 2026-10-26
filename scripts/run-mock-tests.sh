#!/usr/bin/env bash
# Offline-only fake Docker/Git/HTTP unittest suite; no Docker/weights changes.
set -Eeuo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m unittest discover -s tests -p 'test_wizard_*.py' -v
