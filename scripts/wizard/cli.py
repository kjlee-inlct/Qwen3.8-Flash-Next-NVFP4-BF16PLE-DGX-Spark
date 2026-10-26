#!/usr/bin/env python3
"""Korean-first DGX Spark wizard; no implicit clone, migration, replace, or purge."""
from __future__ import annotations
import argparse
import json
import os
import sys
from typing import Any
from engine import (WizardError, activate, adopt_legacy, build_image,
                    deployment_status, inspect_only, prepare, remove_image,
                    stop_or_remove)
from model import PolicyError, policy, targets
from probe import ProbeError, container
from state import StateError


def _manifest_default(name: str) -> Any:
    return policy()["service"][name]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="DGX-Spark-wizard",
        description="Pinned BF16 PLE/MTP deployment; existing YSLAB services are protected")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Read-only inventory, including the legacy installation")
    manifest = sub.add_parser("manifest", help="Inspect or validate declarative deployment policy")
    manifest.add_argument("operation", choices=["show", "validate"])
    adopt = sub.add_parser("adopt-legacy", help="Record verified legacy deployment for READ-ONLY monitoring")
    adopt.add_argument("--confirm-container-id", help="Exact full observed legacy container ID")
    adopt.add_argument("--yes", action="store_true")
    install = sub.add_parser("install", help="Build, prepare, or activate a new wizard-owned deployment")
    install.add_argument("--target", default=_manifest_default("recommended_target"),
                         choices=sorted(targets()))
    install.add_argument("--mtp", type=int)
    modes = install.add_mutually_exclusive_group()
    modes.add_argument("--build-only", action="store_true")
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--activate-only", action="store_true")
    install.add_argument("--skip-login", action="store_true")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--status", action="store_true")
    install.add_argument("--replace", action="store_true",
                         help="Reserved; deliberately blocked until safe rollback is implemented")
    install.add_argument("--yes", action="store_true",
                         help="Confirm new-install actions only, never purge or takeover")
    uninstall = sub.add_parser("uninstall", help="Remove only explicitly recorded new wizard resources")
    uninstall.add_argument("--target", default=_manifest_default("recommended_target"),
                           choices=sorted(targets()))
    removals = uninstall.add_mutually_exclusive_group()
    removals.add_argument("--stop-only", action="store_true")
    removals.add_argument("--remove-container", action="store_true")
    removals.add_argument("--remove-image", action="store_true")
    uninstall.add_argument("--status", action="store_true")
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--yes", action="store_true")
    return parser


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _confirm(text: str, *, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise WizardError("비대화형 변경 작업에는 명시적 --yes가 필요합니다")
    print(text)
    if input("진행할까요? [yes/N] ").strip().lower() != "yes":
        raise WizardError("사용자가 취소했습니다; 변경 없음")


def _install(args: argparse.Namespace) -> None:
    if args.status:
        _print_json(inspect_only())
        return
    if args.replace:
        raise WizardError("--replace는 검증된 rollback 구현 전까지 사용할 수 없습니다. 기존 컨테이너를 보존합니다")
    item = targets()[args.target]
    mtp = args.mtp if args.mtp is not None else (2 if item["mode"] == "mtp_overlay" else 0)
    if item["mode"] != "mtp_overlay" and mtp:
        raise WizardError("MTP 없는 타깃에서는 --mtp 0만 허용")
    if not 0 <= mtp <= 16:
        raise WizardError("MTP depth는 0..16 범위입니다")
    mode = ("build" if args.build_only else "prepare" if args.prepare_only
            else "activate" if args.activate_only else "full")
    # Fail before any expensive build/download if existing target container is present.
    if mode in ("full", "activate") and not args.dry_run:
        name = f"qwen38-flash-{args.target}"
        if container(name) is not None:
            raise WizardError(
                f"{name} 컨테이너가 이미 존재합니다. 기존 YSLAB 설치일 수 있으므로 변경하지 않습니다. "
                "scripts/status.sh / scripts/adopt-legacy.sh로 확인하세요"
            )
    print(f"대상: {args.target}, mode={mode}, MTP={mtp}, cache=현재 Fork/hf-cache")
    if item["mode"] != "mtp_overlay" or args.target != "orca-uncensored-bf16-mtp":
        print("주의: 선택한 프로파일은 기본 qualified MTP2 실행 프로파일이 아닙니다")
    if not args.dry_run:
        _confirm("신규 wizard-owned 자산만 생성/실행합니다. 기존 YSLAB 서비스는 변경하지 않습니다.", yes=args.yes)
    lines: list[str] = []
    if mode in ("full", "build", "prepare"):
        lines.append(build_image(dry_run=args.dry_run))
    if mode in ("full", "prepare"):
        lines.append(prepare(target=args.target, mtp=mtp,
                             skip_login=args.skip_login, dry_run=args.dry_run))
    if mode in ("full", "activate"):
        lines.append(activate(target=args.target, mtp=mtp, dry_run=args.dry_run))
    for line in lines:
        print(line)


def _uninstall(args: argparse.Namespace) -> None:
    if args.status:
        _print_json(deployment_status())
        return
    mode = ("stop" if args.stop_only else "remove" if args.remove_container
            else "image" if args.remove_image else None)
    if mode is None:
        raise WizardError("제거할 대상을 명시하세요: --stop-only / --remove-container / --remove-image")
    print(f"제거 대상: {args.target if mode != 'image' else 'wizard-owned image'}, mode={mode}")
    if not args.dry_run:
        _confirm("소유권 receipt와 Docker ID/label을 검증한 후 해당 자산만 변경합니다.", yes=args.yes)
    if mode == "image":
        print(remove_image(dry_run=args.dry_run))
    else:
        print(stop_or_remove(target=args.target, operation=mode, dry_run=args.dry_run))


def _interactive_install(parser: argparse.ArgumentParser) -> list[str]:
    print("\nDGX Spark 설치 위자드 — 레거시 서비스 자동 변경 금지")
    print(" 1. 기본 프로파일 전체 설치 (MTP2)")
    print(" 2. 신규 이미지 빌드만")
    print(" 3. 모델 준비만")
    print(" 4. 기존 모델 활성화만")
    print(" 5. 설치 계획 미리보기")
    print(" 6. 현재 상태 확인")
    print(" 0. 종료")
    choice = input("선택 [0-6]: ").strip()
    options = {"1": ["install"], "2": ["install", "--build-only"],
               "3": ["install", "--prepare-only"],
               "4": ["install", "--activate-only"],
               "5": ["install", "--dry-run"],
               "6": ["status"], "0": []}
    if choice not in options:
        raise WizardError("올바르지 않은 메뉴 번호")
    return options[choice]


def _interactive_uninstall() -> list[str]:
    print("\nDGX Spark 제거 위자드 — 레거시/모델 가중치 자동 삭제 금지")
    print(" 1. 설치 상태 확인")
    print(" 2. Wizard 관리 컨테이너 정지")
    print(" 3. Wizard 관리 컨테이너 제거")
    print(" 4. 사용되지 않는 Wizard 관리 이미지 제거")
    print(" 5. 제거 계획 미리보기")
    print(" 0. 종료")
    choice = input("선택 [0-5]: ").strip()
    options = {"1": ["status"], "2": ["uninstall", "--stop-only"],
               "3": ["uninstall", "--remove-container"],
               "4": ["uninstall", "--remove-image"],
               "5": ["uninstall", "--remove-container", "--dry-run"], "0": []}
    if choice not in options:
        raise WizardError("올바르지 않은 메뉴 번호")
    return options[choice]


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    incoming = list(sys.argv[1:] if argv is None else argv)
    # The wrappers always supply install/uninstall first.
    if incoming in (["install"], ["uninstall"]) and sys.stdin.isatty():
        incoming = (_interactive_install(parser) if incoming[0] == "install"
                    else _interactive_uninstall())
        if not incoming:
            print("종료: 변경 없음")
            return 0
    if incoming in (["install"], ["uninstall"]) and not sys.stdin.isatty():
        parser.print_help(sys.stderr)
        return 2
    args = parser.parse_args(incoming)
    try:
        if args.command == "status":
            _print_json(deployment_status())
        elif args.command == "manifest":
            data = policy()
            if args.operation == "show":
                _print_json(data)
            else:
                print(f"manifest OK: {data['policy_id']}, {len(targets())} target(s)")
        elif args.command == "adopt-legacy":
            if not args.confirm_container_id:
                record = deployment_status().get("legacy") or {}
                if not record.get("verified"):
                    raise WizardError("레거시 설치 상태를 먼저 확인하세요: scripts/status.sh")
                print("검증된 기존 컨테이너 ID:", record.get("observed_container_id"))
                if not sys.stdin.isatty():
                    raise WizardError("--confirm-container-id FULL_ID가 필요합니다")
                args.confirm_container_id = input("기존 컨테이너 전체 ID를 다시 입력: ").strip()
            _confirm("기존 설치를 읽기 전용 관찰 대상으로 기록합니다. Docker·레거시 state 변경 없음.",
                     yes=args.yes)
            record = adopt_legacy(args.confirm_container_id)
            print("읽기 전용 등록 완료:", record["container_name"])
        elif args.command == "install":
            _install(args)
        elif args.command == "uninstall":
            _uninstall(args)
        else:
            parser.error("unknown command")
        return 0
    except (WizardError, PolicyError, StateError, ProbeError, OSError,
            ValueError, KeyError, RuntimeError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
