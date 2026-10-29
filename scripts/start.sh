#!/usr/bin/env bash
# P1: restore the exact same original YSLAB container ID after maintenance.
# Does not claim health: verify GET /health and /v1/models after start.
set -Eeuo pipefail
umask 077
dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
usage() {
  printf '%s\n' \
    'P1 legacy preflight: scripts/start.sh --preflight --expected-head SHA' \
    'P1 legacy restore:   scripts/start.sh --expected-head SHA --confirm-id FULL64 --execute' >&2
  exit 2
}
[[ $# -gt 0 ]] || usage
case "$1" in
  --preflight)
    shift
    exec "$dir/p1-legacy-service-window.sh" --preflight "$@"
    ;;
  --expected-head)
    exec "$dir/p1-legacy-service-window.sh" --start "$@"
    ;;
  *) usage ;;
esac
