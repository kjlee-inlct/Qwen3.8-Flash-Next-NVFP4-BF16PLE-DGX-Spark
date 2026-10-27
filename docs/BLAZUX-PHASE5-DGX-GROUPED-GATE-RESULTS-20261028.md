# Track A Phase 5 — DGX Group A + G1–G7 Mamba physical-state offline 결과 (2026-10-28)

## 2026-10-28 G8 최초 DGX 실행 결과 — 실패 (회귀시험 함수 바인딩)

- 실행 브랜치 `feature/blazux-phase5-correctness-mtp-offline`, 실제 **실패 SHA `ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5`**. `git fetch` + `git pull --ff-only` Fast-forward PASS.
- GROUP A Source Manifest `PASS_SOURCE_ONLY:177` 및 Wizard Mock `38/38 PASS`. 그러나 `Ran 310 tests in 0.365s` 후 `FAILED (errors=15)`, `FAIL: Phase5 unittest suite failed`. 10개의 새 G8 테스트 중 `test_g8_is_in_pinned_batch_gate`만 PASS, 나머지 9개 테스트가 unbound/bound descriptor 오류(서브테스트 포함 15 error)로 실패. `PHASE5_UNIT_PASS=310`, `PHASE5_SOURCE_AST_OK`, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS`, `G8 PASS`, 최종 Shell success 마커 **없음**.
- 재현/원인: `Phase5MemcopyTiledPartitionTests.setUpClass(cls)`에서 `cls.f = pure_oracles()["tiled_spans"]` 함수 객체를 클래스 속성으로 저장. Python instance lookup `self.f(...)`가 `self`를 1개 더 전달하여 `TypeError: tiled_spans() takes 6 positional arguments but 7 were given`. **테스트 harness의 함수 descriptor 바인딩 오류이며 Triton/GPU/물리 memory fault 증거가 아님**.
- 수정: `cls.f = staticmethod(pure_oracles()["tiled_spans"])`로 인스턴스 자동 바인딩 방지 + 기존 테스트의 staticmethod 형태 확인. 별도 로컬 G8 geometry fixture **13,824/13,824 synthetic CASE PASS**, span 23,552개 검사. 수정 GitHub SHA에서의 **전체 310 unittest, Source177 및 Group B/G1–G8 DGX 실행은 아직 NOT_RUN**. **가장 최근 완전 PASS**는 변경 이전 실측 `3c36420998061f7a3e656eb77390c04b7d2ef935`: 300/300 XFAIL0, Source176/176, G1–G7.
- Fail-closed: Group A failure caused `set -Eeuo pipefail` exit. **Group B G1–G8 전체 NOT_RUN** (앞선 `3c364209`의 G1–G7 PASS를 이 SHA에 귀속하지 않는다). Source-only/synthetic CPU correctness와 활성 GPU runtime/실 Mamba sizes·physical bounds/real speculative acceptance 여부는 구별한다.


> **DGX_GATE_PASS_AT_TESTED_SHA / UNIT_300_XFAIL0 / SOURCE176 / WIZARD_MOCK38 / G1_TO_G7_PASS / ORIGINAL_MEMCPY_BODY_PRINTED / RUNTIME_GPU_NOT_VERIFIED / PATCH_APPROVAL_ZERO.**
>
> 사용자 제공 `붙여넣은 텍스트(1)(20261027-164453).txt` (user-supplied shell transcript), exact tested source **`3c36420998061f7a3e656eb77390c04b7d2ef935`** on `feature/blazux-phase5-correctness-mtp-offline`. Source was fast-forward pulled in a **separate dedicated Phase 5 checkout** from previous source SHA `a5376cc`. Original operational `yslab-qwen38-bf16ple-dgx-spark` shell CWD did not cause a pull there: command changes directory to Phase5 checkout before Git actions.
>
> This evidence does not run real model, active cache config, CUDA/Triton kernels, prefix-hit replay, Parser/Responses or MTP acceptance, real serving benchmark, or GitHub Actions. This follow-up report + G8 CPU-only test **code commit is a new SHA and is NOT the SHA tested in this DGX log**.

## Group A: tracked source, mock, unit and audit

| Marker/result | Observed |
|---|---|
| `PHASE5_BATCH_SOURCE_HEAD` and `PHASE5_SOURCE_HEAD` | exact `3c36420998061f7a3e656eb77390c04b7d2ef935` |
| `PASS_SOURCE_ONLY` | **176 tracked files**, repeated before and after suite |
| `manifest OK` | project manifest, 4 targets |
| Wizard fake services | **38/38 PASS** |
| Python unittest discover | **Ran 300 tests / OK**, `PHASE5_UNIT_PASS=300; XFAIL=0` |
| Source AST | `PHASE5_SOURCE_AST_OK` |
| Full offline wrapper | `PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS` |

The wrapper includes Bash syntax and publication audit; the output above establishes wrapper completion at this exact source SHA, not a separate claim of full production release readiness.

## Group B: pinned installed preview + G1–G7 CPU oracles

- `SOURCE_IMAGE=sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`; isolated disposable `runc`, `--network=none --read-only --cap-drop=ALL`, `CUDA_VISIBLE_DEVICES=-1 NVIDIA_VISIBLE_DEVICES=void`; no mount of weights/service state. Installed preview source SHA/AST pinned for four selected files, including `v1/worker/mamba_utils.py` SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3`.
- G1 hash/source/AST **PASS**, G2 physical state/group table/metadata static anchors **PASS**, G3 V1/V2 batch-row versus request-slot and negative sentinel **PASS**, G4 multiple Mamba group physical byte/element offset synthetic **PASS**, G5 SD/DS convolution, temporal bias, padded/natural payload synthetic **PASS**, G6 equal/unequal cache vs Mamba block arithmetic with **224 mismatched synthetic positions** **PASS**, G7 speculative bias, self-copy, zero/negative/OOB and partial-tail synthetic **PASS**.
- Embedded `BATCH_SOURCE_CPU_CHECKS_PASS=343` (**internal assert/check counter, not 343 independent unittest cases**) and `PHASE5_MAMBA_BATCH_SOURCE_CPU_DONE_NOT_CERTIFIED`; wrapper final `PASS: PHASE5_BATCH_OFFLINE_AND_PINNED_SOURCE_EXECUTED_NOT_CERTIFIED`, user shell final `PHASE5_GROUPED_GATE_EXECUTION_COMPLETED`.
- `_memcpy_u64_tiled` **40–119 inclusive** was printed in full, not a GPU execution. Source static branches: same modulo-8 src/dst alignment `((src_addr_i ^ dst_addr_i) & 7) == 0` uses tile-0 byte head, tiled aligned `tl.uint64` body, tile-0 byte tail; mismatched alignment uses per-tile bytewise fallback. `COPY_BLOCK_SIZE`-rounded ranges and masked ends appear in source. As with source-only prior reports, no proven aliasing correctness, runtime misalignment behavior, or actual CUDA GPU State comparison.

## Remaining Phase5 scope and grouped last offline follow-up (G8)

- G1–G7 synthetic PASS **does not prove** `_memcpy_u64_tiled` branch partition completeness by itself. Source body reveals fast/slow paths, so this update adds **G8 CPU-only geometry oracle** to the same tracked script, with 8×8 pointer mod-8 alignment combinations, tile counts (1/2/3/7), copy-block element spans (8/32/1024) and byte sizes (0–2051 inclusive at selected boundaries). Includes no-duplicate/no-gap and u64 address alignment assertions; full matrix **13,824 synthetic combinations**. Additional **10 stdlib regression tests** inserted in existing Phase5 test module. A preliminary *isolated local* CPU oracle matrix executed **13,824/13,824**; **new GitHub code SHA / full DGX Gate NOT_RUN** until next user log.
- If G8 and the pre-existing Group A/G1–G7 all PASS at exact new SHA, Phase5 *source/CPU* physical state/Mamba offline gate may be labeled completed **only at that scope**. Still **BLOCKED/NOT_VERIFIED** for actual runtime `CacheConfig.block_size == MambaSpec.block_size` equality/group inventory/branch reachability, physical allocation bounds, GPU postprocess/state rollback/real prefix hits, Parser/Responses/MTP acceptance, real inference/TPS and CI.
- Phase6 may be planned as the separate approval-gated runtime verification phase; **no new Phase6 ref/PR/merge, GPU/model/serving or blazux patch creation/application under Phase5** without explicit user authorization. Preserve main/P0/Phase1–4 immutability. No regression result from docs-only follow-up commit may be attributed to tested source `3c364209`.

