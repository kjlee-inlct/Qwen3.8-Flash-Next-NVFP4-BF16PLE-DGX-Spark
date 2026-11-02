## 실제 DGX tokenizer SHA 확정 및 새 집계 연결

- 사용자 DGX에서 d26b854c16c155917da7af722fb06d4090b5db0c 기준 원본/레시피 tokenizer byte exact-match, SHA256 06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523, source-only unit 6/6 PASS. 실서비스 mount 및 tokenizer_config special 검증은 아직 아님.
- 실제 코퍼스 집계 경로는 [P2 오프라인 Token Frequency](P2-TOKEN-FREQUENCY-20261102.md). 허가된 JSONL 자료/패키지 확인 후 결과 counts.json을 본 문서 기존 --build에 전달. 새 기능 DGX NOT_RUN, 운영용 65536 IDs NOT_CREATED.

# P2 Draft Vocabulary 실제 NumPy ID 자산 — 2026-11-02

## DGX 확인된 직전 단계

- 사용자 DGX source HEAD `d6eead92956961b48b3ec711c02c18a1276dba6d`: 통합 Numeric/PLE/MTP 후보 소스 회귀시험 **19/19 PASS** 및 `--stage-mtp` PASS.
- 실제 Stage `/tmp/p2-functional-bundle-qzvkz12s`. Sampler candidate SHA `a62b7cd7...`, BF16 PLE SHA `a7aa7fe7...`, MTP patched candidate SHA `c6fd9daa...`. Docker 3-COPY 소스만 생성되었으며 image build/GPU/API 없음. 원본 컨테이너 변경 없음.
- BF16 MTP Head CPU 7/7 PASS와 Preview 원본 source SHA 3/3 검증은 이전 DGX에서 확인됨. 이것만으로 runtime MTP acceptance 또는 strict numeric PASS를 주장하지 않는다.

## 실제 기능: SHA-verified NumPy .npy 산출물 생성

- `src/p2_mtp_vocab_artifact.py`는 사용자가 이미 토큰화한 aggregate ID 빈도 JSON과 **정확한 로컬 tokenizer.json**을 입력받는다. 텍스트/프롬프트/체크포인트를 읽거나 tokenizer 모델을 로드하지 않는다.
- `tokenizer.json` 내 `added_tokens` 및 `special=true` 표시 ID를 필수 보존하고, 입력의 `special_token_ids` 및 0..255 byte-fallback IDs도 우선 포함한다.
- 65,536개 정렬된 고유 full-vocab ID를 선택한다. 빈도 높은 ID 우선, 나머지는 낮은 ID로 보충. 파일은 NumPy v1.0 little-endian int32, shape (65536,), 기존 후보가 `numpy.load(allow_pickle=False)`로 읽을 수 있는 형식이다.
- 입력의 정확한 tokenizer SHA256과 로컬 파일 SHA256이 일치해야 한다. 중복 JSON 키, 데이터 크기/ID/빈도/필수 토큰 불일치는 차단한다. 토큰 코퍼스 대표성은 검증하지 않는다.
- 기존 Checkout/원본 모델/캐시/이미지를 변경하지 않는다. 오직 새 개인 `/tmp/p2-draft-vocab-*/`(0700) 안에 `ids.npy`, `receipt.json`(0600)만 만든다. 기존 파일은 덮어쓰지 않는다.
- 영수증에는 bytes SHA256, Draft mapping fingerprint, tokenizer/count JSON SHA256, aggregate counts coverage를 저장한다. 텍스트·프롬프트·코퍼스 데이터는 출력하지 않는다.
- 실제 aggregate count/tokenizer 자료가 아직 없으므로 **운영용 mapping .npy는 아직 생성하지 않았고**, 현 신규 코드는 DGX_NOT_RUN / CI_NOT_RUN 이다.

## 입력 형식 (아래 값은 형식 예시이며 실제 어휘가 아님)

```json
{
  "schema": "P2_TOKEN_COUNTS_V1",
  "tokenizer_sha256": "<실제 tokenizer.json의 64자리 SHA256>",
  "token_counts": {"123": 1800, "456": 1250},
  "special_token_ids": [248319]
}
```

빈도는 문자열 token ID→양의 정수이며, 실제 로컬 코퍼스에서 집계해야 한다. `special_token_ids`는 실제 tokenizer_config/제어 토큰 정보를 확인해 제공한다. tokenizer.json의 `added_tokens`는 자동으로 보존하지만 임의의 외부 special ID의 출처까지 인증하지는 않는다.

## DGX 실행 안내

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-vocab-artifact-dgx.sh --check

# 입력 자료가 실제로 준비된 경우에만:
bash scripts/p2-vocab-artifact-dgx.sh --build \
  /path/to/actual-counts.json \
  /path/to/exact-local-tokenizer.json
```

- `--check`: source/manifest 및 신규 stdlib 단위시험만 실행. Docker/GPU/모델/API 없음.
- `--build`: 같은 검증 뒤 개인 `/tmp`에 새 ID 파일과 SHA receipt 생성. 이후 이미지/서버에 자동 적용하지 않음.
- 성공 출력: `P2_DRAFT_VOCAB_PRIVATE_ARTIFACT_CREATED_NOT_DEPLOYABLE` 와 `P2_VOCAB_SOURCE_COMPLETE ... NO_MODEL_NO_GPU_NO_API`.
- 실제 DGX 입력 없이는 `--build`를 진행하지 말고, 샘플 JSON을 실제 모델 자료로 착각하지 않는다.

### 다음 런타임 단계 (별도 GPU 정비창 승인 필요)

생성된 ID 자산을 신규 후보 read-only mount와 SHA256 환경변수로 연결하고, 실제 65,536 Draft Head와 full 248,320 logits interface·MTP2 acceptance·strict logprob 1e-4·H2D/TTFT/TPS를 검증한다. 본 기능만으로 P2 Numeric root cause 또는 full-state reuse 문제는 해결되지 않으며 P1 RELEASE_BLOCKED 유지.

## 2026-11-02 실제 Orcarouter tokenizer source 확인

- 사용자 `find`에서 Orcarouter snapshot과 MTP overlay recipe view를 발견. 레시피 코드 `src/recipe/mtp.py::_copy_metadata`가 Target snapshot의 tokenizer.json을 `shutil.copyfile`로 복제하므로, **두 파일 SHA256 및 ID inventory의 일치**부터 검증한다. RadixArk/임베딩 모델 토크나이저는 실제 Draft 대상이 아님.
- 추가 read-only `scripts/p2-tokenizer-source-audit-dgx.sh --audit`: 실제 파일을 수정하지 않고 `src/p2_tokenizer_source_audit.py`가 SHA256, model.vocab ID, added/special ID 범위를 보고한다. 신규 코드 DGX_NOT_RUN, 완료 후 SHA도 아직 미확정. 상세 [Source 감사](P2-TOKENIZER-SOURCE-AUDIT-20261102.md).
- 이전 `--check` 사용자 10/10 PASS, 예시 경로 `--build`는 `P2_DRAFT_VOCAB_ARTIFACT_BLOCKED` (실제 토큰 빈도 JSON이 없으므로 운영용 .npy 생성 미완료). 임의 aggregate 값으로 채워 생성하지 않는다.
