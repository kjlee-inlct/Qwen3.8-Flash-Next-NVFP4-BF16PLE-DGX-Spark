# P2 MTP BF16 Draft Head: pinned Preview ABI 및 CPU 행 축소 (2026-11-02)

## 검증된 출발점 (실제 DGX 영수증과 신규 구현 분리)

- **사용자 DGX `798575ed34acadb9eb83f004ce76ffc3bf2a2ac4`**: 1회성 기존 이미지의 CPU-only Docker 환경에서 Numeric/MTP/PLE **40/40 PASS, skip0**, import/UID host 4/4 PASS, 원본 운영 컨테이너 전후 불변.
- **사용자 DGX `78f1104b5652dcc78de701e8008e93a2b7cf9181`**: Numeric Sampler + PLE 공동 source stage의 **8/8 unit PASS**; `/tmp/p2-functional-bundle-x8kmxyiv` 안에 정확히 Sampler/PLE/Dockerfile, **빌드/실행/GPU/API 전혀 없음**. 각 opt-in 기본 OFF. 이 staged 소스는 아직 이미지가 아니다.
- 해당 Stage의 **실 설치 코드 탐색**: `Qwen3_8FlashNextMultiTokenPredictor`의 `__init__/forward/load_weights`, `Qwen3_8FlashNextMTP`의 `__init__/compute_logits/forward/load_weights` 확인; target `Qwen3_8FlashNextForCausalLM.compute_logits` 있음. 헤드 공유/가중치 구조/acceptance 정확성 **미검증**.

## CPU에서 실제 구현한 MTP 기초 연산

- `src/p2_mtp_head_cpu.py::reduce_bf16_head`: 이미 검증된 `DraftVocab.validate()`의 행 ID 순서대로 독립 BF16 CPU `torch.index_select` 결과를 만든다. `248320→65536` 차원 및 중복/범위, BF16/CPU/비훈련 weight, storage ownership을 fail-closed로 검사. **기존 Target Head·실 checkpoint를 변경하지 않음**. 248320×2 synthetic도 검증.
- `remap_draft_indices_cpu`: Draft 출력 로컬 index를 전체 tokenizer token ID로 CPU tensor 기반 변환(형상 보존, 범위 검사). **실 vLLM rejection sampler나 모델 loader에 연결되어 있지 않음.**
- `compare_selected_logits`: CPU synthetic hidden activation에서 **전체 Head의 선택된 logit 열과 축소 Head logits**를 비교하는 독립 오라클. BF16 산술·CPU 실험만으로 speculative acceptance 분포, GPU 속도, 품질을 보장하지 않는다.
- 실제 65,536 후보 ID 선정은 아직 없음. 현 synthetic `range(65536)`는 **실서비스 채택 어휘 목록이 아니며**, 중국어/한국어/영어·제어 토큰·효율을 평가하지 못함.

## 설치된 Preview ABI를 SHA-pin으로 분리

`src/p2_mtp_abi_contract.py`는 원본 이미지를 먼저 검사한 뒤, 아래 설치 소스만 **읽기 전용 Docker cp + AST**로 검사한다.

| Preview 설치 소스 | 사용자 DGX에서 관측한 SHA256 | 범위 |
|---|---|---|
| `vllm/models/qwen3_8_flash_next/nvidia/mtp.py` | `d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6` | MTP 2개 클래스, init/forward/compute_logits/load_weights |
| `vllm/models/qwen3_8_flash_next/nvidia/model.py` | `e74a0bf92ed73306ed28366543b00255b23ac7ec3f705b600ff0c8874442f0c6` | Target 모델/Head 구조 참조 |
| `vllm/v1/spec_decode/eagle.py` | `b2b1f7d15117b43108be368756d9c6e9334d9415a070e46178e18bb7c6476378` | speculative engine source references |
| `vllm/models/qwen4_exp.py` | NOT_FOUND_OR_UNREADABLE | 선택 경로, 없음이 해당 기능 부재의 증거가 아님 |

Pinned 파일의 SHA 또는 필수 MTP 클래스/메서드가 하나라도 맞지 않으면 **BLOCKED**. 출력에는 method signature, `self.lm_head`/`self.logits_processor` 같은 AST 속성 명칭과 SHA만 포함. raw installed source·weights·prompt·tensor 내용을 출력하지 않는다. 이 검사 결과가 헤드 독립성이나 runtime ABI 적용 허가를 뜻하지 않는다.

## DGX에서 신규 과제만 한 번에 실행

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-mtp-head-dgx.sh --execute
```

- 기존 `qsa.preflight`의 Fork·브랜치·HEAD·Manifest clean 검사 및 호스트 stdlib ABI 회귀검사.
- 원본 full container ID / image / running / StartedAt 검사, 로컬 고정 이미지에서만 CPU runc 컨테이너 **1회**(2 CPU / 2 GiB / no network / no GPU / read-only repo / host nonroot UID/GID). **신규 Head synthetic 테스트 7/7, skip0**이 아니면 실패. 기존 성공한 40개 시험을 재실행하지 않는다.
- `src.p2_mtp_abi_contract`의 정확한 pinned installed-source AST 출력도 같은 한 번의 명령 안에서 확인.
- Docker build, model load, runtime image patch, HTTP/API inference, real GPU, checkpoint/shard/mmap 수정, 서비스 start/stop/exec 등은 실행하지 않는다.

새 PR 코드 자체는 **DGX_NOT_RUN / CI_NOT_RUN**. 실제 성공 영수증 전 PASS 선언 금지.

## 다음 실제 엔진 구현의 차단 경계

1. 실제 설치된 `MTP.__init__ / compute_logits / load_weights`에서 head 속성·소유권·target sharing·quantization dispatch와 tokenizer full ID 반환 위치를 확인한다. 단순 AST 이름은 충분조건이 아니다.
2. **실제 선택할** Draft 65536 ID 집합(빈도/언어/특수 토큰)의 정확한 순서와 fingerprint를 확정한다.
3. 별도 후보에만 **독립 Draft Head copy + remap + acceptance/rejection 확률/ID 계약**을 연결한다. Target Head, 31개 BF16 MTP 텐서 원본, 기존 P1 Stage는 변경하지 않는다.
4. 새 정비창 승인 후 MTP2 acceptance, 일치 token, strict `1e-4`, GPU H2D·TTFT/TPS, 전계층 state/copy를 분리해 순차 검증한다. 기존 40/40 CPU PASS나 새 7/7 CPU PASS로 배포 승인하지 않는다.

**판정: `P2_REDUCED_DRAFT_CPU_IMPLEMENTED / NATIVE_MTP_HEAD_NOT_BOUND / P2_NUMERIC_ROOT_CAUSE_OPEN / RELEASE_BLOCKED`.**
