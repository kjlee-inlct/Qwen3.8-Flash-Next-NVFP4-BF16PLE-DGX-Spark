## 실증 체크포인트 2026-11-03 — 통합 후보 조립 완료, 런타임 미검증

- 실제 Orcarouter DGX `4c5710d4e5b3085ec5aae1354d1b9052537af2dc`: source preflight / 29 focused CPU tests PASS; actual pinned Sampler/PLE/MTP source SHA + Blazux IDs verified, `/tmp/p2-functional-bundle-ackw9piv`에 4-COPY candidate Dockerfile staged. **No build, no GPU, no HTTP/API, no model mutation.**
- P2 진행은 여기서 **소스/자산 준비 단계를 종료**한다. 다음 핵심 블로커는 `1e-4` strict numeric 첫 불일치 구간 관측. Prefix OFF·MTP OFF 원본에서도 발생했고 QSA-only로 해결되지 않음. 동일한 stock/QSA/MTP A/B를 증거 없이 반복 금지.
- 실제 GPU 실험은 **별도 명시 승인** 전까지 수행 불가. DGX 통합 메모리에서 운영 BF16 PLE 모델이 사용 중이므로, 새로운 GPU full model 동시 로드는 기본적으로 위험하다. 정비창 계획에서 resource footprint, isolated candidate port/namespace, original unchanged/recovery, timeout, abort, no raw model/prompt logging을 먼저 정한다. 수치 원인 수정 / 출시 승인 / operational deployment 모두 미완료.
- 29/29은 DGX-tested **old source SHA**에서만 유효. 본 기록 문서 커밋의 SHA는 테스트 없이 변경되어 PASS로 소급 금지.

## 2026-11-03 DGX 실제 Upstream Draft 호환성 증거 및 통합 GPU 후보 Stage 진전

- **사용자 DGX exact HEAD `e467607219d60fae40690258f98f1de9140063b1`:** source preflight PASS, 신규 8/8 unittest PASS, 실제 Orcarouter recipe tokenizer SHA `06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523`, config SHA `66e427c470fe580fe8c7b5725d857af23d8417e37fae62667ec698306a19987b`, declared 248077, special 21/added33 모두 upstream 65536 ID 포함, unallocated0. 원본 Blazux blob `2b94340a3ca0985a7494af369ac82536d61411de` 및 NPY SHA `6459e0fdc8df30e0c1d1f45be7c1b6bef0d68b0e73c073a82c52ea2a7f4b26d4` PASS. 실제 개인 `/tmp/p2-upstream-draft-ai00xvtw/ids.npy` 및 receipt 생성. **모델/GPU/API 미실행**, Native runtime acceptance·품질·strict numeric OPEN. 코퍼스 단계 종료.
- 후속 개발은 기존 `src/p2_functional_bundle.py` 및 `scripts/p2-functional-bundle-dgx.sh`에 **`--stage-mtp-upstream`** 모드를 추가해, exact SHA-pin Sampler witness + BF16 PLE Unique H2D + MTP compute_logits overlay + 위 upstream draft IDs를 **개인 `/tmp/p2-functional-bundle-*/`에 4-COPY Dockerfile로 함께 Stage**한다. 사용자가 이미 확인한 실제 recipe tokenizer/config ID를 Stage 시 재감사하고 SHA를 재검증하여 mismatch면 실패. Candidate 환경변수는 전부 기본 OFF, 내장 id는 `/opt/llm/p2-orcarouter-draft-65536.npy`에만 복사 예정이며 모델 head/원본 이미지는 아직 수정하지 않는다.
- 다음 **단일 DGX source-stage 명령**: `git pull --ff-only origin feature/blazux-phase6-runtime-gates` 후 `bash scripts/p2-functional-bundle-dgx.sh --stage-mtp-upstream`. 이번 변경은 새 targeted integration tests 및 manifest까지 GitHub 커밋하나 **신규 SHA DGX_NOT_RUN / CI_NOT_RUN**. 기존 37/37 CPU 전체 재실행, 실제 GPU 모델 빌드, 8000/v1 요청, 서버 중지 없음.
- **P2 다음 핵심 행동은 Numeric first-divergence의 실제 후보 실측**. Stage 생성은 실행 승인이나 numeric 원인 해결이 아님. 별도 GPU 정비창 승인과 원본 서비스/자원 분리·후보 제거 계획을 갖추기 전 Candidate image build/serve 금지. Numeric witness 단계의 raw logits/hash ↔ logprobs ↔ API 연계, 이후 PLE H2D 성능과 MTP acceptance를 한 번의 통합 시험으로 묶는다.

# Orcarouter 실운영 목표 기준 Blazux 적용 로드맵 — 2026-11-03

## 최종 목표 및 불변 경계

현재 DGX Spark에서 제공 중인 **Orcarouter Uncensored (NVFP4 routed experts + 약 95.37 GiB BF16 PLE + BF16 MTP2 overlay)** 모델에 [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) 최적화 기술을 **Orcarouter 호환 포팅**한다. 기존 OpenAI-compatible `8000/v1` 및 모델 ID / OpenWebUI·Pi Agent 연결을 보호하고 정확성·Tool Calling·Cache 상태·처리량·메모리·동시성을 함께 검증한다.

이 저장소는 최신 Blazux upstream `b0aa8b77604139557169387b2fa8386355d8b651` (2026-11-02 UTC)와 다른 Preview vLLM, BF16 PLE, BF16 MTP overlay를 사용하므로 upstream `./flash setup/serve`를 운영 환경에 직접 실행하지 않는다. 원본 컨테이너 ID, 이미지, 시작시각, 원본 weights, PLE mmap, HF cache, 열린 API를 변경하지 않는다. 현재 개발 브랜치는 `feature/blazux-phase6-runtime-gates`; `main`/운영 배포/GPU/API 부하는 각각 별도 승인 전 BLOCKED.

## P1 (3개 기본 기능) — 범위 한정 완료, 출시 미승인

1. PLE mmap 단계별 계측: 실제 BF16 gather stats 관측. CUDA H2D 완료시간과 full-state reuse는 아직 미확정.
2. Prefix Cache / GDN state: 실제 cache HIT, MTP accepted +400, 선택 State SHA 12/12 match; 모든 레이어·물리 state-copy와 통합 수치 정확성은 미확정.
3. Tool Calling/Responses: 실제 forced tool-call→tool-result→final 확인, 앞선 Chat/Responses 경로 검증. 현재 운영 ID/API 보존 필요.

실측 한정 `P1_FUNCTIONAL_VERIFIED=BOUNDED_PASS`. 독립 `P1_RELEASE_BLOCKED=TRUE`: 원본의 Prefix OFF, MTP OFF, 첫 토큰에서도 strict logprob `1e-4` 실패.

## P2 (3개 원래 핵심 + 독립 수치 정확성) — 현재 실제 실행 우선순위

1. **Numeric 1e-4 원인 위치 특정/수정이 최우선.** 기존 pinned Sampler witness로 단일 격리 후보의 raw logits ↔ log-softmax/selected token ↔ API logprob를 검증해 첫 차이 지점을 찾는다. 기존 QSA/Prefix/MTP ON/OFF를 근거 없이 반복하지 않는다. 원본에도 존재하는 비재현성을 후보 코드 자체 문제라고 추정하지 않는다. NVIDIA/Blazux의 greedy token 결정성과 API logprob 모든 쌍 1e-4는 서로 다른 요구.
2. **BF16 PLE Gather / H2D 최적화.** 기존 CPU byte-equivalence와 `VLLM_PLE_UNIQUE_H2D` 후보를 실제 Preview ABI/CUDA graph에 붙인다. 중복 제거·pinned memory·CPU→GPU 완료 및 GPU inverse gather를 실계측. baseline 대비 동일 조건 prefill, TTFT, TPS, NVMe fault/working-set, 메모리/동시성 평가.
3. **MTP Reduced Draft Vocabulary (옵션, Corpus 불필요).** Upstream 원본에는 `src/draft_vocab_65536.npy`를 동봉한다. Apache-2.0의 exact upstream snapshot `b0aa8b77604139557169387b2fa8386355d8b651`, Git Blob `2b94340a3ca0985a7494af369ac82536d61411de`를 `assets/blazux/draft_vocab_65536.npy`에 byte-exact 복제. 오름차순 65,536 ID, byte0..255, added range248044..248076 모두 존재, padding 248077..248319 없음은 **upstream binary 자체**에서 검사. 새 도구 `scripts/p2-upstream-draft-dgx.sh --stage`는 실제 Orcarouter recipe tokenizer/config SHA/declared/special/added ID를 재감사하고 정합성 PASS인 경우에만 개인 `/tmp` 읽기 전용 후보를 만든다. **아직 실 DGX 적용/성능 검증 아님.** MTP full vocabulary MTP2를 먼저 기준으로 하고 reduced Draft는 부가 A/B로 선택한다. 새 corpus 수집/가공은 기존 원본 목록이 언어·도구 사용성에서 명시적으로 부족하다는 증거가 있을 때만 검토.
4. **독립 Track B vLLM 0.32 호환성.** Preview Track A와 GPU/이미지/ABI 섞지 않는다. 31 BF16 MTP tensor/PLE constructor/QSA/KV scheduler/Chat parser 모두 서빙 호환 증거가 있어야 0.32 후보 기동 가능.

`P2_NUMERIC_STABILITY_OPEN` / 실제 BF16 MTP reduced candidate GPU acceptance NOT_RUN / H2D completed DMA NOT_RUN / vLLM0.32 Track B NOT_RUN.

## P3 (2개 고급 기능) — P2 후

1. YaRN 500K, M-RoPE long-context/MTP cache window/메모리 실제 검증.
2. Orcarouter 호환 Hybrid FP8 dense side layers, 비파괴 모델 사본에서 정확성·TTFT/TPS/품질 비교. DFlash2·다른 checkpoint/quantization 확장은 본 8개 기본 기능 외 별도 목표.

## 단일 통합 실험 / 운영 전환

실행 권한 승인 후에만 별도 격리 GPU candidate 1회성 창에서 다음을 그룹화: 원본 상태·자원/복구 preflight → strict Numeric 최초 경계 → PLE 실제 H2D·TTFT/TPS → Prefix/HIT state → MTP2/optional reduced head acceptance → Tool/Responses/Stream → 메모리·동시성 비교 → 후보 제거·원본 동일 ID/StartedAt/HTTP 확인. Strict `1e-4` 미달이거나 원본과 품질/상태 불일치 시 자동 release 금지. 원본 자체 strict FAIL은 숨기지 않고 출시 차단 유지. 원본 실행 중인 model/API 교체는 승인된 별도 마지막 단계에서만.

## 이번 source-only 인수인계

- 직전 DGX 실측 `e3a6097501a80114ae663e68c5e84c1f5114a9c7`: 격리 CPU 37/37 PASS, actual tokenizer CPU probe PASS, declared 248077, required specials 21, host 운영 원본 불변.
- 이번 신규 asset audit/개인 stage 코드는 **GitHub 구현 / DGX_NOT_RUN / CI_NOT_RUN**. 실제 출력 전 Orcarouter tokenizer와 완전 호환이라는 주장을 하지 않는다.
- 다음 DGX에는 코드 조각 복사 없이 `git pull --ff-only` 후 `bash scripts/p2-upstream-draft-dgx.sh --stage` **한 번**. 실패 시 사유를 유지하고 이미 통과한 CPU 37건은 재실행하지 않는다.
- 성공 시에도 P2 완료나 GPU candidate opt-in 승인 아님. 다음 기능 개발 주력은 Numeric source-first divergence와 비활성 PLE/MTP 실제 후보 연동.
