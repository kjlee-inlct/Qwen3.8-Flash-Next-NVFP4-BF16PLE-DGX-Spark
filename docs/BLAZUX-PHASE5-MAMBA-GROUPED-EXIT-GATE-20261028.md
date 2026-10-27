# Track A Phase 5 — Mamba physical-address grouped Gate / Phase 6 readiness

## 2026-10-28 현재 이관 상태 (Phase6 실행 미승인)

- Phase5 source/CPU offline scope는 exact DGX-tested `780b780fc7572226a6a9ff2e52cd8e1921c8738b` (310/310 XFAIL0, Source177, G1–G8)에서 종료되었다. Phase5 종료 재시험 계획 없음; 새 대화는 [SESSION-HANDOFF-PROMPT.md](SESSION-HANDOFF-PROMPT.md)의 최신 **Phase6 범위 확정만 진행** 진입점부터 시작할 것.
- 남은 일은 P6-A 실제 설정/ABI, P6-B 격리 GPU state/prefix, P6-C real MTP/Parser/Tool/Responses, P6-D 정확성 후 TPS/메모리/안정성의 묶음 검증 설계와 승인 요건이다. 모두 **NOT_RUN/BLOCKED**, blazux 패치 승인 없음. 운영 서비스/모델/GPU/CI/Phase6 branch/PR/merge는 명시적 승인 전 수행 금지.
- 2026-10-28 확인: Phase5 선행 문서 HEAD `a205a3f958c250e2e30cb20fc99424666b2e0ff5`, open PR 0, Actions run 0, commit statuses 0. 후속 docs-only HEAD를 DGX-tested SHA로 귀속하지 말 것.


## 2026-10-28 Exit decision (CURRENT): Phase5 SOURCE/CPU OFFLINE PASS, Phase6 runtime NOT_RUN

- **DGX tested code `780b780fc7572226a6a9ff2e52cd8e1921c8738b`**: Manifest **177/177**, Wizard **38/38**, unit **310/310 XFAIL0**, AST/offline wrapper PASS, source/CPU G1–G8 PASS, G8 **13,824 synthetic configurations / 23,552 spans**, embedded `25528` checks, required final shell marker PASS. This resolves the *historical* `ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5` G8 descriptor FAIL. [Newest evidence](BLAZUX-PHASE5-DGX-GROUPED-GATE-RESULTS-20261028.md).
- **Phase5 offline exit status: PASS, scoped only to pinned preview source contracts and CPU synthetic oracles.** Original physical GPU buffer access, actual config equality/group/slot bounds, real speculative state and prefix hits, HTTP/MTP/Parser/Responses, performance and CI remain NOT_RUN/BLOCKED. Neither patches nor Phase6 GPU testing are approved by this evidence.
- **Phase6 grouped entry plan awaiting separate scope approval**: P6-A read-only active config/block size/group/ABI observation; P6-B guarded GPU Mamba state rollback/prefix correctness on isolated reproducer; P6-C real MTP acceptance and Tool/Responses protocol; P6-D benchmark regression/stability only after correctness. Define PASS/FAIL/BLOCKED/NOT_RUN + exact model/runtime/image fingerprint; do not mistake static/synthetic for runtime. Never create Phase6 branch or alter serving/GPU/weights/CI/PR before explicit approval.
- **Persistent operating rule**: any new rule, result, error and handoff delta must be committed together to source manifest, handoff, adoption plan, this exit gate, and authoritative evidence on current approved branch. Do not force user to download tools; GitHub CAS commit then dedicated checkout fast-forward pull. Keep tested SHA vs later documentation-only SHA separate and protect main/P0/Phase1–4.


## 2026-10-28 G8 fail-closed 및 새 영구 문서 규칙

`ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5`의 첫 G8 DGX 시도: Source177/177와 Wizard38/38 PASS, 전체 310 unittest는 **FAILED(errors=15)**; Python descriptor 함수 바인딩 `cls.f`에 암묵적 `self` 전달된 신규 테스트 코드 오류. **Group B/G1–G8 NOT_RUN**. 같은 Phase5에서 `staticmethod`로 수정, 기존 test에서 descriptor를 검사하도록 보강. 로컬 참고값 13,824/13,824 synthetic fixture PASS는 **DGX 전체 Gate PASS가 아님**. 완료된 마지막 실제 DGX 전부 PASS `3c364209`: 300/300, Source176, G1–G7. 신규 Github 수정 HEAD 재실행 전 Phase5 G8 종료 주장 금지.

신규 운영 규칙: 규칙/증거/오류/핸드오프 누락 확인 시, **SESSION-HANDOFF-PROMPT.md + 적용 계획 + 해당 정본 보고서/종료기준 + Full Source Manifest를 항상 같은 Phase5 브랜치의 동일 커밋에서 동기화**. 다음 실행은 Github 직접 커밋→DGX 별도 Phase5 checkout의 `git pull --ff-only`→**통합 Gate 한 번**. Phase6 새 브랜치/PR/Merge 및 실 GPU/운영/patch 변경은 별도 승인 전 금지.


> **G1–G7 DGX PASS at 3c364209 / first G8 ff1f66a DGX FAIL / fixed HEAD DGX NOT_RUN / GPU-RUNTIME NOT_CERTIFIED / PATCH_APPROVAL ZERO.** This is a Phase 5 check and does not itself authorize a new phase, real GPU/model access, CI, or runtime patching.

## Evidence provenance

- Last actual full DGX Gate PASS remains **tested code HEAD `3c36420998061f7a3e656eb77390c04b7d2ef935`**, unit **300/300**, XFAIL=0, source **176/176**, G1–G7 PASS. Later source `ff1f66a` **FAILED 310 unittest** because of new G8 Python descriptor binding; Group B/G1–G8 NOT_RUN at that SHA. The new binding fix HEAD has not been fully DGX tested yet.
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

The full G1–G8 offline DGX log has now been recorded at exact tested SHA 780b780f (310/310, Source177, G8 13,824). Future runs should be Phase6 scope-approved and grouped, not redundant Phase5 source/CPU reruns. Keep remaining risks visible, do not make duplicate evidence commits.
