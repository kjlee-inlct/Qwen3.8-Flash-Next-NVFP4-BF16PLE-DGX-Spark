#!/usr/bin/env bash
# One bounded P2 CPU sandbox: focused regressions, actual tokenizer probe,
# optional approved corpus counts and private 65,536 candidate .npy.
set -Eeuo pipefail
umask 077
readonly ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
readonly BRANCH="feature/blazux-phase6-runtime-gates"
readonly ORIGINAL="qwen38-flash-orca-uncensored-bf16-mtp"
readonly ORIGINAL_ID="3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45"
readonly IMAGE="sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
readonly TOKENIZER="$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2/tokenizer.json"
readonly CONFIG="$(dirname -- "$TOKENIZER")/tokenizer_config.json"
fail() { echo "P2_OFFLINE_BUNDLE_BLOCKED REASON=$1" >&2; exit 2; }
[[ "$#" -ge 2 && "$1" == "--execute" &&
   ( "$2" == "--probe" || "$2" == "--count" ) ]] ||
  fail "EXPLICIT_EXECUTE_AND_MODE_REQUIRED"
readonly MODE="$2"
shift 2
if [[ "$MODE" == "--probe" ]]; then
  [[ "$#" -eq 0 ]] || fail "PROBE_REJECTS_CORPUS"
else
  [[ "$#" -gt 0 && "$#" -eq $(( ($# / 3) * 3 )) ]] ||
    fail "COUNT_REQUIRES_EXPLICIT_CORPUS_TRIPLES"
fi
[[ ! -L "$ROOT" && -d "$ROOT/.git" ]] || fail "CHECKOUT_INVALID"
cd -- "$ROOT"
for cmd in docker git python3 id awk stat realpath mktemp; do
  command -v "$cmd" >/dev/null 2>&1 || fail "COMMAND_UNAVAILABLE"
done
readonly HEAD="$(git rev-parse HEAD)"
[[ "$HEAD" =~ ^[0-9a-f]{40}$ &&
   "$(git branch --show-current)" == "feature/blazux-phase6-runtime-gates" &&
   "$(git rev-parse --show-toplevel)" == "$ROOT" ]] ||
  fail "SOURCE_BRANCH_OR_HEAD_DRIFT"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "SOURCE_DIRTY"
readonly HOST_UID="$(id -u)"
readonly HOST_GID="$(id -g)"
[[ "$HOST_UID" =~ ^[0-9]+$ && "$HOST_GID" =~ ^[0-9]+$ ]] || fail "USER_ID_INVALID"
(( 10#$HOST_UID > 0 && 10#$HOST_GID > 0 )) || fail "ROOT_FORBIDDEN"
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=-1
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check ||
  fail "SOURCE_PREFLIGHT_FAILED"
for source in "$TOKENIZER" "$CONFIG"; do
  [[ -f "$source" && ! -L "$source" && -r "$source" ]] ||
    fail "RECIPE_TOKENIZER_METADATA_MISSING_OR_UNREADABLE"
done
[[ "$(stat -c %s "$TOKENIZER")" -gt 0 &&
   "$(stat -c %s "$TOKENIZER")" -le 83886080 &&
   "$(stat -c %s "$CONFIG")" -gt 0 &&
   "$(stat -c %s "$CONFIG")" -le 8388608 ]] ||
  fail "RECIPE_METADATA_SIZE_INVALID"
declare -a mounts=(
  --mount "type=bind,source=$ROOT,target=/p2,readonly"
  --mount "type=bind,source=$TOKENIZER,target=/tmp/p2-tokenizer.json,readonly"
  --mount "type=bind,source=$CONFIG,target=/tmp/p2-tokenizer-config.json,readonly"
)
declare -a arguments=()
declare -A seen=()
number=0
while [[ "$#" -gt 0 ]]; do
  [[ "$MODE" == "--count" && "$#" -ge 3 ]] || fail "INPUT_TRIPLE_INVALID"
  kind="$1"; domain="$2"; path="$3"
  shift 3
  [[ ( "$kind" == "--text" || "$kind" == "--corpus" ) &&
     "$domain" =~ ^(ko|en|code|technical|tool)$ ]] ||
    fail "INPUT_FORMAT_OR_DOMAIN_INVALID"
  [[ "$path" == /* && -f "$path" && ! -L "$path" && -r "$path" ]] ||
    fail "INPUT_NOT_PLAIN_READABLE_ABSOLUTE_FILE"
  actual="$(realpath -e -- "$path")" || fail "INPUT_REALPATH_FAILED"
  [[ -z "${seen[$actual]+yes}" ]] || fail "DUPLICATE_CORPUS"
  seen[$actual]=1
  size="$(stat -c %s -- "$path")" || fail "INPUT_STAT_FAILED"
  [[ "$size" =~ ^[0-9]+$ && "$size" -gt 0 ]] || fail "INPUT_SIZE_INVALID"
  if [[ "$kind" == "--text" ]]; then
    (( size <= 2097152 )) || fail "TEXT_OVER_2_MIB"
  else
    (( size <= 1073741824 )) || fail "JSONL_OVER_1_GIB"
  fi
  (( number += 1 ))
  (( number <= 20 )) || fail "TOO_MANY_CORPORA"
  mounts+=(--mount "type=bind,source=$actual,target=/tmp/p2-input-$number,readonly")
  arguments+=("$kind" "$domain" "/tmp/p2-input-$number")
done
mem_kib() { awk '$1=="MemAvailable:" && $3=="kB" {print $2}' /proc/meminfo; }
before_ram="$(mem_kib)"
[[ "$before_ram" =~ ^[0-9]+$ ]] || fail "RAM_UNAVAILABLE"
(( before_ram >= 8388608 )) || fail "RAM_FLOOR_BEFORE"
identity() {
  docker inspect --type container \
    --format '{{.Id}} {{.State.Running}} {{.Image}} {{.State.StartedAt}}' "$ORIGINAL"
}
original_before="$(identity 2>/dev/null)" || fail "ORIGINAL_IDENTITY_UNAVAILABLE"
[[ "$original_before" == "$ORIGINAL_ID true $IMAGE "* ]] ||
  fail "ORIGINAL_ID_OR_IMAGE_DRIFT"
local_image="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null)" ||
  fail "PINNED_IMAGE_UNAVAILABLE_NO_PULL"
[[ "$local_image" == "$IMAGE" ]] || fail "PINNED_IMAGE_DRIFT"
outdir=""
if [[ "$MODE" == "--count" ]]; then
  outdir="$(mktemp -d /tmp/p2-offline-bundle-XXXXXXXX)" ||
    fail "PRIVATE_OUTPUT_CREATE_FAILED"
  [[ -d "$outdir" && ! -L "$outdir" &&
     "$(stat -c %a "$outdir")" == "700" ]] ||
    fail "PRIVATE_OUTPUT_MODE_INVALID"
  mounts+=(--mount "type=bind,source=$outdir,target=/tmp/p2-offline-output")
fi
echo "P2_OFFLINE_BUNDLE_PREFLIGHT_PASS HEAD=$HEAD MODE=$MODE"
echo "P2_OFFLINE_BUNDLE_BOUNDARY=PINNED_CPU_RUNC_NO_NETWORK_NO_GPU_NONROOT_2CPU_2G"
rc=0
docker run --rm -i --pull=never \
  --runtime=runc --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --cpus=2 --memory=2g --memory-swap=2g --pids-limit=96 \
  --user "$HOST_UID:$HOST_GID" \
  --tmpfs '/tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777' \
  "${mounts[@]}" \
  --workdir /p2 \
  --env NVIDIA_VISIBLE_DEVICES=void \
  --env CUDA_VISIBLE_DEVICES=-1 \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONNOUSERSITE=1 \
  --env PYTHONPATH=/p2 \
  --env HOME=/tmp \
  --env XDG_CACHE_HOME=/tmp/p2-cache \
  --env OMP_NUM_THREADS=1 \
  --env OPENBLAS_NUM_THREADS=1 \
  --env MKL_NUM_THREADS=1 \
  --env P2_OUTPUT_HOST="$outdir" \
  --entrypoint python3 "$IMAGE" -B - "$MODE" "${arguments[@]}" <<'PYCODE' || rc=$?
import json
import os
from pathlib import Path
import re
import sys
import unittest

import tests as repo_tests
import torch
from src import p2_token_frequency as frequency
from src import p2_mtp_vocab_artifact as artifact

try:
    assert Path(repo_tests.__file__).resolve(strict=True) == Path("/p2/tests/__init__.py")
except (AssertionError, OSError, TypeError):
    raise SystemExit("P2_BUNDLE_REPOSITORY_TEST_PACKAGE_MISMATCH")
if torch.cuda.is_available():
    raise SystemExit("P2_BUNDLE_CUDA_VISIBLE_BLOCKED")
names = ["tests.test_p2_token_frequency",
         "tests.test_p2_mtp_vocab_artifact",
         "tests.test_p2_mtp_head_cpu"]
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({"status": "P2_OFFLINE_GROUPED_CPU_TEST_RESULT",
                  "tests": result.testsRun, "skips": len(result.skipped),
                  "errors": len(result.errors), "failures": len(result.failures)},
                 sort_keys=True), flush=True)
if (not result.wasSuccessful() or result.testsRun != 37 or result.skipped
        or result.expectedFailures or result.unexpectedSuccesses):
    raise SystemExit("P2_OFFLINE_GROUPED_CPU_TESTS_FAILED_OR_INCOMPLETE")
mode = sys.argv[1]
tokenizer = Path("/tmp/p2-tokenizer.json")
config = Path("/tmp/p2-tokenizer-config.json")
try:
    proof = frequency.probe(tokenizer, config)
    print(json.dumps(proof, sort_keys=True), flush=True)
    if mode == "--count":
        args = sys.argv[2:]
        if len(args) == 0 or len(args) % 3:
            raise frequency.Blocked("INPUT_TRIPLES_INVALID")
        jsonls, texts = [], []
        for i in range(0, len(args), 3):
            key, domain, name = args[i:i + 3]
            if key == "--corpus":
                jsonls.append((domain, Path(name)))
            elif key == "--text":
                texts.append((domain, Path(name)))
            else:
                raise frequency.Blocked("UNKNOWN_CORPUS_FORMAT")
        output = Path("/tmp/p2-offline-output")
        counts = frequency.count(jsonls, tokenizer, config, output,
                                 text_files=texts)
        counts_path = Path(counts["counts_file"])
        vocab = artifact.build(counts_path, tokenizer, output)
        host = Path(os.environ["P2_OUTPUT_HOST"])
        print(json.dumps({
            "status": "P2_PRIVATE_COUNTS_AND_DRAFT_VOCAB_CREATED_NOT_DEPLOYABLE",
            "counts_json": str(host / counts_path.relative_to(output)),
            "counts_receipt": str(host / Path(counts["private_directory"]).relative_to(output) / "receipt.json"),
            "draft_ids_npy": str(host / Path(vocab["private_directory"]).relative_to(output) / "ids.npy"),
            "draft_receipt": str(host / Path(vocab["private_directory"]).relative_to(output) / "receipt.json"),
            "tokenizer_sha256": counts["tokenizer_sha256"],
            "token_counts_sha256": counts["token_counts_sha256"],
            "npy_sha256": vocab["npy_sha256"],
            "aggregate_count_coverage": vocab["aggregate_count_coverage"],
            "corpus_representativeness_verified": False,
            "native_mtp_runtime_verified": False,
            "gpu_or_api_executed": False,
        }, sort_keys=True), flush=True)
except (frequency.Blocked, artifact.Blocked) as exc:
    reason = str(exc)
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", reason) is None:
        reason = "UNCLASSIFIED_BLOCKED"
    print("P2_OFFLINE_BUNDLE_BLOCKED REASON=" + reason, file=sys.stderr)
    raise SystemExit(2)
except (OSError, ValueError, TypeError, KeyError, OverflowError, MemoryError):
    print("P2_OFFLINE_BUNDLE_BLOCKED REASON=RUNTIME_INPUT_ERROR", file=sys.stderr)
    raise SystemExit(2)
print("P2_OFFLINE_BUNDLE_CPU_COMPLETE MODE=" + mode, flush=True)
PYCODE
original_after="$(identity 2>/dev/null)" || fail "ORIGINAL_POST_IDENTITY_UNAVAILABLE"
[[ "$original_before" == "$original_after" ]] ||
  fail "ORIGINAL_RUNNING_ID_IMAGE_OR_START_CHANGED"
after_ram="$(mem_kib)"
[[ "$after_ram" =~ ^[0-9]+$ ]] || fail "RAM_AFTER_UNAVAILABLE"
(( after_ram >= 4194304 )) || fail "RAM_FLOOR_AFTER"
[[ "$(git rev-parse HEAD)" == "$HEAD" &&
   -z "$(git status --porcelain=v1 --untracked-files=all)" ]] ||
  fail "SOURCE_CHANGED_DURING_RUN"
[[ "$rc" -eq 0 ]] || fail "ISOLATED_CPU_EXECUTION_FAILED"
echo "P2_OFFLINE_BUNDLE_DGX_COMPLETE HEAD=$HEAD MODE=$MODE ORIGINAL_UNCHANGED_NO_GPU_API"
