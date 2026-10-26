# blazux vLLM 0.32 도입 검토 및 실증 계획서

> 상태: **INITIAL_PLAN_DOCUMENT_ONLY / NOT_IMPLEMENTED / NOT_DEPLOYED / NOT_TESTED**
>
> 작성 기준: 2026-10-27 (Asia/Seoul). 외부 blazux 소스는 main SHA **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**로 고정하여 분석했다. 사용자 DGX 운영 모델의 Baseline은 PR #5에서 이미 백업됐다. 현 프로젝트의 기준 main SHA는 **2847e39b4131eb8aff78bf86ffce98892401722a** (Baseline PR #5 병합 커밋)이다. 본 계획의 출발점은 **feature/blazux-vllm032-evaluation-20261027** 브랜치이며 코드 구현/운영 배포는 포함하지 않는다.
>
> 최상위 결정: **기존 Orcarouter NVFP4/BF16 PLE/BF16 MTP=2 서비스의 정식 성능 Baseline을 먼저 확보하고 GitHub에 보존한다.** Smoke Test와 별도로 정식 Baseline **12조건×3회=36회 측정**이 완료되었고, [PR #5](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/5)에서 [원본 result.json](../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json)을 `main`에 보존했다. 단, 신규 Bash runner는 사용자 요청으로 실행 시험을 생략했다.

## 1. 목표·범위·성공 정의

### 1.1 목표

1. blazux/qwen3.8-Flash-DGX의 최적화와 안정성 패치를 **개별 기능·위험 단위**로 파악한다.
2. 현 개인 프로젝트의 Orcarouter NVFP4 **compressed-tensors** trunk, BF16 PLE(NVMe mmap), BF16 MTP overlay **31 tensors / 4.86 GiB** 등 기존 계보와 호환되는 것만 선별한다.
3. 새 엔진 도입 자체의 효과와 모델/checkpoint·양자화·sampling·CPU affinity·KV 용량 변경 효과를 분리한다.
4. 정량 개선이 재현되고 기능 안정성을 통과하면 별도의 격리된 이미지/실험 프로파일로 후속 도입을 검토한다.
5. 기존 레거시 서비스, 설치 receipts, HF cache/recipe views, Wizard 상태 및 다른 OpenWebUI/Ollama/네트워크 운영 자산을 변경하지 않는다.

### 1.2 범위 밖

- blazux 전체 저장소를 현재 프로젝트에 무검토 merge하거나 운영 Docker를 덮어쓰지 않는다.
- 사용자 검증 없이 새 vLLM 0.32 서버를 운영 포트 8000에 띄우거나 기존 모델을 정지·제거하지 않는다.
- blazux published 성능치를 현재 Orcarouter 모델의 성능으로 취급하지 않는다.
- NVIDIA/RadixArk ModelOpt checkpoint로 바꾼 결과를 **동일 Orcarouter 모델의 blazux 패치 순수 효과**로 보고하지 않는다.
- 설치/제거 위자드 또는 GitHub CI 정상화의 별도 보류 과제를 묵시적으로 재개하지 않는다.

### 1.3 성공 조건

- 사전 Baseline: 모델/코드 SHA, 스크립트/토크나이저/코퍼스/인자, 서버/이미지/KV, PP/TG/TTFR/e2e_ttft/정확성, 결과 원본 및 SHA256이 검증·보존됨.
- 호환성: 선택한 패치별 API/shape/dtype/quantization/모델 경로 및 실제 BF16 MTP 31/31 load guard가 근거로 확인됨.
- 품질: 단기·장문·동시성·MTP·prefix-cache·tool calling·JSON/schema 출력 회귀시험에서 신규 치명적 실패가 없음.
- 성능: 원본과 candidate 모두 동일 시험 조건에 대해 반복값·변동성·CPU/GPU/page-cache/KV 자원 자료를 보유; 최소 1회 run의 우연한 차이는 개선으로 간주하지 않음.
- 운영 안전: 실제 구동은 새 소유 자산에서만 하며 레거시의 이미지/컨테이너/포트/mount/receipts에는 쓰기 없음.

## 2. 비교 대상 스냅샷(확정된 사실과 미검증 사항)

| 대상 | 확인 기준 | 비고 |
| --- | --- | --- |
| 현 프로젝트 GitHub main | **2847e39b4131eb8aff78bf86ffce98892401722a** | PR #5 merge; 이후 커밋 시 HEAD 재검증 필요 |
| 현 실행 컨테이너 | **qwen38-flash-orca-uncensored-bf16-mtp** | 사용자 DGX 로그에서 running 및 API PASS |
| 현 서비스 model ID | **qwen3.8-flash-next-orca-uncensored-bf16-mtp** | /v1/models |
| 현 checkpoint revision | **3a3b63161c0745390e5270179af42e46efc70799** | Orcarouter NVFP4 |
| 현 MTP overlay source | **7b719225242aacd3dbd3f9407468c2ee9a9d2594** | RadixArk, BF16 31 tensors |
| 현 런타임 기반 | **vLLM preview 계열**, docs/BENCHMARKS.md의 0.1.dev20073+g8e685d198 | 정확한 현 컨테이너 실행 버전은 현장에서 재조회 |
| blazux 원본 | **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa** | blazux/qwen3.8-Flash-DGX / Dockerfile vllm/vllm-openai:v0.32.0 |
| llama-benchy 원본 | **e9be344578cec17745066b220798b80a0d2686d3** | 버전 0.4.1.dev1+ge9be34457, 독립 runner 설치 PASS |
| 현 실측 | **2026-10-27 Smoke Test PASS + 정식 Baseline 12조건×3회=36회 완료** | [실측 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), PP/TG/TTFT 및 원본 JSON·반복값 보존 |

본 프로젝트는 자체 Fork와 배포 안전 계약을 유지한다. 모델 이름·체크포인트·가중치/텐서 index·quantization 형식·MTP overlay를 먼저 고정해 비교해야 한다.

## 3. blazux 기능별 기술 검토 매트릭스

아래 상태의 **분석 후보**는 곧 호환성이나 적용 완료를 뜻하지 않는다.

| 후보 | blazux 관련 코드·특성 | 현 Orcarouter/BF16 환경 위험 | 예정 검증 | 상태 |
| --- | --- | --- | --- | --- |
| PLE mmap gather | src/vllm_ple_mmap.py: BF16/F16/FP8 dtype, np.memmap, CPU dedup, page fault 병렬, pinned H2D, GPU inverse scatter | 현재 preview 기반 패치와 constructor/load_weights/n-gram hash/compile 경계 구조가 다름 | BF16 16x160 row 매핑, safetensors offset, 데이터 동일성, mmap/PTE 회귀 | INVESTIGATE |
| PLE 계측 | dedup/gather/stage/wait 분리 및 Prometheus 지표 | 계측 오버헤드, backend 프로세스 메트릭 노출 필요 | P50/P95, CPU, page-cache, fault, KV headroom 추적 | INVESTIGATE |
| MTP draft vocab | src/patch_mtp_draft_vocab.py: drafter 248320 → 65536 제한 | Draft/target vocab index, Orcarouter tokenizer, MTP 정확도/수용률/언어별 결과 변동 | off/on 동일 seed, acceptance, Korean/English, EOS/tool/JSON 회귀 | OPTIONAL |
| QSA deterministic top-k | src/patch_qsadet.py; SM121 커널 | 외부 JIT kernel SHA, torch/vLLM symbols, GPU arch, 정확성/재현성 | exact top-k 비교, temperature=0, long prompt, build provenance | OPTIONAL |
| Prefix cache/Mamba block | src/patch_mamba_block_size.py | block alignment, recurrent SSM state restore, MTP cache 연동 | cold vs warm 결과·정확성, 2회/멀티턴/tool 회귀 | HIGH_PRIORITY_CORRECTNESS |
| M-RoPE window | src/patches/qwen-mrope-cache-window.patch | YaRN >262144, draft/target cache 길이·window 불일치, 품질 저하 가능 | native 262144 먼저, extrapolation은 별도 실험, retrieval 테스트 | DEFER_UNTIL_NATIVE_PASS |
| Safe output/Tools | qwen-safe-output.patch, qwen-tool-argument-schema.patch, qwen-tool-preamble.patch, qwen-tool-marker-guard.patch | Chat vs Responses, streamed argument, hidden reasoning, literal tool tokens | parser/tool/JSON regression, exact literal, partial EOS 오류 | HIGH_PRIORITY_CORRECTNESS |
| Hybrid FP8 side layers | scripts/prepare-hybrid.sh, src/vllm_fp8_hybrid_modelopt.py | **compressed-tensors Orcarouter 경로 직접 적용 부적합**; ModelOpt 기대 | 양자화 dispatch 검증 없이 적용 금지 | NOT_DIRECTLY_APPLICABLE |
| MTP NVFP4 graft | scripts/prepare-mtp-graft.sh | blazux ModelOpt 인풋과 현 BF16 31-tensor overlay 계보가 다름 | 원본 tensor inventory/이름·shape·dtype 1:1 후 검토 | NOT_DIRECTLY_APPLICABLE |
| vLLM 0.32 전환 | Dockerfile, 공식 vllm/models/qwen4_exp/nvidia 경로 | 현 vLLM preview models/qwen3_8_flash_next/nvidia와 파일/API/patched symbols drift | 독립 이미지 빌드·ABI/API 단위 분석, 31/31 MTP load guard | SEPARATE_TRACK |

특히 blazux의 hybrid/MTP graft에서 제시한 성능 이점은 해당 NVIDIA/RadixArk 계보에 대한 것으로, 현 Orcarouter compressed-tensors에 곧바로 대입하지 않는다. blazux 공개 기록에서 vLLM 0.32 결과는 ModelOpt NVFP4/FP8-hybrid/FP8 KV 조건 등으로 측정되었으며, 이 사용자 BF16 PLE/BF16 KV/MTP overlay와 **동일한 A/B 조건이 아니다**.

## 4. 단계별 추진 계획 및 Gate

### Gate 0 — 선행 Baseline 동결 (**실측·GitHub 백업 완료; 재현성 보완 남음**)

1. **DONE:** 사용자 DGX에서 Orcarouter 모델의 PP 2048/8192 × TG 128/256 × Depth 0/4096/16384, concurrency 1, 조건별 runs=3/warmup=1, latency-mode=generation, exact-tg, NumPy seed 20261027로 **총 12개 조건·36개 측정값**을 수집했다. 원본 결과 timestamp는 **2026-10-26T22:34:42Z**.
2. **DONE:** llama-benchy 소스 **e9be344578cec17745066b220798b80a0d2686d3**, 사용자 환경 실행 버전 **0.4.1.dev1+ge9be34457**. 사용자 DGX에서 독립 runner 설치와 Smoke PASS를 확인했다.
3. **DONE:** PR #5에서 원본 `result.json`(532,605 bytes, SHA-256 **25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf**), 공개용 environment, 원본 SHA256SUMS 및 보고서/핸드오프를 본 저장소에 보존했다. 내부 Docker 전체 ID가 포함된 원본 environment는 공개하지 않았다.
4. **부분 검증:** 업로드된 원본 result/environment의 SHA-256 2개만 대조됐고, progress JSONL·로그·메모리/GPU 등 체크섬 목록의 나머지 7개 파일은 미첨부였다. 당시 실제 입력 corpus SHA/서버의 모든 sampling 파라미터는 별도 확인 필요하다.
5. **NOT_RUN:** 이번 PR에 추가된 `scripts/benchmark/run-llama-benchy.sh` 자체의 실 DGX 실행 및 새 코드 회귀/CI/공개 감사. 사용자 지시로 생략했고, 과거 수동 벤치 성공을 신규 스크립트 성공으로 주장하지 않는다.
6. **Gate 통과 해석:** 측정 원본을 동결하고 **Gate 1 정적 호환성 분석을 시작할 근거는 확보**했다. 그러나 *엄격히 동등한 A/B* 완료를 주장하려면 코퍼스 hash, sampling/요청 payload, 런타임/모델·KV·메모리·캐시 조건의 동일성 검증을 완료해야 한다. 후보 GPU 실행·운영 교체는 별도 승인과 안전 Gate를 필요로 한다.

### Gate 1 — 1:1 정적 코드·데이터 계약 비교

- 양측 PLE mmap 파일/의존 모듈의 init/load/forward/Gather 함수, dtype dispatch, alignment, missing tensor/duplicate 처리, page-cache/pinned staging 등을 **함수별 표**로 만들고 KEEP/PORT/ADAPT/REJECT를 결정한다.
- MTP draft module과 model loader, fused experts, 31 overlay tensor 목록 및 정확한 BF16 tensor hash/load-guard를 비교한다.
- vLLM preview ↔ 0.32 상속/등록/compile/graph break/op cache와 CPU↔GPU 전송 경계를 추적한다.
- blazux 변경 의존성(일반 patch, 외부 커널, Docker base/torch/triton/transformers)과 라이선스·서드파티 출처를 적는다.
- 문서 산출물: 호환성 매트릭스, 위험도, 최소 포팅 범위, 테스트 가능한 스코프, 명시적인 보류 항목.

### Gate 2 — 오프라인/모의 회귀시험

- 기존 operational mock 및 전체 unit tests는 변경 전 증거로 유지하고, 새 코드 적용 후 새 commit에서 다시 실행한다.
- 핵심 함수별 정상·실패·경계 조건: safetensors offsets/shards, BF16 vs FP8 scale, mmap page offsets, CPU dedup→GPU inverse permutation, async H2D ordering.
- MTP load guard 31/31, draft off/on, unsupported quantization 실패 시 **Fail closed**. Draft vocab이 target logits의 범위를 잘못 축소하지 않는지 확인.
- Stream parser / tool JSON / reasoning vs visible token clocks / prefix-cache state restore 검증.
- 기존 모델/뷰·HF snapshot에 복구 불가능한 변경을 하는 테스트는 금지한다.

### Gate 3 — 독립 실험용 빌드/배포 계약

- blazux scripts/serve.sh는 운영에서 **직접 실행 금지**. 현재 blazux serve.sh에 동일 컨테이너 이름으로 docker rm -f를 실행하는 경로가 존재한다. 별도 소유권 receipt, 정확한 ID/label 확인, replace 거부 및 dry-run이 없는 한 사용하지 않는다.
- blazux 기본 PORT=18300과 본 저장소 Wizard 예약 127.0.0.1:18300의 충돌 여부를 확인하고 **임의로 덮어쓰지 않는다**.
- 단일 GB10에서 레거시 서비스가 운영 중일 때 신규 대형 GPU 이미지 동시 가동 차단 정책을 지킨다. 별도 이름/포트만 바꿔도 통합메모리 부족은 해결되지 않는다.
- HF cache/recipe-views/weight snapshots/legacy receipts 불변. 포트 8000, 기존 컨테이너, image 및 네트워크도 불변.
- Docker base는 가급적 digest까지 기록하고, Python/torch/triton/vLLM와 적용 patch SHA/결과 파일 hash를 고정한다.
- 실제 새 GPU activation/중단/교체·서비스 전환은 **별도 구체적 승인과 안전한 점검 시점** 없이는 실행하지 않는다.

### Gate 4 — 기능 정확성 및 자원 수용

- model load: Orcarouter compressed-tensors trunk+BF16 PLE+BF16 MTP 31/31을 확인; 실제 QSA, KV, SSM, vocab 동일성 확인.
- API: /health, /v1/models, /v1/chat/completions full/stream, tool-call JSON/arguments, parser, reasoning hidden/visible, EOS/stop 처리.
- MTP=0/2 비교, acceptance, 무한/조기 종료, prefix cache fresh/reuse, Korean/English 및 code/JSON/정확한 retrieval fixture.
- Native context에서는 4K, 16K, 32K, 64K, 128K, 240K까지 단계적으로 확대하되 메모리/latency 위험을 관찰한다.
- YaRN 500K는 **native 동작 확인 후 별도**. blazux 기록에서도 보고된 모든 오류의 재현/해결이 입증된 것은 아니므로 광범위한 안정성을 추정하지 않는다.
- GPU/KV 메모리, MemAvailable, swap, PLE page cache, CPU, temperature, start time, OOM 등을 기록한다.

### Gate 5 — 공정한 A/B 성능 시험

- 고정된 pre-blazux와 candidate에서 **같은 모델 가중치·overlay·Tokenizer/코퍼스·인자·도구 SHA·sampling·context·warmup·동시성·cache 조건** 적용.
- 샘플 간 순서/온도/상주 page-cache 영향 및 재부팅·cold start 차이를 통제한다. 부하 중 background service, swap, GPU/KV 메모리 동적 변화를 함께 남긴다.
- PP, TG, TTFR, E2E TTFT, peak/aggregate, P95, 32K+ long-context, prefix cache, 동시성 1/2/4/8을 별도 시리즈로 집계.
- 관찰된 결과만 기록하고 유의하지 않거나 변동이 크면 **INCONCLUSIVE**. 모델 변경·FP8 hybrid 변경을 동반하면 별도 실험군으로 표기.
- 비교 보고서에는 throughput 상승/하락뿐 아니라 정확성, 실패율, startup, 메모리/KV 여유와 operability tradeoff를 포함한다.

### Gate 6 — 코드 리뷰와 통합 결정

- 수집된 원시 결과가 Gate 0 Baseline과 연결되었고, patch provenance/라이선스/수정 영향 및 소유권 검사가 증명된 경우에만 선택적 병합을 검토한다.
- 단계별 롤백 경로는 새 소유 자산 안에서만 검증한다. 기존 레거시 rollback을 핑계로 stop/rm/prune을 호출하지 않는다.
- 전체 vLLM 0.32 포팅은 선택적 기능·계측 포팅과 별도 브랜치/PR로 유지한다.
- 운영 환경 변경은 GitHub 코드 merge와 **별개 승인 절차**로 처리한다.

## 5. 실험군·측정 결과의 저장 구조(제안)

~~~text
docs/
  blazux-VLLM032-ADOPTION-PLAN.md
  SESSION-HANDOFF-PROMPT.md
  benchmark/
    LLAMA-BENCHY-METHODOLOGY.md           # Gate 0 완료 시 추가
    A-B-COMPARISON.md                    # 실측 이후 생성
results/
  llama-benchy/
    baseline/
      pre-blazux/
        <UTC-run-id>/result.json
        <UTC-run-id>/environment.public.json
        <UTC-run-id>/SHA256SUMS
    candidates/
      blazux-vllm032/
        <UTC-run-id>/result.json
        <UTC-run-id>/environment.public.json
        <UTC-run-id>/SHA256SUMS
scripts/
  source-state-manifest.json             # 모든 변경 파일의 SHA/mode 동시 갱신
  benchmark/
    run-llama-benchy.sh                  # 후속 구현 검토
~~~

중요: 경로는 **제안**이다. 현 DGX에 실제 생성됐거나 GitHub에 커밋된 경로로 단정하지 않는다. 공개 업로드 전 출력·요청 payload/프롬프트/토큰 스트림, 파일 경로, 환경변수, image/container full ID를 검사한다. 전체 원시 로그가 민감하면 개인 DGX에 보존하고 공개 Git에는 검증·정제 결과와 원본 해시만 보관한다.

## 6. 커밋·브랜치·Source Manifest 계약

- **Baseline 선행 PR #5는 2026-10-27 MERGED:** 새 `main` SHA **2847e39b4131eb8aff78bf86ffce98892401722a**. 정식 12×3 원본 `result.json`은 이제 `main`에 존재하며 다시 생성·덮어쓰기 금지.
- **blazux 전용 독립 브랜치:** `feature/blazux-vllm032-evaluation-20261027`, PR #5 병합된 main에서 분기. 이번 첫 커밋은 **본 계획서, 핸드오프 상태 기록, Source Manifest만** 포함하며 vLLM/Docker/모델 적용 코드 변경 없음.
- 나중에 실제 변경을 시작할 때는 blazux 고정 SHA, patch 단위 소스 비교, 라이선스/출처 기록, 오프라인 독립 시험과 함께 기능 단위 커밋·PR로 분리한다. 운영 서비스 변경은 GitHub merge와 무관한 승인 행위다.
- `scripts/source-state-manifest.json`은 모든 tracked 파일의 path/mode/Git blob SHA 스냅샷이다. PR #5 머지 직후 **manifest 제외 119개(전체 120개)**였고, 본 계획서 1개 추가 시 **manifest 제외 120개(전체 121개)**를 기록해야 한다. HEAD 이동 시 숫자와 실제 tree를 재확인한다.
- Manifest 자기참조 제외, 실제 Git blob/mode 전수 비교를 요구한다. `--strict`는 현재 `main`과 기존 승인된 release feature만 허용하므로 이번 신규 feature 브랜치에서 strict PASS를 주장할 수 없다.
- 기존 GitHub Actions **run=0**, `CI_NOT_VERIFIED`. CI 정상화는 사용자가 별도로 연기한 과제이고, 이번 문서 작업에서 재개하지 않는다.
- 본 브랜치에 계획서를 최초 커밋하는 것이 **실 DGX test, vLLM 0.32 이미지 빌드, 호환성 확인 또는 서비스 교체 성공**을 의미하지 않는다.

## 7. 위험 목록·중단 기준

| 위험 | 지표/중단 기준 | 완화 |
| --- | --- | --- |
| 기존 레거시 중단/삭제 | 컨테이너/이미지 ID, 포트, legacy receipt 다름 | 즉시 STOP, 조회만. 신규 엔진 강제 rm 실행 금지 |
| 단일 GB10 용량 초과 | MemAvailable 급감, swap/fault 급증, KV 부족/OOM | 새 대형 서버 동시 활성화 금지, 실험 전 자원 gate |
| BF16 PLE scale/index 해석 오류 | 텐서 shape/dtype/gather 결과 mismatch | 오프라인 1:1 비교, 로드 검증 실패 시 중단 |
| compressed-tensors dispatch 실패 | ModelOpt FP8 conversion/quantizer 충돌 | hybrid 모델 변환을 현 target에 직접 적용 금지 |
| BF16 MTP overlay 손실 | 31개 tensor load guard 실패/acceptance 이상 | deployment fail-closed, MTP0/2 회귀 |
| cache/SSM 오류 | prefix 반복 요청 오답, 긴 컨텍스트 재현성 문제 | cache state/정확성 시험으로 검출 |
| Tool/output 파서 변경 | literal token 조기 종료/JSON 형식 오류 | 스트리밍·non-streaming·Korean/English fixture |
| 벤치 측정 왜곡 | 모델/코퍼스/seed/latency-mode/메모리 설정 불일치 | 환경 원본·해시·메트릭 정의 함께 보존 |
| Docker 빌드 provenance 불명 | 이미지 tag만 기록, base digest 없음 | digest/dependency/patch 정확한 SHA 기록 |
| 정보 유출 | 파일·API/모델 로그에 기밀·주소·신원 | 공개 안전 감사, 민감 원본 로컬 보존 |

## 8. 현재 상태·다음 작업

**확정·완료:**
- 실 DGX legacy /v1/models·서비스 running 상태, Tokenizer SHA 확인.
- llama-benchy **0.4.1.dev1+ge9be34457** 독립 설치 PASS, Smoke PASS.
- 정식 pre-blazux **12×3=36** 실측 완료, 원본 JSON SHA-256 확인 및 [PR #5](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/5)로 **main 백업·병합 완료**.
- [정식 Baseline 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), 재실행 Bash 스크립트, Source Manifest 및 핸드오프가 main에 기록되어 있음.
- blazux 원본 **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**, 관련 핵심 소스·패치·테스트 경로를 정적 조회.
- **본 별도 브랜치의 첫 변경은 문서 작성/계획·절차 확정에 한정한다.** 구현 및 배포는 없음.

**미완료·위험/차단:**
- 원본 코퍼스 SHA·샘플링 페이로드/KV 설정/서버 환경 추가 식별 및 해당 수준의 A/B 조건 대조.
- PR #5 신규 벤치 스크립트 실제 실행(사용자 요청으로 테스트 생략), 사후 CI 및 신규 실 DGX 런타임 테스트.
- blazux 1:1 실제 함수/패치/tensor inventory 표와 현 Orcarouter compressed-tensors + BF16 PLE + BF16 MTP 오버레이의 모델 로더 호환성 검증.
- 별도 vLLM 0.32 이미지 빌드, 신규 소유 컨테이너 활성화·회수·rollback, 동시 GPU/메모리 영향 및 실제 A/B 데이터.
- 실제 서빙 서비스 stop/replace/remove/이관 및 blazux 최적화 개선 주장. 단일 GB10 기존 서비스 보호는 계속 P0이다.

**다음 단계:** (1) 이 계획서·증거·Manifest를 별도 브랜치에 고정 → (2) blazux↔현재 소스 계약 함수/텐서 단위 비교 → (3) compat gate와 오프라인 테스트 계획 확정 → (4) 승인된 새 이미지/격리 검증 → (5) 동일 조건 A/B 결과를 기준으로 도입 결정. **현재 실행 중인 레거시는 변경하지 않는다.**
