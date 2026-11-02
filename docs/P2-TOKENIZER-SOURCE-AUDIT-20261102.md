# P2 Orcarouter 토크나이저 원본·레시피 뷰 일치 검사 (2026-11-02)

## 이번 DGX 신규 확인

- 사용자 제공 `find` 결과: (1) `recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2/tokenizer.json`, (2) `hf-cache/hub/models--orcarouter--Qwen3.8-Flash-Next-Uncensored-NVFP4/snapshots/3a3b63161c0745390e5270179af42e46efc70799/tokenizer.json`. RadixArk 및 sentence-transformers MiniLM 임베딩 토크나이저는 P2 대상에서 제외.
- `src/recipe/mtp.py::_copy_metadata`는 Target snapshot의 `tokenizer.json`을 recipe view로 `shutil.copyfile`한다(복사본, 심볼릭 링크 아님). 따라서 SHA256 동일성을 먼저 검사하면 Orcarouter Target 토크나이저 일치 여부를 판단할 수 있다.
- 이전 HEAD `d2c45cc4c41e10ec14e567a992e62fc566aaa257`에서 `scripts/p2-vocab-artifact-dgx.sh --check` **10/10 PASS**. 이어 사용자가 `/path/to/actual-counts.json`, `/path/to/exact-local-tokenizer.json` 형식 예시를 그대로 `--build`에 넣어 `P2_DRAFT_VOCAB_ARTIFACT_BLOCKED` (원인 메시지는 보안상 분류형만 출력). **실제 운영 ID 자산 없음**. 새로운 코드에서는 이 요청을 반복하지 않고 실제 토크나이저 출처를 대조한다.

## 새 읽기 전용 구현

- `src/p2_tokenizer_source_audit.py`: 발견된 두 파일의 byte-for-byte SHA256 대조, base tokenizer `model.vocab` ID inventory, added/special token IDs, 선언된 ID 범위와 248,320 Target Head 상한을 검증한다. 토큰 문자열/원문 코퍼스를 출력하지 않는다.
- Hugging Face snapshot 안 `tokenizer.json`의 blobs symlink는 **읽기만** 허용한다. 레시피 뷰는 실제 복사된 일반 파일인지 확인한다. 파싱 오류, 중복 JSON 키/ID, 크기 제한, 범위 문제, source mismatch는 차단한다.
- `active_container_mount_proven=false`, `tokenizer_config_specials_verified=false`, `actual_domain_token_counts_available=false`를 명시한다. 모델 경로가 일치해도 **실서비스 컨테이너가 실제 그 경로를 마운트했는지는 별도 증거 필요**.
- `scripts/p2-tokenizer-source-audit-dgx.sh --audit`: Source Manifest/Fork/HEAD preflight + 신규 합성 회귀시험 후 **사용자가 관측한 정확한 두 경로만** 읽는다. Docker, GPU, 모델 로드, HTTP, 파일 생성·변경 전혀 없음.

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-tokenizer-source-audit-dgx.sh --audit
```

정상 마커: `P2_RECIPE_ORCAROUTER_TOKENIZER_EXACT_MATCH_SOURCE_ONLY`, `P2_TOKENIZER_SOURCE_AUDIT_COMPLETE ... NO_GPU_NO_API_NO_WRITES`. 실제 SHA/어휘 ID 수는 DGX에서 계산한 결과를 확인해야 하며 GitHub 코드만으로 예단하지 않는다.

## 다음 기능 진행 조건

이 SHA가 일치하고 특수 ID 목록이 확인되면, 실제 한국어·영어·코드·Tool 사용 문맥 등 **사용자가 지정한 허용된 코퍼스**를 해당 토크나이저로 오프라인 토큰화해 aggregate counts를 만든다. 그때 `scripts/p2-vocab-artifact-dgx.sh --build`에 실제 counts 경로와 **레시피 뷰의 일반 파일** 경로를 넣는다. 빈도 데이터나 자료 출처 없이 65,536개 ID를 임의로 운영용으로 확정하지 않는다.

Strict 1e-4 Numeric 원인 OPEN, GPU native MTP acceptance/Head 공유 미검증, P1 RELEASE_BLOCKED 유지. 이번 신규 코드는 DGX_NOT_RUN/CI_NOT_RUN.
