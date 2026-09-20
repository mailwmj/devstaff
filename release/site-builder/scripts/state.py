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
import importlib.util as runtime_importlib
import secrets as runtime_secrets
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_runtime.common import Problem as RuntimeProblem, JsonParser as RuntimeParser, metadata_dir as runtime_metadata_dir, error_result as runtime_error_result
from site_runtime import contract as runtime_contract
RUNTIME_RISKS = ("sensitive_data", "money", "permissions", "external_write", "irreversible")

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
# The recorded brief is the evidence that the user was asked. state.py checks
# its shape only (like the contract block); the questions themselves belong to
# site-brief. Legacy schema_revision < 3 keeps its old gate until migrate.
BRIEF_REL_PATH = ".site/brief.md"
BRIEF_BLOCK_RE = re.compile(r"```brief\n(.*?)\n```", re.DOTALL)
BRIEF_FACT_SOURCES = ("user", "reused", "assumed")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_path(root: Path) -> Path:
    return runtime_metadata_dir(root) / 'state.json'


def read_state(root: Path) -> dict:
    path = state_path(root)
    if path.is_symlink(): raise RuntimeProblem('UNSAFE_PATH', 'state cannot be a symlink')
    if not path.is_file(): raise RuntimeProblem('STATE_MISSING','state does not exist; initialize it first','Run state.py init PROJECT.')
    state = json.loads(path.read_bytes())
    if not isinstance(state,dict): raise ValueError('state must be a JSON object')
    if type(state.get('version')) is not int or state['version']!=3: raise ValueError('unsupported state version')
    revision=state.get('schema_revision',1)
    if type(revision) is not int or revision not in (1,2,3): raise ValueError('unsupported state schema_revision')
    if state.get('mode') not in ('guided','strict') or state.get('stage') not in tuple(STAGES): raise ValueError('unsupported state')
    if 'decision' not in state and revision < 3 and state['stage'] == 'discovering':
        state['decision'] = {'confirmed': False, 'task': '', 'direction': '', 'include': [], 'exclude': [], 'quote': ''}
    decision=state.get('decision')
    if not isinstance(decision,dict) or type(decision.get('confirmed')) is not bool: raise ValueError('state decision.confirmed must be a boolean')
    if not isinstance(state.get('history'),list): raise ValueError('state history must be a list')
    if 'discovery' not in state and revision<3: state['discovery']=default_discovery()
    discovery=state.get('discovery')
    if not isinstance(discovery,dict) or not isinstance(discovery.get('structure'),dict): raise ValueError('state discovery must contain structure')
    if discovery['structure'].get('mode') not in tuple(STRUCTURE_MODES): raise ValueError('invalid structure mode')
    verification=state.get('verification')
    if verification is None and revision<3: verification=blank_verification()
    if not isinstance(verification,dict): raise ValueError('state verification must be an object')
    if 'phase' not in verification and revision<3: verification['phase']='idle'
    if verification.get('phase') not in tuple(VERIFICATION_PHASES): raise ValueError('invalid verification phase in state')
    state['verification']={**blank_verification(),**verification}
    state.setdefault('revision',0); state.setdefault('revisions',[])
    state.setdefault('delivery',{'scope':'preview','risks':[],'authorizations':[]})
    if not isinstance(state['revisions'],list) or not isinstance(state['delivery'],dict): raise ValueError('invalid revisions/delivery state')
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


def brief_path(root: Path) -> Path:
    return runtime_metadata_dir(root) / 'brief.md'


def _brief_block(root: Path) -> dict | None:
    """Parse the fenced brief block; None when file, fence or JSON is unusable."""
    path = brief_path(root)
    if not path.is_file():
        return None
    match = BRIEF_BLOCK_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _brief_problems(data: dict | None) -> list[str]:
    """Reasons a recorded brief cannot stand in for the user's answers.

    The gate checks shape, not truth: an agent can still write a false file,
    but it cannot skip the questions without writing the omission down where
    the confirmed decision and its hash point at it. Facts are user-stated
    (``user``), inherited from an earlier confirmation (``reused``) or
    explicitly assumed only after asking (``assumed`` + ``asked``).
    """
    if data is None:
        return [f'no readable brief block in {BRIEF_REL_PATH}']
    migrated = isinstance(data.get('migrated_from'), str) and bool(data['migrated_from'].strip())
    facts = data.get('facts')
    if not isinstance(facts, dict):
        return ['brief facts must be an object']
    if not facts and not migrated:
        return ['brief facts cannot be empty']
    for name, fact in facts.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(fact, dict):
            return ['each brief fact needs a name and an object']
        if not isinstance(fact.get('value'), str) or not fact['value'].strip():
            return [f'brief fact {name} needs a nonempty value']
        if fact.get('source') not in BRIEF_FACT_SOURCES:
            return [f'brief fact {name} source must be user, reused or assumed']
        if fact['source'] == 'assumed' and fact.get('asked') is not True:
            return [f'brief fact {name} is assumed without asked: true']
    assumptions = data.get('assumptions')
    if not isinstance(assumptions, list) or any(not isinstance(item, str) or not item.strip() for item in assumptions):
        return ['brief assumptions must be a list of plain-language lines']
    if any(fact['source'] == 'assumed' for fact in facts.values()) and not assumptions:
        return ['assumed brief facts need at least one plain-language assumption line']
    exclusions = data.get('exclusions')
    if not isinstance(exclusions, list) or any(not isinstance(item, str) or not item.strip() for item in exclusions):
        return ['brief exclusions must be a list']
    return []


def _recorded_brief_sha256(root: Path, state: dict) -> str | None:
    """Require the recorded brief for modern states; return its file hash.

    Schema revision < 3 projects keep their old gate until ``migrate``. For a
    modern project the brief is the record of what the user was asked; without
    it, ``decide`` would confirm a direction nobody stated.
    """
    if state.get('schema_revision', 1) < 3:
        return None
    problems = _brief_problems(_brief_block(root))
    if problems:
        raise RuntimeProblem(
            'BRIEF_REQUIRED',
            'the brief is not recorded: ' + '; '.join(problems),
            'Ask the first-version questions, record the answers and assumptions in '
            f'{BRIEF_REL_PATH} as a fenced brief block, then confirm the direction.',
        )
    return hashlib.sha256(brief_path(root).read_bytes()).hexdigest()


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


def preflight_state(state: dict, root: Path | None = None) -> dict:
    stage=state['stage']; modern=state.get('schema_revision',1)>=3
    structure=state.get('discovery',{}).get('structure',{})
    phase=verification_phase(state)
    pending=structure.get('mode')=='choice' and not structure.get('selected')
    unassessed=modern and structure.get('mode','undetermined')=='undetermined'
    # Without a root a modern project cannot prove the brief was recorded, so
    # the question gate stays closed instead of silently disappearing.
    brief_problems=_brief_problems(_brief_block(root) if root is not None else None)
    gate=None
    if stage=='discovering':
        action='present_structure_choice' if pending else 'prepare_and_confirm_direction'
        allowed=['ask_user','site-brief','site-design','discover','block','reopen','policy']
        if pending: allowed.append('select-structure')
        if not pending and not unassessed: allowed.append('decide')
        blocked=['write_source','start_build','deliver']
        if 'decide' not in allowed: blocked.append('decide')
        if modern and brief_problems:
            gate='brief_questions'; action='prepare_and_confirm_direction'
            allowed=['ask_user','site-brief','block','reopen','policy']
            blocked=['discover','select-structure','decide','write_source','start_build','deliver']
        elif modern:
            gate='structure_choice' if pending else (None if unassessed else 'direction_confirmation')
        else:
            gate='structure_choice' if pending else None
    elif stage=='decided':
        action,allowed,blocked='start_build',['start','reopen','block','policy'],['deliver','change_scope_silently']
    elif stage=='building':
        action,allowed,blocked=building_actions(phase)
        if modern and phase in ('idle','review'):
            action='build_then_verify' if phase=='idle' else 'collect_feedback_or_verify'
            if 'begin-check' not in allowed: allowed.append('begin-check')
            blocked=[x for x in blocked if x!='begin-check']
        if phase!='checking': allowed+=['revise','reopen','policy']
    elif stage=='blocked':
        action,allowed,blocked='resolve_blocker',['ask_user','resume','reopen','policy'],['write_source','deliver']
    else:
        action,allowed,blocked='report_delivery',['report','revise','reopen','policy'],['write_source','start_build']
    missing=[]
    if modern and brief_problems and stage=='discovering': missing.append('brief_record')
    if not state['decision']['confirmed']: missing.append('confirmed_direction')
    if unassessed: missing.append('structure_assessment')
    if pending: missing.append('structure_selection')
    if stage=='building' and phase in ('idle','review') and not modern: missing.append('user_review')
    if stage=='building' and phase=='checking': missing.append('check_report')
    if state['mode']=='strict' and stage=='building': missing.append('independent_verification')
    owner='site-design' if pending else ('site-check' if phase=='checking' else 'site-builder')
    if stage=='discovering' and gate=='brief_questions': owner='site-brief'
    if stage=='discovering':
        recorded=brief_path(root).is_file() if root is not None else False
        if gate=='brief_questions':
            inputs=[]; missing_inputs=[BRIEF_REL_PATH]
            outputs=[BRIEF_REL_PATH,'user questions']
            forbidden_outputs=['implementation_plan','source_changes','scaffold']
        else:
            inputs=[BRIEF_REL_PATH] if recorded else []
            missing_inputs=[] if recorded else [BRIEF_REL_PATH]
            if action=='present_structure_choice': outputs=['user choice']
            elif modern and unassessed: outputs=['structure assessment']
            else: outputs=['user confirmation']
            forbidden_outputs=[]
    else:
        inputs=[CONTRACT_REL_PATH,'.site/journal.md']; missing_inputs=[]
        outputs=['five-field receipt']; forbidden_outputs=[]
    return {'version':3,'schema_revision':state.get('schema_revision',1),'mode':state['mode'],'stage':stage,
            'next_action':action,'allowed_actions':list(dict.fromkeys(allowed)),'blocked_actions':blocked,
            'user_gate':gate,
            'action':{'id':action,'owner':owner,'inputs':inputs,'missing_inputs':missing_inputs,
                      'outputs':outputs,'forbidden_outputs':forbidden_outputs,'preconditions':missing,
                      'recovery':'Resolve the named prerequisite; keep valid decisions, then preflight.',
                      'needs_user':gate is not None or (stage=='building' and phase=='review' and not modern)},
            'missing':missing,'decision':{k:state['decision'].get(k) for k in ('confirmed','task','direction')},
            'discovery':state.get('discovery',default_discovery()),'verification':state['verification'],
            'delivery':state.get('delivery',{'scope':'preview','risks':[],'authorizations':[]}),
            'revision':state.get('revision',0),'blocked_reason':state.get('blocked_reason')}


def init(root: Path, mode: str, schema_revision: int = 3) -> dict:
    if type(schema_revision) is not int or schema_revision not in (2, 3):
        raise ValueError("unsupported new state schema_revision")
    if not root.is_dir():
        raise ValueError("project root must be an existing directory")
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(MODES))}")
    if state_path(root).exists():
        raise ValueError("state already exists")
    state = {
        "version": 3,
        "schema_revision": schema_revision,
        "revision": 0, "revisions": [],
        "delivery": {"scope": "preview", "risks": [], "authorizations": []},
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
    return preflight_state(state,root)


def decide(root: Path, task: str, direction: str, quote: str, include: list[str], exclude: list[str], message_id=None) -> dict:
    state=read_state(root)
    if state['stage']!='discovering': raise ValueError('a direction can only be confirmed while discovering')
    brief_sha256=_recorded_brief_sha256(root,state)
    if 'decide' not in preflight_state(state,root)['allowed_actions']:
        raise RuntimeProblem('STRUCTURE_DECISION_REQUIRED','assess/select the structure before confirming direction','Run discover, then select-structure if alternatives exist.')
    if not all(isinstance(x,str) and x.strip() for x in (task,direction,quote)): raise ValueError('task, direction and quote are required')
    old=state['stage']
    state['decision']={'confirmed':True,'task':task.strip(),'direction':direction.strip(),'quote':quote.strip(),'include':clean_items(include),'exclude':clean_items(exclude)}
    confirmation={'kind':'product_direction','revision':state.get('revision',0),'quote':quote.strip(),'message_id':message_id,
        'target_sha256':hashlib.sha256(json.dumps({k:state['decision'][k] for k in ('task','direction','include','exclude')},sort_keys=True).encode()).hexdigest()}
    if brief_sha256: confirmation['brief_sha256']=brief_sha256
    state['decision']['confirmation']=confirmation
    state['stage']='decided'; state['verification']=blank_verification()
    record(state,'decide',old); write_state(root,state); return preflight_state(state,root)


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
    if structure == "choice" and (len(candidates) < 2 or len(set(candidates)) != len(candidates)):
        raise ValueError("choice structure requires at least two distinct candidates")
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
    return preflight_state(state,root)


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
    return preflight_state(state,root)


def contract_path(root: Path) -> Path:
    return runtime_contract.path(root)


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
    if state.get("schema_revision", 1) not in (2, 3) or state["mode"] not in MODES:
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
    if report.get("passed") is not True:
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
    if state.get("schema_revision") in (2, 3):
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
    state["approved_contract_sha256"] = _contract_sha256(root)
    state["stage"] = "building"
    record(state, "start", old)
    write_state(root, state)
    result = preflight_state(state,root)
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


def _check_verdict(root: Path, report) -> dict:
    script=_check_script()
    if script is None: raise ValueError('cannot validate the check report: site-check/scripts/check.py was not found next to site-builder; install the skills as a bundle')
    spec=runtime_importlib.spec_from_file_location('site_check_validation',script)
    validator=runtime_importlib.module_from_spec(spec); spec.loader.exec_module(validator)
    return validator.validate_report_data(root,report) if isinstance(report,dict) else validator.validate_report(root,report)


def _load_check_report(report, root: Path) -> dict:
    data=report if isinstance(report,dict) else json.loads(Path(report).read_bytes())
    if not isinstance(data,dict): raise ValueError('check report must be a JSON object')
    if Path(str(data.get('project_root',''))).resolve()!=root.resolve(): raise ValueError('check report project_root does not match this project')
    if data.get('overall') not in tuple(VERIFY_STATUSES): raise ValueError('check report overall must be verified, limited or blocked')
    if type(data.get('independent',False)) is not bool: raise ValueError('independent must be a JSON boolean')
    return {'status':data['overall'],'evidence':data.get('evidence',[]),'limitations':data.get('limitations',[]),'independent':data.get('independent',False)}


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
    return preflight_state(state,root)


def begin_check(root: Path, quote: str='') -> dict:
    state=read_state(root)
    if state['stage']!='building': raise ValueError('a verification round only opens while building')
    phase=verification_phase(state)
    if phase=='checking': raise ValueError('a verification round is already open')
    modern=state.get('schema_revision',1)>=3
    current=_plan_fingerprint(root)
    if not modern:
        if phase!='review': raise ValueError('hand the build to the user first: state.py handoff PROJECT')
        if not quote.strip(): raise ValueError("the user's own words giving the go-ahead are required")
        shown=state['verification'].get('handoff_fingerprint')
        if not isinstance(shown,dict): raise ValueError('no record of which version he looked at; handoff again')
        if shown!=current: raise ValueError('the build changed after he looked at it; handoff the current version again')
    elif quote.strip() and (phase!='review' or state['verification'].get('handoff_fingerprint')!=current):
        raise ValueError('review quote requires a handoff of this current version')
    state['verification'].update(phase='checking',round_fingerprint=current,round_id=runtime_secrets.token_hex(12),review_quote=quote.strip() or None,execution_scope='isolated_checks_only')
    record(state,'begin-check',state['stage']); write_state(root,state); return preflight_state(state,root)


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
    return preflight_state(state,root)


def verify(root: Path, report=None) -> dict:
    state=read_state(root)
    entry_state_bytes=state_path(root).read_bytes()
    if state['stage']!='building': raise ValueError('verification can only be recorded while building')
    if verification_phase(state)!='checking': raise ValueError('no verification round is open; run begin-check before verify')
    if report is None: raise ValueError('verification requires --report, a site-check report')
    modern=state.get('schema_revision',1)>=3
    shown=state['verification'].get('round_fingerprint') or state['verification'].get('handoff_fingerprint')
    current=_plan_fingerprint(root)
    if not isinstance(shown,dict) or shown!=current:
        raise ValueError('the source or contract changed during verification; cancel-check and write a fresh report in a new round')
    # Read ONCE. Validation and recording consume the same immutable snapshot.
    payload=json.loads(Path(report).read_bytes())
    if not isinstance(payload,dict): raise ValueError('check report must be a JSON object')
    if modern and payload.get('round_id')!=state['verification'].get('round_id'):
        raise RuntimeProblem('ROUND_MISMATCH','report is not bound to the open round','Read check.py plan after begin-check and run a current check.')
    verdict=_check_verdict(root,payload)
    if not verdict.get('valid'):
        reasons=list(verdict.get('errors') or [])
        if verdict.get('invalidated_axes'): reasons.append('fingerprints changed; write a fresh report')
        raise ValueError('check report does not hold for this tree: '+'; '.join(reasons or ['unknown']))
    derived=_load_check_report(payload,root)
    if _plan_fingerprint(root)!=current or state_path(root).read_bytes()!=entry_state_bytes:
        raise RuntimeProblem('VERSION_CHANGED','source, contract or policy changed during report validation')
    status=derived['status']; evidence=clean_items(derived['evidence']); limits=clean_items(derived['limitations']); independent=derived['independent']
    if not evidence: raise ValueError('at least one concrete evidence item is required')
    if state['mode']=='strict' and status=='limited': raise ValueError('strict mode cannot be delivered with limited verification')
    if state['mode']=='strict' and status=='verified' and not independent: raise ValueError('strict mode requires independent verification')
    if modern and status!='blocked':
        axes=payload.get('axes',{})
        for key in ('contract','static_build','core_task','negative_path'):
            if axes.get(key,{}).get('status')!='verified':
                raise RuntimeProblem('CORE_NOT_VERIFIED','core and static checks must be verified before usable delivery','Return a preview or rerun the missing checks; do not call it usable.')
    old=state['stage']; prior=state['verification']
    state['verification']={**blank_verification(),'status':status,'evidence':evidence,'limitations':limits,'independent':independent,'checked_at':now(),
        'handed_at':prior.get('handed_at'),'review_quote':prior.get('review_quote'),'handoff_fingerprint':prior.get('handoff_fingerprint'),
        'round_id':prior.get('round_id'),'round_fingerprint':current,'report_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()}
    if status=='blocked':
        state['stage']='blocked'; state['blocked_reason']=limits[0] if limits else evidence[0]; state['resume_stage']='building'
    else:
        state['stage']='delivered'; state.pop('blocked_reason',None); state.pop('resume_stage',None)
    record(state,'verify',old); write_state(root,state); return preflight_state(state,root)


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
    return preflight_state(state,root)


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
    return preflight_state(state,root)


def reopen(root: Path, reason: str) -> dict:
    return revise(root,'scope',reason)


def build_parser() -> argparse.ArgumentParser:
    parser=RuntimeParser(description='Versioned execution state. New projects use schema revision 3.')
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('init');p.add_argument('root',type=Path);p.add_argument('--mode',choices=sorted(MODES),default='guided');p.add_argument('--schema-revision',type=int,choices=[2,3],default=3)
    for name in ('preflight','resume','handoff','migrate'):
        sub.add_parser(name).add_argument('root',type=Path)
    p=sub.add_parser('start');p.add_argument('root',type=Path);p.add_argument('--contract-report',type=Path)
    p=sub.add_parser('decide');p.add_argument('root',type=Path)
    for field in ('task','direction','quote'):p.add_argument('--'+field,required=True)
    for field in ('include','exclude'):p.add_argument('--'+field,action='append',default=[])
    p.add_argument('--message-id')
    p=sub.add_parser('discover');p.add_argument('root',type=Path);p.add_argument('--structure',choices=['single','choice'],required=True);p.add_argument('--reason',required=True)
    p.add_argument('--axis',action='append',default=[]);p.add_argument('--candidate',action='append',default=[])
    p=sub.add_parser('select-structure');p.add_argument('root',type=Path);p.add_argument('--candidate',required=True);p.add_argument('--quote',required=True)
    p=sub.add_parser('begin-check');p.add_argument('root',type=Path);p.add_argument('--quote',default='')
    p=sub.add_parser('verify');p.add_argument('root',type=Path);p.add_argument('--report',type=Path,required=True)
    for name in ('cancel-check','block','reopen'):
        p=sub.add_parser(name);p.add_argument('root',type=Path);p.add_argument('--reason',required=True)
    p=sub.add_parser('revise');p.add_argument('root',type=Path);p.add_argument('--change-kind',choices=['local','feature','scope'],required=True);p.add_argument('--reason',required=True);p.add_argument('--risk',action='append',default=[])
    p=sub.add_parser('policy');p.add_argument('root',type=Path);p.add_argument('--scope',choices=['preview','personal','shared','public'],required=True);p.add_argument('--risk',action='append',default=[]);p.add_argument('--quote',default='')
    return parser


def main() -> int:
    try:
        a=build_parser().parse_args();root=a.root.resolve()
        if a.action=='init':result=init(root,a.mode,schema_revision=a.schema_revision)
        elif a.action=='preflight':result=preflight_state(read_state(root),root)
        elif a.action=='decide':result=decide(root,a.task,a.direction,a.quote,a.include,a.exclude,a.message_id)
        elif a.action=='discover':result=discover(root,a.structure,a.reason,a.axis,a.candidate)
        elif a.action=='select-structure':result=select_structure(root,a.candidate,a.quote)
        elif a.action=='start':result=start(root,contract_report=a.contract_report)
        elif a.action=='handoff':result=handoff(root)
        elif a.action=='begin-check':result=begin_check(root,a.quote)
        elif a.action=='cancel-check':result=cancel_check(root,a.reason)
        elif a.action=='verify':result=verify(root,a.report)
        elif a.action=='block':result=block(root,a.reason)
        elif a.action=='resume':result=resume(root)
        elif a.action=='reopen':result=reopen(root,a.reason)
        elif a.action=='revise':result=revise(root,a.change_kind,a.reason,a.risk)
        elif a.action=='policy':result=set_policy(root,a.scope,a.risk,a.quote)
        else:result=migrate_state(root)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps(runtime_error_result(exc),ensure_ascii=False));return 2




def revise(root: Path, change_kind: str, reason: str, risks=None) -> dict:
    state=read_state(root)
    if change_kind not in ('local','feature','scope') or not reason.strip(): raise ValueError('revise needs local/feature/scope and a reason')
    if verification_phase(state)=='checking': raise ValueError('cancel-check before revising a checked version')
    risks=list(risks or [])
    if any(r not in RUNTIME_RISKS for r in risks): raise ValueError('unknown risk')
    if change_kind=='local' and (risks or not state['decision']['confirmed']): raise ValueError('local revision needs a confirmed direction and cannot add risk')
    if change_kind=='local' and state.get('approved_contract_sha256') and _contract_sha256(root)!=state['approved_contract_sha256']:
        raise ValueError('contract changed; classify this as feature or scope')
    old=state['stage']
    state['revisions'].append({'revision':state.get('revision',0),'decision':state['decision'],'discovery':state['discovery'],'verification':state['verification'],'kind':change_kind,'reason':reason.strip(),'at':now()})
    state['revision']=state.get('revision',0)+1; state['change_kind']=change_kind; state['verification']=blank_verification()
    if change_kind=='local': state['stage']='building'
    elif change_kind=='feature':
        state['stage']='discovering'; state['decision']={**state['decision'],'confirmed':False,'quote':''}
        if state['discovery']['structure']['mode']=='undetermined': state['discovery']['structure'].update(mode='single',reason='inherit confirmed project')
    else:
        state['stage']='discovering'; state['decision']={'confirmed':False,'task':'','direction':'','include':[],'exclude':[],'quote':''}; state['discovery']=default_discovery()
    state['delivery']['risks']=sorted(set(state['delivery'].get('risks',[]))|set(risks))
    if risks: state['mode']='strict'
    state['delivery']['authorizations']=[]; state['reopen_reason']=reason.strip()
    state.pop('blocked_reason',None); state.pop('resume_stage',None)
    record(state,'revise',old,reason.strip()); write_state(root,state); return preflight_state(state,root)


def set_policy(root: Path, scope: str, risks: list[str], quote: str='') -> dict:
    state=read_state(root); old=state['stage']
    if verification_phase(state)=='checking': raise ValueError('cancel-check before changing delivery policy')
    if scope not in ('preview','personal','shared','public') or any(r not in RUNTIME_RISKS for r in risks): raise ValueError('invalid delivery scope or risk')
    if not set(state['delivery'].get('risks',[])).issubset(risks): raise ValueError('risk removal requires an explicitly reviewed scope revision')
    if scope=='shared': risks=sorted(set(risks)|{'permissions'})
    state['delivery']={'scope':scope,'risks':risks,'authorizations':[]}
    if risks: state['mode']='strict'
    if quote.strip(): state['delivery']['authorizations'].append({'scope':scope,'quote':quote.strip(),'revision':state.get('revision',0),'at':now(),'not_a_publish_token':True})
    state['verification']=blank_verification()
    if old=='delivered': state['stage']='building'
    record(state,'policy',old); write_state(root,state); return preflight_state(state,root)


def _seed_migrated_brief(root: Path) -> Path | None:
    """Give a migrated legacy project a brief so the new gate has an anchor.

    The seed carries no facts because revision 1/2 projects never recorded
    them in that shape. It is marked so the gate accepts it and a later reader
    can tell it apart from an agent-written brief.
    """
    path = brief_path(root)
    if path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    block = {'facts': {}, 'assumptions': [], 'exclusions': [], 'migrated_from': 'schema_revision_2'}
    path.write_text(
        '# 需求记录（由 state.py migrate 从旧状态生成）\n\n'
        '旧项目不重复提问；后续范围变更时补齐 `facts`，来源只能是 user / reused / assumed。\n\n'
        '```brief\n' + json.dumps(block, ensure_ascii=False, indent=2) + '\n```\n',
        encoding='utf-8',
    )
    return path


def migrate_state(root: Path) -> dict:
    state=read_state(root)
    if state.get('schema_revision')==3: return preflight_state(state,root)
    if verification_phase(state)=='checking': raise ValueError('cancel-check before migrating state')
    path=state_path(root); backup=path.with_name('state.'+hashlib.sha256(path.read_bytes()).hexdigest()[:12]+'.bak.json')
    if not backup.exists(): backup.write_bytes(path.read_bytes())
    brief=_seed_migrated_brief(root)
    state['schema_revision']=3; state['verification']=blank_verification()
    if state['stage']=='delivered': state['stage']='building'
    note='backup: '+backup.name+('; brief seeded' if brief else '')
    record(state,'migrate',state['stage'],note); write_state(root,state)
    result={**preflight_state(state,root),'migration_backup':str(backup)}
    if brief is not None: result['migration_brief']=str(brief)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
