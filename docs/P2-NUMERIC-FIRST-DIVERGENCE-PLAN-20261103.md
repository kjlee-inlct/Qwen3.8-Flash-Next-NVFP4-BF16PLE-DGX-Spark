# P2 Numeric 최초 비재현성 경계 — 최소 Sampler 단독 후보 (2026-11-03)

## 목적

최종 목표는 DGX Spark의 운영 **Orcarouter NVFP4/BF16 PLE/MTP2**에 Blazux 최적화를 이식하는 것이다. 직전 DGX 실측 4-COPY stage는 이미 PASS였으므로 재구축하거나 재시험하지 않는다. 다음 독립 장애는 원본 Prefix OFF/MTP OFF에서도 나타나는 **strict abs logprob tolerance 1e-4 비재현성의 최초 계산 경계**이다.

- 사용자 DGX 소스 HEAD: `4c5710d4e5b3085ec5aae1354d1b9052537af2dc`, `--stage-mtp-upstream` 29/29 PASS, SKIP0, 실제 설치 Sampler/PLE/MTP exact source pin, Blazux 65,536 IDs 검증, 원본 container unchanged.
- 사용자 DGX 4-COPY private stage: `/tmp/p2-functional-bundle-ackw9piv` (sampler.py, vllm_ple_mmap.py, mtp.py, draft_vocab_65536.npy, Dockerfile). 해당 기존 private stage를 **읽기 전용**으로 재사용한다.
- 위 경로는 사용자 제공 실측에 기반한 명시적 진입점이다. 다른 `/tmp` 디렉터리 자동 탐색 금지.

## 왜 1-COPY 단독 후보가 필요한가?

성능 통합용 4-COPY 소스는 이미 조립했지만 실제 numeric 원인 추적에서는 PLE Gather·Draft MTP 축소를 켜면 관측 변수가 증가한다. 다음 Numeric 비교는 **원본 영상 그대로의 BF16 PLE/Stock QSA**를 유지하고, 오직 설치 Sampler에 SHA 고정 Witness만 추가한 **one-COPY 진단 전용** 후보로 분리한다. 향후 승인된 정비창에서 `Prefix OFF`, `MTP OFF`, 동일 단일 synthetic 요청, `max_tokens=1` 및 API logprob가 실제 raw_logprobs witness를 만들 수 있는지 먼저 확인해야 한다. Event가 없으면 설계 검증이 미완료인 것이지 오차가 없다는 뜻이 아니다.

기존 P1 A/B/C: Stock QSA 원본, QSA-only 후보, MTP-OFF 모두 strict FAIL; 이미 확인한 동일 실험 반복 금지. 후보의 Sampler 계측은 CPU/GPU 동기화를 포함할 수 있어 계측 OFF의 결정성을 대신 증명하지 못한다.

## 이번에 구현한 실 기능

- `src/p2_numeric_minimal_candidate.py`: pinned 4-COPY stage의 5개 파일명, 소유자, 0700/0600, no symlink, 실제 SHA 검증. 읽기 전용 원본 Docker `inspect` 및 동일 ID/image/StartedAt 재확인, 기존 실증 원본 CLI semantics (Prefix OFF + MTP2) 점검. 신규 후보 계획은 MTP OFF를 **문자열로만 산출**, 절대 실행하지 않는다. `--prepare`는 private `/tmp/p2-numeric-first-divergence-*`에 `sampler.py`, `Dockerfile`, `receipt.json`만 새로 만든다.
- 생성 `Dockerfile`: 기존 pinned 이미지 `FROM`, **sampler.py 하나의 COPY**, `VLLM_P2_NUMERIC_WITNESS=0`, `VLLM_PLE_UNIQUE_H2D=0`, `VLLM_P2_DRAFT_VOCAB=` 기본 OFF. PLE/MTP 소스, Draft ID를 COPY하지 않음. 이미지 빌드, 네트워크, CUDA, HTTP, model loading, Docker create/run/stop/start/exec 명령 없음.
- `tests/test_p2_numeric_minimal_candidate.py`: 새 소스 유효성/보안/변조 차단/원본 ID/상태/전후 StartedAt/단일 COPY/개인 artifact·영수증 계약을 검증하는 집중 CPU synthetic 10건. 운영 모델/컨테이너를 열거나 테스트하지 않는다.
- `scripts/p2-numeric-first-divergence-dgx.sh`: 이전 29개나 과거 37개 시험을 다시 실행하지 않는다. 오직 새 집중 10건 + 현재 소스 HEAD/clean manifest 검증 + 원본 읽기 전용 검사 + 사본 준비.

## 실제 DGX 다음 한 번의 실행 (GPU 미사용)

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-numeric-first-divergence-dgx.sh --prepare /tmp/p2-functional-bundle-ackw9piv
```

- 성공 시 `P2_MINIMAL_NUMERIC_PRIVATE_SOURCE_STAGED_NOT_BUILT`, `P2_NUMERIC_MINIMAL_SOURCE_COMPLETE ... NO_DOCKER_BUILD_NO_GPU_NO_HTTP`.
- 코드의 일반 `--preflight` 옵션도 같은 경계 체크를 하지만 디렉터리는 만들지 않는다.
- 실패 시 `P2_MINIMAL_NUMERIC_STAGE_BLOCKED`: source SHA/Stage 내용/소유권/원본 Docker identity/명령의 어느 하나가 변한 것으로 간주. 원본 수정, 보안 완화, 디렉터리 자동 검색/재생성, fallback build 금지. 이전 29/29 실측 효력은 과거 소스 SHA에 남는다.
- **이번 변경 HEAD는 병합된 뒤 사용자 DGX 실측을 받기 전까지 DGX_NOT_RUN/CI_NOT_RUN**.

## 실제 GPU 창이 풀어야 할 것 — 별도의 운영 중단 명시 승인 필요

1. 정비창 시작 전에 동일 원본 ID/Image/StartedAt/운영 8000 HTTP 상태, 최소 96GiB+의 BF16 PLE 모델 메모리 요구를 반영한 현재 GPU/통합 메모리, 체크포인트·cache read-only mount, 다른 candidate 부재, 단독 정비창·중단 복구 계획을 확인. 기존 서비스를 유지한 채 대형 두 번째 모델 동시 기동 **불허**.
2. 명시적으로 별도 승인된 운영 정비창에서만 기존 같은-ID 원본을 정상 stop(삭제 금지), Numeric 단독 candidate image를 검증된 방식으로 build/launch, model Prefix OFF/MTP OFF로 **원본과 동일한 request 조건에서** 제한된 synthetic 첫 토큰 요청을 수행한다. 이 문서와 스크립트는 그 실행을 승인/수행하지 않는다. 후보 health/자원/계측 수집에 실패하면 격리된 후보만 owner-check 후 cleanup, 원본 same-ID restart 및 HTTP restoration.
3. 최초 각 run의 `raw logits SHA`, `raw logprobs SHA`, `selected-token ID digest/logprob`, `API logprob`만 (원문·raw logits·토큰값 무출력) 대응. 동일 tokens/finish/worker/serial provenance가 성립할 때만 `src/p2_numeric_report.py` 분석. `1e-6` 값 대응은 witness↔API 매핑 확인 전용이며 strict release `1e-4`와 다름.
4. 첫 발견 차이가 logits 이전이면 model forward/PLE/BF16 연산 경계, logits 동일하지만 logprobs 차이면 reduction/log_softmax, logprobs도 동일한데 API 차이면 post-Sampler/serialization 경계를 차례로 조사. 최초 관측 차이와 물리적 원인을 동일시하지 말 것.
5. 실제 시점까지 `strict_numeric_release_pass=false`, `native_mtp_runtime_verified=false`, `full_state_reuse_verified=false`, `DEPLOYED=false`. 이미 확보된 4-COPY 통합 후보로의 복귀는 단독 원인 분석 후 별도 통합 GPU 정확성·성능 단계에서만.

**운영 승인 경계:** 사용자의 일반적인 “계속”은 GitHub 코드 작성·PR·merge 및 CPU/source-only 준비 계속의 승인이지, stop/start 또는 API/GPU 부하의 명시적인 정비창 실행 승인이 아니다. 승인 전에는 이 계획의 source-only 실행까지만.
