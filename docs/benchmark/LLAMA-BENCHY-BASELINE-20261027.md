# llama-benchy Baseline — pre-blazux — 2026-10-27

## 2026-10-28 최신 Phase6 실제 A 관찰 시도 + 승인된 기존 서비스 벤치 스크립트 검증 — 선행 상태

- **사용자 신규 실행 승인**: 실제 P6-A ABI 검증을 시도하고 이미 과거 Baseline이 있더라도 신규 벤치를 **스크립트 검증 목적**으로 수행, 오래된 문서를 갱신. 이 승인은 운영 서비스 재시작/변경·새 GPU 모델·blazux patch/CI/PR/Merge 권한이 아님. **DGX는 사용자 조작**, GitHub가 제공하는 스크립트를 검사해 실행하고 결과를 수집한다. [현재 실행·안전 경계 정본](BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md).
- **직전 실제 DGX 통합 검사 exact SHA `fb5deae540812a300cb8404a53a202e505c40577`**: Phase6 70/70 unittest PASS, Source204/204 PASS, 기존 2026-10-26/27 llama-benchy 12×3/36 pre-blazux result SHA·runner/tokenizer/frozen matrix PASS, `PLAN_READY_NOT_EXECUTED`, `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`. 70/204는 해당 소스 SHA 전용이며 새 GitHub 코드에 자동 귀속하지 않음.
- **신규 Phase6 P6-A 실제 노출형 관찰기**: clean checkout/source manifest·Docker pinned image/StartedAt/ID 전후 확인 후 loopback `GET /v1/models`, `GET /metrics`만 조회; vLLM `vllm:cache_config_info`가 이미 제공하는 경우만 block_size/prefix_caching/gpu_utilization의 allowlist 값 표시. 이 메트릭은 **시작 시 공개된 cache-config 값**이며 실제 Scheduler class/그룹별 MambaSpec/physical table·GPU state pointers를 증명하지 못함. 이 필드의 실제 in-process 안전 observer가 없으면 `P6-A ACTIVE ABI BLOCKED` 유지. `docker exec`, ptrace, live code instrumentation, 2nd model start는 이 승인에 포함되지 않음.
- **신규 Phase6 P6-AB 실제 부하 검증**: `scripts/phase6-ab-provisional-run.sh --preflight`(무부하) 후 `--execute`(기존 `127.0.0.1:8000/v1` 모델에 **추론 부하 12조건×3회/총36회**). P6-A 여전히 BLOCKED이므로 결과를 **PROVISIONAL_PRE_B_EXISTING_SERVICE_NOT_GATE_PASS**로만 기록. Pre-blazux 원본은 불변; private staging에 별도 `phase6-pre-b-provisional` 새 결과 + SHA·36 raw repeats 및 허용된 공개용 12조건 numeric summary. Runner/head·Tokenizer·현재 corpus 해시·Docker image/StartedAt·RAM ≥8GiB preflight, 진행 중 RAM <4GiB 또는 identity drift/1시간 초과시 **벤치 자식 프로세스 그룹만 중단**, 레거시 운영 컨테이너 stop/restart/exec 절대 하지 않음. 현재 데이터만으로 정상 서비스 응답시간 불변을 보장하지 않으며 부하 시 영향 가능.
- **새 HEAD GitHub 소스 상태**: 신규 A observer 12 synthetic/offline tests + 벤치 watchdog/결과 검증 17 tests, 새 runbook 등으로 기존 70건에서 **99건 예상**, Source204에서 **211 tracked 파일 예상**. **신규 HEAD DGX NOT_RUN**이며 결과를 받기 전 PASS 주장 금지. P6-B/C/D 미실행. 과거 Baseline의 실제 corpus SHA·샘플링·KV(cache) 동일성 여전히 미확정 → 원본↔신규 strict 성능 개선율 금지; 새로운 같은 조건 PRE-B/POST-B 쌍으로만 추후 비교 가능. `main`/P0/Phase1–5, 고정 이미지/기존 서비스/원본 Baseline 보호.


> **사용자 DGX 실측 완료**: 12개 조건 × 3회 = 36회, 원본 결과 보존. **신규 자동화 스크립트는 미시험**. 외부 blazux 적용 전 자료이며 A/B 개선율을 주장하지 않는다.

## 기준 대상과 실행 계보

| 항목 | 측정 당시 근거 |
| --- | --- |
| 벤치 도구 | eugr/llama-benchy SHA e9be344578cec17745066b220798b80a0d2686d3 |
| 설치 버전 | 0.4.1.dev1+ge9be34457 |
| DGX runner | $HOME/Workspace/llm/llama-benchy-runner |
| API | 기존 DGX host loopback, port 8000 /v1 |
| Served ID | qwen3.8-flash-next-orca-uncensored-bf16-mtp |
| Container / image tag | qwen38-flash-orca-uncensored-bf16-mtp / yslab-qwen38-bf16ple:9492b78c |
| 설치 소스 Git SHA | 66051cdcd4b2c5766de55421579867c195fe4084 |
| Orcarouter checkpoint revision (소스 계약) | 3a3b63161c0745390e5270179af42e46efc70799 |
| BF16 MTP overlay RadixArk revision (소스 계약) | 7b719225242aacd3dbd3f9407468c2ee9a9d2594 |
| Tokenizer SHA-256 | 06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523 |
| 실험 시작 UTC | 2026-10-26T22:19:25Z |
| 결과 timestamp UTC | 2026-10-26T22:34:42Z |

모델 full container/image ID가 기록된 원본 environment.json은 **비공개**이다. 공개용 환경 파일에는 안전한 provenance만 두고 원본 SHA를 별도로 기록한다.

## 시험 조건 및 해석

- PP 2048/8192, TG 128/256, depth 0/4096/16384, 동시성 1, warmup 1회, 각 조합 본 측정 3회, generation latency mode, exact-tg 사용.
- NumPy 입력 선택 seed=20261027. 샘플링 설정/온도·top_p·reasoning 및 실제 코퍼스 SHA는 첨부된 JSON만으로 완전히 확정되지 않는다. 같은 값과 corpus/cache 상태를 확보하기 전에는 엄밀하게 동일한 A/B라고 주장하지 않는다.
- 원본 tool의 PP tok/s는 est_ppt 기반 추정 처리량, TG tok/s는 스트리밍 첫 토큰 이후 관측 구간에서 측정한 decode 처리량이다. TTFR(첫 응답 chunk)과 E2E TTFT(첫 content 토큰)를 혼동하지 않는다.
- 2단계 enable-prefix-caching 별도 시험은 비활성이다. 이 사실이 서버 prefix cache 기능 자체가 꺼져 있었다는 증거는 아니다.
- 이전 MTP sweep의 end-to-end completion 44.23 tok/s와 이 시리즈의 TG는 계산 방식이 달라 직접 비교하지 않는다.

## 결과 전체 12개 조합

| PP | TG | Depth | PP tok/s | TG tok/s | peak tok/s | E2E TTFT (ms) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 128 | 0 | 694.99 | 33.70 | 41.33 | 3102.83 |
| 2048 | 256 | 0 | 741.02 | 33.36 | 46.33 | 2927.20 |
| 8192 | 128 | 0 | 1467.21 | 32.41 | 40.33 | 6517.36 |
| 8192 | 256 | 0 | 928.69 | 35.89 | 59.67 | 8997.82 |
| 2048 | 128 | 4096 | 869.52 | 32.62 | 42.67 | 7322.39 |
| 2048 | 256 | 4096 | 969.07 | 32.92 | 48.00 | 6682.11 |
| 8192 | 128 | 4096 | 892.29 | 32.74 | 41.00 | 13956.37 |
| 8192 | 256 | 4096 | 874.84 | 33.26 | 46.33 | 14293.72 |
| 2048 | 128 | 16384 | 912.18 | 30.42 | 41.00 | 20385.75 |
| 2048 | 256 | 16384 | 871.38 | 31.69 | 44.33 | 21320.43 |
| 8192 | 128 | 16384 | 920.42 | 32.31 | 44.33 | 26894.51 |
| 8192 | 256 | 16384 | 1024.94 | 32.93 | 48.33 | 24549.41 |

각 행의 지표는 3회 산술 평균이다. 원본 JSON에는 원시 반복값·표준편차·추가 TTFR/est_ppt 및 시계열 자료가 있으며, 요약표로 대체하지 않는다. Smoke PP256/TG32 1회 PASS는 정식 36회 결과와 독립된 사전 동작 점검이다.

## 원본 보존과 SHA 경계

- [result.json](../../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json): 사용자 첨부 **원본 바이트**, SHA-256 **25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf**.
- 원본 environment.json: 전체 container/image ID가 있으므로 GitHub에 올리지 않음. SHA-256 **76c94d48aa4597bd09e9973b6f5cba118db0009062f592e4a764398443f97eb6**.
- [environment.public.json](../../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/environment.public.json): 위 원본에서 안전 필드만 선별한 파생 자료이며 원본과 다른 바이트.
- [SHA256SUMS.original](../../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/SHA256SUMS.original): DGX가 산출한 원본 해시 목록. 이 대화에 업로드된 result.json, environment.json의 **2개 해시만 실제 대조**했다. 진행 로그와 메모리/GPU 파일 등 나머지 7개는 업로드되지 않아 검증 미완료다.
- 원본 결과는 prompt, completion, 응답 원문 등 개인 데이터가 없는 숫자·시계열 위주 키로 구성됨을 업로드 자료에서 확인했다. **향후 스크립트 출력까지 일괄 공개해도 된다는 뜻은 아니다.**

## 재실행 방법 (새 스크립트 테스트는 이번 PR에서 생략)

- 진입점: [scripts/benchmark/run-llama-benchy.sh](../../scripts/benchmark/run-llama-benchy.sh).
- DGX에서 Bash로 실행하면 별도 runner의 원본 SHA, /v1/models ID, tokenizer SHA, Gutenberg corpus cache 존재 여부를 확인한 뒤 동일 12×3 조건을 측정한다.
- output staging 기본 경로: $HOME/Workspace/llm/bench-results-staging. 고유 디렉터리에 result.json, progress.jsonl, run.log, environment.private.json, memory-before/after, gpu-before/after, python-packages, SHA256SUMS 생성. Git으로 push하지 않는다.
- 서버 프로파일 변경/기존 Docker stop/rm/restart/이미지 빌드/HF cache 이동 및 원본 receipt 수정은 금지. 모델에는 실제 추론 부하가 들어간다.
- 코퍼스는 기존 책 캐시의 SHA를 확인하고 파일을 재사용한다. 완전히 공정한 후보 비교에서는 당시 코퍼스 hash와 추가 sampler/KV 메모리 조건도 확보해야 한다.
- **새 Bash 스크립트의 실제 실행/회귀/CI/publication audit은 이번 PR에서 사용자 요청으로 NOT_RUN**. 제공된 DGX 과거 성공 로그를 새 스크립트 검증으로 승격하지 않는다.

## blazux 새 브랜치 전환 기준

- 현재 PR 범위: Baseline 원본/공개 안전 환경/해시, 방법론, 재실행 스크립트, 핸드오프, Source Manifest.
- blazux vLLM 0.32 적용 계획서 초안은 **별도 신규 브랜치**에 기록. 현재 PR에 직접 포함하지 않음.
- 외부 blazux 코드 기준 SHA 8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa. 새 브랜치는 이 PR 확정 후 최신 main에서 시작.
- single DGX Spark 운영 서비스와 Wizard 포트·컨테이너·HF cache/receipt는 불변. 기존 Orcarouter compressed-tensors + BF16 PLE/31 BF16 MTP tensor 계보를 유지하지 못하면 원래 Baseline과 별도 실험군으로 명시한다.

## 2026-10-28 후속 진행: Phase6의 신규 Runner 검증 (원본 무변경)

이 문서의 당시 `scripts/benchmark/run-llama-benchy.sh`는 **초기 PR 시점에 미실행**이었다는 역사적 진술은 유지한다. 이후 DGX Phase6 `fb5deae540812a300cb8404a53a202e505c40577`에서 과거 raw 12×3/36 원본 SHA와 tool/tokenizer/frozen matrix 검증이 PASS했다. 사용자는 현재 시점에 기존 Baseline과 별도로 **같은 12×3 bench 스크립트를 실제 시험하도록 승인**했다. 이 실행은 `scripts/phase6-ab-provisional-run.sh --preflight` 및 `--execute`를 통해 **기존 운영 서버에 유한 추론 부하**로 수행할 계획이며 실제 결과는 DGX operator log 이후에만 확정한다. 신규 결과는 외부 private staging의 `phase6-pre-b-provisional`, 이 PR의 2026-10-26 원본 `result.json` 바이트는 불변. 역사적 corpus SHA/sampler/KV 미확정으로 신규 숫자와 본 표를 strict 공정한 A/B라고 단정하지 않는다. [현행 Phase6 실행 정본](../BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md).
