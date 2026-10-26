# Legacy deployment observation — 2026-10-26

> Evidence: **DGX Spark shell outputs supplied by the user**. The GitHub connector
> cannot execute commands on that machine. These are *observations*, not
> independent remote tests. Do not commit real host Docker IDs or secrets.

## What the operator observed

| Category | Evidence | Meaning |
| --- | --- | --- |
| Source checkout | `$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark` | Same directory used by legacy installer AND current personal fork |
| Git origin | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` | Changed from YSLAB-ai upstream after installation |
| Current Git HEAD | `513b39f7fffdfc6f051f1663bb8d2f65bf5b857b` at observation | Different from install-time PIN, clean working tree |
| Historical PIN | `9492b78c6bc04638587b42f2ffeb0680b0fcb3ef` | `git cat-file -t` reported `commit` |
| Legacy receipts | `paths`, `image-id`, `container-id` | Recorded repo/cache path and Docker IDs matched observed resources |
| Image | `yslab-qwen38-bf16ple:9492b78c` | Image tag and ID correspond to legacy receipt |
| Container | `qwen38-flash-orca-uncensored-bf16-mtp` | Running, exact recorded ID, recipe/target labels matched |
| Mount 1 | `$REPO_DIR/hf-cache → /recipe/hf-cache` | Matches recorded cache location |
| Mount 2 | `$REPO_DIR/recipe-views → /recipe/recipe-views` | Matches recipe source directory |
| Port | `0.0.0.0:8000 → 8000/tcp` | Existing host binding; externally accessible if network/firewall allow |
| API | `GET /health` completed successfully; `GET /v1/models` returned model ID | Reported HTTP health and model listing, **not generation inference** |
| Model alias | `qwen3.8-flash-next-orca-uncensored-bf16-mtp` | Matches expected selected target |
| Max context | `262144` | Reported by `/v1/models`, not long-context inference proof |
| Runtime behavior after checkout change | Container remained running | Mounts were weights/views; checkout source history changes are distinct from existing container identity |

## Legacy probe semantics after update

- `legacy.checks.*` contains strict *existing deployment identity* checks:
  recorded paths, image ID, container ID, recipe/target labels, port binding,
  exact cache and recipe-view Docker mount source paths.
- `legacy.identity_verified` and compatibility field `legacy.verified` are
  true **only** if these runtime identity checks all pass. They grant **zero**
  modification or deletion authority.
- `legacy.checkout` reports current origin/HEAD, whether they still match the
  original install, whether the historical pinned commit exists, whether the
  checkout is the wizard checkout, and tracked worktree cleanliness.
- `legacy.checkout_warnings` reports origin/HEAD drift separately.
  Drift alone must **not** invalidate verified Docker identity.
- `legacy.api` optionally checks current local `/health` and model listing.
  API health is time-varying and is **not** proof of ownership. No generation
  inference request is made by status checks.
- `scripts/adopt-legacy.sh` records only a **read-only observation** to the
  wizard's own local state file. It does not alter legacy receipts, Docker,
  checkpoint files or the Git checkout.
- Wizard `install.sh` continues to refuse the existing Docker container name.
  Wizard `uninstall.sh` never removes a legacy-observed container.

## Next operator step (read-only)

```bash
# On the existing personal-fork feature branch, after a safe --ff-only pull:
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
scripts/status.sh
scripts/doctor.sh
```

Expect identity checks true if the host assets are unchanged; origin/head warnings
remain informative. If checks are false, **do not reset Git, stop Docker, purge
weights or write legacy state** to force a green result. Investigate the exact
reported failed check.

**Security:** legacy API binds to 0.0.0.0:8000 and has no implicit authentication
guarantee. Keep firewall/authorized-network restrictions in place. Wizard code
does not modify firewall rules or the existing bind.


## 운영자 제공: 읽기 전용 legacy adoption 성공

2026-10-26 추가 쉘 로그에 `scripts/adopt-legacy.sh --confirm-container-id ... --yes`
실행 후 `읽기 전용 등록 완료`가 출력되고,
`scripts/status.sh`의 `recorded_legacy`가 null에서 저장 당시 관찰
객체로 변경된 것을 확인했습니다. 저장 객체와 즉시 조회한 live legacy는
컨테이너 ID·이미지 ID·마운트·포트·6개 신원 검사·API health/model PASS에서
일치했습니다.

이는 **사용자가 제공한 실행 결과**이며, GitHub connector가 자체적으로
DGX에 접속해 명령을 수행한 증거는 아닙니다. 기존 Docker 서비스의
stop/rm/rebuild 없이 모니터링 대상이 로컬 wizard-state에 관찰자로
등록되었고, 관리 권한은 `OBSERVE_ONLY`입니다.

새 상태 비교 기능과 모의 테스트: [STATUS-COMPARE-AND-HEALTH.md](STATUS-COMPARE-AND-HEALTH.md).

## 2026-10-26 운영자 모의/전체 시험 결과

기능 브랜치 HEAD `3b00eafc44ebf5fa6e16134f30fb4be2679c0978`에서
사용자가 `scripts/run-mock-tests.sh` **36/36 PASS** 및 전체 단위시험
**156/156 PASS**를 보고했습니다. 기존 legacy container의 Docker 신원
6/6 PASS, API Health/Models PASS, 저장된 관찰 정보와의 실제 변동은
Git HEAD 단독 1건으로 확인되었습니다. 신규 source verifier 회귀 시험은
해당 실행 범위에 포함되지 않았습니다.

[전체 검증 기록 및 한계](VALIDATION-RESULTS-20261026.md).
