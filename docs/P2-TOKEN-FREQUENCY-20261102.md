## 2026-11-02 신규 사용자 DGX `--probe` 실측 차단 및 오류 분류 보강

- **실제 DGX 실행 SHA `ac850ccdb3b0f891fef1924cc8a0e84c18b1f846`**: `git pull --ff-only` up-to-date, Source preflight PASS, 집중 synthetic **16/16 PASS**, SKIP 0. 실제 토크나이저 준비 절차에서 `P2_OFFLINE_TOKEN_COUNTS_BLOCKED` (exit2) 반환. **실제 토크나이저 CPU 인코딩 PASS 아님**. 이 오류만으로 tokenizers package/metadata/config/encoding 중 원인 분류 불가.
- 이번 GitHub 변경은 동일 `--probe` 커맨드가 기존 fail-closed 상태를 유지하면서 `P2_OFFLINE_TOKEN_COUNTS_BLOCKED REASON=<STATIC_CODE>` 형태의 **분류된 사유만** 출력하도록 개선한다. 예: `TOKENIZER_CONFIG_FILE_REQUIRED_NO_SYMLINK`, `TOKENIZERS_PACKAGE_NOT_INSTALLED_OFFLINE`, `TOKENIZER_CONFIG_DECODER_MISMATCH`, `TOKENIZER_LOADING_FAILED`, `TOKENIZER_PROBE_ENCODING_FAILED`. 민감한 원문/파일 경로/예외 메시지를 출력하지 않으며, 미등록 사유는 `UNCLASSIFIED_BLOCKED`, I/O 실패는 정적 분류.
- 검증용 synthetic 4건을 더해 targeted 20개. **새 GitHub 변경 SHA의 실제 DGX 테스트/CI는 아직 NOT_RUN**. 이전 16/16 성공을 새 코드를 실행한 결과로 소급하지 않음.

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-token-frequency-dgx.sh --probe
```

실제 출력 `REASON` 값을 받은 다음 해당 원인만 좁혀 해결한다. 패키지 임의 설치/운영 Docker 접근/모델 GPU/API 실행은 금지. 코퍼스는 사용자에게 허가된 실제 파일이 준비될 때만 `--count` 가능하며, 현재 `ids.npy` 운영 자산은 미생성.

# P2 오프라인 토큰 ID 빈도 집계 — 2026-11-02

## 2026-11-02 사용자 DGX 신규 집계 CPU 검증 및 후속 기능

- 실제 실행 HEAD a95256de940abd046d40e84e047749f92acb7054: git pull fast-forward 후 scripts/p2-token-frequency-dgx.sh --check, Source preflight PASS, targeted 11/11 PASS (SKIP 0), NO_DOCKER_NO_GPU_NO_API. 이전 신규 기능 DGX_NOT_RUN 표기는 이 결과보다 앞선 역사 기록.
- 해당 실행은 실제 tokenizers 패키지, tokenizer_config, 실제 corpus를 읽지 않았다. 실제 Token ID 빈도와 운영 65,536 IDs 미생성.
- 후속 GitHub 기능: --probe 읽기 전용 고정 토크나이저 CPU 인코딩으로 실행환경 준비 확인. --text DOMAIN PATH 명시 입력으로 UTF-8 원문 파일 전체를 단일 문서로 토큰화. JSONL --corpus와 병용 가능. 자동 디렉터리 검색/자료 수집/원문 저장 없음.
- 단일 plain-text 입력은 2MiB 제한. 초과 파일은 토큰 경계 보존을 위해 자동 분할하지 않고 차단. CPU probe는 실제 운영 컨테이너 mount 증명이나 representative corpus 품질 증명이 아니다.
- 신규 synthetic tests 5건을 더해 16건 대상. 해당 후속 SHA는 DGX_NOT_RUN / CI_NOT_RUN. 실제 데이터 없으면 --probe까지 실행하고 --count는 생략.

~~~bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-token-frequency-dgx.sh --probe
# 실제 사용권이 확인된 입력 파일이 있을 때에만 다음 예시 경로를 대체하여 실행
bash scripts/p2-token-frequency-dgx.sh --count --text technical /actual/authorized/report.md --text code /actual/authorized/code.py
~~~
## 실제 DGX 선행 검사 증거

사용자 DGX HEAD d26b854c16c155917da7af722fb06d4090b5db0c에서 tokenizer source preflight PASS, 합성시험 6/6 PASS, Orcarouter 원본 snapshot/레시피 뷰 exact byte match 확인. 실제 tokenizer SHA256: 06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523. 기본 vocab ID 248044, added IDs 33, marked specials 21, distinct declared IDs 248077 (최대 248076), Target Head 248320 rows. 미선언 243개 행을 실제 token ID로 간주하지 않는다. 이 영수증은 기존 DGX 실행 HEAD의 결과이며 새 기능의 DGX 실행 증거가 아니다.

## 실제 기능 / 데이터 보안

- src/p2_token_frequency.py는 **사용자가 출처·이용 권한을 확인하여 명시적으로 제공한** UTF-8 JSONL 코퍼스를 지정 파일만 읽는다. 각 줄은 JSON object 하나이며 정확히 단일 필드 text(비어 있지 않은 문자열)를 포함해야 한다. 예: {"text":"한국어 기술 문장"}.
- 입력 구분 ko/en/code/technical/tool, 여러 --corpus DOMAIN FILE 반복 가능. 레코드 하나를 독립적인 텍스트로 보고, 이미 설치된 Python tokenizers 패키지의 Tokenizer.from_file(tokenizer.json).encode(text, add_special_tokens=False)를 사용한다. 서비스 실제 프롬프트 포맷과 동일하다는 보장은 없다.
- 실제 사용자 감사에서 확인된 SHA256에 고정. 같은 레시피 뷰의 tokenizer_config.json 내 special token 이름과 tokenizer.json 선언 ID를 대조한다. 누락/충돌/미선언/잘못된 JSON/초과 크기/중복 corpus/symlink는 차단. 해당 config 파일이 없으면 실제 --count는 BLOCKED.
- 임의 임베딩 토크나이저, 사전 토큰화한 테스트 ID, 누락된 248320 head padding ID를 **실제 빈도**로 쓰지 않는다.
- 새 개인 /tmp/p2-token-counts-*/counts.json 및 receipt.json만 0600 모드로 생성(디렉터리 0700). counts.json은 기존 P2_TOKEN_COUNTS_V1 schema: schema, tokenizer_sha256, token_counts, special_token_ids. Receipt는 corpus SHA256/레코드 수/ID 집계/Tokenizer config SHA를 기록. 원문 텍스트와 실제 로컬 corpus 경로를 파일에 기록하지 않는다. 출처/이용권/대표성은 자동 인증되지 않는다.
- --check는 stdlib 합성시험 11건과 기존 Source Manifest 검사. --count는 명시적으로 제공한 파일에 대한 CPU tokenization을 추가 수행하며 토크나이저 패키지가 없다면 자동 설치하지 않고 차단. Docker, GPU, 네트워크, 운영 모델, 추론 HTTP, weights/cache 원본 변경 없음.

## DGX 실행 명령

~~~bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-token-frequency-dgx.sh --check
~~~

실제 허가된 JSONL 자료를 확보한 **경우에만** 아래 --count를 실행한다. 예제 파일 경로를 그대로 사용하지 말 것.

~~~bash
bash scripts/p2-token-frequency-dgx.sh --count \
  --corpus ko /actual/authorized/ko.jsonl \
  --corpus en /actual/authorized/en.jsonl \
  --corpus code /actual/authorized/code.jsonl \
  --corpus technical /actual/authorized/technical.jsonl \
  --corpus tool /actual/authorized/tool.jsonl
~~~

성공 결과 JSON의 counts_file에 실제 /tmp/p2-token-counts-XXXX/counts.json 경로가 나온다. 결과·소스 SHA·영수증을 확인한 다음에만 기존 src/p2_mtp_vocab_artifact.py 빌더를 사용한다.

~~~bash
bash scripts/p2-vocab-artifact-dgx.sh --build \
  /tmp/p2-token-counts-REAL_RESULT/counts.json \
  "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2/tokenizer.json"
~~~

REAL_RESULT는 실제 출력값으로 대체하며 가상 경로를 실행하지 않는다. **실제 허가된 대표 코퍼스와 tokenizers가 없으면 --check 후 중단**, 운영용 IDs .npy를 만들었다고 주장하지 않는다.

## 상태 및 차단

실제 토크나이저 source identity: DGX VERIFIED, tokenizer_config/실제 token counts: DGX NOT_RUN, 새 코드: GitHub SOURCE_ONLY / local stdlib synthetic 11/11 / DGX NOT_RUN / CI_NOT_RUN. 실제 65,536 ID mapping, 런타임 Draft Head, Native MTP2 acceptance, GPU H2D 성능, strict numeric 1e-4, GDN/PLE full-state, P2 배포는 계속 별도 검증/승인 전 BLOCKED.
