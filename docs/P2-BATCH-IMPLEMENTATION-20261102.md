# P2 묶음 구현 — Numeric / MTP draft vocabulary / BF16 PLE unique H2D (2026-11-02)

## 실제 코드 변화

1. **Numeric offline report**: `src/p2_numeric_report.py`는 승인된 별도 격리 후보에서 얻은 단일 토큰 API 결과(`runs`)와 Sampler witness(`events`)를 민감한 원문 재출력 없이 `classify_witness`로 해석한다. `prefix_off_verified`, `mtp_off_verified`, `single_active_request_verified`를 모두 명시적으로 증명하지 못하면 `INCONCLUSIVE`. 기존 strict absolute logprob release 기준 `1e-4`를 변경하지 않는다. **실제 숫자 원인/수정은 아직 OPEN**.
2. **MTP 65,536/248,320 ID 매핑 계약**: `src/p2_mtp_draft_vocab.py`에 축소 Draft Vocabulary의 local→full tokenizer ID 변환, 역매핑, 범위/중복/필수 특수 토큰 보존, Head 행수 65,536 검증 및 fingerprint를 추가했다. **CPU 계약 코드이며 실제 31 BF16 MTP tensor 수정·모델 head slicing/weight 적용/실서빙 추론을 수행하지 않는다.** 현재 Draft Head가 target 248320 rows를 공유한다면, 별도 pinned Preview ABI/loader 분석 전 축소 적용 **BLOCKED**. 이 helper는 실제 vocab 선정 알고리즘, 언어별 품질 검증 또는 vLLM 연결 완료를 뜻하지 않는다.
3. **실제 PLE 로딩 경로 코드 변경 (opt-in)**: `src/vllm_ple_mmap.py`는 BF16에서만 `VLLM_PLE_UNIQUE_H2D=1`일 때 `np.unique(ids, return_inverse=True)`로 중복 행을 모아 기존 `MmapPleTable.gather(unique)`를 사용하고, **중복 제거 행만 CPU→device 전송한 뒤 device `index_select`로 원래 N행 순서를 복원**한다. 기본값 OFF이며 BF16 외 FP8은 기존 경로 유지. `VLLM_PLE_PHASE_STATS=1`인 경우 `forward_s`가 새 경로 전체를 포괄하나 기존 `device_copy_call_s`는 이 경로에서 inverse+gather 완료시간을 포함하지 않으므로 GPU H2D 실측으로 사용 금지. 기존 P1 builder의 `NEW_PLE_SHA`는 **이전 소스에 고정된 보호 SHA**로 보존: P2 코드를 기존 P1 builder로 빌드하려 하면 SHA drift 차단이 정상이며 새 P2 격리 후보가 별도로 필요하다. BF16 unique 행 수가 작은 입력에서는 inverse H2D·GPU index_select 비용이 오히려 커질 수 있으므로 **성능 향상/graph 안전성을 아직 주장하지 않는다**.

## DGX Git pull 후 한 번에 CPU/source 확인

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-batch-dgx.sh
```

스크립트는 P2 branch/HEAD/개인 Fork/clean Source Manifest 확인, Python AST, 기존 P2 Numeric 단위시험과 추가 Numeric/MTP/PLE 시험, Bash 구문을 **한 번** 검증한다. 어떤 Docker inspect/build/run/exec/stop, GPU/API/inference, 외부 네트워크, 모델/캐시/체크포인트 수정도 수행하지 않는다. Torch/NumPy가 호스트에 없을 때 PLE 테스트는 명시적 `skipped` 상태이며 **CPU byte-exact PASS로 보고하지 않는다**. 실제 DGX가 실행한 SHA의 시험 개수·skip/FAIL을 로그로 확인한다.

격리 후보에서 얻은 **원문을 포함하지 않는** 정규화 JSON 파일이 승인된 후 제공됐을 때만 선택적으로 다음을 수행한다(지금 실행할 실제 witness evidence는 없음):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m src.p2_numeric_report --input /path/to/approved-offline-witness.json
```

`--input`에는 `runs` list(단일 token ID 및 선택 logprob), `events` list(candidate witness), `provenance` verified flags를 포함한다. 이벤트 유실/불일치/근거 누락이면 exit 2. 입력 파일·raw tensor/prompt를 그대로 내보내지 않음. **운영 포트 8000/HTTP 추론을 자동 호출하지 않는다**.

## 남아 있는 실제 blocker와 다음 묶음

- **Numeric:** pinned Sampler 경계 실 GPU 샘플/row-API 대응은 별도 정비창 GPU 승인과 격리 후보 기동 없이는 불가. 소스/CPU PASS로 strict FAIL을 해결했다고 하지 않는다.
- **MTP reduced draft:** token frequency/다국어/필수 token 목록 근거, 정확한 installed Preview draft head↔target head ABI, weight layout, sampler/rejection remap, 성능 측정 미완료. 실제 모델 변경은 별도 candidate-only 작업.
- **PLE Gather:** BF16 unique-only H2D 소스 구현은 준비, CPU byte-exact와 후속 승인된 격리 모델에서 TTFT/TPS/H2D 완료·GPU memory·CUDA graph 영향 검증 미완료. 원본·P1 pinned stage/운영 변형 금지.
- **vLLM v0.32 Track B / GDN/PLE full-state reuse:** 별도 소스/ABI/검증 미착수 유지. 이 묶음에 억지로 승격하지 않는다.

**상태:** `P2_BATCH_SOURCE_IMPLEMENTED / DGX_NOT_RUN / GPU_NOT_RUN / P2_NUMERIC_ROOT_CAUSE_OPEN / P1_RELEASE_BLOCKED`. SHA·시험 증거가 들어오기 전 PASS 승격 금지.

## 2026-11-02 실제 DGX P2 묶음 결과 및 1회성 CPU 컨테이너 검증

- **DGX-tested exact source HEAD** `c648d885c9e26d1c25ad40d8cf16449f94593f72`: `scripts/p2-batch-dgx.sh` `P2_SOURCE_PREFLIGHT_PASS_NO_DOCKER_OR_GPU`, `P2_BATCH_SOURCE_AST_PASS`, targeted unittest `Ran 40 tests`, `OK (skipped=4)`. 36개 PASS / **PLE Torch+NumPy 필요한 4개 SKIP**. PLE CPU correctness NOT_VERIFIED (SKIP은 PASS가 아님).
- 이전에는 고정 이미지 기반 `scripts/ple-phase-stats-cpu-container.sh` 등에서 독립 `runc` CPU 전용 일회성 Docker를 사용한 선례가 있음. 호스트에 `numpy`/`torch`를 설치하거나 운영 원본 `docker exec`하지 않는다.
- 신규 `scripts/p2-batch-cpu-container.sh --execute`: 기존 원본 고정 **container full ID / image digest / running / StartedAt** 사전·사후 검사, 기존 로컬 고정 이미지 ID, MemAvailable 8 GiB 전제/4 GiB 종료 하한, 정확한 개인 Fork/브랜치/HEAD/Source Manifest 검사. **Docker run 1회**: `--rm -i --pull=never --runtime=runc --network=none --read-only --cpus=2 --memory=2g --memory-swap=2g --pids-limit=96 --user=65534:65534`, GPU 노출 없음, repo read-only bind, 128 MiB 임시 tmpfs, 패키지/모델/weights/HF cache/호스트 데이터/네트워크 접근 불필요. 정확한 기존 P2 6개 unittest 모듈 **40 tests / skipped=0**만 PASS로 인정. Docker run은 **오직 DGX 사용자가 `--execute` 명시 실행한 경우**에만 발생.
- DGX에서: `cd ~/Workspace/llm/blazux-phase6-gates` → `git pull --ff-only origin feature/blazux-phase6-runtime-gates` → `bash scripts/p2-batch-cpu-container.sh --execute`. 이 새 스크립트 자체는 **DGX_NOT_RUN/CI_NOT_RUN**. 컨테이너가 Python 의존성을 갖추지 못했거나 Torch CUDA가 가시적이면 FAIL-CLOSED.
- 실제 GPU H2D/cuda graph/TTFT/TPS, MTP real head/acceptance, numeric first-divergence **미검증**. strict 1e-4 / P1_RELEASE_BLOCKED 유지.


## 2026-11-02 DGX 첫 Docker CPU 시도 실패 — 테스트 패키지 충돌 수정

- **DGX 실측 실행 HEAD** `51134f2ecd48b0a13496075c402f3edda255e47e`. Source preflight PASS, pinned image 내 NumPy **2.2.6**, PyTorch **2.13.0+cu130** 확인. 하지만 6개 모듈 모두 `ModuleNotFoundError: No module named 'tests.test_p2_...'`로 `_FailedTest`, 총 **Ran 6 tests / FAILED(errors=6)**. 실 40개 기능 시험 **NOT_RUN**, PLE correctness 미판정. 사후 원본 불변 검사는 스크립트 실행 경로상 실패 차단 전에 정상 수행되었으나 로그에는 원본 신원 값 출력 없음. GPU/API 사용 없음.
- **원인:** 저장소의 `tests/`는 `__init__.py`가 없는 namespace directory였고, 고정 vLLM 이미지에서 다른 distribution의 regular `tests` 패키지가 모듈 이름을 가로채는 import-resolution 충돌. `tests.test_p2_numeric_dgx_prepare` 내부에서도 `from tests.test_p2_numeric_sampler_witness import fixture`를 사용하므로 단순 loader 이름 변경은 불완전.
- **코드 수정:** `tests/__init__.py`로 저장소 내부 `tests`를 regular package로 만들고, 1회성 Docker runner에서 import된 `tests.__file__`이 정확히 `/p2/tests/__init__.py`인지 확인. 잘못된 패키지면 `P2_TEST_PACKAGE_ORIGIN_MISMATCH`로 차단, 정상이면 `P2_TEST_PACKAGE_LOCAL_VERIFIED`. 독립적인 site-packages collision 회귀시험을 별도로 추가. 기존 40-case 선택 목록과 0 SKIP 원칙, Docker ID/StartedAt와 resource boundary는 유지.
- 다음 DGX는 개발 브랜치 `git pull --ff-only` 후 `bash scripts/p2-batch-cpu-container.sh --execute` **한 번**으로 확인. 이 수정 이후 Docker **DGX_NOT_RUN**, CI_NOT_RUN. 실제 기능/수치/GPU 출시는 이전처럼 BLOCKED.
