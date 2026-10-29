#!/usr/bin/env bash
# P1: pause only the manifest/receipt-verified original YSLAB container.
# Docker pause retains model memory/GPU allocations: NOT for freeing GPU RAM.
# Pausing an API may time out requests; do not use while clients are active.
set -Eeuo pipefail
umask 077
dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
usage() {
  printf '%s\n' \
    'Legacy preflight: scripts/pause.sh --preflight --expected-head SHA' \
    'Legacy pause:     scripts/pause.sh --expected-head SHA --confirm-id FULL64 --execute' >&2
  exit 2
}
[[ $# -gt 0 ]] || usage
case "$1" in
  --preflight)
    shift
    exec "$dir/p1-legacy-service-window.sh" --preflight "$@"
    ;;
  --expected-head)
    exec "$dir/p1-legacy-service-window.sh" --pause "$@"
    ;;
  *) usage ;;
esac
