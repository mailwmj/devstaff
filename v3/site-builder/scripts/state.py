#!/usr/bin/env python3
"""Minimal, fail-closed state interface for the v3 execution loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODES = {"guided", "strict"}
VERIFY_STATUSES = {"verified", "limited", "blocked"}
STAGES = {"discovering", "decided", "building", "blocked", "delivered"}
CONTRACT_REL_PATH = ".v3/design/surface-brief.md"
# Mirrors site-design/scripts/design.py: presence of this fenced block is what
# check-contract treats as "contract present". state.py only checks presence
# (never parses the JSON) so the legacy warning stays in step with the
# authoritative missing/invalid-contract blockers.
CONTRACT_BLOCK_RE = re.compile(r"```v3-contract\n(.*?)\n```", re.DOTALL)


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
    # Older revision-1 states never carried a discovery block; normalize it in
    # memory so new structure-choice logic can run without forcing a re-init.
    if "discovery" not in state:
        state["discovery"] = default_discovery()
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


STRUCTURE_MODES = {"undetermined", "single", "choice"}
DISCOVERY_PHASES = {"briefing", "structure_assessment", "structure_choice", "direction_ready"}


def default_discovery() -> dict:
    """Fresh discovery block for a project still being understood.

    `phase` tracks where the agent is inside ``discovering``:
    briefing -> structure_assessment -> (structure_choice | direction_ready).
    ``structure`` records whether there is a real structural divergence and,
    if so, which candidate the user picked. It never adds a top-level stage.
    """
    return {
        "phase": "briefing",
        "structure": {
            "mode": "undetermined",
            "reason": "",
            "axes": [],
            "candidates": [],
            "selected": None,
            "quote": None,
        },
    }


def normalize_quote(quote: str) -> str:
    """Drop all whitespace and case so verbatim reuse (including trivial
    spacing variants) is still detected. CJK text carries no word-separating
    whitespace, so collapsing to nothing is the right equivalence for a short
    confirmation phrase."""
    return "".join(quote.split()).lower()


def discovery_next_action(discovery: dict) -> str:
    """The only discovering sub-state that pauses for the user is a real,
    unresolved structural divergence; everything else proceeds to forming and
    confirming one complete direction."""
    structure = discovery.get("structure", {})
    if structure.get("mode") == "choice" and not structure.get("selected"):
        return "present_structure_choice"
    return "prepare_and_confirm_direction"


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
    if state["stage"] == "discovering":
        action = discovery_next_action(state.get("discovery", {}))
    missing = []
    if not state["decision"]["confirmed"]:
        missing.append("confirmed_direction")
    discovery = state.get("discovery", {})
    structure = discovery.get("structure", {})
    if structure.get("mode") == "choice" and not structure.get("selected"):
        missing.append("structure_selection")
    if state["mode"] == "strict" and state["stage"] == "building":
        missing.append("independent_verification")
    return {
        "version": 3,
        "schema_revision": state.get("schema_revision", 1),
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
        "discovery": discovery,
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
        "schema_revision": 2,
        "mode": mode,
        "stage": "discovering",
        "discovery": default_discovery(),
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
    prior_quote = state.get("discovery", {}).get("structure", {}).get("quote")
    if prior_quote and normalize_quote(quote) == normalize_quote(prior_quote):
        raise ValueError(
            "structure selection quote and direction confirmation quote must differ"
        )
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


def discover(
    root: Path,
    structure: str,
    reason: str,
    axes: list[str],
    candidates: list[str],
) -> dict:
    """Record the result of the structure assessment inside ``discovering``.

    ``single`` means no real structural divergence: the agent forms one
    recommended structure and visual direction and the user confirms once via
    ``decide``. ``choice`` means the brief surfaced genuinely different
    information topologies, so the user must pick a structure first. The
    distinction is a product judgment made by the agent from project facts, not
    by this tool: colour, font, radius, shadow and other visual-only
    differences must use ``single``.
    """
    state = read_state(root)
    if state["stage"] != "discovering":
        raise ValueError("structure assessment only happens while discovering")
    if structure not in {"single", "choice"}:
        raise ValueError("structure must be single or choice")
    if not reason.strip():
        raise ValueError("a structure reason is required")
    discovery = state.get("discovery") or default_discovery()
    candidates = clean_items(candidates)
    if structure == "choice" and not candidates:
        raise ValueError("choice structure requires at least one candidate")
    discovery["phase"] = "structure_assessment"
    discovery["structure"] = {
        "mode": structure,
        "reason": reason.strip(),
        "axes": clean_items(axes),
        "candidates": candidates,
        "selected": None,
        "quote": None,
    }
    discovery["phase"] = (
        "structure_choice" if structure == "choice" else "direction_ready"
    )
    state["discovery"] = discovery
    record(state, "discover", state["stage"])
    write_state(root, state)
    return preflight_state(state)


def select_structure(root: Path, candidate: str, quote: str) -> dict:
    """Record the user's structural choice. Stays in ``discovering`` so the
    full visual direction can still be confirmed once via ``decide``."""
    state = read_state(root)
    if state["stage"] != "discovering":
        raise ValueError("structure selection only happens while discovering")
    discovery = state.get("discovery") or default_discovery()
    structure = discovery.get("structure", {})
    if structure.get("mode") != "choice":
        raise ValueError("select-structure requires a choice assessment first")
    if structure.get("selected"):
        raise ValueError("a structure has already been selected")
    candidate = candidate.strip()
    if not candidate:
        raise ValueError("a candidate is required")
    if candidate not in structure.get("candidates", []):
        raise ValueError("selected candidate must be one of the assessed candidates")
    if not quote.strip():
        raise ValueError("a selection quote is required")
    structure["selected"] = candidate
    structure["quote"] = quote.strip()
    discovery["phase"] = "direction_ready"
    discovery["structure"] = structure
    state["discovery"] = discovery
    record(state, "select-structure", state["stage"])
    write_state(root, state)
    return preflight_state(state)


def contract_path(root: Path) -> Path:
    return root / CONTRACT_REL_PATH


def _contract_sha256(root: Path) -> str | None:
    """SHA-256 of the current contract file, or None if it is absent."""
    path = contract_path(root)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _contract_has_v3_block(root: Path) -> bool:
    """True if the surface brief carries a v3-contract fenced block.

    Absent file and absent block both count as missing. Only presence is
    checked -- JSON validity is check-contract's job, not state.py's.
    """
    path = contract_path(root)
    if not path.is_file():
        return False
    return CONTRACT_BLOCK_RE.search(path.read_text(encoding="utf-8")) is not None


def _validate_contract_report(root: Path, state: dict, report_path) -> None:
    """Require a passing prebuild report for schema_revision 2 guided/strict.

    Old revision-1 states and legacy cases are handled per the handoff: they
    proceed without a report. A revision-2 guided/strict project must hand in a
    report whose project path, phase and contract SHA-256 still match.
    """
    if state.get("schema_revision") != 2 or state["mode"] not in MODES:
        return
    if report_path is None:
        raise ValueError(
            "schema_revision 2 guided/strict requires a passing prebuild contract report "
            "before start; run: design.py check-contract --root . --phase prebuild"
        )
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"contract report is unreadable: {exc}") from exc
    if not isinstance(report, dict):
        raise ValueError("contract report must be a JSON object")
    if Path(str(report.get("project_root", ""))).resolve() != root.resolve():
        raise ValueError("contract report project_root does not match this project")
    if report.get("phase") != "prebuild":
        raise ValueError("contract report phase must be prebuild")
    if not report.get("passed"):
        raise ValueError("contract report did not pass; resolve blockers before start")
    current = _contract_sha256(root)
    if current is None:
        raise ValueError("contract file is missing; cannot validate report")
    if report.get("contract_sha256") != current:
        raise ValueError(
            "contract has changed since the report was generated; re-run check-contract"
        )


def _legacy_start_warnings(root: Path, state: dict) -> list:
    """Soft, non-fatal warnings for legacy schema_revision 1 projects at start.

    revision-2 guided/strict projects are blocked hard in
    _validate_contract_report (no passing prebuild report -> raise). Legacy
    revision-1 projects proceed without a report, but when their surface brief
    lacks a v3-contract block we surface a warning so the gap is visible in the
    CLI JSON instead of being silently passed through. revision-2 projects
    return an empty list -- they are never downgraded to a warning here.
    """
    if state.get("schema_revision") == 2:
        return []
    if _contract_has_v3_block(root):
        return []
    return [
        {
            "code": "legacy_missing_contract_block",
            "message": (
                "schema_revision 1 surface brief has no v3-contract block; "
                "add one and run design.py check-contract --phase prebuild"
            ),
        }
    ]


def start(root: Path, contract_report=None) -> dict:
    state = read_state(root)
    if state["stage"] != "decided" or not state["decision"]["confirmed"]:
        raise ValueError("building requires a confirmed direction")
    _validate_contract_report(root, state, contract_report)
    warnings = _legacy_start_warnings(root, state)
    old = state["stage"]
    state["stage"] = "building"
    record(state, "start", old)
    write_state(root, state)
    result = preflight_state(state)
    result["warnings"] = warnings
    return result


def _load_check_report(report_path, root: Path) -> dict:
    """Derive verification fields from a site-check-v3 report.

    The report's top-level ``overall``/``evidence``/``limitations``/
    ``independent`` are the checker's honest summary; the per-axis detail is
    validated by ``check.py validate-report``. state.py only needs the summary
    plus a project_root match so a report from another project cannot be
    attached here.
    """
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"check report is unreadable: {exc}") from exc
    if not isinstance(report, dict):
        raise ValueError("check report must be a JSON object")
    if Path(str(report.get("project_root", ""))).resolve() != root.resolve():
        raise ValueError("check report project_root does not match this project")
    overall = report.get("overall")
    if overall not in VERIFY_STATUSES:
        raise ValueError(
            "check report overall must be one of: " + ", ".join(sorted(VERIFY_STATUSES))
        )
    evidence = report.get("evidence", [])
    limitations = report.get("limitations", [])
    if not isinstance(evidence, list):
        evidence = []
    if not isinstance(limitations, list):
        limitations = []
    return {
        "status": overall,
        "evidence": evidence,
        "limitations": limitations,
        "independent": bool(report.get("independent", False)),
    }


def verify(
    root: Path,
    status: str | None = None,
    evidence: list[str] | None = None,
    limitations: list[str] | None = None,
    independent: bool = False,
    report=None,
) -> dict:
    """Record verification while building.

    ``--report`` is the preferred path: it derives status, evidence,
    limitations and independent from a site-check-v3 report. ``--status`` with
    ``--evidence`` is kept as a transitional path for callers that have not yet
    adopted the report protocol. Either way the three deliverable statuses
    (verified / limited / blocked) and the mode rules are enforced the same.
    """
    state = read_state(root)
    if state["stage"] != "building":
        raise ValueError("verification can only be recorded while building")
    if report is not None:
        derived = _load_check_report(report, root)
        status = derived["status"]
        evidence = derived["evidence"]
        limitations = derived["limitations"]
        independent = derived["independent"]
    else:
        if status is None:
            raise ValueError("either --report or --status is required")
        if status not in VERIFY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(VERIFY_STATUSES))}")
    evidence = clean_items(evidence or [])
    limitations = clean_items(limitations or [])
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
    state["discovery"] = default_discovery()
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

    for name in ("preflight", "resume"):
        sub.add_parser(name).add_argument("root", type=Path)

    command = sub.add_parser("start")
    command.add_argument("root", type=Path)
    command.add_argument(
        "--contract-report", type=Path, default=None,
        help="path to a passing prebuild contract report (required for schema_revision 2 guided/strict)",
    )

    command = sub.add_parser("decide")
    command.add_argument("root", type=Path)
    command.add_argument("--task", required=True)
    command.add_argument("--direction", required=True)
    command.add_argument("--quote", required=True)
    command.add_argument("--include", action="append", default=[])
    command.add_argument("--exclude", action="append", default=[])

    command = sub.add_parser("discover")
    command.add_argument("root", type=Path)
    command.add_argument(
        "--structure", required=True, choices=["single", "choice"]
    )
    command.add_argument("--reason", required=True)
    command.add_argument("--axis", action="append", default=[])
    command.add_argument("--candidate", action="append", default=[])

    command = sub.add_parser("select-structure")
    command.add_argument("root", type=Path)
    command.add_argument("--candidate", required=True)
    command.add_argument("--quote", required=True)

    command = sub.add_parser("verify")
    command.add_argument("root", type=Path)
    command.add_argument(
        "--status", choices=sorted(VERIFY_STATUSES), default=None,
        help="deliverable status; transitional, mutually exclusive with --report",
    )
    command.add_argument(
        "--report", type=Path, default=None,
        help="path to a site-check-v3 report; derives status/evidence/limitations/independent",
    )
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
        elif args.action == "discover":
            result = discover(root, args.structure, args.reason, args.axis, args.candidate)
        elif args.action == "select-structure":
            result = select_structure(root, args.candidate, args.quote)
        elif args.action == "start":
            result = start(root, contract_report=args.contract_report)
        elif args.action == "verify":
            result = verify(root, status=args.status, evidence=args.evidence,
                            limitations=args.limitation, independent=args.independent,
                            report=args.report)
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
