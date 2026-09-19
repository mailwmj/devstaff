#!/usr/bin/env python3
"""Minimal, fail-closed state interface for the execution loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')

MODES = {"guided", "strict"}
VERIFY_STATUSES = {"verified", "limited", "blocked"}
STAGES = {"discovering", "decided", "building", "blocked", "delivered"}
VERIFICATION_PHASES = {"idle", "review", "checking"}
CONTRACT_REL_PATH = ".site/design/surface-brief.md"
# Mirrors site-design/scripts/design.py: presence of this fenced block is what
# check-contract treats as "contract present". state.py only checks presence
# (never parses the JSON) so the legacy warning stays in step with the
# authoritative missing/invalid-contract blockers.
CONTRACT_BLOCK_RE = re.compile(r"```(?:site-contract|v3-contract)\n(.*?)\n```", re.DOTALL)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_path(root: Path) -> Path:
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and child.name.lower() in (".site", ".v3"):
                candidate = child / "state.json"
                if candidate.is_file():
                    return candidate
    for candidate in (root / ".site" / "state.json", root / ".SITE" / "state.json", root / ".v3" / "state.json"):
        if candidate.exists():
            return candidate
    return root / ".site" / "state.json"


def read_state(root: Path) -> dict:
    path = state_path(root)
    if not path.exists():
        raise ValueError("state does not exist; initialize it first")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid state: {exc}") from exc
    if (
        state.get("version") != 3
        or state.get("mode") not in MODES
        or state.get("stage") not in STAGES
    ):
        raise ValueError("unsupported state")
    # Older revision-1 states never carried a discovery block; normalize it in
    # memory so new structure-choice logic can run without forcing a re-init.
    if "discovery" not in state:
        state["discovery"] = default_discovery()
    verification = state.get("verification")
    if not isinstance(verification, dict):
        state["verification"] = blank_verification()
    elif verification.get("phase") not in VERIFICATION_PHASES:
        # States written before verification rounds existed: no round is open.
        verification["phase"] = "idle"
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


def record(state: dict, action: str, from_stage: str, note: str | None = None) -> None:
    entry = {"action": action, "from": from_stage, "to": state["stage"], "at": now()}
    if note:
        entry["note"] = note
    state["history"].append(entry)


JOURNAL_HEADER = (
    "# 工作日志\n"
    "\n"
    "切片勾选、验证证据、发现的缺陷和被推翻的假设都写在这里，只追加，不改旧行。\n"
    "`.site/design/surface-brief.md` 参与指纹，改它会作废已经跑过的验证，所以这些内容不写进合同。\n"
    "\n"
    "| 时间 | 对象 | 客观事实 | 影响 |\n"
    "| --- | --- | --- | --- |\n"
)


def journal_path(root: Path) -> Path:
    return state_path(root).parent / "journal.md"


def ensure_journal(root: Path) -> Path:
    """Create the append-only work log if absent. Never rewrites an existing one."""
    path = journal_path(root)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(JOURNAL_HEADER, encoding="utf-8")
    return path


def blank_verification() -> dict:
    """Fresh verification block.

    ``phase`` tracks how far the verify sequence has got. ``idle`` is still
    building slices; ``review`` means the build was handed to the user and the
    agent is waiting for his answer; ``checking`` means an approved round is
    open, which blocks ``write_source`` while a checker reads the tree.

    Why ``review`` exists: the round costs far more than the user's own look at
    the page, and a report is bound to the version it was written against. Any
    change he asks for after the round has run voids it, so his look has to
    happen first. ``review_quote`` holds his own words at that moment: a round
    may only open on a version he has actually seen and said yes to.
    """
    return {
        "phase": "idle",
        "status": None,
        "evidence": [],
        "limitations": [],
        "independent": False,
        "checked_at": None,
        "handed_at": None,
        "review_quote": None,
        "handoff_fingerprint": None,
    }


def verification_phase(state: dict) -> str:
    phase = (state.get("verification") or {}).get("phase")
    return phase if phase in VERIFICATION_PHASES else "idle"


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


def building_actions(phase: str) -> tuple[str, list[str], list[str]]:
    """What is allowed while building, by verify sub-phase.

    ``idle`` writes slices and runs the cheap local checks. ``review`` is the
    build sitting in front of the user: source stays writable because his
    answer may well be "this bit is wrong", but a round cannot open until he
    has answered. ``checking`` freezes source while a checker reads it.
    """
    if phase == "review":
        return (
            "wait_for_user_review",
            ["ask_user", "write_source", "run_checks", "handoff", "begin-check", "block"],
            ["deliver", "start_build"],
        )
    if phase == "checking":
        return (
            "finish_verification",
            ["site-check", "verify", "cancel-check", "block"],
            ["write_source", "deliver"],
        )
    return (
        "build_then_handoff",
        ["write_source", "run_checks", "handoff", "block"],
        ["begin-check", "deliver"],
    )


def preflight_state(state: dict) -> dict:
    actions = {
        "discovering": (
            "prepare_and_confirm_direction",
            ["ask_user", "site-brief", "site-design", "decide"],
            ["write_source", "start_build", "deliver"],
        ),
        "decided": (
            "start_build",
            ["start"],
            ["change_scope_silently", "deliver"],
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
    phase = verification_phase(state)
    if state["stage"] == "building":
        action, allowed, blocked = building_actions(phase)
    else:
        action, allowed, blocked = actions[state["stage"]]
    if state["stage"] == "discovering":
        action = discovery_next_action(state.get("discovery", {}))
    checking = state["stage"] == "building" and phase == "checking"
    missing = []
    if not state["decision"]["confirmed"]:
        missing.append("confirmed_direction")
    discovery = state.get("discovery", {})
    structure = discovery.get("structure", {})
    if structure.get("mode") == "choice" and not structure.get("selected"):
        missing.append("structure_selection")
    if state["stage"] == "building" and phase in {"idle", "review"}:
        missing.append("user_review")
    if checking:
        missing.append("check_report")
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
        raise ValueError("state already exists")
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
        "verification": blank_verification(),
        "history": [],
        "created_at": now(),
        "updated_at": now(),
    }
    write_state(root, state)
    # The work log is where slice state and evidence live: the contract
    # participates in the fingerprint, so writing progress into it would void
    # every verification already run.
    ensure_journal(root)
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
    state["verification"] = blank_verification()
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
    for rel in (CONTRACT_REL_PATH, ".SITE/design/surface-brief.md", ".v3/design/surface-brief.md"):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return root / CONTRACT_REL_PATH


def _contract_sha256(root: Path) -> str | None:
    """SHA-256 of the current contract file, or None if it is absent."""
    path = contract_path(root)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _contract_has_site_block(root: Path) -> bool:
    """True if the surface brief carries a site-contract fenced block.

    Absent file and absent block both count as missing. Only presence is
    checked -- JSON validity is check-contract's job, not state.py's.
    """
    path = contract_path(root)
    if not path.is_file():
        return False
    return CONTRACT_BLOCK_RE.search(path.read_text(encoding="utf-8")) is not None


_contract_has_v3_block = _contract_has_site_block


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
    lacks a contract block we surface a warning so the gap is visible in the
    CLI JSON instead of being silently passed through. revision-2 projects
    return an empty list -- they are never downgraded to a warning here.
    """
    if state.get("schema_revision") == 2:
        return []
    if _contract_has_site_block(root):
        return []
    return [
        {
            "code": "legacy_missing_contract_block",
            "message": (
                "schema_revision 1 surface brief has no site-contract block; "
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


def _check_script() -> Path | None:
    """Locate the site-check protocol script installed next to this skill.

    Both layouts are the same relative hop: the four skills are siblings, in
    the repository (``release/site-builder``) and after installation
    (``agent-skills/site-builder``).
    """
    candidate = (Path(__file__).resolve().parent.parent.parent
                 / "site-check" / "scripts" / "check.py")
    return candidate if candidate.is_file() else None


def _check_verdict(root: Path, report_path) -> dict:
    """Ask the site-check protocol whether a report holds for this tree.

    The protocol owns the rules; state.py must not re-derive them, or the two
    drift and a report the protocol rejects can still be recorded as
    delivered. Fail closed: no validator, no verification.
    """
    script = _check_script()
    if script is None:
        raise ValueError(
            "cannot validate the check report: site-check/scripts/check.py was "
            "not found next to site-builder; install the skills as a bundle"
        )
    try:
        interpreter = sys.executable or "python3"
        proc = subprocess.run(
            [interpreter, str(script), "validate-report", str(root), str(report_path)],
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot validate the check report: {exc}") from exc
    try:
        verdict = json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise ValueError(
            f"check report validation produced no verdict: {exc} {detail}".strip()
        ) from exc
    if not isinstance(verdict, dict) or "error" in verdict:
        raise ValueError(f"cannot validate the check report: {verdict}")
    return verdict


def _load_check_report(report_path, root: Path) -> dict:
    """Read a site-check report's summary fields.

    Rules are not repeated here: ``check.py validate-report`` has already
    accepted the report for this tree (see :func:`_check_verdict`). This only
    carries the checker's honest summary into the state file.
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


def _plan_fingerprint(root: Path) -> dict:
    """Ask the check protocol what this tree is right now.

    What counts as source, and how it is hashed, lives in check.py; a second
    definition here would drift from the report this gate exists to protect.
    Fail closed when the protocol cannot answer: an unfingerprinted tree is a
    tree nobody can say the user looked at.
    """
    script = _check_script()
    if script is None:
        raise ValueError(
            "cannot fingerprint the tree: site-check/scripts/check.py was "
            "not found next to site-builder; install the skills as a bundle"
        )
    contract = contract_path(root)
    try:
        rel = contract.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = CONTRACT_REL_PATH
    try:
        interpreter = sys.executable or "python3"
        proc = subprocess.run(
            [interpreter, str(script), "plan", str(root), "--contract", rel],
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot fingerprint the tree: {exc}") from exc
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise ValueError(f"cannot fingerprint the tree: {exc} {detail}".strip()) from exc
    if not isinstance(data, dict) or "error" in data:
        raise ValueError(f"cannot fingerprint the tree: {data}")
    return {
        "contract_sha256": data.get("contract_sha256"),
        "source_sha256": data.get("source_sha256"),
    }


def handoff(root: Path) -> dict:
    """Put the built page in front of the user and stop until he answers.

    The look is cheap and the round is not, and a report only ever holds for
    the version it was written against. Run the round first and every change he
    then asks for voids it, which is the waste this state exists to prevent.
    Handing over also reopens the approval: whatever he said about an earlier
    version does not carry over to this one.

    The fingerprint is what makes the approval mean a version rather than a
    moment: it is the same fingerprint the report will be checked against, so
    a round that opens on a tree he never saw is refused by construction.
    """
    state = read_state(root)
    if state["stage"] != "building":
        raise ValueError("only a build in progress can be handed to the user")
    if verification_phase(state) == "checking":
        raise ValueError(
            "a verification round is open; close it first: state.py cancel-check PROJECT --reason"
        )
    fingerprint = _plan_fingerprint(root)
    state["verification"]["phase"] = "review"
    state["verification"]["handed_at"] = now()
    state["verification"]["review_quote"] = None
    state["verification"]["handoff_fingerprint"] = fingerprint
    record(state, "handoff", state["stage"])
    write_state(root, state)
    return preflight_state(state)


def begin_check(root: Path, quote: str) -> dict:
    """Open a verification round on the version the user approved.

    Handing the tree to a checker and then editing it invalidates the round
    already in progress; the same waste happens one step earlier when the user
    has not seen the page at all. So the round needs his own words, not the
    agent's judgement that it is probably fine. This tool cannot tell who
    typed the quote: writing down words the user never said defeats the gate
    exactly the way a hand-typed PASS defeats the report protocol.
    """
    state = read_state(root)
    if state["stage"] != "building":
        raise ValueError("a verification round only opens while building")
    phase = verification_phase(state)
    if phase == "checking":
        raise ValueError("a verification round is already open")
    if phase != "review":
        raise ValueError(
            "hand the build to the user and let him answer first: state.py handoff PROJECT"
        )
    if not quote.strip():
        raise ValueError("the user's own words giving the go-ahead are required")
    shown = state["verification"].get("handoff_fingerprint")
    if not isinstance(shown, dict):
        raise ValueError(
            "no record of which version he looked at; hand the build over "
            "again: state.py handoff PROJECT"
        )
    current = _plan_fingerprint(root)
    if any(shown.get(key) != current.get(key) for key in current):
        raise ValueError(
            "the build changed after he looked at it; hand this version over "
            "and let him answer again: state.py handoff PROJECT"
        )
    state["verification"]["phase"] = "checking"
    state["verification"]["review_quote"] = quote.strip()
    record(state, "begin-check", state["stage"])
    write_state(root, state)
    return preflight_state(state)


def cancel_check(root: Path, reason: str) -> dict:
    """Close an open round without a verdict and go back to fixing.

    The reason is what the round found; it goes into the history, because a
    round that ends without a verdict still produced a fact worth keeping.
    Fixing changes the tree, so the approval goes with the round it belonged
    to: the next round needs a fresh handoff and fresh words from the user.
    """
    state = read_state(root)
    if state["stage"] != "building" or verification_phase(state) != "checking":
        raise ValueError("there is no open verification round to cancel")
    if not reason.strip():
        raise ValueError("a reason is required: what did the round find?")
    state["verification"]["phase"] = "idle"
    state["verification"]["review_quote"] = None
    record(state, "cancel-check", state["stage"], note=reason.strip())
    write_state(root, state)
    return preflight_state(state)


def verify(root: Path, report=None) -> dict:
    """Record verification while building, from a validated site-check report.

    The report is the evidence. A status typed in by hand says nothing about
    what was actually checked, so there is no path to ``delivered`` that skips
    the protocol: the report must match this tree's fingerprints, respect the
    gating rules and state what each passing axis examined.
    """
    state = read_state(root)
    if state["stage"] != "building":
        raise ValueError("verification can only be recorded while building")
    if verification_phase(state) != "checking":
        raise ValueError(
            "no verification round is open; hand the build to the user first "
            "(state.py handoff PROJECT), then open one on his go-ahead "
            "(state.py begin-check PROJECT --quote \"his words\")"
        )
    if report is None:
        raise ValueError("verification requires --report, a site-check report")
    verdict = _check_verdict(root, report)
    if not verdict.get("valid"):
        reasons = list(verdict.get("errors") or [])
        if verdict.get("invalidated_axes"):
            reasons.append(
                "the report's fingerprints do not match the current tree; re-run "
                "the affected checks and write a fresh report for this tree"
            )
        raise ValueError(
            "check report does not hold for this tree: " + "; ".join(reasons or ["unknown"])
        )
    derived = _load_check_report(report, root)
    status = derived["status"]
    evidence = clean_items(derived["evidence"])
    limitations = clean_items(derived["limitations"])
    independent = derived["independent"]
    if not evidence:
        raise ValueError("at least one concrete evidence item is required")
    if state["mode"] == "strict" and status == "limited":
        raise ValueError("strict mode cannot be delivered with limited verification")
    if state["mode"] == "strict" and status == "verified" and not independent:
        raise ValueError("strict mode requires independent verification")

    old = state["stage"]
    prior = state["verification"]
    state["verification"] = {
        **blank_verification(),
        "status": status,
        "evidence": evidence,
        "limitations": limitations,
        "independent": independent,
        "checked_at": now(),
        # The round ran on the version he looked at. His words and the moment
        # he saw it stay, so delivery can name which build he approved.
        "handed_at": prior.get("handed_at"),
        "review_quote": prior.get("review_quote"),
        "handoff_fingerprint": prior.get("handoff_fingerprint"),
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
    # Coming back means going back to fixing, so no round is open any more.
    state["verification"]["phase"] = "idle"
    state["verification"]["review_quote"] = None
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
    state["verification"] = blank_verification()
    state["reopen_reason"] = reason.strip()
    state.pop("blocked_reason", None)
    state.pop("resume_stage", None)
    record(state, "reopen", old)
    write_state(root, state)
    return preflight_state(state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="minimal execution state")
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

    command = sub.add_parser(
        "handoff",
        help="hand the build to the user and wait for his go-ahead; "
             "no verification round opens before that",
    )
    command.add_argument("root", type=Path)

    command = sub.add_parser(
        "begin-check",
        help="open a verification round on the version the user approved; "
             "source writes stay blocked until it closes",
    )
    command.add_argument("root", type=Path)
    command.add_argument(
        "--quote", required=True,
        help="the user's own words giving the go-ahead, written down as he said them",
    )

    command = sub.add_parser(
        "cancel-check",
        help="close an open round without a verdict and go back to fixing",
    )
    command.add_argument("root", type=Path)
    command.add_argument("--reason", required=True)

    command = sub.add_parser("verify")
    command.add_argument("root", type=Path)
    command.add_argument(
        "--report", type=Path, required=True,
        help="path to a site-check report; validated against this tree by "
             "site-check/scripts/check.py before it is recorded",
    )

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
        elif args.action == "handoff":
            result = handoff(root)
        elif args.action == "begin-check":
            result = begin_check(root, args.quote)
        elif args.action == "cancel-check":
            result = cancel_check(root, args.reason)
        elif args.action == "verify":
            result = verify(root, report=args.report)
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
