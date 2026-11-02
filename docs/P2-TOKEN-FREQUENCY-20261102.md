# P2 오프라인 토큰 ID 빈도 집계 — 2026-11-02

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
