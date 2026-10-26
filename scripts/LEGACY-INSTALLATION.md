# 이미 설치된 YSLAB 서비스: 보호 및 읽기 전용 관리

> **실제 DGX 상태는 GitHub만으로 확인할 수 없다.** 아래는 사용자가 제공한 **운용 중인 참조 install.sh/uninstall.sh**를 기준으로 한 호환 규칙이다. 신규 위자드는 이 레거시 스크립트를 수정하거나 실행하지 않는다.

## 참조 스크립트의 기본 레이아웃

| 항목 | 기존 설치 기본값 |
| --- | --- |
| Repository | `$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark` |
| 원격 origin | `YSLAB-ai/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git` |
| PIN | `9492b78c6bc04638587b42f2ffeb0680b0fcb3ef` |
| Image | `yslab-qwen38-bf16ple:9492b78c` |
| Container | `qwen38-flash-orca-uncensored-bf16-mtp` |
| Target | `orca-uncensored-bf16-mtp` |
| API | `0.0.0.0:8000`, host local health `127.0.0.1:8000/health` |
| Cache | `$REPO_DIR/hf-cache` |
| Legacy state | `$HOME/.local/state/yslab-qwen38-bf16ple` |
| State files | `paths`, `image-id`, `container-id`, 선택적 `installer-created-repo` |
| Operation | `--prepare-only` / `--activate-only` / `--skip-login` |

기존 참조 스크립트는 사용자가 현재 운용 중이라고 설명했다. 이 정보는 **실제 호스트 관찰 결과가 아니다**. 경로는 `YSLAB_REPO_DIR`, `YSLAB_CACHE_DIR`, `YSLAB_STATE_DIR`로 변경되었을 수도 있다.

## 새 위자드의 감지·등록 방식

1. `scripts/status.sh`: legacy state를 읽고 Docker/Git을 검사하지만 아무 자산도 변경하지 않는다.
2. `legacy.verified=true`가 되려면 기록된 경로/IDs, 이미지 ID, 컨테이너 ID, Docker recipe/target labels, Git origin/HEAD, 게시 포트가 일치해야 한다.
3. `scripts/adopt-legacy.sh --confirm-container-id ... --yes`: 일치 확인한 내용을 신규 receipt의 `legacy_observation` 필드에 저장한다. 기존 `paths/image-id/container-id` 파일에는 쓰지 않는다.
4. 레거시 설치가 검증되지 않으면 신규 receipt 등록을 거부한다. 명칭만 같다는 이유로 소유권을 추정하지 않는다.
5. **adoption은 read-only이며 정지·삭제 권한을 이전하지 않는다.** 신규 `uninstall.sh`는 레거시 컨테이너를 건드릴 수 없다.

## 중요: 컨테이너 이름 충돌

현행 `src/recipe/runtime.py`의 container name은 target에서 결정된다. 레거시와 신규 위자드가 `orca-uncensored-bf16-mtp`를 실행하면 둘 다 `qwen38-flash-orca-uncensored-bf16-mtp`라는 이름을 사용한다.

따라서 포트가 8000과 18300으로 달라도 **같은 Docker 데몬에서 동시 활성화할 수 없다**. 신규 위자드는 기존 컨테이너가 있으면 `--replace` 없이도 실행이 거부되며 기존 컨테이너를 임의로 제거하지 않는다. 안전한 이름 분리나 migration은 추후 독립 설계·실환경 시험 후 구현한다.

## 기존 제거 스크립트의 purge 위험

참조 uninstall.sh는 `--purge-cache`, `--purge-repo`와 `--yes`를 지원하며 일부 조건에서 `rm -rf`를 수행한다. 새 위자드는 **이 옵션을 제공하지 않는다**. 기존 스크립트의 실행도 자동화하지 않는다. 원본 checkout/모델 파일을 삭제하려면 별도 백업, path/owner 감사 및 수동 계획이 반드시 필요하다.

## 데이터 이전 정책 (미구현)

- 기존 모델을 이미 내려받았다고 해서 새 Fork 하위 `hf-cache`로 옮기거나 link를 만드는 동작은 하지 않는다.
- 임의 symbolic link나 상대경로를 통해 복잡하게 연결하면 audit/readonly Docker mounts 가정이 깨질 수 있다.
- 향후 이전 작업에는 **기존 파일 보존**, 무결성 검사, 정확한 새 경로, Docker 이름/포트 설계, rollback과 사용자의 별도 승인이 필요하다.
