import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

STATE_PATH = Path(__file__).parents[1] / "site-builder" / "scripts" / "state.py"
SPEC = importlib.util.spec_from_file_location("v3_state", STATE_PATH)
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)


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
        return state.start(self.root)

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
        self.assertEqual(state.start(self.root)["next_action"], "verify_core_task")

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


if __name__ == "__main__":
    unittest.main()
