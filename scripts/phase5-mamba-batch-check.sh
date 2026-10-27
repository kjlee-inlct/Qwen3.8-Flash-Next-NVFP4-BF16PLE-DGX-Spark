#!/usr/bin/env bash
# Track A Phase5: G1-G8 grouped, source-only/stdlib synthetic CPU verification.
# Reads installed vLLM only inside isolated runc CPU container; does not touch service.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase5-correctness-mtp-offline"
BASE="69860277122dffe3082c5b065e4361a571317a8e"
case "$(git remote get-url origin)" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git"|"ssh://git@github.com/$REPO"|"ssh://git@github.com:$REPO.git") ;;
  *) echo "STOP: wrong repository origin" >&2; exit 2 ;;
esac
[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "STOP: wrong branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "STOP: working tree is not clean" >&2; exit 2;
}
git merge-base --is-ancestor "$BASE" HEAD || {
  echo "STOP: Phase4 protected ancestor missing" >&2; exit 2;
}
[[ $# -eq 0 ]] || { echo "usage: scripts/phase5-mamba-batch-check.sh" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1
echo "PHASE5_BATCH_SOURCE_HEAD=$(git rev-parse HEAD)"
echo "=== PHASE5 GROUP A: MANIFEST / MOCK / UNIT / AST / AUDIT ==="
scripts/phase5-check-offline.sh
echo "=== PHASE5 GROUP B: PINNED INSTALLED SOURCE + SYNTHETIC CPU G1-G8 ==="
CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"
IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
echo "SOURCE_IMAGE=$IMAGE"
docker run --rm -i --pull=never \
  --network=none --runtime=runc --read-only \
  --tmpfs /tmp:rw,mode=1777,size=64m \
  --cpus=2 --memory=2g --pids-limit=128 \
  --cap-drop=ALL --security-opt=no-new-privileges \
  -e CUDA_VISIBLE_DEVICES=-1 -e NVIDIA_VISIBLE_DEVICES=void \
  -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint python3 "$IMAGE" -B - <<'PYCODE'
import ast
import hashlib
import importlib.util
from pathlib import Path

EXPECTED = {
    "v1/worker/mamba_utils.py": "25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3",
    "v1/worker/gpu/model_states/mamba_hybrid.py": "2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0",
    "v1/engine/core.py": "f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad",
    "v1/attention/backends/utils.py": "9ecfa5ed0ddd22760837572eb279759afa5fdbe24b5ba607b1cf49340be7280f",
}
checks = 0

def check(condition, explanation):
    global checks
    if not condition:
        raise AssertionError(explanation)
    checks += 1


def node_for(tree, name, cls=None):
    body = tree.body
    if cls:
        match = [n for n in body if isinstance(n, ast.ClassDef) and n.name == cls]
        check(len(match) == 1, f"class missing: {cls}")
        body = match[0].body
    match = [n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    check(len(match) == 1, f"function missing: {cls}.{name}")
    return match[0]


def require_pieces(text, pieces, label):
    for part in pieces:
        check(part in text, f"{label}: missing source anchor: {part}")


def index_for_positive(n, block):
    if type(n) is not int or type(block) is not int or n < 0 or block <= 0:
        raise ValueError("invalid block units")
    return -1 if n == 0 else (n - 1) // block


def mapped_row(batch, mapping=None):
    if type(batch) is not int or batch < 0:
        raise ValueError("negative/noninteger batch index")
    if mapping is not None and (batch >= len(mapping) or
                                type(mapping[batch]) is not int):
        raise ValueError("invalid batch mapping")
    req = batch if mapping is None else mapping[batch]
    return None if req < 0 else (batch if mapping is not None else req, req)


def post(new_computed, accepted, source_col, block):
    if any(type(x) is not int for x in (new_computed, accepted, source_col, block)) or block <= 0 or new_computed < 0 or accepted < 0:
        raise ValueError("invalid postprocess input")
    running = new_computed - accepted + 1
    aligned = (new_computed // block) * block
    if aligned < running:
        return ("SKIP", None, None)
    dst = aligned // block - 1
    bias = aligned - running
    if dst < 0 or bias < 0:
        return ("INVALID_SYNTHETIC", dst, bias)
    return ("NOOP" if source_col == dst and bias == 0 else "COPY", dst, bias)


def copy_span(source, dest, start, length, dst_start=0):
    # Deliberately stricter CPU oracle; these checks are NOT asserted to exist in Triton.
    if min(start, length, dst_start) < 0 or start + length > len(source) or dst_start + length > len(dest):
        raise ValueError("synthetic state copy would be out of bounds")
    dest[dst_start:dst_start + length] = source[start:start + length]


def rejects(call):
    try:
        call()
    except (ValueError, IndexError):
        return True
    return False



def tiled_spans(src_addr, dst_addr, copy_size, tile_idx, num_tiles, copy_block_size):
    """CPU reference to the source's alignment-dependent tile ranges, not CUDA."""
    ints = (src_addr, dst_addr, copy_size, tile_idx, num_tiles, copy_block_size)
    if any(type(x) is not int for x in ints):
        raise ValueError("integer inputs required")
    if (min(src_addr, dst_addr, copy_size, tile_idx) < 0 or num_tiles <= 0 or
            copy_block_size <= 0 or copy_block_size & (copy_block_size - 1) or
            tile_idx >= num_tiles):
        raise ValueError("invalid synthetic pointer, tile or block")
    spans = []
    if ((src_addr ^ dst_addr) & 7) == 0:
        head = min((-dst_addr) & 7, copy_size)
        if tile_idx == 0 and head:
            spans.append((0, head, "u8_head"))
        body_u64 = (copy_size - head) // 8
        raw = (body_u64 + num_tiles - 1) // num_tiles
        per = ((raw + copy_block_size - 1) // copy_block_size) * copy_block_size
        start = tile_idx * per
        end = min(start + per, body_u64)
        if start < end:
            spans.append((head + start * 8, (end - start) * 8, "u64_body"))
        if tile_idx == 0:
            tail_start = head + body_u64 * 8
            if tail_start < copy_size:
                spans.append((tail_start, copy_size - tail_start, "u8_tail"))
    else:
        raw = (copy_size + num_tiles - 1) // num_tiles
        per = ((raw + copy_block_size - 1) // copy_block_size) * copy_block_size
        start = tile_idx * per
        end = min(start + per, copy_size)
        if start < end:
            spans.append((start, end - start, "u8_fallback"))
    return spans


spec = importlib.util.find_spec("vllm")
if spec is None or not spec.submodule_search_locations or len(spec.submodule_search_locations) != 1:
    raise SystemExit("STOP: unique installed vLLM root not found")
root = Path(list(spec.submodule_search_locations)[0]).resolve()
contents = {}
for rel, expected_sha in EXPECTED.items():
    file = root / rel
    if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
        raise SystemExit("STOP: invalid/symlink source " + rel)
    if file.stat().st_size > 2_000_000:
        raise SystemExit("STOP: oversized source " + rel)
    data = file.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha:
        raise SystemExit(f"STOP: SHA drift {rel}: {digest}")
    contents[rel] = data.decode("utf-8")
    ast.parse(contents[rel], filename=rel)
    check(True, "parsed pinned source")
print("G1 PASS: four installed preview source SHA256/AST fingerprints pinned")

src = contents["v1/worker/mamba_utils.py"]
lines = src.splitlines()
tree = ast.parse(src)
copy = node_for(tree, "_copy_mamba_state_block")
memcpy = node_for(tree, "_memcpy_u64_tiled")
meta = node_for(tree, "_populate_metadata", "MambaSpecDecodeGPUContext")
create = node_for(tree, "create", "MambaSpecDecodeGPUContext")
pre = node_for(tree, "precopy_mamba_align_fused_kernel")
postproc = node_for(tree, "postprocess_mamba_fused_kernel")
segments = {
    "copy": ast.get_source_segment(src, copy),
    "metadata": ast.get_source_segment(src, meta),
    "create": ast.get_source_segment(src, create),
    "precopy": ast.get_source_segment(src, pre),
    "postprocess": ast.get_source_segment(src, postproc),
}
require_pieces(segments["copy"], [
    "state_group_indices_ptr + state_idx", "block_table_ptrs_ptr + group_idx",
    "bt_row_idx * block_table_stride_req", "block_table_base + dst_col",
    "block_table_base + src_col", "block_table_base + src_col + token_bias",
    "dest_block_id * state_block_stride", "src_block_id * state_block_stride",
    "(conv_width - token_bias)", "state_inner_size * state_elem_size",
    "NUM_TILES=TEMPORAL_TILES", "state_dim_row_stride_ptr + state_idx",
], "physical-copy")
require_pieces(segments["metadata"], [
    "enumerate(self.mamba_group_ids)", "forward_context[layer_name]",
    "len(kv_caches) == len(mamba_spec.shapes)", "state.data_ptr()",
    "state.stride(0)", "state.element_size()", "state.size(2)",
    "state.size(1)", "state.stride(1)", "state[0].numel()",
    "self.state_group_indices[idx] = group_local_idx", "idx == self.num_states",
    "len(block_tables) == self.num_groups", "bt.stride(0)",
    "len(strides) == 1", "block_tables", "bt.data_ptr()",
    "self.is_initialized = True",
], "metadata")
require_pieces(segments["create"], ["block_size=mamba_spec.block_size"], "context-create")
require_pieces(segments["precopy"], [
    "req_idx = tl.load(idx_mapping_ptr + batch_idx)", "if req_idx < 0:",
    "src_col < 0 or src_col == dst_col", "state_idx,", "batch_idx,",
], "precopy")
require_pieces(segments["postprocess"], [
    "bt_row_idx = batch_idx if HAS_IDX_MAPPING else req_idx",
    "new_num_computed // block_size", "aligned_new_computed - num_tokens_running_state",
    "if src_block_idx == dest_block_idx and accept_token_bias == 0:",
], "postprocess")
print("G2 PASS: pinned physical/table/metadata/decision source expressions")

check(mapped_row(2) == (2, 2), "V1 row and slot")
check(mapped_row(0, [5, -1, 2]) == (0, 5), "V2 batch != slot")
check(mapped_row(1, [5, -1, 2]) is None, "negative sentinel")
check(mapped_row(2, [5, -1, 2]) == (2, 2), "V2 mapped row")
check("src_col < 0 or src_col == dst_col" in segments["precopy"], "fresh/same pre-copy")
print("G3 PASS: V1/V2 batch-table row, request-state slot and negative sentinel")

# Synthetic tables: same local physical block id does not mean shared state memory across groups.
tables = [ [[3, 1, 2], [6, 5, 4]], [[8, 9, 10], [11, 12, 13]] ]
group_index_by_state = [0, 1, 1, 0]
state_idx, batch_row = 1, 0
g = group_index_by_state[state_idx]
src_phys = tables[g][batch_row][1]
dst_phys = tables[g][batch_row][0]
check((g, src_phys, dst_phys) == (1, 9, 8), "group-local table lookup")
check(tables[0][batch_row][1] != src_phys, "distinct group tables")
check(0x10000 + src_phys * 128 == 0x10480, "physical state address bytes")
check(4 * (1 * 16 + 2) == 72, "int32 table offset vs row stride elements")
print("G4 PASS: multi-group table selection and physical byte/element units (synthetic)")

# Conv SD: width=5, inner=3 elements, elem=2 bytes, accepted bias=2.
src_sd = bytearray(range(30))
dst_sd = bytearray([255] * 30)
copy_span(src_sd, dst_sd, start=2 * 3 * 2, length=(5 - 2) * 3 * 2)
check(dst_sd[:18] == src_sd[12:30] and dst_sd[18:] == bytes([255]*12), "SD conv shift")
# Conv DS: dim rows with padded stride (row_stride=14 bytes, row_width=10 bytes).
src_ds = bytearray(range(42))
dst_ds = bytearray([255] * 42)
for row in range(3):
    copy_span(src_ds, dst_ds, start=row * 14 + 2 * 2, length=(5 - 2) * 2, dst_start=row * 14)
check(all(dst_ds[r*14:r*14+6] == src_ds[r*14+4:r*14+10] for r in range(3)), "DS row offset")
check(all(dst_ds[r*14+6:(r+1)*14] == bytes([255]*8) for r in range(3)), "DS row tail")
# Temporal padded block stride=128 bytes, natural payload=34 bytes.
src_temp = bytearray(range(128))
dst_temp = bytearray([255]*128)
copy_span(src_temp, dst_temp, 0, 17 * 2)
check(dst_temp[:34] == src_temp[:34] and dst_temp[34:] == bytes([255]*94), "temporal natural bytes, not padded stride")
check(tables[1][0][1+1] == 10, "temporal src_col + token_bias table selection")
print("G5 PASS: SD/DS conv, temporal bias, padded stride and natural copy size (synthetic)")

mismatches = 0
for bc, bm in ((16,16),(16,32),(32,16),(32,32)):
    for n in range(1, 129):
        seed = index_for_positive(n, bc)
        spec_idx = index_for_positive(n, bm)
        if bc == bm:
            check(seed == spec_idx, "equal block token index")
        elif seed != spec_idx:
            mismatches += 1
check(mismatches > 0, "unequal block sensitivity")
check(index_for_positive(0,16) == -1, "zero computed synthetic sentinel")
check(index_for_positive(16,16) == 0 and index_for_positive(17,16) == 1, "exact boundary")
check(index_for_positive(33,32) == 1, "partial-tail after boundary")
require_pieces(contents["v1/worker/gpu/model_states/mamba_hybrid.py"], [
    "self.cache_config.block_size", "mamba_spec.block_size"
], "worker unit provenance")
require_pieces(contents["v1/engine/core.py"], ["cache_config.block_size", "kv_cache_spec.block_size"], "engine unit provenance")
print(f"G6 PASS: equal/unequal block sizes, empty/resume/boundaries, synthetic mismatch positions={mismatches}")

check(post(31,1,1,16)[0] == "SKIP", "post not aligned")
check(post(32,1,1,16) == ("NOOP",1,0), "same column zero bias")
check(post(32,2,1,16) == ("COPY",1,1), "same column nonzero accepted bias")
check(post(32,2,0,16) == ("COPY",1,1), "changed column accepted bias")
check(post(0,1,-1,16)[0] == "INVALID_SYNTHETIC", "invalid synthetic destination")
check(rejects(lambda: post(-1,1,0,16)), "negative token guard CPU")
check(rejects(lambda: post(32,2,0,0)), "zero block guard CPU")
check(rejects(lambda: copy_span(bytearray(10),bytearray(10),-1,2)), "negative offset CPU")
check(rejects(lambda: copy_span(bytearray(10),bytearray(10),9,2)), "source OOB CPU")
check(rejects(lambda: copy_span(bytearray(10),bytearray(10),0,11)), "destination OOB CPU")
check(rejects(lambda: index_for_positive(1,0)), "invalid block CPU")
zero_dest=bytearray([77]*7)
copy_span(bytearray([1]*7),zero_dest,3,0)
check(zero_dest == bytes([77]*7), "zero length copy")
# Byte tail / tile coverage is an independent CPU reference, NOT a Triton tiled-copy proof.
chunks = [list(range(i,min(i+1024,2051))) for i in range(0,2051,1024)]
check(len(chunks)==3 and [j for c in chunks for j in c]==list(range(2051)), "partial-tail chunk coverage")
print("G7 PASS: speculative bias, self-copy decision, invalid ranges, zero and partial-tail (synthetic)")


# G8: exact CPU coverage oracle for source fast(u64)/slow(u8) tile partition math.
# Does NOT test actual Triton loads/stores, CUDA alignment exceptions or alias races.
memcpy_src = ast.get_source_segment(src, memcpy)
require_pieces(memcpy_src, [
    "((src_addr_i ^ dst_addr_i) & 7) == 0",
    "head_bytes = tl.minimum", "body_u64 = body_bytes // 8",
    "per_tile_u64 = tl.cdiv", "tail_bytes = copy_size - tail_start",
    "per_tile_bytes = tl.cdiv", "mask = (i + offsets) < tile_end",
    "tl.pointer_type(tl.uint64)", "tl.pointer_type(tl.uint8)"
], "memcpy-alignment-source")
from itertools import product
g8_cases = 0
g8_spans = 0
for src_mod, dst_mod, tiles, bs, n in product(
        range(8), range(8), (1, 2, 3, 7), (8, 32, 1024),
        (0, 1, 2, 7, 8, 9, 15, 16, 31, 32, 33,
         63, 64, 65, 1023, 1024, 1025, 2051)):
    covered = bytearray(n)
    for tile in range(tiles):
        for start, length, kind in tiled_spans(
                0x10000 + src_mod, 0x20000 + dst_mod, n, tile, tiles, bs):
            check(0 <= start and 0 < length and start + length <= n,
                  "tiled span bounds")
            if kind == "u64_body":
                check((src_mod + start) % 8 == 0 and
                      (dst_mod + start) % 8 == 0 and length % 8 == 0,
                      "u64 alignment after byte head")
            for pos in range(start, start + length):
                if covered[pos] != 0:
                    raise AssertionError("G8: overlapping synthetic tiled spans")
                covered[pos] = 1
            g8_spans += 1
    if not all(covered):
        raise AssertionError("G8: uncovered synthetic tiled copy span")
    g8_cases += 1
check(g8_cases == 13824, "G8 matrix completeness")
check(rejects(lambda: tiled_spans(0, 0, -1, 0, 1, 8)),
      "reject negative length")
check(rejects(lambda: tiled_spans(0, 0, 8, 3, 2, 8)),
      "reject out-of-range tile")
check(rejects(lambda: tiled_spans(0, 0, 8, 0, 2, 7)),
      "reject non-power-of-two copy block")
print(f"G8 PASS: u64/u8 alignment+tiling coverage {g8_cases} cases, {g8_spans} spans (synthetic)")

count = memcpy.end_lineno-memcpy.lineno+1
if count > 160:
    raise SystemExit("STOP: _memcpy_u64_tiled body exceeds bounded output; do not truncate")
print(f"\n=== PINNED ORIGINAL HELPER BODY: _memcpy_u64_tiled L{memcpy.lineno}-L{memcpy.end_lineno} ===")
for n in range(memcpy.lineno,memcpy.end_lineno+1):
    print(f"{n:5d}: {lines[n-1]}")
print("\nBATCH_SOURCE_CPU_CHECKS_PASS=",checks)
print("SOURCE_ONLY=True SYNTHETIC_CPU_ONLY=True")
print("RUNTIME_CORRECTNESS_VERIFIED=False")
print("ACTIVE_BLOCK_EQUALITY_VERIFIED=False")
print("PATCH_APPROVED=False")
print("PHASE5_MAMBA_BATCH_SOURCE_CPU_DONE_NOT_CERTIFIED")
PYCODE

echo "PASS: PHASE5_BATCH_OFFLINE_AND_PINNED_SOURCE_EXECUTED_NOT_CERTIFIED"
