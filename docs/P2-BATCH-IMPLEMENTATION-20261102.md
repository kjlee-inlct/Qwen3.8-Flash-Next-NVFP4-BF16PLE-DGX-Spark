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

## 2026-11-02 DGX 두 번째 1회성 CPU 컨테이너 실행 — 비root UID 파일 접근 거부

- **실제 실행 HEAD `b4a643d0cfb0d9f093858ad200845d384b5223d6`:** Git fast-forward PASS, P2 source/manifest preflight PASS, host tests import guard **2/2 PASS**, pinned CPU-only disposable container launch. `P2_TEST_PACKAGE_LOCAL_VERIFIED` 확인 ⇒ 앞선 `tests` 충돌은 해결. 40-case `unittest.loadTestsFromNames`는 `/p2/src/p1_preview_qsa_exact_topk.py` import 시 **`PermissionError [Errno 13]`**으로 중단; `P2_BATCH_CPU_CONTAINER_BLOCKED` 반환. **40개 시험은 수행되지 않았으며 PASS 아님.**
- **가능성이 높은 근본 원인:** Runner `--user=65534:65534`가 호스트 체크아웃 내 제한된 모드(예: 0600)의 Python 소스를 읽지 못함. 정확한 호스트 파일 owner/mode는 로그에 출력되지 않았으므로 0600 자체는 추정이다. 호스트 Python은 동일 파일을 import하여 preflight를 통과함.
- **수정:** 컨테이너만 `--user "$HOST_UID:$HOST_GID"`로 실행(실제 DGX checkout을 사용하는 **호스트 비root 계정의 UID/GID**를 `id -u`/ `id -g`로 조회). 숫자 및 root(UID/GID 0)를 fail-closed로 차단하고, 문제 소스와 신규 PLE 시험 파일의 호스트 읽기 권한을 사전에 검증. **호스트 chmod/chown 금지**, 원본 모델/이미지·Docker 상태 변경 없음. Docker repo bind/rootfs read-only, network none, GPU void, nonroot, 2CPU/2GiB, 원본 동일 container ID/StartedAt 전후 확인 및 40/40 no-SKIP 원칙 불변.
- **다음 DGX 1회 명령:** `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 후 `bash scripts/p2-batch-cpu-container.sh --execute`. 새 runner는 **DGX_NOT_RUN**, 결과 미예측. 불가 시 증거를 기반으로 다음 실패 지점을 정확히 분리한다. Numeric root cause OPEN / strict 1e-4 / P1_RELEASE_BLOCKED 불변.

## 2026-11-02 P2 후속 — Numeric Sampler witness + PLE Unique-H2D 공동 후보

**실 DGX 성공 체크포인트**: 정확한 SHA `798575ed34acadb9eb83f004ce76ffc3bf2a2ac4`, 1회성 네트워크·GPU 차단 CPU container에서 **40 tests / 0 skip / OK**, host import/UID 4 tests PASS, original container unchanged. PLE BF16 byte-exact synthetic CPU는 검증 완료. 수치 strict 1e-4는 해소되지 않았음.

### 실제 기능 준비

- `src/p2_functional_bundle.py`는 현재 Fork HEAD/source manifest를 검증한 뒤 원본 고정 image tag가 원본 image ID를 가리키는지 read-only inspect한다. Sampler의 설치 SHA `f95805b2...`를 확인해 기존 `src/p2_numeric_sampler_witness.py`를 적용하고, `src/vllm_ple_mmap.py`에서 실제 Unique-H2D forward function 및 opt-in을 AST로 검증한다.
- 사용자 HOME의 active repository가 아니라 **새 개인 `/tmp/p2-functional-bundle-*/`** 안에 `sampler.py`, `vllm_ple_mmap.py`, 정확한 기존 원본 이미지 기반의 **2-COPY Dockerfile**만 쓴다. 파일 0600/디렉터리 0700. 원본 컨테이너 실행·이미지·시작 시각을 read-only 전후 비교. Numeric witness와 Unique-H2D는 **Dockerfile 기본 OFF**. 두 소스가 같은 GPU candidate에 존재하도록 연결하는 source feature이며 실제 `docker build`·로딩·실추론·H2D 측정은 **미실행/별도 승인**.
- MTP 경로들(`vllm/models/qwen3_8_flash_next/nvidia/{mtp,model}.py`, `vllm/models/qwen4_exp.py`, `vllm/v1/spec_decode/eagle.py`)을 **읽기 전용 Docker cp**로 찾되, 파일 누락은 이름/경로가 다를 수 있다는 뜻으로 취급한다. 발견된 소스는 SHA/선별 AST 메서드만 요약하며, 원문·모델 데이터 출력 또는 실제 draft head modification 없음. 이 triage로 65,536 축소 로더/ID remapping의 정확한 이식 범위를 다음 단계에서 결정한다.
- `scripts/p2-functional-bundle-dgx.sh --check`: 새 소스 단위시험과 전체 preflight만, **Docker 접근 없음**.
- `scripts/p2-functional-bundle-dgx.sh --stage`: 같은 preflight·회귀시험 뒤 기존 원본 **read-only `docker inspect`+`docker cp`**와 private source stage를 한 번에 실행. Docker build/run/exec/stop/start, API, GPU 불허.

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-functional-bundle-dgx.sh --stage
```

**주의:** P2 sampler witness의 선택 scalar↔API 대응은 실제 **MTP OFF·Prefix OFF·직렬 단일 요청 후보**에서만 진단. 원본 MTP2 활성 실행에서 해당 Sampler tap이 곧바로 활성화된다고 주장 금지. API 수치 비교와 raw logits 원인은 GPU 실관측 전 OPEN. 해당 `/tmp` Stage는 새 분리된 GPU 운영 정비창 승인이 아니며, P1 builder의 이전 PLE pin을 재작성하지 않는다. 이번 신규 소스/테스트는 DGX_NOT_RUN / GitHub CI_NOT_RUN.

## 2026-11-02 P2 MTP Head 다음 기능 작업

- DGX 공동 Numeric+PLE source stage **8/8 PASS**, pinned original unchanged, Docker **NOT_BUILT/GPU NOT_RUN**. 실제 Preview MTP/target/speculative source 3개 SHA 확인 (정확한 SHA/AST 계약 [별도 정본](P2-MTP-HEAD-ABI-20261102.md)).
- `src/p2_mtp_head_cpu.py`는 독립 BF16 Head 행 선택, 기존 65,536 ↔ 248,320 계약의 local→full ID CPU Tensor 변환, synthetic full-head 선택 logits 등가성을 제공한다. **actual MTP Draft Head weight 적용·loader/rejection integration은 미완료**.
- 설치 ABI 조사 `src/p2_mtp_abi_contract.py`는 정확한 SHA 3종 drift와 MTP 필수 2 class/method surface fail-closed. 출력은 함수·속성·SHA만; MTP actual loaded tensor or head ownership은 증명하지 않음. `qwen4_exp.py` missing is NOT_CERTIFIED.
- `scripts/p2-mtp-head-dgx.sh --execute`: Fork/branch/manifest and host stdlib audit, original ID/image/running/StartedAt, read-only installed code, 1회성 기존 immutable CPU runc image에서 신규 BF16 MTP 7/7 skip0. 고장난 경우 fail-closed. 기존 Numeric/PLE CPU 40/40 재실행하지 않음. 새 기능/CPU 결과는 DGX_NOT_RUN/CI_NOT_RUN.

