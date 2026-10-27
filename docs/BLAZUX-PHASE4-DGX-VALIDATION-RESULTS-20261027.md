# Track A Phase 4 — DGX 오프라인 통합 검증 결과 (2026-10-27)

> **판정: PHASE4_CPU_OFFLINE_PASS / SOURCE_137_OF_137 / UNIT_194_OF_194 / XFAIL_0 / FLAG_MATRIX_4_OF_4_BYTE_EXACT.**
>
> **사용자 제공 DGX 로그에 근거**한다. 이 문서를 기록하는 GitHub 플러그인은 DGX에서 시험을 실행하지 않았다. **실제로 시험한 소스 HEAD는 `a90eb081a9d85d290d191674c303d33cadb6f22d`**이며, 이 보고서/Manifest를 추가하는 후속 커밋은 다른 SHA이고 DGX에서 재시험하지 않았다.
>
> **GPU/실제 모델 추론, pinned H2D, 실제 95.37GiB PLE, KV/Mamba/SSM, vLLM ABI, TPS/TTFT 및 성능 A/B, CI는 미실행.** 운영 Docker/모델과 `main` 및 이전 Phase는 변경하지 않는다.

## 1. 대상과 기능 경계

| 항목 | 값 |
|---|---|
| Branch | `feature/blazux-phase4-ple-cpu-bundle` |
| DGX 테스트 소스 SHA | `a90eb081a9d85d290d191674c303d33cadb6f22d` |
| Phase 3 확정 부모 | `760f227e46a358445db3d3931b5efbe40de5f609` |
| 독립 기능 A 커밋 | `4aa692624f95008abbd76f808791b524335fb0c7` |
| 독립 기능 B 커밋 | `b83ecc66a70e53515fcd0992b51dc705236778e1` |
| 통합 회귀 fixture 커밋 | `a90eb081a9d85d290d191674c303d33cadb6f22d` |
| 외부 비교 소스 | [blazux 고정 SHA](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) |

- 기능 A: `VLLM_PLE_FAST_GATHER=0` (**기본 OFF**). 명시적 ON의 작은 N 행 모드만 inline gather를 수행하고, OFF 및 threshold 초과 입력은 기존 중복제거/정렬/threadpool 경로 유지.
- 기능 B: `VLLM_PLE_PHASE_STATS=0` (**기본 OFF**). 명시적 ON에서만 per-table CPU gather `calls/errors/rows/logical_bytes/gather_s/fast_calls` 카운터 기록. `logical_bytes`는 실제 NVMe I/O 바이트가 아니다.
- 독립 기능 2개와 통합 회귀를 **동일 Phase 4에서 각각 별도 구현 커밋**으로 수행했다. 기능 기본 OFF/롤백은 GPU 배포 승인과 다르다.

## 2. 사용자 DGX 소스/단위시험 실측

```text
OK
PHASE4_UNIT_PASS=194; XFAIL=0
PASS_SOURCE_ONLY: 137 tracked file(s)
  branch=feature/blazux-phase4-ple-cpu-bundle HEAD=a90eb081a9d85d290d191674c303d33cadb6f22d
  NOTE: Untracked/ignored files, model payload, Docker and runtime are NOT verified
PASS: PHASE4_BUNDLED_CPU_SOURCE_CONTRACTS
NOTE: phase4 CPU flag matrix runs only with --ple-cpu or in isolated container
NOT_RUN: GPU inference, serving image, KV/Mamba, pinned H2D, TPS benchmark, CI
```

- **137/137 Source Manifest PASS**, 단위시험 **194개 정상 종료 XFAIL=0**, Phase 4 오프라인 runner 성공.
- Phase 4 fail-fast wrapper는 origin/branch/clean checkout/부모 조상 확인, deployment manifest, Mock, Python unit, Bash 문법, publication audit 및 전후 Source Manifest를 포함한다. 이 메시지는 요약 출력이므로 개별 Mock 실행 수를 별도 관측했다고 주장하지 않는다.
- Source 검증은 untracked/ignored 파일, 모델 payload, Docker 및 runtime을 보증하지 않는다.

## 3. 사용자 DGX CPU BF16 경로 실측

```text
PASS: BF16 mmap gather/torch forward byte-exact workers=1 chunk=1024
PASS: BF16 mmap gather/torch forward byte-exact workers=4 chunk=2
PHASE3_PLE_DUPLICATE_GUARD_ALL_OK
PHASE2_PLE_CPU_ALL_OK
PASS: PHASE4_FLAG_MATRIX fast=0 stats=0 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=1 stats=0 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=0 stats=1 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=1 stats=1 byte_exact=1
PHASE4_CPU_MATRIX_ALL_OK
PASS: PHASE4_COMBINED_OFFLINE_VERIFICATION
```

| FAST | STATS | 정상·오류·BF16 바이트 비교 |
|---|---|---|
| OFF | OFF | PASS (`byte_exact=1`) |
| ON | OFF | PASS (`byte_exact=1`) |
| OFF | ON | PASS (`byte_exact=1`) |
| ON | ON | PASS (`byte_exact=1`) |

- 정상 경로의 worker=1/4 결과와 Phase 3 `G2-01` 중복 샤드 거부가 유지됐다.
- 새 fixture의 네 조합은 작은 합성 BF16 safetensors의 empty/duplicate/out-of-order/short shard, threshold 512/513, 음수·범위초과, 계측 스냅샷, torch forward의 바이트 정확성을 검사한다.
- 이 결과는 **값 일치 검증이지 성능 향상 검증이 아니다**. CPU/GPU 처리량·지연·page cache·실 모델 및 제품 품질 개선은 측정되지 않았다.

## 4. Gate 4 판정과 보호 규칙

**Gate 4 계획된 DGX CPU 오프라인 정합성 시험 완료(PASS).** CI·GPU·실 서비스 A/B는 별도 미검증 Gate이며, 벤치마크를 실행했다고 주장하지 않는다.

**Phase 수 절감:** 같은 위험·rollback·실험 승인 범위의 CPU 회귀 보완, 문서·성능 *시험 설계* 등은 새로운 Phase를 만들지 않고 Phase 4 안에서 처리한다. GPU/운영 이미지/모델·HF cache/포트에 영향을 주는 실행은 별도 사용자 승인 전 금지한다.

**브랜치:** `main`, P0, Phase1/2/3 불변. PR·Merge는 현재 불필요. 리뷰가 요구되면 `head=feature/blazux-phase4-ple-cpu-bundle`, `base=feature/blazux-phase3-ple-duplicate-shard-guard`의 **비병합 Draft PR**만 고려한다. **`main`으로 향하는 PR/merge/cherry-pick/rebase/squash/sync 영구 금지.**

**SHA 경계:** DGX 실기 검증 HEAD `a90eb081a9d85d290d191674c303d33cadb6f22d`. 이후 문서만 추가한 커밋의 Github source manifest/Git tree 일치를 따로 확인하며, 그 새 SHA에서 194개를 다시 실행했다고 기록하지 않는다.
