# P2 — 새 대화 작업 인수인계 (2026-11-02)

## 2026-11-02 P2 3기능 Stage 실제 19/19 PASS + ID 파일 생성기

- **사용자 DGX `d6eead92956961b48b3ec711c02c18a1276dba6d`**: `git pull --ff-only` 성공, source/PLE SHA preflight PASS, `tests.test_p2_functional_bundle` + `tests.test_p2_mtp_candidate_overlay` **19/19 PASS**, `--stage-mtp` 실행으로 원본 신원 불변 확인. 개인 `/tmp/p2-functional-bundle-qzvkz12s`에 실제 Sampler/PLE/MTP 3-COPY source Stage 생성; MTP candidate SHA `c6fd9daa8b9ebc07bf12af20f4b110897b470a686d4e1fba46bae2b26d51db40`. Docker build/GPU/API 미실행, 기능 opt-in OFF, P1 release BLOCKED.
- **이번 신규 코드** `src/p2_mtp_vocab_artifact.py`: 실제 pre-tokenized aggregate token-count JSON과 동일 로컬 tokenizer.json의 SHA 일치 검증, added/special/0..255 ID 보존, deterministic 65536개 int32 ID 선택, **NumPy v1.0 .npy**와 SHA/fingerprint/coverage receipt를 새 `/tmp/p2-draft-vocab-*/` 디렉터리에만 안전 생성. 데이터 없으면 파일 생성 불가; 현재 **실제 코퍼스 미제공, 운영용 어휘 .npy NOT_CREATED**. 문서 [P2 자산 가이드](P2-DRAFT-VOCAB-ASSET-20261102.md). 신규 코드 DGX_NOT_RUN/CI_NOT_RUN.
- **단일 명령** `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 이후 `bash scripts/p2-vocab-artifact-dgx.sh --check`. 실제 집계 counts/tokenizer 파일이 준비된 경우만 `--build /path/counts.json /path/tokenizer.json`. Docker/GPU/API/모델 가중치/운영 서비스 미변경.
- Numeric 최초 strict `1e-4` 문제와 full-state physical reuse 미해결, MTP 실제 CPU logits ABI만 검증. 실제 native GPU MTP2 acceptance/PLE H2D, logits 병합 동등성은 별도 승인 필요.


## 2026-11-02 DGX MTP BF16 CPU 7/7 PASS → 실제 Preview 축소 Draft logits 후보 구현

- **사용자 DGX 확정 `9e3d9e656ec0fc5825cf75a8791e4c4df4b024d4`**: Source preflight PASS, host import/UID 4/4 PASS, pinned ABI AST 6/6 PASS, installed SHA 3/3 exact, 1회성 runc CPU `P2_MTP_HEAD_CPU_7_OF_7_PASS_NO_SKIPS`, 원본 동일 ID/image/StartedAt, GPU/API NO. CPU Head BF16 selected rows, 독립 스토리지, local→full 토큰 매핑, synthetic logits equivalence 입증. 설치 MTP `self.lm_head/self.logits_processor` 참조 확인, 그러나 Head sharing/loader/rejection runtime 미검증.
- **새 기능 코드** `src/p2_mtp_candidate_overlay.py`: 정확한 설치 MTP SHA `d1ee05d4...` 및 `compute_logits` AST SHA `83eb59ba...`에 고정한 **후보 전용 default-OFF** source transform. 비활성 시 기존 `compute_logits` 그대로. opt-in `VLLM_P2_DRAFT_VOCAB` 및 별도 **required SHA256**가 모두 설정돼야 시작; 기존 full BF16 `self.lm_head`의 65536행을 독립 Tensor로 복사, reduced GEMV 결과를 전체 248320 logits에 scatter, 나머지 ID는 `-inf`. Target Head·31 MTP tensors·rejection/proposer 소스는 변경하지 않는다. Runtime GPU/torch.compile/Graph·확률정합성은 아직 NOT_RUN.
- **단일 통합 후보** `src/p2_functional_bundle.py`와 `scripts/p2-functional-bundle-dgx.sh --stage-mtp`: 이전 성공한 Numeric Sampler witness·BF16 PLE source Stage에 **정확히 세 번째 MTP patched source만 추가**. 별도 개인 /tmp Stage, 고정 이미지 FROM, 3 COPY, 3 opt-in flags default OFF, SHA/원본 신원 검사. Docker build/run/exec/stop/start/GPU/API 모두 없음. `--stage`의 역사적 2-COPY 경로 그대로 보존.
- **어휘 선정 CPU 함수** `src/p2_mtp_vocab_selection.py`: 빈도 상위→ID 순 보충, special/added/byte fallback IDs 필수 보존, 결정적 fingerprint/coverage; 실제 한국어·다국어 corpus/Tokenizer 입력 **미수령**, 진짜 65536 `.npy` 파일 **NOT_CREATED**. stage는 IDs 파일 없이 안전하게 생성하고, 실제 candidate OPT-IN 실행은 누락/잘못된 SHA/파일/구성에 대해 fail-closed.
- **DGX 다음 한 번의 작업**: `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 후 `bash scripts/p2-functional-bundle-dgx.sh --stage-mtp`. 새 소스·회귀 시험과 private Stage 작성까지만. 이 새 코드 **DGX_NOT_RUN/CI_NOT_RUN**; 다음 GPU inference/release 승인 아니며 Numeric strict `1e-4` root cause OPEN 및 P1 RELEASE_BLOCKED 유지.


## 2026-11-02 P2 8/8 공동 Stage 실증 + MTP Draft Head CPU 기능 신설

- **DGX 실측 `78f1104b5652dcc78de701e8008e93a2b7cf9181`**: `tests.test_p2_functional_bundle` **8/8 PASS**; `P2_NUMERIC_PLE_CANDIDATE_SOURCE_STAGED_NOT_BUILT` 및 `P2_BUNDLE_SOURCE_COMPLETE`. 실제 private Stage `/tmp/p2-functional-bundle-x8kmxyiv` 내 정확한 Sampler SHA witness와 PLE Unique-H2D 소스 및 두-COPY Dockerfile. `candidate_build_or_gpu_or_api_executed=false`; 원본 그대로.
- **확정된 Preview 소스 SHA**: MTP `mtp.py` **`d1ee05d4...`**, target `model.py` **`e74a0bf9...`**, speculative `eagle.py` **`b2b1f7d1...`**; `Qwen3_8FlashNextMultiTokenPredictor` 및 `Qwen3_8FlashNextMTP`의 `__init__/forward/load_weights`와 후자의 `compute_logits` 확인. `qwen4_exp.py` 누락은 기능 부재 증거 아님. Header/target sharing/acceptance는 아직 OPEN.
- **이번 신규 기능** `src/p2_mtp_head_cpu.py`: BF16 Draft Head 고유 행의 **독립 CPU tensor copy**, `248320→65536` 사전 검증, Draft local ID→full tokenizer ID CPU remap, full Head 선택 logits vs reduced logits CPU oracle. **실 Head/loader/rejection 통합·실모델 변경 없음**. `src/p2_mtp_abi_contract.py`는 사용자가 실측한 위 3개 SHA를 exact PIN으로 강제하고 AST 속성·메서드 surface만 기록. AST 일치는 runtime ABI PASS가 아니다.
- **DGX 일괄 명령** `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 후 `bash scripts/p2-mtp-head-dgx.sh --execute`. 호스트 stdlib ABI 6건, 고정 설치 소스 read-only inspect/cp, pinned 1회성 CPU Docker에서 **새 MTP Head 7건만** 검증 (기존 40건 재실행 안 함). 원본 컨테이너/이미지/시작시각/모델/GPU/API 불변. **새 코드 DGX_NOT_RUN/CI_NOT_RUN**. 상세 [MTP Head 정본](P2-MTP-HEAD-ABI-20261102.md).
- 전체 출시 기준 strict `1e-4` 그대로 FAIL/OPEN, P1 RELEASE_BLOCKED, P2 GPU 후보 NOT_RUN. 허가 없이 build/실서버/계측 OFF→ON 금지.


## 2026-11-02 P2 실제 DGX CPU 40/40 PASS 및 Numeric+PLE 후보 소스 통합

- **사용자 제공 실제 DGX 영수증**: 통합 소스 `798575ed34acadb9eb83f004ce76ffc3bf2a2ac4`; Git pull fast-forward, Source preflight PASS, 호스트 import/UID 회귀시험 **4/4 PASS**. 기존 고정 이미지의 단일 disposable CPU `runc --network=none --read-only`에서 NumPy **2.2.6**, Torch **2.13.0+cu130**, P2 기능 시험 **40/40 PASS (SKIP 0)**, `P2_BATCH_ISOLATED_CPU_40_OF_40_PASS_NO_SKIPS`, `P2_BATCH_DGX_CPU_COMPLETE_HEAD=798575e... ORIGINAL_UNCHANGED_NO_GPU_API`. CPU PLE byte-exact 확인; GPU/실서버 결과 아님. 기존 두 실패 원인 테스트 package 충돌·UID 접근 거부는 해결.
- **다음 기능 변경**: `src/p2_functional_bundle.py`와 `scripts/p2-functional-bundle-dgx.sh`를 통해 pinned installed Sampler SHA 고정 numeric witness + 최신 BF16 PLE unique-only H2D 모듈을 동일한 **후보 전용 두-COPY Dockerfile**로 결합. 두 환경 변수 OFF; **Stage 생성만 가능, Docker build/run/GPU/API/원본 변경 없음**. 4개 MTP 관련 installed-source 경로의 SHA/클래스·로더 메서드만 읽기 전용 조회, 누락 경로는 NOT_CERTIFIED. Token ID 65,536/248,320 계약 CPU PASS는 유지하지만 Draft Head tensor slicing/loader/rejection runtime 연결은 아직 BLOCKED.
- **DGX 단일 후속 호출**: `cd ~/Workspace/llm/blazux-phase6-gates` → `git pull --ff-only origin feature/blazux-phase6-runtime-gates` → `bash scripts/p2-functional-bundle-dgx.sh --stage`. 새로운 8개 소스 회귀시험과 source/manifest guard 후 `docker inspect` 및 `docker cp` 읽기 전용 접근, private /tmp에 Sampler/PLE/Dockerfile 작성. 최종 태그 `P2_BUNDLE_SOURCE_COMPLETE ... NO_BUILD_NO_GPU_NO_API`. 이 새 기능 코드는 **DGX_NOT_RUN/CI_NOT_RUN**이며 CPU 40/40 결과를 새 코드 SHA로 소급하지 않음.
- **공통 출시 차단 불변**: strict `1e-4` numeric root cause OPEN, full-state 재사용 미입증, P1 RELEASE_BLOCKED, P2 실제 GPU/H2D·MTP Draft Head 미검증, vLLM 0.32 Track B 및 P3 별도 대기. [P2 묶음 Runbook](P2-BATCH-IMPLEMENTATION-20261102.md).


## 2026-11-02 P2 CPU sandbox 파일 권한 진단 및 수정

- DGX HEAD `b4a643d0cfb0d9f093858ad200845d384b5223d6`: 새 패키지 경로 host 2/2 PASS, container `P2_TEST_PACKAGE_LOCAL_VERIFIED` PASS, 그러나 `/p2/src/p1_preview_qsa_exact_topk.py` import `PermissionError [Errno 13]`. 테스트 40개는 로딩 단계에서 중지, `P2_BATCH_CPU_CONTAINER_BLOCKED`. 그 시점 container `--user=65534:65534`; 컨테이너 NumPy·Torch 설치 자체는 앞선 DGX에서 확인됐음.
- 현재 GitHub 패치에서 Docker UID/GID를 현재 DGX 비root 사용자 `id -u/id -g`로 바꾸고 root 거부·호스트 읽기 권한 사전확인·격리 제약 불변. `tests.test_p2_runner_import_resolution`에 두 가지 host 단위시험 추가. 새 GitHub 패치 `DGX_NOT_RUN`, 40 PASS 주장 금지.
- 실제 DGX에서 `git pull --ff-only` 후 `bash scripts/p2-batch-cpu-container.sh --execute` 한 번 수행. 다른 GPU/API/운영 실험 승인과 구별; Numeric 원인 OPEN, P1 release BLOCKED.


## 2026-11-02 P2 CPU container 테스트 로더 실패 수정

- DGX source `51134f2ecd48b0a13496075c402f3edda255e47e`: pinned image 내 NumPy 2.2.6/PyTorch 2.13.0+cu130 존재하나 `tests.test_p2_*` import 6건 실패, **Ran 6 / FAILED(errors=6)**. 40개 테스트는 시작되지 않았으며 40 PASS가 아님. 원본/GPU/API 변화 증거 없음.
- 저장소 `tests/__init__.py` 부재와 이미지 내부의 타 `tests` 패키지 충돌이 원인. `tests/__init__.py` 추가 및 단일 Docker runner에서 `tests.__file__ == /p2/tests/__init__.py` 검사, 서드파티 패키지 섀도잉 회귀시험 추가. 새 코드 DGX 미실행. `git pull --ff-only` 후 `bash scripts/p2-batch-cpu-container.sh --execute` 재시도 시 40개/skip0 아니면 차단.
- 수치 원인 OPEN, MTP 실제 head 연동 미완료, PLE GPU/실제 H2D 성능 미확인, P1 release BLOCKED. 상세 [P2 묶음 정본](P2-BATCH-IMPLEMENTATION-20261102.md).


## 2026-11-02 DGX P2 batch CPU 40개 중 4 SKIP — Docker 일회성 시험

- **실 DGX 소스** `c648d885c9e26d1c25ad40d8cf16449f94593f72`, AST PASS / `40 tests OK (skipped=4)` (**36 PASS, PLE 4 SKIP**). 호스트 NumPy/PyTorch 미설치, PLE CPU byte-exact까지는 확인되지 않았음.
- 신규 `scripts/p2-batch-cpu-container.sh --execute`를 기존 원본 이미지 digest의 **1회성 CPU-only runc (2CPU/2GiB, read-only repo, network=none, GPU void)**로 준비. 원본 컨테이너 ID/StartedAt/이미지 전후 확인, 명시적 실행 플래그, 모든 40건 PASS/skip0 필수. `git pull --ff-only` 후 **한 번 실행**. 운영·모델·가중치·GPU/API 부하 없음. 이 신규 스크립트 DGX_NOT_RUN, 이전 36 PASS+4 SKIP을 40 PASS로 승격하지 않음.
- P2 실제 기능 code 및 의의는 [P2-BATCH-IMPLEMENTATION-20261102.md](P2-BATCH-IMPLEMENTATION-20261102.md). Numeric root cause OPEN, PLE GPU NOT_RUN, reduced MTP 실제 Head ABI/acceptance 미확인, 출시 차단 불변.


## 2026-11-02 P2 Numeric / MTP / PLE 묶음 구현 (현재 과제)

- 사용자 요청에 따라 비핵심 활동 중단. **실제 기능 코드·CPU 시험·DGX 단일 명령**을 하나의 PR로 묶어 진행. [P2 묶음 세부사항](P2-BATCH-IMPLEMENTATION-20261102.md).
- **PLE 구현**: `src/vllm_ple_mmap.py` BF16 전용 `VLLM_PLE_UNIQUE_H2D=1` opt-in은 고유 행만 H2D 후 device `index_select`로 원래 N행 순서를 복원. 빈 행 처리 포함. 기본값 OFF / FP8 무영향. P1 pinned builder SHA는 유지하여 이전 이미지를 자동 재빌드하지 않음. 실제 GPU H2D 완료 및 TTFT/TPS는 미측정.
- **MTP CPU 계약**: `src/p2_mtp_draft_vocab.py`의 65,536/248,320 index mapping, special token 및 Head shape 검증. 실제 Head 로더/weight slicing/rejection acceptance와 연결은 설치된 Preview ABI 확인 전 미완료.
- **Numeric offline**: `src/p2_numeric_report.py`가 1-token witness와 API 값의 대응 판정, strict `1e-4` 불변. GPU sample/원인 수정 OPEN.
- **DGX** `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 후 `bash scripts/p2-batch-dgx.sh` 1회로 preflight+targeted numeric/MTP/PLE CPU tests+AST/쉘을 묶음 실행. NumPy/Torch 미설치 시 PLE 시험은 skipped(미검증). **새 GitHub HEAD는 아직 DGX_NOT_RUN, Docker/GPU/API/CI NOT_RUN**.
- P1 FUNCTIONAL BOUNDED_PASS, RELEASE_BLOCKED, full state reuse 미입증, P2 NUMERIC ROOT_CAUSE_OPEN 그대로. 새 P2 candidate image/run을 자동 시작하지 않음.


## 2026-11-02 실제 DGX 참조 감사 결과 (최신)

- Git HEAD `3dccb50e6f9528fea8a7b4cd799b2e2fdcfe3d09`, 실제 DGX CPU suite **15/15 PASS**; Docker mount inventory AVAILABLE, `--references` scoped scan **1,119개 파일 COMPLETE**. Phase 1~5 문자열 참조 수는 각각 **9·10·7·9·19** (Phase5 초과 히트 생략). **폴더 이동/삭제 0**.
- GitHub에서 확인한 phase2/3/4/5 및 phase5-mamba Shell의 매치 문자열은 독립 checkout의 **브랜치 이름 지정**이며, 작업 디렉터리는 스크립트 상대경로 기반이다. 따라서 이 매치는 실제 외부 디렉터리 의존성을 단독 입증하지 못한다. 역사적 문서·테스트 fixture의 Phase 명칭도 구분 필요. 별도 외부 프로세스·cron/systemd·절대 경로 동작은 확인되지 않았으므로 보관 후보 확정/실행은 아직 BLOCKED.
- 상세 증거와 제한 및 다음 안전 절차: [P2-WORKSPACE-CLEANUP-RUNBOOK.md](P2-WORKSPACE-CLEANUP-RUNBOOK.md). **신규 GPU/운영/숫자 수정 없음**, P2 numeric root cause OPEN, strict 1e-4 및 P1 release BLOCKED 유지.


## 2026-11-02 DGX Workspace 15개 폴더 실측과 참조 감사

- 실제 DGX source HEAD `384eaa12e30b1dfd4605050fc11be3f7f79540e4`에서 `p2-workspace-inventory.sh`: docker=AVAILABLE, 보호 5/추가 확인 5/Phase1~5 보관 검토 후보 5, 이동·삭제 0. `open-webui` Docker bind overlap, spark-stack/spark-vllm-docker/stack 변경·미추적 파일 확인.
- Phase1~5는 **미사용으로 입증된 것이 아님**. 기존 Git 검사 실패시 REVIEW 표기 가능성을 fail-closed로 수정하고, 경로 문자열을 제한적으로 확인하는 `--references` 도입. DGX에서 개발 브랜치 `git pull --ff-only` 후 `bash scripts/p2-workspace-inventory.sh --references`; 자세한 정본은 [Workspace Runbook](P2-WORKSPACE-CLEANUP-RUNBOOK.md).
- 신규 reference audit는 **DGX_NOT_RUN**, 기존 numeric DGX `3e4492c` CPU 24/24·source stage PASS와 구별. P2 numeric root cause OPEN, strict `1e-4` 출시 차단 불변. 아카이브 이동·삭제·운영/GPU/HTTP 미실행.


## 2026-11-02 사용자 DGX P2 실기 receipt 및 Workspace 정리 현안

- **실제 사용자 DGX 실행:** `~/Workspace/llm/blazux-phase6-gates`, personal Fork origin, `feature/blazux-phase6-runtime-gates`, `git pull --ff-only` fast-forward `50fc65b..3e4492c` 완료. **DGX-tested source HEAD `3e4492c73ce95f8129e99b1f21f4a67252e8891f`.** `bash scripts/p2-numeric-dgx.sh --check`와 `--stage` 두 모드 각각 targeted CPU unit tests **24/24 PASS**, source preflight PASS.
- **read-only 실기 stage PASS:** 설치 Preview Sampler SHA256 `f95805b2c6d06218c724826aa5f881a606e8d0a534a566aee7c85948520dd216`, patched SHA256 `a62b7cd7f7eb637fdee7d8dd1e51b1bc47c3931bb1174f4f22280db28ccaead4`, stage `/tmp/p2-numeric-witness-_w30fuax`, 원본 동일 ID/StartedAt/이미지 식별 및 env default OFF. **Build/GPU/API NOT_RUN.** Numeric root cause OPEN, strict `1e-4` 및 P1 RELEASE_BLOCKED 변함없음.
- 사용자 `~/Workspace/llm`에 예전 `blazux-phase1-*`~`phase5-*`, bench-results, llama-benchy 2종, qwen38-orca-uncensored, YSLAB 운영 관련 폴더 존재. 현재 목록만으로 어떤 디렉터리도 삭제/이동 안전성 입증 못함. [Read-only workspace inventory](P2-WORKSPACE-CLEANUP-RUNBOOK.md) `bash scripts/p2-workspace-inventory.sh`를 DGX Git pull로 실행하도록 제공. **단계별 신규 checkout 증식 중단**, 운영 원본/마운트/모델/결과 보호, 정리는 별도 증거·승인 필요.
- 이 문서 변경 시 GitHub 새로운 SHA는 **코드가 DGX-tested 되었다는 뜻이 아니며**, 위 영수증은 `3e4492c`로 고정.


## 2026-11-02 P2 DGX 실행 위임 — Git pull 후 단일 실행 명령

- **실행 정본:** [P2-DGX-GIT-PULL-RUNBOOK.md](P2-DGX-GIT-PULL-RUNBOOK.md). 기능 코드·소스 확인·CPU 검사·수동 DGX 절차는 GitHub에 커밋된 `bash scripts/p2-numeric-dgx.sh --check` 또는 `--stage`로 실행한다. P2 Fork checkout에서 `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 후 호출한다. 기존 `--strict`는 P2 브랜치를 허용하지 않으므로 개발 스크립트에서 사용하지 않는다.

- `--check`: P2 전용 기존 preflight (정확 HEAD/개인 Fork/origin/clean manifest) + targeted CPU 단위시험. **원본 Docker를 조회하지 않음.** `--stage`: 동일 검사 후 원본 동일-ID·image/StartedAt 및 설치 Sampler source SHA를 read-only Docker inspect/cp로 확인하고, 새 개인 /tmp 디렉터리에 **기본 OFF** 1-COPY candidate-only witness source/Dockerfile을 생성. **Docker build/run/exec/stop/start/HTTP/GPU 전혀 수행하지 않음.** SHA/ID drift에는 exit 2.

- 이 단계의 생성물은 P2 소스 준비이며 실제 원인 분석의 숫자 증거 또는 P2 numeric PASS가 아니다. 신규 DGX 실행 로그, 실제 source HEAD, CPU PASS, 신원 확인 결과를 받기 전 **DGX_NOT_RUN**으로 유지한다. 기존 마지막 DGX-tested source는 `50fc65b65d10b36804c65e8a48d06d9bf3abecfe`, strict `1e-4`와 출시 차단 불변. GPU/API/운영 서비스 정비창은 승인하지 않는다.

## 2026-11-02 P2 후속: 선택 토큰 단위 Sampler 경계 계측 준비

- **실제 P2 코드 변화:** `src/p2_numeric_sampler_witness.py`는 기존 Preview 설치본 `vllm/v1/sample/sampler.py`의 **고정 SHA256 `f95805b2c6d06218c724826aa5f881a606e8d0a534a566aee7c85948520dd216`**과 정확한 `Sampler.forward` anchor 3개를 만족할 때만 패치를 생성하는 SOURCE-ONLY 변환이다. `Sampler.compute_logprobs(logits)` 직후 Raw logits/전체 logprobs SHA, `sampled.long()` 직후 선택 token ID SHA256과 **단일 logprob 스칼라**를 함께 수집한다. processed override·다른 모드/shape·SHA drift는 skip/block. 기본 환경 `VLLM_P2_NUMERIC_WITNESS=0`, 후보 전용 `/tmp/p2-numeric-witness.jsonl`, 최대 8 event/process. 원본/P1 pin 이미지·GPU/운영 미변경.
- `src/p2_numeric_boundary.py::classify_witness()`는 동일 Token ID 해시, 선택 logprob와 API 첫 토큰 logprob의 **1e-6 이내 값 대응**, 이벤트 순서·worker PID, **별도로 검증된 Prefix OFF/MTP OFF/직렬 단일 활성 요청**이 모두 충족될 때만 Raw logits → log_softmax/pre-gather → post-Sampler/API **최초 관측 텐서 차이**를 분류한다. `1e-6`은 오직 witness↔API 대응 확인용이며 **strict release `1e-4`를 대체하지 않는다**. 값 불일치/계측 누락/ABI drift는 FAIL-CLOSED, root_cause_fixed=false.
- **소스 근거의 한계:** 공개 vLLM v0.11.1 Sampler에서는 `logits.log_softmax(dim=-1, dtype=torch.float32)`와 `gather_logprobs()`의 `logprobs.gather(-1, token_ids)`가 확인되나, 커스텀 설치 Preview의 전체 Sampler/Engine/API 호출 순서와 활성 경로는 미입증. 후보에서 pinned SHA/anchor와 실제 활성 row→API 관계를 확인해야 함. 텐서 SHA 변화는 선택 토큰 logprob 변화의 인과 크기를 단독 증명하지 못함.
- **검증 범위:** 별도 Python stdlib synthetic targeted unittest **17/17 PASS**, py_compile PASS. 4개 GitHub 코드/테스트 Blob SHA는 로컬 시험 파일의 Git blob SHA와 일치하게 생성. **DGX/CI/GPU/HTTP NOT_RUN**. P1 BOUNDED_PASS, RELEASE_BLOCKED, `full_state_reuse_verified=false` 유지.
- **남은 차단:** 정확한 설치 Source/ABI 확인 후 **별도 사용자 승인 하에서만** 격리 MTP-OFF 후보 첫 토큰 직렬 요청의 소량 경계 관측. GPU 동기화 계측은 실행 타이밍을 바꿀 수 있으므로 비계측 운영 경로의 결정성 입증 아님. 원인 수정 및 strict 실측 미완료. 원본 stop/HTTP inference/CI 무승인 실행 금지.

## 2026-11-02 P2 numeric 첫 소스 조사 및 오프라인 코드 (신규)

- GitHub 개발 브랜치 feature/p2-numeric-first-boundary-20261102; P1과 main은 보호. 첫 실수치 차이의 계산 경계는 아직 미확정이고 P1 최종 strict 및 출시 BLOCKED 유지.
- Source: src/p1_numeric_source_trace.py 는 AST 위치만 보고하고 runtime call order는 검증하지 못함. src/p1_numeric_sampler_overlay.py의 고정된 Sampler.forward raw_logprobs 분기는 logits 입력과 compute_logprobs 결과의 두 해시를 캡처할 수 있지만, MTP2의 RejectionSampler 경로는 우회될 수 있다. 실제 2026-11-02 MTP2 rejection tap 0건은 boundary 증거가 아니다.
- 단일 반증 가설: 동등한 첫 토큰 raw logits 바이트가 일치하더라도 Sampler.compute_logprobs 또는 후단 gather/API 과정에서 strict logprob 불일치가 발생할 수 있다. 반증 조건: 동일 요청 첫 토큰에서 raw logits 해시가 먼저 변하면 이 가설의 post-logits-only 형태는 기각. 반대로 logits/normalized logprobs 모두 일치하고 API만 변하면 후단 출력 경로에 한정. 해시 변화는 크기·인과 관계를 증명하지 않는다.
- 최소 구현: src/p2_numeric_boundary.py 와 tests/test_p2_numeric_boundary.py 는 기존 P1 Sampler 계측 digest를 조건부로 분류하는 offline oracle. 정확한 prefix OFF, MTP OFF, 단일 활성 요청, first-row-to-API 매핑 증거가 없으면 INCONCLUSIVE로 유지. strict 1e-4 유지. 로컬 순수 Python synthetic 단위시험 8/8 PASS (DGX, CI, GPU, API NOT_RUN). 기존 모델/이미지/원본 tap 변경 없음.
- 다음 막힘: 원본 Preview Sampler->engine logprobs->OpenAI 반환의 정확한 실행/row alignment가 현재 GitHub 소스만으로 검증되지 않음. pinned 컨테이너 source 및 승인된 단일 no-MTP 후보에 대한 계측 경계의 별도 증거 없이는 root cause FIXED나 numeric PASS 불가. 새로운 GPU 승인 자동 확장 금지.


> **P2_NUMERIC_OFFLINE_STARTED / ROOT_CAUSE_OPEN / GPU_NOT_RUN.** P1 이력은 정본을 참조한다. 위 P2 첫 소스 조사와 CPU-only 분류기는 실행했으나 설치된 Preview runtime의 첫 오차 위치, 수치 수정 및 운영 검증은 아직 미완료. 이후 세션은 GitHub HEAD·PR·CI를 새로 조회하고 P2 활성 작업만 진행한다.

## 우선 읽을 정본

1. [SESSION-HANDOFF-PROMPT.md](SESSION-HANDOFF-PROMPT.md) — 상시 확정·보호·GitHub 사용 규칙. 특히 **2026-11-02 P2 전환** 항목을 오래된 P1 작업 지시보다 우선.
2. [P1 최종 DGX 증거 및 release blocker](BLAZUX-PHASE6-RESULTS.md), [P1 종료 인수인계](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md) — 재실험 방지용 근거.
3. [P1/P2/P3 8개 목표 정본](BLAZUX-UPSTREAM-COMPARISON-20261029.md), [vLLM 0.32 Track A/B 전략](BLAZUX-VLLM032-ADOPTION-PLAN.md).
4. [실제 기능 진전 우선·불필요 Gate 증식 금지](BLAZUX-DELIVERY-DRIFT-POSTMORTEM-AND-GUARDRAILS-20261028.md), [동일 ID 서비스 보호·복구](P1-PREFIX-LIVE-SERVICE-WINDOW-20261029.md).
5. [기존 단일 토큰 원본 수치](P1-ORIGINAL-NUMERIC-BASELINE.md), [QSA/No-MTP 원인 분리](P1-QSA-ONLY-NUMERIC-ISOLATION.md), [통합 실서버 결과](P1-INTEGRATED-EVIDENCE-20261031.md).

**단계 이름 주의:** 이 P2는 **8개 기능 로드맵상의 Priority 2**이며 10월 27일 예전 `BLAZUX-PHASE2` CPU Gate와 같은 뜻이 아니다.

## 종료점과 실제 근거 (이 수치의 상세는 결과 장부 참조)

- 개인 fork: `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`, P1 source/문서 기능 브랜치 `feature/blazux-phase6-runtime-gates`. **P2 문서 작업 이전** feature HEAD `185ed9d4a3241d69ae6bc876cee66a8800aa8d90`. P2 문서 PR 병합 후 feature SHA가 변경되므로 최신값으로 다시 조회.
- 실제 **DGX-tested source SHA** `50fc65b65d10b36804c65e8a48d06d9bf3abecfe`: source 327/327 PASS, targeted CPU 20/20 PASS, Tool call→result→final 왕복 PASS, BF16 PLE calls=1 / forward_calls=1 / rows=131072, Prefix HIT `[0,6400,6400,6400]`, MTP accepted +400, 선택 상태 Cold/HIT SHA 12/12 match. `P1_FUNCTIONAL_VERIFIED=BOUNDED_PASS`.
- 독립 **출시 차단 유지:** `P1_RELEASE_BLOCKED=TRUE`, `P1_FINAL_PASS=FALSE`, `DEPLOYED=FALSE`, `full_state_reuse_verified=false`, `strict_numeric_release_pass=false`, `P2_NUMERIC_STABILITY_OPEN=TRUE`. Strict per-token logprob absolute tolerance **1e-4**를 완화하지 않았으며 Prefix ON / 원본 Prefix OFF / MTP OFF / 1-token에서도 이미 실패 증거 존재. 첫 오차 발생 경로 불명.
- 마지막 사용자 DGX 영수증: 운영 원본 full Docker container ID `3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45`, 원본 image SHA `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`, port 8000. 동일 ID running/이미지 불변/후보 삭제/`/health`·`/v1/models` 모두 PASS. **이는 당시 영수증이지 이후 실시간 상태 보증 아님**.
- DGX 소스 checkout `~/Workspace/llm/blazux-phase6-gates`. 기존 운영 YSLAB checkout, pinned Stage/모델, HF cache/views RO 마운트는 영구 안전 규칙에 따르며 P2 준비라고 임의 교체/정지하지 않는다.

## P2 미완료 과제와 실행 순서

| 권고 순위 | 과제 / 완료되지 않은 기술 | 다음 대화의 구체적 첫 행동 | 완료 판단 |
| --- | --- | --- | --- |
| **1** | **공통 숫자 비재현성 / 출시 차단 원인**: Prefix OFF / No-MTP / 짧은·긴 입력 및 max_tokens=1에서도 logprob 1e-4 실패; raw model forward/GDN·PLE/서빙 batching 대 logits→log-softmax→API 중 **최초 오차 위치 미확정** | 기존 `src/p1_numeric_source_trace.py`, `src/p1_original_numeric_baseline.py`, 이전 결과 장부, 실제 pinned Preview 모델의 logits/postprocessor 경로를 소스 기준으로 좁혀 **반증 가능한 1개 가설**을 세움. 가설에 필요한 최소 코드 수정/CPU 검증부터 처리 | 정확한 원인·수정 위치와 이후 승인된 동등조건 GPU strict 1e-4 검증 없이는 해결 아님 |
| **2** | **MTP Reduced Draft Vocabulary** (원래 P2-1): BF16 31 MTP tensor overlay와 MTP2 수락 동작은 기존 PASS, reduced draft vocab은 미적용 | blazux 고정 `patch_mtp_draft_vocab.py`의 65,536/248,320 draft 후보, Preview BF16 draft-head/target-head 공유·로더·ID mapping ABI 조사, 최소 overlay 검토 | token mapping/acceptance·다국어 정확성·실 decode speed 증거 필요 |
| **3** | **PLE Gather 최적화** (원래 P2-2): FAST_GATHER 기본 OFF/CPU byte-exact 있음; unique-only H2D, pinned stage, GPU inverse 미포팅 | `src/vllm_ple_mmap.py`의 실제 95.37GiB BF16 PLE gather·CPU→GPU 전송 위치, 원본 구현, CUDA graph boundary를 비교하고 실제 의미 있는 최소 패치 선정 | byte-exact + cold/warm·TTFT/TPS·GPU memory·H2D **완료**시간 실증. `device_copy_call_s`는 DMA 완료시간 아님 |
| **4** | **독립 vLLM 0.32 Track B** (원래 P2-3): Preview 운영 유지, 0.32 Orcarouter BF16 overlay 실포팅 NOT_RUN | 별도 계보/이미지에서 BF16 PLE constructor, 31 BF16 MTP tensor, 로더/quantization, Tool Parser, KV/Scheduler ABI 소스 비교. 기존 Track A와 파일·이미지 혼합 금지 | GPU/API/메모리/품질/성능 독립 검증 전 포팅 완료 주장 금지 |
| **5** | **전 계층 상태/copy 물리 감사(출시 연계)**: 선택 SHA 12/12 match이나 전체 GDN/PLE state restore/copy semantics 미입증 | 실제 post-write/post-copy 위치, GDN/PLE 모든 state, physical block identity와 시점에 대한 소스 검증 설계. P1 bounded 샘플 증거는 유지 | `full_state_reuse_verified=false` 유지; 실제 전체 상태 증명 전 출시 PASS 금지 |

P3 YaRN 500K/M-RoPE 및 Hybrid FP8은 이번 단계에 포함하지 않음. 과거 QSA A/B/C/B2, MTP on/off, Rejection tap zero, P1 Tool·PLE·HIT/MTP·선택 SHA 검사를 **새로운 원인과 해결 목표 없이 반복 금지**. 새 이미지/테스트 Gate/무의미한 자료 수집 증식도 금지.

## P2 새 대화에서의 실제 수행 절차

1. 연결된 GitHub 도구로 **최신** 영구 규칙·이 문서·Phase6 장부, 현재 개발 브랜치·`main`·PR·GitHub Actions·check-runs·status를 재조회한다. 기존 문서의 '현재' 문구는 상단 최신 P2 전환에 비해 과거이면 역사적 기록으로만 사용. GitHub 상태를 예전 메모리/로그로 대체 금지.
2. 먼저 수치 불일치 최초 경계를 좁힐 **pinned 실제 소스**를 확인하고, 가설 및 최소 범위 패치·반증 가능 테스트를 직접 작성한다. 필요하면 P1 checkpoint에서 분리된 별도 P2 feature branch를 만들되 기존 P1 feature 및 `main` history를 무단 변경하지 않는다.
3. 코딩에 필요한 `src/`, `tests/`, `scripts/` 및 영구 문서를 직접 편집·생성. 모든 변경은 `scripts/source-state-manifest.json`의 tracked source count/blob SHA/mode까지 정확히 갱신. 가능한 targeted CPU·소스 검증은 실행하고, 로컬에서 실행할 수 없으면 못했다고 명시. 기존 GPU·API 로그에서 보장되지 않은 PASS를 창작 금지.
4. 사용자의 **이번 2026-11-02 명시 위임**으로 GitHub 연결 도구의 commit, PR 생성, 실제 변경 diff 검토, GitHub review/CI 상태 확인, 지정된 **P2 개발 통합 브랜치로 merge**까지 직접 수행 가능. `main` merge·운영 적용·CI 리소스 소비는 포괄 승인에 포함되지 않는다. PR target/ref/HEAD SHA, 충돌, 리뷰, 요구 CI를 확인하고 검증 미충족·충돌 시 병합하지 않는다. **자동 도구 검토를 GitHub 공식 제3자 APPROVED review로 위장하지 않음**.
5. GitHub 접속 권한과 **DGX 제어 권한을 분리**한다. 운영 stop/start/exec/pause, 실제 GPU 모델 기동, HTTP 추론 부하, benchmark, 원본 이미지·모델·캐시·Stage 변경은 해당 위험/중단·exact ID 복구 범위에 대해 **사용자에게 별도 명시 승인받은 후**만 수행. 이전 P1 GPU window 승인은 소진. GPU 메모리 해제 목적 pause 사용 금지.
6. 결과는 `SOURCE_REVIEWED` / `IMPLEMENTED_OFFLINE` / `CPU_VERIFIED` / `GPU_VERIFIED` / `API_VERIFIED` / `DEPLOYED_VERIFIED` 중 증거에 맞는 상태만 표기. DGX tested SHA와 GitHub docs/source SHA를 구분해 장부 및 필요한 상시 문서에 최신 확정만 기록. P1 bounded PASS와 출시 BLOCKED를 혼동하지 않는다.

## 현재 대화에서만 전달하는 임시 규칙 및 GitHub 전환 전 스냅샷

- 이번 인수인계는 다음 대화에서 P2 **1순위 numeric root-cause**를 바로 착수하도록 돕는 문서 작업이다. 새 P2 code/GPU/CI/운영 작업은 **현재 대화에서 실행하지 않는다**.
- GitHub 2026-11-02 전환 전 관측: P1 feature HEAD **185ed9d4a3241d69ae6bc876cee66a8800aa8d90**, main HEAD **b0c7d9067c555dd43a31b49bca9be75664c06c97**. open PR **0**, 마지막 병합 PR **#7** (2026-10-29, base feature), Actions workflow run **0**, 이 feature commit check-runs **0**, statuses **0**. GitHub combined `pending`은 **검사가 없다는 뜻이지 CI PASS 아님**. 이번 문서 PR과 병합 이후 HEAD/PR 번호는 변하므로 반드시 재조회한다.
- 이 문서만으로 추가 임시 승인·변경 금지 규칙을 만들어내지 않는다. 현재 작업을 진행해 필요한 새 사실을 확인한 경우 관련 **상시 정본 먼저 갱신**하고 새 대화에는 짧게 링크만 잇는다.

