# P1 Prefix-cache: 승인된 legacy 서비스 중지·복구 준비 (2026-10-29)

> **상태: 스크립트 준비 / DGX 신규 코드 시험 NOT_RUN / 기존 서비스 중지 NOT_RUN / 실제 GPU·Prefix-cache 후보 런타임 NOT_READY.** 사용자는 기존 서비스를 멈추고 P1 검증해도 된다고 했지만, 반드시 **만들어진 스크립트로 중지할 것**을 조건으로 승인했다. 이 변경은 실제 중지/재시작이 아니다.

## 스크립트 관리 경계의 실제 차이

- 현 개인 Fork의 `scripts/stop.sh`는 **새 Wizard 소유자 전용**이며 기존 YSLAB 서비스를 정지할 수 없다. 우회하거나 변경하지 말 것.
- 사용자가 설치했던 YSLAB `uninstall.sh --keep-image`는 컨테이너를 `docker rm -f`로 **삭제**한다. 이미지를 남겨도 컨테이너 ID는 보존되지 않는다. **일시 중지 목적으로 사용 금지.**
- 원본 YSLAB GitHub `9492b78c` 자체에는 사용자에게 별도로 제공된 install/uninstall 스크립트가 추적되지 않는다. 기존 정지 전용 스크립트의 존재도 확인되지 않았다.
- 기존 스크립트로 안전한 stop-only가 불가능하므로 **신규 독립** `scripts/p1-legacy-service-window.sh` (내부 `src/p1_legacy_service_window.py`)를 준비했다. 변경을 원치 않는 기존 Wizard 코드나 원본 installer/uninstaller는 수정하지 않는다.

## 안전 계약

1. 정확한 개인 Fork / Phase6 branch / clean HEAD / Source Manifest 확인. 현재 YSLAB state의 `paths`, `container-id`, `image-id`를 확인하고 default original checkout, cache/views 디렉터리 및 symlink 여부 검증.
2. 컨테이너 ID, 이미지 digest `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`, image tag, recipe/target labels, `0.0.0.0:8000`, 두 모델 bind mounts, restart policy `no`를 검사. 하나라도 불일치하면 **fail-closed**.
3. `--preflight`는 읽기 전용. `--stop`은 기록된 full ID의 Docker **stop only** (container/image/state receipt 삭제 없음); `--start`는 같은 ID의 Docker start만 수행한다. 각각 전후 Docker ID·이미지·마운트·포트 확인. 실행은 full ID `--confirm-id` 및 `--execute`를 요구.
4. STOP 명령은 **GPU 후보 이미지/런처/프리플라이트/restore 계획을 완성한 후에만** 실행. 단일 DGX 128 GiB 통합 메모리·BF16 95.37GiB PLE는 GPU 후보와 기존 모델을 동시 기동하지 않으며 후보 실패 시 기존 서비스를 다시 먼저 복구. 새 Wizard `scripts/stop.sh` 및 YSLAB uninstall·purge 금지.
5. start 성공 마커는 Docker Running=true일 뿐 **HTTP 건강·모델 로딩·실서비스 복구 검증은 아님**. 별도로 GET `127.0.0.1:8000/health`와 `/v1/models`에서 동일 모델명을 확인해야 최종 복구 PASS. 불확실하면 중단하고 민감 원문을 공개하지 않는다.

## 지금 실행 가능한 명령: 조회 전용 preflight 한 번

기존 서비스가 계속 실행 중인 상태에서 **전용 Phase6 체크아웃**에서 아래를 실행한다. `<NEW_COMMIT_SHA>`는 아래 commit 결과를 확인해 치환한다.

```bash
cd "$HOME/Workspace/llm/blazux-phase6-gates"
git pull --ff-only
bash scripts/p1-legacy-service-window.sh --preflight \
  --expected-head <NEW_COMMIT_SHA>
```

기대 마커: `P1_LEGACY_WINDOW_PREFLIGHT_PASS_RUNNING`.

**중지 명령은 아직 실행하지 않는다.** 이후 실제 테스트용 운영 정지/재시작 명령도 검증된 전용 스크립트만 제공한다. 새 GPU Prefix-cache 후보의 모델 경로/해시, old vs candidate first-token logprobs, cache hit 증거, 메모리 예산/중단 기준, 동일 컨테이너 재기동·HTTP 복구가 준비되기 전에는 불필요한 다운타임을 발생시키지 않는다. 이전 `p1-prefix-candidate`의 실제 DGX source PASS는 **런타임 정합성 PASS가 아니다**.
