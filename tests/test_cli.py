import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "release" / "site-builder" / "scripts" / "state.py"
DESIGN = Path(__file__).parents[1] / "release" / "site-design" / "scripts" / "design.py"
CHECK = Path(__file__).parents[1] / "release" / "site-check" / "scripts" / "check.py"

# A contract that passes prebuild: every indexed ID exists in the body, the BR
# has a handoff target, the required IC has a structural impact, the VA is
# observable, and the design-judgment fields differ from the template defaults.
VALID_CONTRACT = """# 页面设计合同

```site-contract
{
  "work_type": "new-surface",
  "structure_mode": "single",
  "scope_refs": ["BR-01"],
  "required_constraints": ["IC-01"],
  "pages": ["PG-01"],
  "sections": [],
  "responsive": [],
  "components": [],
  "assets": [],
  "acceptance": ["VA-01"],
  "unresolved_confirm": [],
  "blocking_missing_assets": [],
  "intentional_exceptions": []
}
```

## 项目事实

- **使用者：** 仓管员
- **主任务：** 登记并查看库存
- **业务对象：** 库存项
- **真实内容：** 名称、数量、单位
- **已确认状态：** 正常
- **后果与约束：** 可逆
- **设备与视口：** 桌面与移动
- **继承依据：** 无

## 设计推导

- **反默认原因：** 仓管员高频登记需单工作台而非多页工作台（依据 `IC-01`）

## 视觉方向

- **设计主线：** 以表格为视觉主角密度优先（依据 `PG-01`）
- **构图命题：** 表格居中占主区新增入口在顶部（依据 `PG-01`）
- **细节签名：** 数量列等宽数字对齐（依据 `BR-01`）

## 首版承诺 × 原型覆盖

| 来源引用 | 可观察结果 / 验收条件 | 原型位置与覆盖判定 | 正式实现必须补齐 | 交接目标 ID |
| --- | --- | --- | --- | --- |
| `BR-01` | 登记库存 | `covered` | 无 | `IC-01` |

## 任务交互合同

| ID | 约束 | 等级 | 依据 | 对结构/状态的影响 |
| --- | --- | --- | --- | --- |
| `IC-01` | 必须登记 | `required` | `measured` | 工作台主操作 |

## 页面地图

| ID | 页面 / 路由 | 用途 | 主任务或转化 | 优先级 | 动态 / CMS |
| --- | --- | --- | --- | --- | --- |
| `PG-01` | / | 库存工作台 | 登记 | `primary` |  |

### 视觉验收标准

| ID | 页面 / 状态 / 视口 | 可观察标准 | 检查轴 | 阻断 |
| --- | --- | --- | --- | --- |
| `VA-01` | `PG-01` | 登记后数量增加且可见 | `core_task` | `yes` |
"""


class StateCliTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        # Retained compatibility cases explicitly request schema 2; a test that
        # needs the current schema passes --schema-revision 3 itself.
        if args and args[0] == "init" and "--schema-revision" not in args:
            args = (*args, "--schema-revision", "2")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, expected, (result.stdout or '') + (result.stderr or ''))
        return json.loads(result.stdout)

    def write_contract_report(self, root):
        """Write a valid contract and generate its prebuild report via design.py."""
        path = root / ".site" / "design" / "surface-brief.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(VALID_CONTRACT, encoding="utf-8")
        report = root / ".site" / "contract-report.json"
        subprocess.run(
            [sys.executable, str(DESIGN), "check-contract", "--root", str(root),
             "--phase", "prebuild", "--out", str(report)],
            check=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        return report

    def write_check_report(self, root, overall="verified"):
        """Write a check report the protocol accepts for ``root`` as it is now.

        Fingerprints come from check.py itself, so the CLI flow exercises the
        same validation a real verification does.
        """
        plan = json.loads(subprocess.run(
            [sys.executable, str(CHECK), "plan", str(root)],
            check=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        ).stdout)
        status = "verified" if overall == "verified" else "not_run"
        axes = {axis: {"status": status, "observed": f"{axis} 覆盖"}
                for axis in plan["required_axes"]}
        report = root / ".site" / "check-report.json"
        report.write_text(json.dumps({
            "project_root": str(root.resolve()),
            "mode": plan["mode"],
            "overall": overall,
            "independent": False,
            "contract_sha256": plan["contract_sha256"],
            "source_sha256": plan["source_sha256"],
            "axes": axes,
            "evidence": ["新增库存后刷新仍可见"],
            "limitations": [] if overall == "verified" else ["未验证"],
        }, ensure_ascii=False), encoding="utf-8")
        return report

    def test_guided_cli_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialized = self.run_cli("init", root, "--mode", "guided")
            self.assertEqual(initialized["next_action"], "prepare_and_confirm_direction")

            self.run_cli(
                "decide",
                root,
                "--task",
                "登记库存",
                "--direction",
                "单工作台",
                "--quote",
                "就按这个方向做",
            )
            report = self.write_contract_report(root)
            started = self.run_cli("start", root, "--contract-report", report)
            # 1.1: the build goes to the user before any round opens. handoff
            # moves the sub-phase to review, and begin-check only opens a round
            # on those reviewed fingerprints with the user's own words.
            self.assertEqual(started["next_action"], "build_then_handoff")
            handed = self.run_cli("handoff", root)
            self.assertEqual(handed["next_action"], "wait_for_user_review")
            self.run_cli("begin-check", root, "--quote", "看着没问题，去验吧")
            delivered = self.run_cli(
                "verify",
                root,
                "--report",
                self.write_check_report(root),
            )
            self.assertEqual(delivered["next_action"], "report_delivery")

    def test_plan_cli_always_reports_the_source_manifest(self):
        """1.1 dropped --full-manifest: the manifest is part of every plan.

        The manifest is what a later --changed-from run needs to list changed
        files, so it is no longer an opt-in extra. The old flag is gone rather
        than silently ignored, and the default output carries the manifest.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_contract_report(root)
            (root / "index.html").write_text("<html></html>", encoding="utf-8")

            def run_check(*args):
                result = subprocess.run(
                    [sys.executable, str(CHECK), *map(str, args)],
                    check=False, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return json.loads(result.stdout)

            summary = run_check("plan", root)
            self.assertIn("source_manifest", summary)
            self.assertIn("index.html", summary["source_manifest"])
            self.assertEqual(summary["source_files"], len(summary["source_manifest"]))
            rejected = subprocess.run(
                [sys.executable, str(CHECK), "plan", str(root), "--full-manifest"],
                check=False, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            self.assertEqual(rejected.returncode, 2,
                             "the removed --full-manifest flag must not be accepted")

    def test_verify_rejects_a_stale_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root, "--mode", "guided")
            self.run_cli("decide", root, "--task", "登记库存", "--direction",
                         "单工作台", "--quote", "就按这个方向做")
            self.run_cli("start", root, "--contract-report", self.write_contract_report(root))
            report = self.write_check_report(root)
            self.run_cli("handoff", root)
            self.run_cli("begin-check", root, "--quote", "看着没问题，去验吧")
            # The product changes after the report was written: the report now
            # describes a tree that no longer exists and cannot be recorded.
            (root / "app.js").write_text("show()", encoding="utf-8")
            result = self.run_cli("verify", root, "--report", report, expected=2)
            self.assertIn("fresh report", result["error"])

    def test_user_review_gates_the_verification_round(self):
        """1.1: a round opens only on the version the user was shown.

        handoff records the fingerprints he looked at. Without a handoff there
        is nothing to approve, and an edit after the handoff means he never saw
        this tree -- both are refused, and only a fresh handoff reopens the gate.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root, "--mode", "guided")
            self.run_cli("decide", root, "--task", "登记库存", "--direction",
                         "单工作台", "--quote", "就按这个方向做")
            self.run_cli("start", root, "--contract-report", self.write_contract_report(root))
            early = self.run_cli("begin-check", root, "--quote", "去验吧", expected=2)
            self.assertIn("handoff", early["error"])

            self.run_cli("handoff", root)
            (root / "app.js").write_text("show()", encoding="utf-8")
            stale = self.run_cli("begin-check", root, "--quote", "可以，去验吧", expected=2)
            self.assertIn("handoff", stale["error"])

            self.run_cli("handoff", root)
            opened = self.run_cli("begin-check", root, "--quote", "这回可以，去验吧")
            self.assertEqual(opened["next_action"], "finish_verification")

    def test_invalid_transition_returns_machine_readable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root)
            result = self.run_cli("start", root, expected=2)
            self.assertIn("error", result)

    def test_choice_structure_cli_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root, "--mode", "guided")

            assessed = self.run_cli(
                "discover",
                root,
                "--structure",
                "choice",
                "--reason",
                "先做落地页还是工作台，信息拓扑不同",
                "--axis",
                "信息拓扑",
                "--candidate",
                "落地页",
                "--candidate",
                "工作台",
            )
            self.assertEqual(assessed["next_action"], "present_structure_choice")
            self.assertIn("structure_selection", assessed["missing"])

            selected = self.run_cli(
                "select-structure",
                root,
                "--candidate",
                "工作台",
                "--quote",
                "就选工作台结构",
            )
            self.assertEqual(selected["next_action"], "prepare_and_confirm_direction")

            self.run_cli(
                "decide",
                root,
                "--task",
                "登记库存",
                "--direction",
                "工作台展示当前库存",
                "--quote",
                "按工作台这个方向做",
            )
            report = self.write_contract_report(root)
            self.run_cli("start", root, "--contract-report", report)
            self.run_cli("handoff", root)
            self.run_cli("begin-check", root, "--quote", "看着没问题，去验吧")
            delivered = self.run_cli(
                "verify", root, "--report", self.write_check_report(root)
            )
            self.assertEqual(delivered["next_action"], "report_delivery")

    def test_single_structure_cli_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root)
            assessed = self.run_cli(
                "discover", root, "--structure", "single", "--reason", "无结构分歧"
            )
            self.assertEqual(assessed["next_action"], "prepare_and_confirm_direction")
            self.run_cli(
                "decide",
                root,
                "--task",
                "登记库存",
                "--direction",
                "单工作台",
                "--quote",
                "就按这个方向做",
            )
            report = self.write_contract_report(root)
            self.run_cli("start", root, "--contract-report", report)

    def test_schema_3_refuses_a_single_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root, "--schema-revision", "3")
            refused = self.run_cli(
                "discover", root, "--structure", "single", "--reason", "无结构分歧",
                expected=2,
            )
            self.assertEqual(refused["code"], "STRUCTURE_CHOICE_REQUIRED")
            # The gate tells the agent how to recover, not just that it failed.
            self.assertIn("--structure choice", refused["recovery"])

    def test_separate_confirmations_may_repeat_the_same_words(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root)
            self.run_cli(
                "discover",
                root,
                "--structure",
                "choice",
                "--reason",
                "信息拓扑不同",
                "--candidate",
                "A",
                "--candidate",
                "B",
            )
            self.run_cli(
                "select-structure", root, "--candidate", "A", "--quote", "就按这个方向做"
            )
            result = self.run_cli(
                "decide",
                root,
                "--task",
                "任务",
                "--direction",
                "方向",
                "--quote",
                "就按这个方向做",
                expected=0,
            )
            self.assertEqual(result["stage"], "decided")
            stored = json.loads((root / ".site/state.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["decision"]["quote"], stored["discovery"]["structure"]["quote"])


if __name__ == "__main__":
    unittest.main()
