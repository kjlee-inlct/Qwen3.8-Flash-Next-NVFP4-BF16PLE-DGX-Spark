# Track A Phase 5 — Mamba physical-address grouped Gate / Phase 6 readiness

> **G1–G7 DGX PASS at 3c364209 / G8 NEW HEAD DGX NOT_RUN / GPU-RUNTIME NOT_CERTIFIED / PATCH_APPROVAL ZERO.** This is a Phase 5 check and does not itself authorize a new phase, real GPU/model access, CI, or runtime patching.

## Evidence provenance

- Last actual full DGX Gate PASS remains **tested code HEAD `a5376cc06536ce786cdb6db8425e26e21b608910`**, unit **276/276**, XFAIL=0, source **169/169**. Neither later docs-only HEADs nor the new code in this Gate has been DGX tested yet.
- User DGX source-only evidence in [fused-kernel body report](BLAZUX-PHASE5-DGX-MAMBA-FUSED-KERNEL-BODIES-RESULTS-20261027.md) and [physical state/metadata report](BLAZUX-PHASE5-DGX-PHYSICAL-STATE-METADATA-RESULTS-20261028.md). Installed `v1/worker/mamba_utils.py` pinned SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3`, physical helper lines 122–252, metadata lines 843–957.
- This commit introduces `scripts/phase5-mamba-batch-check.sh` and `tests/test_blazux_phase5_mamba_batch_gate.py` (24 locally executed synthetic/unit cases, **not** full DGX run). A pinned installed vLLM source SHA drift blocks verification.

## One pull, one bundled command

Use only the separate dedicated Phase 5 checkout; never pull in the operational `yslab-qwen38-bf16ple-dgx-spark` checkout. After guarded `git pull --ff-only`, run:

```bash
scripts/phase5-mamba-batch-check.sh
```

The tracked script rejects wrong origin/branch, dirty checkout and missing Phase 4 ancestor. GROUP A runs `scripts/phase5-check-offline.sh` (manifest, wizard mocks, **all** unittest, AST, shell syntax and publication audit). GROUP B uses `docker inspect` only for an existing serving container's image ID, then starts a **disposable**, network-none, read-only, no-GPU, runc, CPU-limited container without serving/model mounts, for G1–G7:

| Group | Coverage | Certification boundary |
|---|---|---|
| G1 | Installed Python source hashes for four pinned files, AST parse | Original version identity only |
| G2 | Copy/helper, group block table, metadata, context, pre/postprocess original source anchors | Source contract, not a CUDA run |
| G3 | V1/V2 batch-row vs request-slot, negative sentinel, fresh/same-column | Synthetic/source checks |
| G4 | Multiple Mamba group table selection, int32 element offset, int64 physical ID, byte stride | Synthetic physical arithmetic |
| G5 | SD/DS conv accepted bias, temporal selection, page padding/natural payload | Synthetic byte-copy |
| G6 | B_cache=B_mamba and unequal, zero, resumed, boundary and partial-tail | Math sensitivity, **not an observed bug** |
| G8 | 8×8 source/destination alignment, u64 head/body/tail vs byte fallback; 13,824 synthetic tile-partition combinations, no gaps/overlap | CPU proof only; not actual Triton GPU memcpy |
| G7 | Spec acceptance, self-column+bias, zero/negative/OOB and partial tail | Stronger CPU oracle bounds, **not Triton guards** |

The bounded `_memcpy_u64_tiled` original function **body** is also printed; synthetic byte-tail PASS alone does **not** certify Triton uint64 alignment, masking, aliasing or tiled runtime correctness. The final expected marker is `PASS: PHASE5_BATCH_OFFLINE_AND_PINNED_SOURCE_EXECUTED_NOT_CERTIFIED`. Every earlier group must finish for the wrapper to print it. Record actual test count, Source Manifest count and source SHA from output; never pre-label new HEAD as DGX PASS.

## Exit criteria and Phase 6 no-omission handoff

Evaluate each as **PASS / FAIL / BLOCKED / NOT_RUN**, rather than allowing empty items to appear as passes.

1. Repository: same Phase 5 branch, full path/mode/blob Source Manifest matching Tree, approved origin and clean checkout, protected main/P0/Phase1–4 unchanged, no Phase 5 PR/Merge. Preserve separately the **DGX-tested code SHA** and later **docs-only commit SHA**.
2. Offline Gate: manifest, all unit/XFAIL0, mock and source AST, shell syntax and publication audit, plus pinned installed source/fused helpers printed without truncation.
3. Mamba contract: CacheConfig seed/Scheduler split vs MambaSpec/context/align block size semantics; V1/V2 batch-row and request slot mapping, sentinel; group-local table base; physical ID and byte offsets; DS/SD conv/temporal, speculative bias, tiling and negative boundary cases.
4. CPU oracle: equal/unequal blocks, fresh/resumed, exact boundary, partial tail, zero, same-column/bias, multi-group and page strides, OOB reference check. **Synthetic checks never prove GPU correctness.**
5. **Explicitly NOT verified** by this batch: active running CacheConfig and MambaSpec values, actual group inventory and branch reachability, concrete state tensor physical bounds, CUDA copy/rollback/prefix cache hit, real inference or MTP acceptance, Parser/Responses, TPS and CI. These remain visible requirements if Phase 6 scope needs them.
6. **Phase 6 boundary**: completion of this Phase 5 source/CPU suite means only that those *offline* gates are ready. Do not create Phase 6 or launch real model/GPU/CI/tests, deploy patches, modify service/weights/cache, or alter protected refs without separate explicit user authorization of that scope.

On the next DGX log, record complete G1–G7 and offline Gate output against its exact tested SHA, including unresolved statuses. Batch follow-up checks instead of serial one-by-one probes. Do not make duplicate evidence commits.
