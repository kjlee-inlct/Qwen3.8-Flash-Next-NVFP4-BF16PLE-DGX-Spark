# P1 Prefix-cache: 승인된 legacy 서비스 중지·복구 준비 (2026-10-29)

> **2026-10-29 최신 GPU 정비창 복구 영수증:** 시험 소스 `14075d6a413d002d6c8c97f78b175a7f40d015eb`에서 Prefix HIT 3회, 장문 150 token IDs/text 완전 동일, MTP 실제 accepted +400을 확인했지만 strict logprob 차이 및 Mamba physical mapping 부재로 P1 완전 정합성은 **INCONCLUSIVE (exit 2)**. 원본 동일 컨테이너 ID/HTTP 복구, 후보 잔존 없음은 사용자 로그에서 **PASS**. `start.sh`·`--recover` 재호출 불필요. **새 GPU 유지보수 실행은 별도 승인 필요**. [상세 결과](BLAZUX-PHASE6-RESULTS.md).

## 2026-10-29 현재 적용 완료 상태 — 이전 'NOT_RUN' 준비 단락보다 우선

- **현재 서비스 조작 불필요:** 사용자 DGX GPU 시험 `c342e033c6e601f374520eefb6a9d0e9277b54ef` 종료 메시지 `P1_PREFIX_ORIGINAL_SAME_ID_HTTP_RESTORED` 확인, 원본 동일 Docker ID 재기동 및 모델 HTTP 준비 성공, 후보 정리됨. 실시간 시점은 별도 읽기 전용 상태 조회로만 판단. `running`이면 `start.sh` 실행할 이유가 없다. `start.sh`는 정확한 HEAD/영수증 ID를 검사하는 `running → NO-OP` 계약으로 구현되어 있지만 불필요한 재호출은 하지 않는다.
- **서비스 실행 계약은 이미 실 DGX 검증됨:** 정상 후보 준비 → guarded `stop.sh` → GPU candidate Prefix ON, original BF16 PLE + MTP=2 유지 → 4회 API 확인 → candidate cleanup → **same-ID `start.sh` 및 `/health`·`/v1/models` 복구**. 실제 결과는 9,492 tokens, query deltas `[9492,9492,9492,9492]`, hit deltas `[0,6400,6400,6400]`; text/3 token IDs 일치, logprob drift 최대 `0.003320594`로 strict (1e-4) 미충족. **P1 correctness 완료 아님.**
- **구현·보안:** 원본 private Stage 0700 directory/0600 두 files 유지. 독립 후보가 `docker create`된 정지 상태에서 pinned Python 두 파일만 in-memory tar `docker cp`(0644)로 후보 writable overlay에 적용하고 readback SHA 검증. **호스트 Stage를 후보의 source RO mount로 사용한다는 과거 설계는 폐기**되었다. 모델 cache/views 원래 RO mounts 그대로. 원본 패치/이미지/가중치 변경 없음.
- **다음 시험 전 조건:** 현재 코드 HEAD와 사용자 DGX-tested SHA 구분. 활성 Mamba physical block/group mapping을 관측할 안전한 후보 내부 계측을 준비한 뒤 숫자 logprob drift 분해와 긴 생성 검사를 묶는 최소 실험만 제안. 복구 실패 시에만 현 checkout 정확한 `scripts/p1-prefix-gpu-window.sh --expected-head SHA --recover --confirm-id FULL64`로 후보 소유권 검증·cleanup 후 원본 복구를 시도한다. **현재는 --recover 또는 수동 docker start를 실행하지 말 것.** P2/P3·운영 배포 불승인.


> **최신 사용자 DGX 실측 `c342e033c6e601f374520eefb6a9d0e9277b54ef`:** CPU20/20, Source263/263, 실제 GPU 후보 HTTP + Prefix HIT PASS. 9,492 token Cold/Repeat×3 cache query delta [9492×4], HIT delta **[0,6400,6400,6400]**, 출력 text/token IDs 모두 일치. 단 최대 logprob delta **0.003320594** > 0.0001 strict → **P1 전체 수치 정합성 INCONCLUSIVE/exit2**; active Mamba physical mapping 未관측. 후보 삭제 후 원본 동일 ID HTTP 복구 PASS. 후속 logprob drift 분해 오라클은 DGX_NOT_RUN. [실증 장부](BLAZUX-PHASE6-RESULTS.md).


> **최신 실기기 GPU 실행 증거 (`85260bfa60e5b683681f8877447e326f69223d05`):** 신규 CPU 15/15 PASS, Source263/263, 후보 소스 두 SHA256 검증 및 **실제 후보 GPU HTTP 준비 PASS**, cold/repeat API 2회 실행, Prefix-cache hit 불확실 + 출력 양쪽 빈 문자열 + first token logprob 불일치 → **P1 correctness INCONCLUSIVE, exit 2**. 후보 제거/원본 동일-ID 재기동 및 `/health`, `/v1/models` HTTP 200까지 PASS. GPU/active Mamba ABI/P1 완료 아님. 후속 오라클 수정은 **신규 SHA DGX_NOT_RUN**. [근거 원장](BLAZUX-PHASE6-RESULTS.md) 참조.


## 2026-10-29 DGX P1 CPU 11/11 통과, 스테이지 비-root 접근 차단 (소스 c9901ba9)

- 사용자 실기기 `HEAD=c9901ba9f4f98c272ef704a3f29e199ab729e58c`: 신규 CPU 회귀 **11/11 PASS**, Source manifest **263/263 PASS**, `--preflight`에서 `P1_PREFIX_GPU_BLOCKED_SUBPROCESS_FAILED_DOCKER` (exit 2). 원래 서비스 `Up 7 days`, 후보 컨테이너 없음, 기존 메모리 가용 약 14 GiB. `--execute`는 **NOT_STARTED**.
- 추가 사용자 읽기 전용 진단: `docker ps` return 0, metadata preflight PASS; `docker run` CPU-only probe return 1. 내부 Python `PermissionError: [Errno 13] Permission denied: '/p1stage/mamba_hybrid.py'`. **원본 호스트 Stage는 소유자 전용 0700 디렉터리와 0600 파일, 원본 Docker USER는 이 호스트 소유자와 다름.**
- 후속 소스 수정(본 신규 커밋 **DGX_NOT_RUN**): CPU probe는 pinned 원본 Preview source SHA만 원래 Docker 사용자로 점검하며 **호스트 Stage bind mount 없음**. 기존 Stage의 0700/0600 및 SHA256 확인은 호스트 실행기가 계속 수행. GPU 후보는 원본 image digest/USER/WORKDIR/원본 RO cache/views 마운트와 명령 유지하여 **Docker create 상태(시작 전)**로 구성하고, 정확히 두 파일만 `docker cp` 메모리 tar(0644 읽기 권한)로 **후보의 독립 writable overlay**에 복사; `docker cp` readback의 bytes SHA256 및 mode 0644 검증 후에만 `scripts/stop.sh` 호출. 원본 운영 컨테이너/이미지/호스트 Stage 파일은 변경하지 않는다. 복사/검증 실패 시 후보만 제거하고 원래 서비스를 유지.
- 이전 설계의 **후보 source RO bind 두 개는 이 커밋부터 사용하지 않음**. 대신 후보별 Docker writable layer의 source file copy-up 두 건으로 제한. 이 차이를 명시하지 않고 예전 RO source mount 안내를 재사용하지 않는다.
- 새 HEAD의 실제 CPU/Docker preflight·candidate cp·GPU readiness/cold-hit/MTP/복구/physical mapping 모두 **미검증**. P1 GPU correctness 성공과 동등하지 않음.


## Prefix 후보 소스 두 파일의 CPU-only 출력 — DGX 완료

> **확정 DGX 결과:** `8e7b2e7535d7c27500b55046220c3f68de788aab`의 신규 CPU **6/6 PASS**, Source Manifest **259/259 PASS**, 두 후보 파일 실제 Stage PASS. `P1_PREFIX_GPU_SOURCE_STAGE_READY_ONLY_NOT_APPLIED` 및 `P1_PREFIX_STAGE_DGX_CPU_ONLY_READY_NOT_GPU_TESTED`. 사용자 DGX 보고 임시 경로: `/tmp/p1-prefix-stage.2dSPVPR6`; `mamba_hybrid.py` SHA256 `1dfb7b5566c8e683afff6640b1764c774c27daaa817437862fd465e63da9f381`, `scheduler.py` SHA256 `0501cec135d23a21f988c67371f8f1dbf97cc63726c9c44b89e350c8887178d7`. 파일은 아직 vLLM 엔진/운영 Docker에 적용되지 않았다. `/tmp`은 비영구적이다. 다음 단계에서 **무조건 stage 재생성을 실행하지 말고**, 기존 출력의 존재·해시·소유/권한을 확인한다.



- 신규 `src/p1_prefix_stage_files.py`와 `scripts/p1-prefix-stage.sh`는 **운영 서비스 가동 중** GPU 사용 없이, 고정 이미지에서 원본 SHA 확인 및 Mamba Hybrid/Scheduler 두 개의 정확한 AST 패치를 수행해 개인 호스트 임시 폴더에 결과 파일을 생성한다. 기존 검증은 패치한 임시 사본을 지웠지만 이번 단계는 외부 후보 Docker에 RO mount할 두 파일을 실제 남긴다는 차이가 있다.
- 출력은 `/tmp/p1-prefix-stage.XXXXXXXX/mamba_hybrid.py`와 `scheduler.py` **두 개만** 허용하며 root 디렉터리는 mode 0700, 파일은 mode 0600이다. 기존 이미지, 설치 vLLM, 레거시 컨테이너, 모델/캐시는 수정하지 않는다. 원본 소스 SHA가 어긋나거나 출력 디렉터리가 깨끗하지 않으면 fail-closed. CPU Docker는 `--runtime=runc --network=none` / no GPU / no model mounts / 메모리 512 MiB.
- **실행 전에 신규 코드를 시험:** `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_blazux_phase6_prefix_stage_files.py' -v`. 성공 시 후보 파일 생성은 `bash scripts/p1-prefix-stage.sh --expected-head <LATEST_COMMITTED_HEAD> --execute`. 기대 `P1_PREFIX_GPU_SOURCE_STAGE_READY_ONLY_NOT_APPLIED` 및 `P1_PREFIX_STAGE_DGX_CPU_ONLY_READY_NOT_GPU_TESTED` 출력. 경로는 로컬 메모리/파일시스템의 임시 staging이며 이미지에 설치된 경로가 아니다.
- **당시 Stage 완료 직후에는 GPU 후보 기동과 운영 중지가 금지였음(역사적 단계):** 후보 Docker launch, RO mount 지점, 실제 active ABI 관측, prefix ON/OFF cold/cache-hit 오라클, 메모리·타임아웃 제한, 실패 시 기존 서비스 복구가 준비되어야 이후 `scripts/stop.sh`로 메모리를 확보한다. 지금의 stage PASS는 GPU 정합성 증거가 아니다.


> **현행 상태 (2026-10-29): 운영 관리 스크립트 CPU 16/16·Source 256/256 및 실제 start → start NO-OP PASS at `7fecba2`; Stage CPU 6/6·Source 259/259 및 실제 후보 Python 파일 2개 출력 PASS at `8e7b2e7`. 기존 서비스 실제 stop/pause/복구는 NOT_RUN, GPU 후보 런타임·Prefix hit correctness·활성 ABI는 NOT_RUN/BLOCKED.** 사용자는 기존 서비스를 멈추고 P1 검증해도 된다고 했지만, 반드시 **만들어진 스크립트로 중지할 것**을 조건으로 승인했다. 이 변경은 실제 중지/재시작이 아니다.

## 스크립트 관리 경계의 실제 차이

- **이전 버전의 문제:** 개인 Fork의 `scripts/stop.sh`는 신규 Wizard 소유자 전용이었다. **이번 수정부터** `scripts/stop.sh`는 기본적으로 기존 YSLAB 서비스의 정확한 ID stop-only를 실행하도록 전용 P1 검증기에 위임한다. 구 Wizard 정지는 명시적 `--wizard` 옵션에서만 동작하고, `scripts/start.sh`는 원래 컨테이너를 동일 ID로 복구한다.
- 사용자가 설치했던 YSLAB `uninstall.sh --keep-image`는 컨테이너를 `docker rm -f`로 **삭제**한다. 이미지를 남겨도 컨테이너 ID는 보존되지 않는다. **일시 중지 목적으로 사용 금지.**
- 원본 YSLAB GitHub `9492b78c` 자체에는 사용자에게 별도로 제공된 install/uninstall 스크립트가 추적되지 않는다. 기존 정지 전용 스크립트의 존재도 확인되지 않았다.
- 검증된 P1 전용 저수준 실행기 `scripts/p1-legacy-service-window.sh` (내부 `src/p1_legacy_service_window.py`)는 유지하며 **`scripts/stop.sh` 및 `scripts/start.sh`가 동일한 검증 경로를 사용한다**. 기존 Wizard의 `uninstall.sh` 및 원본 YSLAB installer/uninstaller는 수정하지 않는다.

**Manifest의 역할:** `scripts/deployment-manifest.json`의 `legacy` 항목을 기존 서비스의 이름·태그·full 이미지 SHA256·모델 target·recipe 레이블·8000 포트/바인드·설치 경로의 **유일한 배포 정책**으로 읽는다. 새 `legacy.image_id`는 사용자 DGX에서 검증된 기존 이미지 digest를 고정한 값이다. 실제 대상 ID는 `~/.local/state/yslab-qwen38-bf16ple/container-id`, 이미지 ID는 동일 디렉터리 `image-id`에서 읽으며 Docker inspect 값과 모두 일치해야 한다. 이들 파일은 소스 Manifest나 배포 Manifest를 수정해도 자동으로 갱신되지 않는다. `scripts/source-state-manifest.json`은 Git SHA/파일 모드 검증용이며 Docker 대상 선택용이 아니다.

## Pause / Stop / 공통 Start — Docker/GPU 의미 구분

- `scripts/pause.sh --preflight --expected-head SHA`는 읽기 전용 신원·상태 확인. `scripts/pause.sh --expected-head SHA --confirm-id FULL64 --execute`는 **Docker `pause`**로 해당 컨테이너 프로세스를 일시 동결한다. 이는 모델/GPU 메모리를 해제하지 않는다. HTTP 포트 바인드는 남아 있어도 API 호출은 응답이 멈추거나 timeout할 수 있다. 활성 요청이 있는 상태에선 사용하지 않는다.
- `scripts/stop.sh --expected-head SHA --confirm-id FULL64 --execute`는 Docker `stop`으로 프로세스를 종료하고 GPU 사용 메모리를 회수할 때 사용한다. **P1의 별도 BF16 모델 GPU 로드 시험에서는 `pause`가 아닌 `stop`이 필수**이며, 이것만으로 GPU 여유 용량이 충분함이 보장되지는 않는다.
- **공통 `scripts/start.sh`:** 원래 컨테이너가 `paused`이면 `docker unpause`, `exited`이면 `docker start`를 수행한다. **이미 `running`이면 신원 검사 후 성공(NO-OP, Docker 상태 변경 명령 0회)** 으로 종료한다. 이때 마커는 `P1_LEGACY_ALREADY_RUNNING_NOOP_SAME_ID_HEALTH_NOT_CHECKED`이다. 양쪽 모두 동일 ID·image digest·labels·ports·mounts/receipt를 전후 검증하고, `/health`/`/v1/models` 확인 전에는 READY로 기록하지 않는다.
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
