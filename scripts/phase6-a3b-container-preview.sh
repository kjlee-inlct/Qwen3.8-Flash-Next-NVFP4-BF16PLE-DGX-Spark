#!/usr/bin/env bash
# Only prints the proposed isolated CPU-only source probe command.
# Intentionally has NO docker run execution path, regardless of arguments.
set -Eeuo pipefail
[[ "$#" == 1 && "$1" == "--preview" ]] || {
  echo "BLOCKED: CPU-only Docker run is NOT approved; --preview only" >&2
  exit 2
}
cat <<'PREVIEW'
PHASE6_A3B_CPU_CONTAINER_PROPOSAL_ONLY_NOT_EXECUTED
Proposed isolation for a separately approved future operation:
- Image: existing locally pinned sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a
- Runtime: runc, NVIDIA_VISIBLE_DEVICES=void, CUDA_VISIBLE_DEVICES=-1, no GPU device attachment
- --pull=never --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges
- --cpus=1 --memory=512m --memory-swap=512m --pids-limit=64 --user=65534:65534
- tmpfs /tmp: rw,nosuid,nodev,size=64m
- mount only the dedicated Phase6 checkout read-only at /phase6
- python3 /phase6/src/phase6_a3b_cpu_config.py --installed-source-only
- HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
- PHASE6_A3B_CPU_INSPECTION_ONLY=1, no vLLM imports, no config constructor
STOP: No docker run or model startup will be performed by this preview script.
PREVIEW
