#!/usr/bin/env bash
# P2 source-only: validate real aggregate token counts and write private /tmp
# .npy+SHA receipt. No model, torch, Docker, HTTP, GPU or network operation.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
if [[ "$#" -eq 1 && "$1" == "--check" ]]; then
  MODE="check"
elif [[ "$#" -eq 3 && "$1" == "--build" ]]; then
  MODE="build"
else
  echo "P2_VOCAB_USAGE: --check | --build /path/counts.json /path/tokenizer.json" >&2
  exit 2
fi
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
HEAD="$(git rev-parse HEAD)"
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 -m unittest -v tests.test_p2_mtp_vocab_artifact
if [[ "$MODE" == "build" ]]; then
  python3 -m src.p2_mtp_vocab_artifact \
    --counts-json "$2" --tokenizer-json "$3" --output-parent /tmp
fi
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || {
  echo "P2_VOCAB_HEAD_CHANGED" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P2_VOCAB_SOURCE_DIRTY" >&2; exit 2;
}
echo "P2_VOCAB_SOURCE_COMPLETE HEAD=$HEAD MODE=$MODE NO_MODEL_NO_GPU_NO_API"
