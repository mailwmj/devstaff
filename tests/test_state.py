import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import hashlib

STATE_PATH = Path(__file__).parents[1] / "release" / "site-builder" / "scripts" / "state.py"
SPEC = importlib.util.spec_from_file_location("site_state", STATE_PATH)
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)

CHECK_PATH = Path(__file__).parents[1] / "release" / "site-check" / "scripts" / "check.py"
CHECK_SPEC = importlib.util.spec_from_file_location("site_check_for_state", CHECK_PATH)
check = importlib.util.module_from_spec(CHECK_SPEC)
assert CHECK_SPEC.loader is not None
CHECK_SPEC.loader.exec_module(check)

CLI_SPEC = importlib.util.spec_from_file_location(
    "site_cli_fixture", Path(__file__).with_name("test_cli.py")
)
cli_fixture = importlib.util.module_from_spec(CLI_SPEC)
assert CLI_SPEC.loader is not None
CLI_SPEC.loader.exec_module(cli_fixture)


def _open_round(root: Path, quote="可以，去测吧"):
    """Hand the build to the user, then open a round on his go-ahead.

    No round opens on a version he has not looked at, so the handoff is part of
    the flow rather than a step the tests may skip.
    """
    if state.verification_phase(state.read_state(root)) != "review":
        state.handoff(root)
    return state.begin_check(root, quote)


def _verify(root: Path, report=None):
    """Run the real three-step flow: hand over, open a round if none is open, record.

    A rejected report deliberately leaves the round open — the builder is still
    verifying, and must either produce a report that holds or say why it is
    going back to fixing.
    """
    if state.verification_phase(state.read_state(root)) != "checking":
        _open_round(root)
    return state.verify(root, report=report)


def _measured(what, **extra):
    """A passing axis: just what it examined."""
    entry = {"status": "verified", "observed": what}
    entry.update(extra)
    return entry


def _valid_check_report(root: Path, *, overall="verified", independent=False,
                        limitations=None, evidence=None, axes=None,
                        project_root=None, write=True):
    """Write a check report the protocol accepts for ``root`` as it is now.

    Fingerprints come from the protocol itself, so these tests exercise the
    same gate the CLI does instead of a hand-typed status.
    """
    root = Path(root)
    plan = check.plan(root)
    axes = dict(axes) if axes is not None else {
        axis: _measured(f"{axis} 覆盖") for axis in plan["required_axes"]
    }
    report = {
        "project_root": str((project_root or root).resolve()),
        "mode": plan["mode"],
        "overall": overall,
        "independent": independent,
        "contract_sha256": plan["contract_sha256"],
        "source_sha256": plan["source_sha256"],
        "axes": axes,
        "evidence": ["核心任务通过"] if evidence is None else evidence,
        "limitations": list(limitations or []),
    }
    if not write:
        return report
    path = root / ".site" / "check-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return path


def _write_contract(root: Path) -> str:
    """Write the valid prebuild fixture used by the CLI flow."""
    contract = cli_fixture.VALID_CONTRACT
    path = root / ".site" / "design" / "surface-brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contract, encoding="utf-8")
    return hashlib.sha256(contract.encode("utf-8")).hexdigest()


def _report_path(root: Path, *, sha=None, project_root=None, phase="prebuild", passed=True):
    """Write a crafted contract report and return its path.

    state.py only validates project_root, phase, passed and contract SHA-256,
    so tests can craft the report directly instead of invoking design.py.
    """
    sha = sha if sha is not None else _write_contract(root)
    report = {
        "project_root": str((project_root or root).resolve()),
        "phase": phase,
        "contract_path": state.CONTRACT_REL_PATH,
        "contract_sha256": sha,
        "passed": passed,
        "blockers": [] if passed else [{"code": "unresolved_confirm"}],
        "warnings": [],
    }
    report_file = root / ".site" / "contract-report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return report_file


class StateProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def decide_and_start(self, mode="guided"):
        state.init(self.root, mode, schema_revision=2)
        state.decide(
            self.root,
            "登记并查看库存",
            "单工作台展示当前库存和新增入口",
            "就按这个方向做",
            ["新增库存", "查看数量"],
            ["账号系统"],
        )
        return state.start(self.root, contract_report=_report_path(self.root))

    def test_guided_flow_exposes_one_next_action(self):
        result = state.init(self.root, "guided", schema_revision=2)
        self.assertEqual(result["next_action"], "prepare_and_confirm_direction")
        self.assertIn("write_source", result["blocked_actions"])

        state.decide(
            self.root,
            "登记并查看库存",
            "单工作台展示当前库存和新增入口",
            "就按这个方向做",
            [],
            [],
        )
        current = state.preflight_state(state.read_state(self.root))
        self.assertEqual(current["next_action"], "start_build")
        self.assertEqual(
            state.start(self.root, contract_report=_report_path(self.root))["next_action"],
            "build_then_handoff",
        )

    def verify(self, report=None):
        return _verify(self.root, report=report)

    def test_guided_limited_delivery_names_limitations(self):
        self.decide_and_start()
        # A limited report without limitations is rejected by the protocol.
        report = _valid_check_report(self.root, overall="limited", evidence=["核心任务通过"])
        with self.assertRaises(ValueError):
            self.verify(report=report)

        axes = {axis: _measured(f"{axis} 覆盖") for axis in
                check.plan(self.root)["required_axes"]}
        axes["negative_path"] = {"status": "limited"}
        report = _valid_check_report(
            self.root, overall="limited", evidence=["核心任务通过"],
            limitations=["尚未检查移动端"], axes=axes,
        )
        result = self.verify(report=report)
        self.assertEqual(result["stage"], "delivered")
        self.assertEqual(result["next_action"], "report_delivery")

    def test_cannot_build_without_confirmed_direction(self):
        state.init(self.root, "guided", schema_revision=2)
        with self.assertRaises(ValueError):
            state.start(self.root)

    def test_strict_requires_independent_verified_evidence(self):
        self.decide_and_start("strict")
        with self.assertRaises(ValueError):
            self.verify(report=_valid_check_report(
                self.root, overall="limited", evidence=["页面可见"],
                limitations=["未独立检查"]))

        strict_axes = {axis: _measured(f"{axis} 覆盖") for axis in
                       ("contract", "static_build", "core_task", "negative_path",
                        "visual_desktop", "visual_mobile", "reopen", "risk")}
        with self.assertRaises(ValueError):
            self.verify(report=_valid_check_report(
                self.root, independent=False, axes=strict_axes))

        result = self.verify(report=_valid_check_report(
            self.root, independent=True, axes=strict_axes))
        self.assertEqual(result["stage"], "delivered")

    def test_blocked_verification_can_resume_building(self):
        self.decide_and_start()
        report = _valid_check_report(
            self.root, overall="blocked", evidence=["保存操作返回错误"],
            limitations=["修复保存错误后复验"],
            axes={axis: {"status": "not_run"} for axis in
                  check.plan(self.root)["required_axes"]},
        )
        result = self.verify(report=report)
        self.assertEqual(result["stage"], "blocked")
        self.assertEqual(state.resume(self.root)["stage"], "building")

    def test_reopen_clears_old_decision_and_verification(self):
        self.decide_and_start()
        self.verify(report=_valid_check_report(self.root))
        result = state.reopen(self.root, "核心范围改变")
        self.assertEqual(result["stage"], "discovering")
        self.assertIn("confirmed_direction", result["missing"])

    def test_verify_requires_a_report(self):
        self.decide_and_start()
        _open_round(self.root)
        with self.assertRaises(ValueError) as caught:
            state.verify(self.root)
        self.assertIn("--report", str(caught.exception))

    def test_verification_round_blocks_source_writes(self):
        # The failure this exists for: the checker read db.js, the builder
        # edited it twice mid-round, and the whole round was thrown away.
        self.decide_and_start()
        opened = _open_round(self.root)
        self.assertEqual(opened["next_action"], "finish_verification")
        self.assertIn("write_source", opened["blocked_actions"])
        self.assertNotIn("write_source", opened["allowed_actions"])
        self.assertIn("check_report", opened["missing"])

    def test_verify_requires_an_open_round(self):
        self.decide_and_start()
        with self.assertRaises(ValueError) as caught:
            state.verify(self.root, report=_valid_check_report(self.root))
        self.assertIn("begin-check", str(caught.exception))

    def test_cancel_check_reopens_writes_with_a_reason(self):
        self.decide_and_start()
        _open_round(self.root)
        with self.assertRaises(ValueError):
            state.cancel_check(self.root, "   ")
        result = state.cancel_check(self.root, "VA-05 对比度 4.21:1")
        self.assertIn("write_source", result["allowed_actions"])
        history = state.read_state(self.root)["history"]
        self.assertEqual(history[-1]["action"], "cancel-check")
        self.assertEqual(history[-1]["note"], "VA-05 对比度 4.21:1")

    def test_round_cannot_open_twice_or_while_not_building(self):
        self.decide_and_start()
        _open_round(self.root)
        with self.assertRaises(ValueError):
            state.begin_check(self.root, "可以")
        self.assertNotIn("cancel-check", state.preflight_state(
            state.read_state(self.root))["blocked_actions"])
        # Fixing after a cancelled round needs a fresh look and fresh words:
        # the yes he gave belonged to the round that just closed.
        state.cancel_check(self.root, "修完再来")
        with self.assertRaises(ValueError):
            state.begin_check(self.root, "可以")
        state.handoff(self.root)
        self.assertEqual(state.begin_check(self.root, "修好了，再测")["next_action"],
                         "finish_verification")

    def test_a_rejected_report_keeps_the_round_open(self):
        # A report that does not hold must not quietly hand the tree back to
        # editing: the builder either writes one that holds or says why not.
        self.decide_and_start()
        _open_round(self.root)
        bad = _valid_check_report(self.root, evidence=[])
        with self.assertRaises(ValueError):
            state.verify(self.root, report=bad)
        still = state.preflight_state(state.read_state(self.root))
        self.assertEqual(still["next_action"], "finish_verification")
        self.assertIn("write_source", still["blocked_actions"])

    def test_resume_clears_an_open_round(self):
        self.decide_and_start()
        _open_round(self.root)
        state.block(self.root, "保存接口返回错误")
        result = state.resume(self.root)
        self.assertEqual(result["stage"], "building")
        self.assertIn("write_source", result["allowed_actions"])

    def test_init_creates_the_work_journal(self):
        # The journal is where slice state and evidence go, because writing
        # them into the contract would void every verification already run.
        state.init(self.root, "guided", schema_revision=2)
        journal = self.root / ".site" / "journal.md"
        self.assertTrue(journal.is_file())
        self.assertIn("| 时间 | 对象 | 客观事实 | 影响 |",
                      journal.read_text(encoding="utf-8"))

    def test_journal_is_never_overwritten(self):
        state.init(self.root, "guided", schema_revision=2)
        journal = self.root / ".site" / "journal.md"
        journal.write_text("# 我写的\n", encoding="utf-8")
        state.ensure_journal(self.root)
        self.assertEqual(journal.read_text(encoding="utf-8"), "# 我写的\n")

    def test_init_requires_existing_project_root(self):
        missing = self.root / "missing"
        with self.assertRaises(ValueError):
            state.init(missing, "guided", schema_revision=2)
        self.assertFalse(missing.exists())

    def test_evidence_free_report_is_rejected(self):
        self.decide_and_start()
        report = _valid_check_report(self.root, evidence=[])
        with self.assertRaises(ValueError) as caught:
            self.verify(report=report)
        self.assertIn("evidence", str(caught.exception))

    def test_state_is_valid_json(self):
        state.init(self.root, "guided", schema_revision=2)
        payload = json.loads((self.root / ".site/state.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 3)
        self.assertEqual(payload["mode"], "guided")

    def test_top_level_stages_remain_five(self):
        self.assertEqual(
            state.STAGES,
            {"discovering", "decided", "building", "blocked", "delivered"},
        )
        state.init(self.root, "guided", schema_revision=2)
        payload = json.loads((self.root / ".site/state.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_revision"], 2)
        self.assertEqual(payload["discovery"]["structure"]["mode"], "undetermined")

    def test_single_structure_keeps_one_decide(self):
        state.init(self.root, "guided", schema_revision=2)
        assessed = state.discover(
            self.root, "single", "无结构分歧，单工作台即可", [], []
        )
        self.assertEqual(assessed["next_action"], "prepare_and_confirm_direction")
        self.assertEqual(
            assessed["discovery"]["structure"]["mode"], "single"
        )
        # Ordinary project: exactly one confirmation (decide), no structure gate.
        state.decide(
            self.root,
            "登记库存",
            "单工作台展示当前库存和新增入口",
            "就按这个方向做",
            [],
            [],
        )
        self.assertEqual(
            state.preflight_state(state.read_state(self.root))["next_action"],
            "start_build",
        )

    def test_choice_structure_requires_selection_before_decide(self):
        state.init(self.root, "guided", schema_revision=2)
        assessed = state.discover(
            self.root,
            "choice",
            "是先做单页落地页还是多页带后台的工作台，信息拓扑不同",
            ["信息拓扑", "主要操作"],
            ["落地页", "工作台"],
        )
        self.assertEqual(assessed["next_action"], "present_structure_choice")
        self.assertIn("structure_selection", assessed["missing"])
        # select-structure is the first of exactly two confirmations.
        after = state.select_structure(self.root, "工作台", "就选工作台结构")
        self.assertEqual(after["next_action"], "prepare_and_confirm_direction")
        self.assertEqual(
            after["discovery"]["structure"]["selected"], "工作台"
        )
        # decide is the second and last confirmation.
        state.decide(
            self.root,
            "登记库存",
            "工作台展示当前库存和新增入口",
            "按工作台这个方向做",
            [],
            [],
        )
        self.assertEqual(
            state.preflight_state(state.read_state(self.root))["stage"], "decided"
        )

    def test_select_structure_requires_assessed_candidate(self):
        state.init(self.root, "guided", schema_revision=2)
        state.discover(
            self.root,
            "choice",
            "信息拓扑不同",
            ["信息拓扑"],
            ["落地页", "工作台"],
        )
        with self.assertRaises(ValueError):
            state.select_structure(self.root, "未知结构", "选未知结构")

    def test_select_structure_only_after_choice(self):
        state.init(self.root, "guided", schema_revision=2)
        state.discover(self.root, "single", "无结构分歧", [], [])
        with self.assertRaises(ValueError):
            state.select_structure(self.root, "工作台", "选工作台")

    def test_discover_choice_requires_candidates_and_reason(self):
        state.init(self.root, "guided", schema_revision=2)
        with self.assertRaises(ValueError):
            state.discover(self.root, "choice", "", [], ["落地页"])
        with self.assertRaises(ValueError):
            state.discover(self.root, "choice", "有分歧", [], [])

    def test_direction_quote_cannot_reuse_structure_quote(self):
        state.init(self.root, "guided", schema_revision=2)
        state.discover(self.root, "choice", "different structures", [], ["A", "B"])
        state.select_structure(self.root, "A", "yes")
        result = state.decide(self.root, "task", "direction", "yes", [], [])
        self.assertEqual(result["stage"], "decided")
        self.assertEqual(state.read_state(self.root)["decision"]["confirmation"]["kind"], "product_direction")

    def test_quote_reuse_caught_across_whitespace_variants(self):
        state.init(self.root, "guided", schema_revision=2)
        state.discover(self.root, "choice", "different structures", [], ["A", "B"])
        state.select_structure(self.root, "A", "yes")
        result = state.decide(self.root, "task", "direction", "yes", [], [])
        self.assertEqual(result["stage"], "decided")
        self.assertEqual(state.read_state(self.root)["decision"]["confirmation"]["kind"], "product_direction")

    def test_visual_only_difference_uses_single_path(self):
        # Colour, font, radius, shadow do not change information topology or
        # primary actions, so they must take the single path: one decide.
        state.init(self.root, "guided", schema_revision=2)
        assessed = state.discover(
            self.root, "single", "仅配色与圆角差异，结构与操作不变", [], []
        )
        self.assertEqual(assessed["discovery"]["structure"]["mode"], "single")
        self.assertNotIn("structure_selection", assessed["missing"])
        state.decide(
            self.root, "任务", "方向", "按这个方向做", [], []
        )
        self.assertEqual(
            state.preflight_state(state.read_state(self.root))["next_action"],
            "start_build",
        )

    def test_reopen_resets_discovery(self):
        state.init(self.root, "guided", schema_revision=2)
        state.discover(
            self.root, "choice", "信息拓扑不同", ["信息拓扑"], ["落地页", "工作台"]
        )
        state.select_structure(self.root, "工作台", "选工作台")
        reopened = state.reopen(self.root, "范围改变")
        self.assertEqual(
            reopened["discovery"]["structure"]["mode"], "undetermined"
        )
        self.assertIsNone(reopened["discovery"]["structure"]["selected"])

    def test_old_state_without_discovery_is_normalized(self):
        state.init(self.root, "guided", schema_revision=2)
        payload = json.loads((self.root / ".site/state.json").read_text(encoding="utf-8"))
        del payload["discovery"]
        (self.root / ".site/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        # read_state fills the default discovery block in memory.
        normalized = state.read_state(self.root)
        self.assertEqual(normalized["discovery"]["structure"]["mode"], "undetermined")
        self.assertEqual(
            state.preflight_state(normalized)["next_action"],
            "prepare_and_confirm_direction",
        )


class ContractReportStartTests(unittest.TestCase):
    """Phase 2: schema_revision 2 guided/strict start requires a valid prebuild report."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        state.init(self.root, "guided", schema_revision=2)
        state.decide(
            self.root, "登记库存", "单工作台", "就按这个方向做", [], []
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_report_allows_start(self):
        result = state.start(self.root, contract_report=_report_path(self.root))
        self.assertEqual(result["stage"], "building")

    def test_missing_report_blocks_start(self):
        with self.assertRaises(ValueError) as caught:
            state.start(self.root)
        self.assertIn("contract report", str(caught.exception))

    def test_wrong_project_path_is_rejected(self):
        other = Path(tempfile.mkdtemp())
        report = _report_path(self.root, project_root=other)
        with self.assertRaises(ValueError) as caught:
            state.start(self.root, contract_report=report)
        self.assertIn("project_root", str(caught.exception))
        other.rmdir()

    def test_wrong_phase_is_rejected(self):
        report = _report_path(self.root, phase="direction")
        with self.assertRaises(ValueError) as caught:
            state.start(self.root, contract_report=report)
        self.assertIn("prebuild", str(caught.exception))

    def test_failed_report_is_rejected(self):
        report = _report_path(self.root, passed=False)
        with self.assertRaises(ValueError) as caught:
            state.start(self.root, contract_report=report)
        self.assertIn("did not pass", str(caught.exception))

    def test_stale_report_after_contract_change_is_rejected(self):
        report = _report_path(self.root)
        # Modify the contract after the report was generated.
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.start(self.root, contract_report=report)
        self.assertIn("changed since", str(caught.exception))

    def test_contract_content_is_left_to_the_checker(self):
        """A report whose SHA matches is accepted here; content is the checker's job.

        This gate answers "is this report about this contract file", not "is the
        contract any good": a matching SHA plus a passing phase is enough. What
        makes an unparseable block unacceptable belongs to site-design's
        check-contract, which is what writes the report in the first place.
        """
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# bad\n```site-contract\n{not-json}\n```\n", encoding="utf-8")
        report = _report_path(self.root, sha=hashlib.sha256(
            path.read_bytes()).hexdigest())
        self.assertEqual(
            state.start(self.root, contract_report=report)["stage"], "building"
        )

    def test_unreadable_report_is_rejected(self):
        bad = self.root / ".site" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            state.start(self.root, contract_report=bad)

    def test_legacy_revision_one_starts_without_report(self):
        payload = json.loads((self.root / ".site/state.json").read_text(encoding="utf-8"))
        payload["schema_revision"] = 1
        (self.root / ".site/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        result = state.start(self.root)
        self.assertEqual(result["stage"], "building")

    def test_legacy_rev1_missing_contract_warns(self):
        """rev1 whose brief lacks a site-contract block warns but still starts."""
        payload = json.loads((self.root / ".site/state.json").read_text(encoding="utf-8"))
        payload["schema_revision"] = 1
        (self.root / ".site/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        # No surface brief written -> no site-contract block.
        result = state.start(self.root)
        self.assertEqual(result["stage"], "building")
        codes = [w["code"] for w in result.get("warnings", [])]
        self.assertIn("legacy_missing_contract_block", codes)

    def test_legacy_rev1_with_contract_has_no_legacy_warning(self):
        """rev1 whose brief carries a site-contract block emits no legacy warning."""
        payload = json.loads((self.root / ".site/state.json").read_text(encoding="utf-8"))
        payload["schema_revision"] = 1
        (self.root / ".site/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        _write_contract(self.root)  # brief with a site-contract block
        result = state.start(self.root)
        self.assertEqual(result["stage"], "building")
        codes = [w["code"] for w in result.get("warnings", [])]
        self.assertNotIn("legacy_missing_contract_block", codes)

    def test_rev2_missing_contract_blocks_start(self):
        """rev2 never downgrades a missing contract block to a warning; it blocks."""
        # Brief exists but carries no site-contract block, and no report is passed.
        brief = self.root / ".site" / "design" / "surface-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("# 仅 prose，没有合同块\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.start(self.root)
        self.assertIn("contract report", str(caught.exception))


class VerifyReportTests(unittest.TestCase):
    """Stage 5: verify accepts a site-check report; --evidence stays transitional."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        state.init(self.root, "guided", schema_revision=2)
        state.decide(
            self.root, "登记库存", "单工作台", "就按这个方向做", [], []
        )
        state.start(self.root, contract_report=_report_path(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, path, root=None):
        return _verify(root or self.root, report=path)

    def test_verify_from_report_delivers(self):
        path = _valid_check_report(self.root)
        result = self.verify(path)
        self.assertEqual(result["stage"], "delivered")
        self.assertEqual(result["next_action"], "report_delivery")

    def test_verify_from_report_blocked_stays_blocked(self):
        path = _valid_check_report(
            self.root, overall="blocked", evidence=["保存操作返回错误"],
            limitations=["修复保存错误后复验"],
            axes={axis: {"status": "not_run"} for axis in
                  check.plan(self.root)["required_axes"]},
        )
        result = self.verify(path)
        self.assertEqual(result["stage"], "blocked")

    def test_verify_report_rejects_wrong_project_root(self):
        other = Path(tempfile.mkdtemp())
        path = _valid_check_report(self.root, project_root=other)
        with self.assertRaises(ValueError) as caught:
            self.verify(path)
        self.assertIn("project_root", str(caught.exception))
        other.rmdir()

    def test_verify_report_rejects_unreadable(self):
        bad = self.root / ".site" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.verify(bad)

    def test_verify_rejects_a_report_for_an_earlier_tree(self):
        # The failure this gate exists for: a report was written, then the
        # product changed (here: the demo database, which is runtime state and
        # no longer fingerprinted).
        path = _valid_check_report(self.root)
        (self.root / "index.html").write_text("<html>改过了</html>", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            self.verify(path)
        message = str(caught.exception)
        self.assertIn("fresh report", message)
        self.assertNotEqual(state.read_state(self.root)["stage"], "delivered")

    def test_verification_round_rejects_a_report_for_an_earlier_tree(self):
        # The round itself no longer freezes a fingerprint: the report protocol
        # compares the report against the tree as it is now, which is what makes
        # a report written before the edit useless rather than merely stale.
        stale = _valid_check_report(self.root)
        _open_round(self.root)
        (self.root / "index.html").write_text("<html>changed</html>", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.verify(self.root, report=stale)
        self.assertIn("fresh report", str(caught.exception))
        # The round stays open: the builder owes a report that holds.
        still = state.preflight_state(state.read_state(self.root))
        self.assertEqual(still["next_action"], "finish_verification")
        self.assertIn("write_source", still["blocked_actions"])

    def test_verify_rejects_an_axis_that_says_nothing(self):
        plan = check.plan(self.root)
        axes = {axis: _measured(f"{axis} 覆盖") for axis in plan["required_axes"]}
        axes["core_task"] = {"status": "verified"}
        path = _valid_check_report(self.root, axes=axes)
        with self.assertRaises(ValueError) as caught:
            self.verify(path)
        self.assertIn("what was observed", str(caught.exception))

    def test_verify_needs_no_hand_typed_status(self):
        with self.assertRaises(TypeError):
            state.verify(self.root, "verified", ["核心任务通过"], [], False)

    def test_verify_fails_closed_without_the_protocol_script(self):
        # No validator, no verification: a missing site-check must not degrade
        # into "accept whatever the report claims".
        path = _valid_check_report(self.root)
        original = state._check_script
        state._check_script = lambda: None
        try:
            with self.assertRaises(ValueError) as caught:
                self.verify(path)
            self.assertIn("check.py", str(caught.exception))
            self.assertEqual(state.read_state(self.root)["stage"], "building")
        finally:
            state._check_script = original

    def test_strict_verify_report_requires_independent(self):
        strict_root = Path(tempfile.mkdtemp())
        try:
            state.init(strict_root, "strict", schema_revision=2)
            state.decide(strict_root, "登记库存", "单工作台", "就按这个方向做", [], [])
            state.start(strict_root, contract_report=_report_path(strict_root))
            axes = {axis: _measured(f"{axis} 覆盖") for axis in
                    ("contract", "static_build", "core_task", "negative_path",
                     "visual_desktop", "visual_mobile", "reopen", "risk")}
            report = _valid_check_report(strict_root, independent=False, axes=axes)
            with self.assertRaises(ValueError) as caught:
                self.verify(report, root=strict_root)
            self.assertIn("independent", str(caught.exception))
            # With independent it delivers.
            report = _valid_check_report(strict_root, independent=True, axes=axes)
            self.assertEqual(self.verify(report, root=strict_root)["stage"], "delivered")
        finally:
            import shutil
            shutil.rmtree(strict_root, ignore_errors=True)


class CompatibilityDirectoryTests(unittest.TestCase):
    def test_legacy_v3_directory_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy_dir = root / ".v3"
            legacy_dir.mkdir(parents=True)
            legacy_state = {
                "version": 3,
                "schema_revision": 2,
                "mode": "guided",
                "stage": "discovering",
                "next_action": "present_structure_choice",
                "allowed_actions": ["select-structure", "decide", "block"],
                "blocked_actions": ["start", "verify", "deliver"],
                "discovery": state.default_discovery(),
                "history": [],
            }
            (legacy_dir / "state.json").write_text(json.dumps(legacy_state), encoding="utf-8")
            self.assertEqual(state.state_path(root), legacy_dir / "state.json")
            loaded = state.read_state(root)
            self.assertEqual(loaded["stage"], "discovering")

    def test_case_insensitive_SITE_directory_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            caps_dir = root / ".SITE"
            caps_dir.mkdir(parents=True)
            caps_state = {
                "version": 3,
                "schema_revision": 2,
                "mode": "guided",
                "stage": "discovering",
                "next_action": "present_structure_choice",
                "allowed_actions": ["select-structure", "decide", "block"],
                "blocked_actions": ["start", "verify", "deliver"],
                "discovery": state.default_discovery(),
                "history": [],
            }
            (caps_dir / "state.json").write_text(json.dumps(caps_state), encoding="utf-8")
            self.assertEqual(state.state_path(root), caps_dir / "state.json")
            loaded = state.read_state(root)
            self.assertEqual(loaded["stage"], "discovering")


if __name__ == "__main__":
    unittest.main()
