import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import hashlib

STATE_PATH = Path(__file__).parents[1] / "site-builder" / "scripts" / "state.py"
SPEC = importlib.util.spec_from_file_location("v3_state", STATE_PATH)
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)


def _write_contract(root: Path) -> str:
    """Write a minimal contract file under the project and return its SHA-256."""
    contract = (
        "# 页面设计合同\n\n"
        "```v3-contract\n"
        '{"work_type": "new-surface", "structure_mode": "single"}\n'
        "```\n"
    )
    path = root / ".v3" / "design" / "surface-brief.md"
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
    report_file = root / ".v3" / "contract-report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return report_file


class StateProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def decide_and_start(self, mode="guided"):
        state.init(self.root, mode)
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
        result = state.init(self.root, "guided")
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
            "verify_core_task",
        )

    def test_guided_limited_delivery_names_limitations(self):
        self.decide_and_start()
        with self.assertRaises(ValueError):
            state.verify(self.root, "limited", ["新增库存成功"], [], False)

        result = state.verify(
            self.root,
            "limited",
            ["新增库存成功"],
            ["尚未检查移动端"],
            False,
        )
        self.assertEqual(result["stage"], "delivered")
        self.assertEqual(result["next_action"], "report_delivery")

    def test_cannot_build_without_confirmed_direction(self):
        state.init(self.root, "guided")
        with self.assertRaises(ValueError):
            state.start(self.root)

    def test_strict_requires_independent_verified_evidence(self):
        self.decide_and_start("strict")
        with self.assertRaises(ValueError):
            state.verify(self.root, "limited", ["页面可见"], ["未独立检查"], False)
        with self.assertRaises(ValueError):
            state.verify(self.root, "verified", ["核心任务通过"], [], False)

        result = state.verify(self.root, "verified", ["独立检查核心任务通过"], [], True)
        self.assertEqual(result["stage"], "delivered")

    def test_blocked_verification_can_resume_building(self):
        self.decide_and_start()
        result = state.verify(
            self.root,
            "blocked",
            ["保存操作返回错误"],
            ["修复保存错误后复验"],
            False,
        )
        self.assertEqual(result["stage"], "blocked")
        self.assertEqual(state.resume(self.root)["stage"], "building")

    def test_reopen_clears_old_decision_and_verification(self):
        self.decide_and_start()
        state.verify(self.root, "verified", ["核心任务通过"], [], False)
        result = state.reopen(self.root, "核心范围改变")
        self.assertEqual(result["stage"], "discovering")
        self.assertIn("confirmed_direction", result["missing"])

    def test_invalid_status_is_rejected_for_direct_callers(self):
        self.decide_and_start()
        with self.assertRaises(ValueError):
            state.verify(self.root, "unknown", ["看起来正常"], [], False)

    def test_init_requires_existing_project_root(self):
        missing = self.root / "missing"
        with self.assertRaises(ValueError):
            state.init(missing, "guided")
        self.assertFalse(missing.exists())

    def test_blank_evidence_is_rejected(self):
        self.decide_and_start()
        with self.assertRaises(ValueError):
            state.verify(self.root, "verified", ["   "], [], False)

    def test_state_is_valid_json(self):
        state.init(self.root, "guided")
        payload = json.loads((self.root / ".v3/state.json").read_text())
        self.assertEqual(payload["version"], 3)
        self.assertEqual(payload["mode"], "guided")

    def test_top_level_stages_remain_five(self):
        self.assertEqual(
            state.STAGES,
            {"discovering", "decided", "building", "blocked", "delivered"},
        )
        state.init(self.root, "guided")
        payload = json.loads((self.root / ".v3/state.json").read_text())
        self.assertEqual(payload["schema_revision"], 2)
        self.assertEqual(payload["discovery"]["structure"]["mode"], "undetermined")

    def test_single_structure_keeps_one_decide(self):
        state.init(self.root, "guided")
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
        state.init(self.root, "guided")
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
        state.init(self.root, "guided")
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
        state.init(self.root, "guided")
        state.discover(self.root, "single", "无结构分歧", [], [])
        with self.assertRaises(ValueError):
            state.select_structure(self.root, "工作台", "选工作台")

    def test_discover_choice_requires_candidates_and_reason(self):
        state.init(self.root, "guided")
        with self.assertRaises(ValueError):
            state.discover(self.root, "choice", "", [], ["落地页"])
        with self.assertRaises(ValueError):
            state.discover(self.root, "choice", "有分歧", [], [])

    def test_direction_quote_cannot_reuse_structure_quote(self):
        state.init(self.root, "guided")
        state.discover(
            self.root,
            "choice",
            "信息拓扑不同",
            ["信息拓扑"],
            ["落地页", "工作台"],
        )
        state.select_structure(self.root, "工作台", "就按这个方向做")
        with self.assertRaises(ValueError):
            state.decide(
                self.root,
                "登记库存",
                "工作台展示当前库存",
                "就按这个方向做",  # reused verbatim
                [],
                [],
            )
        # A different quote succeeds.
        state.decide(
            self.root,
            "登记库存",
            "工作台展示当前库存",
            "按工作台方向实现",
            [],
            [],
        )

    def test_quote_reuse_caught_across_whitespace_variants(self):
        state.init(self.root, "guided")
        state.discover(
            self.root, "choice", "信息拓扑不同", ["信息拓扑"], ["A", "B"]
        )
        state.select_structure(self.root, "A", "  就按   这个方向做  ")
        with self.assertRaises(ValueError):
            state.decide(
                self.root, "任务", "方向", "就按这个方向做", [], []
            )

    def test_visual_only_difference_uses_single_path(self):
        # Colour, font, radius, shadow do not change information topology or
        # primary actions, so they must take the single path: one decide.
        state.init(self.root, "guided")
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
        state.init(self.root, "guided")
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
        state.init(self.root, "guided")
        payload = json.loads((self.root / ".v3/state.json").read_text())
        del payload["discovery"]
        (self.root / ".v3/state.json").write_text(
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
        state.init(self.root, "guided")
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
        path = self.root / ".v3" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.start(self.root, contract_report=report)
        self.assertIn("changed since", str(caught.exception))

    def test_unreadable_report_is_rejected(self):
        bad = self.root / ".v3" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            state.start(self.root, contract_report=bad)

    def test_legacy_revision_one_starts_without_report(self):
        payload = json.loads((self.root / ".v3/state.json").read_text())
        payload["schema_revision"] = 1
        (self.root / ".v3/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        result = state.start(self.root)
        self.assertEqual(result["stage"], "building")

    def test_legacy_rev1_missing_contract_warns(self):
        """rev1 whose brief lacks a v3-contract block warns but still starts."""
        payload = json.loads((self.root / ".v3/state.json").read_text())
        payload["schema_revision"] = 1
        (self.root / ".v3/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        # No surface brief written -> no v3-contract block.
        result = state.start(self.root)
        self.assertEqual(result["stage"], "building")
        codes = [w["code"] for w in result.get("warnings", [])]
        self.assertIn("legacy_missing_contract_block", codes)

    def test_legacy_rev1_with_contract_has_no_legacy_warning(self):
        """rev1 whose brief carries a v3-contract block emits no legacy warning."""
        payload = json.loads((self.root / ".v3/state.json").read_text())
        payload["schema_revision"] = 1
        (self.root / ".v3/state.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        _write_contract(self.root)  # brief with a v3-contract block
        result = state.start(self.root)
        self.assertEqual(result["stage"], "building")
        codes = [w["code"] for w in result.get("warnings", [])]
        self.assertNotIn("legacy_missing_contract_block", codes)

    def test_rev2_missing_contract_blocks_start(self):
        """rev2 never downgrades a missing contract block to a warning; it blocks."""
        # Brief exists but carries no v3-contract block, and no report is passed.
        brief = self.root / ".v3" / "design" / "surface-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("# 仅 prose，没有合同块\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.start(self.root)
        self.assertIn("contract report", str(caught.exception))


class VerifyReportTests(unittest.TestCase):
    """Stage 5: verify accepts a site-check-v3 report; --evidence stays transitional."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        state.init(self.root, "guided")
        state.decide(
            self.root, "登记库存", "单工作台", "就按这个方向做", [], []
        )
        state.start(self.root, contract_report=_report_path(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def _check_report(self, *, overall="verified", independent=False,
                      limitations=None, evidence=None, mode="guided",
                      project_root=None):
        rep = {
            "project_root": str((project_root or self.root).resolve()),
            "mode": mode,
            "overall": overall,
            "evidence": evidence or ["核心任务通过"],
            "limitations": limitations or [],
            "independent": independent,
        }
        path = self.root / ".v3" / "check-report.json"
        path.write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        return path

    def test_verify_from_report_delivers(self):
        path = self._check_report()
        result = state.verify(self.root, report=path)
        self.assertEqual(result["stage"], "delivered")
        self.assertEqual(result["next_action"], "report_delivery")

    def test_verify_from_report_blocked_stays_blocked(self):
        path = self._check_report(
            overall="blocked", evidence=["保存操作返回错误"],
            limitations=["修复保存错误后复验"],
        )
        result = state.verify(self.root, report=path)
        self.assertEqual(result["stage"], "blocked")

    def test_verify_report_rejects_wrong_project_root(self):
        other = Path(tempfile.mkdtemp())
        path = self._check_report(project_root=other)
        with self.assertRaises(ValueError) as caught:
            state.verify(self.root, report=path)
        self.assertIn("project_root", str(caught.exception))
        other.rmdir()

    def test_verify_report_rejects_unreadable(self):
        bad = self.root / ".v3" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            state.verify(self.root, report=bad)

    def test_verify_requires_either_report_or_status(self):
        with self.assertRaises(ValueError) as caught:
            state.verify(self.root)
        self.assertIn("either --report or --status", str(caught.exception))

    def test_old_evidence_path_still_works(self):
        # Transitional --status/--evidence path is unchanged.
        result = state.verify(
            self.root, status="verified", evidence=["核心任务通过"], limitations=[], independent=False
        )
        self.assertEqual(result["stage"], "delivered")

    def test_strict_verify_report_requires_independent(self):
        strict_root = Path(tempfile.mkdtemp())
        try:
            state.init(strict_root, "strict")
            state.decide(strict_root, "登记库存", "单工作台", "就按这个方向做", [], [])
            state.start(strict_root, contract_report=_report_path(strict_root))
            report = strict_root / ".v3" / "check-report.json"
            report.write_text(json.dumps({
                "project_root": str(strict_root.resolve()),
                "mode": "strict", "overall": "verified",
                "evidence": ["核心任务通过"], "limitations": [],
                "independent": False,
            }, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                state.verify(strict_root, report=report)
            self.assertIn("independent", str(caught.exception))
            # With independent it delivers.
            report.write_text(json.dumps({
                "project_root": str(strict_root.resolve()),
                "mode": "strict", "overall": "verified",
                "evidence": ["独立检查核心任务通过"], "limitations": [],
                "independent": True,
            }, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(state.verify(strict_root, report=report)["stage"], "delivered")
        finally:
            import shutil
            shutil.rmtree(strict_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
