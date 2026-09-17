#!/usr/bin/env python3
"""Minimal, fail-closed state interface for the v3 execution loop."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODES = {"guided", "strict"}
VERIFY_STATUSES = {"verified", "limited", "blocked"}
STAGES = {"discovering", "decided", "building", "blocked", "delivered"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_path(root: Path) -> Path:
    return root / ".v3" / "state.json"


def read_state(root: Path) -> dict:
    path = state_path(root)
    if not path.exists():
        raise ValueError("v3 state does not exist; initialize it first")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid v3 state: {exc}") from exc
    if (
        state.get("version") != 3
        or state.get("mode") not in MODES
        or state.get("stage") not in STAGES
    ):
        raise ValueError("unsupported v3 state")
    return state


def write_state(root: Path, state: dict) -> None:
    directory = state_path(root).parent
    directory.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    fd, temp_name = tempfile.mkstemp(prefix="state-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, state_path(root))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def record(state: dict, action: str, from_stage: str) -> None:
    state["history"].append(
        {"action": action, "from": from_stage, "to": state["stage"], "at": now()}
    )


def clean_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def preflight_state(state: dict) -> dict:
    actions = {
        "discovering": (
            "prepare_and_confirm_direction",
            ["ask_user", "site-brief-v3", "site-design-v3", "decide"],
            ["write_source", "start_build", "deliver"],
        ),
        "decided": (
            "start_build",
            ["start"],
            ["change_scope_silently", "deliver"],
        ),
        "building": (
            "verify_core_task",
            ["write_source", "run_checks", "site-check-v3", "verify", "block"],
            ["deliver"],
        ),
        "blocked": (
            "resolve_blocker",
            ["ask_user", "resume", "reopen"],
            ["write_source", "deliver"],
        ),
        "delivered": (
            "report_delivery",
            ["report", "reopen"],
            ["write_source", "start_build"],
        ),
    }
    action, allowed, blocked = actions[state["stage"]]
    missing = []
    if not state["decision"]["confirmed"]:
        missing.append("confirmed_direction")
    if state["mode"] == "strict" and state["stage"] == "building":
        missing.append("independent_verification")
    return {
        "version": 3,
        "mode": state["mode"],
        "stage": state["stage"],
        "next_action": action,
        "allowed_actions": allowed,
        "blocked_actions": blocked,
        "missing": missing,
        "decision": {
            "confirmed": state["decision"]["confirmed"],
            "task": state["decision"]["task"],
            "direction": state["decision"]["direction"],
        },
        "verification": state["verification"],
        "blocked_reason": state.get("blocked_reason"),
    }


def init(root: Path, mode: str) -> dict:
    if not root.is_dir():
        raise ValueError("project root must be an existing directory")
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(MODES))}")
    if state_path(root).exists():
        raise ValueError("v3 state already exists")
    state = {
        "version": 3,
        "mode": mode,
        "stage": "discovering",
        "decision": {
            "confirmed": False,
            "task": "",
            "direction": "",
            "include": [],
            "exclude": [],
            "quote": "",
        },
        "verification": {
            "status": None,
            "evidence": [],
            "limitations": [],
            "independent": False,
            "checked_at": None,
        },
        "history": [],
        "created_at": now(),
        "updated_at": now(),
    }
    write_state(root, state)
    return preflight_state(state)


def decide(
    root: Path,
    task: str,
    direction: str,
    quote: str,
    include: list[str],
    exclude: list[str],
) -> dict:
    state = read_state(root)
    if state["stage"] != "discovering":
        raise ValueError("a direction can only be confirmed while discovering")
    if not task.strip() or not direction.strip() or not quote.strip():
        raise ValueError("task, direction and quote are required")
    old = state["stage"]
    state["decision"] = {
        "confirmed": True,
        "task": task.strip(),
        "direction": direction.strip(),
        "include": clean_items(include),
        "exclude": clean_items(exclude),
        "quote": quote.strip(),
    }
    state["stage"] = "decided"
    state["verification"] = {
        "status": None,
        "evidence": [],
        "limitations": [],
        "independent": False,
        "checked_at": None,
    }
    record(state, "decide", old)
    write_state(root, state)
    return preflight_state(state)


def start(root: Path) -> dict:
    state = read_state(root)
    if state["stage"] != "decided" or not state["decision"]["confirmed"]:
        raise ValueError("building requires a confirmed direction")
    old = state["stage"]
    state["stage"] = "building"
    record(state, "start", old)
    write_state(root, state)
    return preflight_state(state)


def verify(
    root: Path,
    status: str,
    evidence: list[str],
    limitations: list[str],
    independent: bool,
) -> dict:
    state = read_state(root)
    if state["stage"] != "building":
        raise ValueError("verification can only be recorded while building")
    if status not in VERIFY_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VERIFY_STATUSES))}")
    evidence = clean_items(evidence)
    limitations = clean_items(limitations)
    if not evidence:
        raise ValueError("at least one concrete evidence item is required")
    if status == "limited" and not limitations:
        raise ValueError("limited verification must name its limitations")
    if state["mode"] == "strict" and status == "limited":
        raise ValueError("strict mode cannot be delivered with limited verification")
    if state["mode"] == "strict" and status == "verified" and not independent:
        raise ValueError("strict mode requires independent verification")

    old = state["stage"]
    state["verification"] = {
        "status": status,
        "evidence": evidence,
        "limitations": limitations,
        "independent": independent,
        "checked_at": now(),
    }
    if status == "blocked":
        state["stage"] = "blocked"
        state["blocked_reason"] = limitations[0] if limitations else evidence[0]
        state["resume_stage"] = "building"
    else:
        state["stage"] = "delivered"
        state.pop("blocked_reason", None)
        state.pop("resume_stage", None)
    record(state, "verify", old)
    write_state(root, state)
    return preflight_state(state)


def block(root: Path, reason: str) -> dict:
    state = read_state(root)
    if state["stage"] in {"blocked", "delivered"}:
        raise ValueError("this stage cannot be blocked")
    if not reason.strip():
        raise ValueError("a blocker reason is required")
    old = state["stage"]
    state["stage"] = "blocked"
    state["blocked_reason"] = reason.strip()
    state["resume_stage"] = old
    record(state, "block", old)
    write_state(root, state)
    return preflight_state(state)


def resume(root: Path) -> dict:
    state = read_state(root)
    if state["stage"] != "blocked" or state.get("resume_stage") not in {
        "discovering",
        "decided",
        "building",
    }:
        raise ValueError("there is no resumable blocker")
    old = state["stage"]
    state["stage"] = state.pop("resume_stage")
    state.pop("blocked_reason", None)
    record(state, "resume", old)
    write_state(root, state)
    return preflight_state(state)


def reopen(root: Path, reason: str) -> dict:
    state = read_state(root)
    if not reason.strip():
        raise ValueError("a reopen reason is required")
    old = state["stage"]
    state["stage"] = "discovering"
    state["decision"] = {
        "confirmed": False,
        "task": "",
        "direction": "",
        "include": [],
        "exclude": [],
        "quote": "",
    }
    state["verification"] = {
        "status": None,
        "evidence": [],
        "limitations": [],
        "independent": False,
        "checked_at": None,
    }
    state["reopen_reason"] = reason.strip()
    state.pop("blocked_reason", None)
    state.pop("resume_stage", None)
    record(state, "reopen", old)
    write_state(root, state)
    return preflight_state(state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="v3 minimal execution state")
    sub = parser.add_subparsers(dest="action", required=True)

    command = sub.add_parser("init")
    command.add_argument("root", type=Path)
    command.add_argument("--mode", default="guided", choices=sorted(MODES))

    for name in ("preflight", "start", "resume"):
        sub.add_parser(name).add_argument("root", type=Path)

    command = sub.add_parser("decide")
    command.add_argument("root", type=Path)
    command.add_argument("--task", required=True)
    command.add_argument("--direction", required=True)
    command.add_argument("--quote", required=True)
    command.add_argument("--include", action="append", default=[])
    command.add_argument("--exclude", action="append", default=[])

    command = sub.add_parser("verify")
    command.add_argument("root", type=Path)
    command.add_argument("--status", required=True, choices=sorted(VERIFY_STATUSES))
    command.add_argument("--evidence", action="append", default=[])
    command.add_argument("--limitation", action="append", default=[])
    command.add_argument("--independent", action="store_true")

    command = sub.add_parser("block")
    command.add_argument("root", type=Path)
    command.add_argument("--reason", required=True)

    command = sub.add_parser("reopen")
    command.add_argument("root", type=Path)
    command.add_argument("--reason", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    try:
        if args.action == "init":
            result = init(root, args.mode)
        elif args.action == "preflight":
            result = preflight_state(read_state(root))
        elif args.action == "decide":
            result = decide(root, args.task, args.direction, args.quote, args.include, args.exclude)
        elif args.action == "start":
            result = start(root)
        elif args.action == "verify":
            result = verify(root, args.status, args.evidence, args.limitation, args.independent)
        elif args.action == "block":
            result = block(root, args.reason)
        elif args.action == "resume":
            result = resume(root)
        else:
            result = reopen(root, args.reason)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
