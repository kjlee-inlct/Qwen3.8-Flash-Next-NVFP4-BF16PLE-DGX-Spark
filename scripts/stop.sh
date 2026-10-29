#!/usr/bin/env bash
# P1: stop the verified ORIGINAL YSLAB running Docker container, not its image.
# To stop a NEW Wizard-owned container instead, require --wizard explicitly.
# Never remove a container, image, state receipt, weights or HF cache.
set -Eeuo pipefail
umask 077
dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
usage() {
  printf '%s\n' \
    'P1 legacy preflight: scripts/stop.sh --preflight --expected-head SHA' \
    'P1 legacy stop:      scripts/stop.sh --expected-head SHA --confirm-id FULL64 --execute' \
    'New Wizard only:    scripts/stop.sh --wizard [wizard stop options]' >&2
  exit 2
}
[[ $# -gt 0 ]] || usage
case "$1" in
  --preflight)
    shift
    exec "$dir/p1-legacy-service-window.sh" --preflight "$@"
    ;;
  --expected-head)
    exec "$dir/p1-legacy-service-window.sh" --stop "$@"
    ;;
  --wizard)
    shift
    [[ $# -gt 0 ]] || usage
    exec "$dir/uninstall.sh" --stop-only "$@"
    ;;
  *) usage ;;
esac
