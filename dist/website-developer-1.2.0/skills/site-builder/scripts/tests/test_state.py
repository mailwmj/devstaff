"""The user-look gate: no verification round opens on a version he has not seen.

These tests run state.py in process against a hand-written building state, so
they exercise the gate itself instead of re-testing contract reporting and the
check protocol, which have their own tests.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "state.py"
STATE_DIR = ".site"
CONTRACT_REL = Path(STATE_DIR) / "design" / "surface-brief.md"
# The gate fingerprints the tree through check.py, so the fixture needs a real
# contract and real source; a stubbed one would leave the thing under test
# untested.
CONTRACT_TEXT = (
    "# 合同\n\n```site-contract\n{\"mode\": \"guided\"}\n```\n\n正文\n"
)

_SPEC = importlib.util.spec_from_file_location("site_builder_state", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
state = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(state)


def building_state(root: Path, verification: dict | None = None) -> dict:
    """A project that finished its slices and is ready to be handed over."""
    (root / STATE_DIR).mkdir(parents=True, exist_ok=True)
    contract = root / CONTRACT_REL
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(CONTRACT_TEXT, encoding="utf-8")
    (root / "index.html").write_text("<h1>预约演示</h1>\n", encoding="utf-8")
    payload = {
        "version": 3,
        "schema_revision": 2,
        "mode": "guided",
        "stage": "building",
        "discovery": state.default_discovery(),
        "decision": {
            "confirmed": True,
            "task": "预约演示",
            "direction": "先看它怎么答",
            "include": [],
            "exclude": [],
            "quote": "就这个方向",
        },
        "verification": verification
        if verification is not None
        else state.blank_verification(),
        "history": [],
        "created_at": state.now(),
        "updated_at": state.now(),
    }
    (root / STATE_DIR / "state.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


class ReviewGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        building_state(self.root)

    def _fresh_root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_begin_check_refused_before_the_build_is_handed_over(self):
        with self.assertRaises(ValueError) as caught:
            state.begin_check(self.root, "可以")
        self.assertIn("handoff", str(caught.exception))
        self.assertEqual(state.read_state(self.root)["verification"]["phase"], "idle")

    def test_source_stays_writable_while_he_looks(self):
        result = state.handoff(self.root)
        self.assertEqual(result["next_action"], "wait_for_user_review")
        self.assertIn("write_source", result["allowed_actions"])
        self.assertIn("begin-check", result["allowed_actions"])
        self.assertIn("user_review", result["missing"])
        self.assertEqual(result["verification"]["phase"], "review")
        self.assertTrue(result["verification"]["handed_at"])
        shown = result["verification"]["handoff_fingerprint"]
        self.assertTrue(shown["source_sha256"] and shown["contract_sha256"])

    def test_a_write_after_he_looked_forces_a_second_look(self):
        state.handoff(self.root)
        (self.root / "index.html").write_text("<h1>改过的</h1>\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.begin_check(self.root, "可以")
        self.assertIn("changed after he looked", str(caught.exception))
        self.assertIn("handoff", str(caught.exception))
        # Handing the new version over is the way through, and it re-asks him.
        result = state.handoff(self.root)
        self.assertEqual(result["next_action"], "wait_for_user_review")
        self.assertIsNone(result["verification"]["review_quote"])
        self.assertEqual(
            state.begin_check(self.root, "这版可以")["next_action"],
            "finish_verification",
        )

    def test_editing_the_contract_after_he_looked_also_re_asks_him(self):
        state.handoff(self.root)
        contract = self.root / CONTRACT_REL
        contract.write_text(CONTRACT_TEXT + "\n新增一条验收\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            state.begin_check(self.root, "可以")

    def test_begin_check_needs_his_words_not_the_agents_judgement(self):
        state.handoff(self.root)
        for quote in ("", "   ", "\n"):
            with self.assertRaises(ValueError):
                state.begin_check(self.root, quote)
        self.assertEqual(state.read_state(self.root)["verification"]["phase"], "review")

    def test_his_yes_opens_the_round_and_freezes_the_tree(self):
        state.handoff(self.root)
        result = state.begin_check(self.root, "可以，去测吧")
        self.assertEqual(result["next_action"], "finish_verification")
        self.assertIn("write_source", result["blocked_actions"])
        self.assertIn("check_report", result["missing"])
        self.assertEqual(result["verification"]["review_quote"], "可以，去测吧")

    def test_a_round_cannot_be_opened_twice(self):
        state.handoff(self.root)
        state.begin_check(self.root, "可以")
        with self.assertRaises(ValueError) as caught:
            state.begin_check(self.root, "可以")
        self.assertIn("already open", str(caught.exception))

    def test_handoff_is_refused_while_a_round_is_open(self):
        state.handoff(self.root)
        state.begin_check(self.root, "可以")
        with self.assertRaises(ValueError):
            state.handoff(self.root)

    def test_fixing_after_a_cancelled_round_needs_a_fresh_look_and_fresh_words(self):
        state.handoff(self.root)
        state.begin_check(self.root, "可以")
        state.cancel_check(self.root, "手机号那步点不动")
        self.assertIsNone(state.read_state(self.root)["verification"]["review_quote"])
        with self.assertRaises(ValueError):
            state.begin_check(self.root, "可以")  # the old yes does not carry over
        result = state.handoff(self.root)
        self.assertIsNone(result["verification"]["review_quote"])

    def test_delivery_keeps_the_words_he_said(self):
        state.handoff(self.root)
        state.begin_check(self.root, "看着没问题，测吧")
        original = state._validated_report
        state._validated_report = lambda root, report: (
            {"valid": True, "independent": True, "errors": []},
            {
                "project_root": str(self.root.resolve()),
                "mode": "guided",
                "overall": "verified",
                "evidence": ["核心任务走通，1 条记录"],
                "limitations": [],
            },
        )
        try:
            result = state.verify(self.root, report="report.json")
        finally:
            state._validated_report = original
        self.assertEqual(result["stage"], "delivered")
        self.assertEqual(result["verification"]["review_quote"], "看着没问题，测吧")
        self.assertTrue(result["verification"]["handed_at"])
        self.assertTrue(result["verification"]["independent"])

    def test_choice_structure_cannot_decide_before_selection(self):
        root = self._fresh_root()
        state.init(root, "guided")
        state.discover(root, "choice", "信息拓扑不同", ["信息拓扑"], ["A", "B"])
        with self.assertRaises(ValueError) as caught:
            state.decide(root, "任务", "方向", "就这个方向", [], [])
        self.assertIn("select-structure", str(caught.exception))

    def test_discover_refuses_and_reset_clears_the_selection(self):
        root = self._fresh_root()
        state.init(root, "guided")
        state.discover(root, "choice", "信息拓扑不同", ["信息拓扑"], ["A", "B"])
        state.select_structure(root, "A", "选 A")
        with self.assertRaises(ValueError) as caught:
            state.discover(root, "single", "重判", [], [])
        self.assertIn("--reset-selection", str(caught.exception))
        result = state.discover(
            root, "single", "重判", [], [], reset_selection=True
        )
        structure = result["discovery"]["structure"]
        self.assertEqual(structure["mode"], "single")
        self.assertIsNone(structure["selected"])
        self.assertIsNone(structure["quote"])

    def test_unknown_schema_revision_is_rejected(self):
        path = self.root / STATE_DIR / "state.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["schema_revision"] = 9
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state.read_state(self.root)
        self.assertIn("schema_revision", str(caught.exception))

    def test_read_state_rejects_malformed_shapes(self):
        path = self.root / STATE_DIR / "state.json"
        base = json.loads(path.read_text(encoding="utf-8"))
        for label, mutate in (
            ("discovery", lambda p: p.update({"discovery": []})),
            ("structure", lambda p: p.update({"discovery": {"structure": []}})),
            ("history", lambda p: p.update({"history": "nope"})),
        ):
            with self.subTest(label=label):
                payload = json.loads(json.dumps(base))
                mutate(payload)
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                with self.assertRaises(ValueError):
                    state.read_state(self.root)
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(ValueError):
            state.read_state(self.root)

    def test_clean_items_keeps_only_non_empty_strings(self):
        self.assertEqual(state.clean_items([" a ", 1, None, "  ", "b"]), ["a", "b"])

    def test_report_without_project_root_is_rejected(self):
        report = self.root / ".site" / "no-root.json"
        report.write_text(json.dumps({
            "mode": "guided", "overall": "verified",
            "evidence": ["核心任务"],
        }), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            state._validated_report(self.root, report)
        self.assertIn("project_root", str(caught.exception))

    def test_state_written_before_this_rule_still_reads(self):
        legacy = {
            "phase": "idle",
            "status": None,
            "evidence": [],
            "limitations": [],
            "independent": False,
            "checked_at": None,
        }
        building_state(self.root, verification=legacy)
        result = state.preflight_state(state.read_state(self.root))
        self.assertEqual(result["next_action"], "build_then_handoff")
        self.assertIn("begin-check", result["blocked_actions"])
        self.assertEqual(state.handoff(self.root)["verification"]["phase"], "review")

    def test_a_review_with_no_recorded_version_refuses_to_open_a_round(self):
        # A state hand-edited straight to review, or written by an older build
        # of this tool: nobody can say which version he saw, so no round.
        building_state(
            self.root,
            verification={**state.blank_verification(), "phase": "review"},
        )
        with self.assertRaises(ValueError) as caught:
            state.begin_check(self.root, "可以")
        self.assertIn("no record of which version", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
