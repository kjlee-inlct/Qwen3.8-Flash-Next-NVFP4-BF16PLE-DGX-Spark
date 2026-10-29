# P1 Prefix-cache: 승인된 legacy 서비스 중지·복구 준비 (2026-10-29)

> **상태: 스크립트 준비 / DGX 신규 코드 시험 NOT_RUN / 기존 서비스 중지 NOT_RUN / 실제 GPU·Prefix-cache 후보 런타임 NOT_READY.** 사용자는 기존 서비스를 멈추고 P1 검증해도 된다고 했지만, 반드시 **만들어진 스크립트로 중지할 것**을 조건으로 승인했다. 이 변경은 실제 중지/재시작이 아니다.

## 스크립트 관리 경계의 실제 차이

- **이전 버전의 문제:** 개인 Fork의 `scripts/stop.sh`는 신규 Wizard 소유자 전용이었다. **이번 수정부터** `scripts/stop.sh`는 기본적으로 기존 YSLAB 서비스의 정확한 ID stop-only를 실행하도록 전용 P1 검증기에 위임한다. 구 Wizard 정지는 명시적 `--wizard` 옵션에서만 동작하고, `scripts/start.sh`는 원래 컨테이너를 동일 ID로 복구한다.
- 사용자가 설치했던 YSLAB `uninstall.sh --keep-image`는 컨테이너를 `docker rm -f`로 **삭제**한다. 이미지를 남겨도 컨테이너 ID는 보존되지 않는다. **일시 중지 목적으로 사용 금지.**
- 원본 YSLAB GitHub `9492b78c` 자체에는 사용자에게 별도로 제공된 install/uninstall 스크립트가 추적되지 않는다. 기존 정지 전용 스크립트의 존재도 확인되지 않았다.
- 검증된 P1 전용 저수준 실행기 `scripts/p1-legacy-service-window.sh` (내부 `src/p1_legacy_service_window.py`)는 유지하며 **`scripts/stop.sh` 및 `scripts/start.sh`가 동일한 검증 경로를 사용한다**. 기존 Wizard의 `uninstall.sh` 및 원본 YSLAB installer/uninstaller는 수정하지 않는다.

**Manifest의 역할:** `scripts/deployment-manifest.json`의 `legacy` 항목을 기존 서비스의 이름·태그·full 이미지 SHA256·모델 target·recipe 레이블·8000 포트/바인드·설치 경로의 **유일한 배포 정책**으로 읽는다. 새 `legacy.image_id`는 사용자 DGX에서 검증된 기존 이미지 digest를 고정한 값이다. 실제 대상 ID는 `~/.local/state/yslab-qwen38-bf16ple/container-id`, 이미지 ID는 동일 디렉터리 `image-id`에서 읽으며 Docker inspect 값과 모두 일치해야 한다. 이들 파일은 소스 Manifest나 배포 Manifest를 수정해도 자동으로 갱신되지 않는다. `scripts/source-state-manifest.json`은 Git SHA/파일 모드 검증용이며 Docker 대상 선택용이 아니다.

## Pause / Stop / 공통 Start — Docker/GPU 의미 구분

- `scripts/pause.sh --preflight --expected-head SHA`는 읽기 전용 신원·상태 확인. `scripts/pause.sh --expected-head SHA --confirm-id FULL64 --execute`는 **Docker `pause`**로 해당 컨테이너 프로세스를 일시 동결한다. 이는 모델/GPU 메모리를 해제하지 않는다. HTTP 포트 바인드는 남아 있어도 API 호출은 응답이 멈추거나 timeout할 수 있다. 활성 요청이 있는 상태에선 사용하지 않는다.
- `scripts/stop.sh --expected-head SHA --confirm-id FULL64 --execute`는 Docker `stop`으로 프로세스를 종료하고 GPU 사용 메모리를 회수할 때 사용한다. **P1의 별도 BF16 모델 GPU 로드 시험에서는 `pause`가 아닌 `stop`이 필수**이며, 이것만으로 GPU 여유 용량이 충분함이 보장되지는 않는다.
- **공통 `scripts/start.sh`:** 원래 컨테이너가 `paused`이면 `docker unpause`, `exited`이면 `docker start`를 수행한다. `running`이면 중복 작동을 거부한다. 양쪽 모두 동일 ID·image digest·labels·ports·mounts/receipt를 전후 검증하고, `/health`/`/v1/models` 확인 전에는 READY로 기록하지 않는다.
- 명령은 모두 전용 `blazux-phase6-gates` checkout에서 수행한다. 이미지 자체를 pause/stop/start할 수 없다. NVIDIA `cuda-checkpoint`는 별도 GPU checkpoint 기능이며 **이 프로젝트에서 지원/검증/허가된 기능이 아니다**. Docker `pause`는 그 기능을 제공하지 않는다.
- **2026-10-29 실기기 기존 서비스 Cmd 읽기 전용 결과:** `Running=true`, `--no-enable-prefix-caching` 명시, `--enable-prefix-caching` 없음, `--block-size` **CLI 미지정(NULL)**, `--max-model-len=262144`, `--max-num-seqs=8`, `--gpu-memory-utilization=0.8`, `MTP method=mtp,num_speculative_tokens=2`, 모델 view=`recipe-views`. CLI의 `block_size=null`은 실제 vLLM 런타임 block size가 null임을 뜻하지 않으므로 기존 process 내부 ABI는 여전히 BLOCKED.
- **증거 경계:** 코드 HEAD `7fd423db3e9fe260ce786e185f755f387975c31b`에서 사용자 실제 DGX `PASS_SOURCE_ONLY:255`와 `P1_LEGACY_WINDOW_PREFLIGHT_PASS_RUNNING` 확인. 이후의 `pause`/공통 `start` 변경은 **DGX 미시험 / 운영 상태 변경 미실행**이다.

## 안전 계약

1. 정확한 개인 Fork / Phase6 branch / clean HEAD / Source Manifest 확인. 현재 YSLAB state의 `paths`, `container-id`, `image-id`를 확인하고 default original checkout, cache/views 디렉터리 및 symlink 여부 검증.
2. 컨테이너 ID, 이미지 digest `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`, image tag, recipe/target labels, `0.0.0.0:8000`, 두 모델 bind mounts, restart policy `no`를 검사. 하나라도 불일치하면 **fail-closed**.
3. `--preflight`는 읽기 전용. `--stop`은 기록된 full ID의 Docker **stop only** (container/image/state receipt 삭제 없음); `--start`는 같은 ID의 Docker start만 수행한다. 각각 전후 Docker ID·이미지·마운트·포트 확인. 실행은 full ID `--confirm-id` 및 `--execute`를 요구.
4. STOP 명령은 **GPU 후보 이미지/런처/프리플라이트/restore 계획을 완성한 후에만** 실행. 단일 DGX 128 GiB 통합 메모리·BF16 95.37GiB PLE는 GPU 후보와 기존 모델을 동시 기동하지 않으며 후보 실패 시 기존 서비스를 다시 먼저 복구. 이번 유지보수에서는 새 Wizard 정지 모드인 `scripts/stop.sh --wizard`와 원본 YSLAB uninstall·purge를 사용하지 않는다.
5. start 성공 마커는 Docker Running=true일 뿐 **HTTP 건강·모델 로딩·실서비스 복구 검증은 아님**. 별도로 GET `127.0.0.1:8000/health`와 `/v1/models`에서 동일 모델명을 확인해야 최종 복구 PASS. 불확실하면 중단하고 민감 원문을 공개하지 않는다.

## 지금 실행 가능한 명령: 조회 전용 preflight 한 번

기존 서비스가 계속 실행 중인 상태에서 **전용 Phase6 체크아웃**에서 아래를 실행한다. `<NEW_COMMIT_SHA>`는 아래 commit 결과를 확인해 치환한다.

```bash
cd "$HOME/Workspace/llm/blazux-phase6-gates"
git pull --ff-only
bash scripts/stop.sh --preflight \
  --expected-head <NEW_COMMIT_SHA>
```

기대 마커: `P1_LEGACY_WINDOW_PREFLIGHT_PASS_RUNNING`.

**사용자가 실제 DGX에서 확인한 이전 코드 HEAD `a84301625f8b72495f72519c32cc3f46773b91cb`의 결과:** `PASS_SOURCE_ONLY: 254 tracked file(s)`와 `P1_LEGACY_WINDOW_PREFLIGHT_PASS_RUNNING`. 이는 기존 `p1-legacy-service-window.sh` 원래 진입점의 성공으로, 새 `scripts/stop.sh` 진입점이 DGX에서 재시험됐다는 뜻은 아니다. Docker 이미지 `yslab-qwen38-bf16ple:9492b78c`가 아니라 컨테이너 `qwen38-flash-orca-uncensored-bf16-mtp`가 정지 대상이다.

**중지 명령은 실제 GPU 후보 실행/중단 기준·정확한 모델 및 이미지를 포함한 rollback 준비가 끝나기 전까지 실행하지 않는다.** 동일 컨테이너 ID를 사용자 로컬 원본 receipt에서 읽어 `scripts/stop.sh --expected-head SHA --confirm-id FULL64 --execute`, 시험 후 `scripts/start.sh`의 동일 인자로 복구한다. API `/health` 및 `/v1/models`까지 확인해야 최종 복구 PASS이다. 이후 실제 테스트용 운영 정지/재시작 명령도 검증된 전용 스크립트만 제공한다. 새 GPU Prefix-cache 후보의 모델 경로/해시, old vs candidate first-token logprobs, cache hit 증거, 메모리 예산/중단 기준, 동일 컨테이너 재기동·HTTP 복구가 준비되기 전에는 불필요한 다운타임을 발생시키지 않는다. 이전 `p1-prefix-candidate`의 실제 DGX source PASS는 **런타임 정합성 PASS가 아니다**.
