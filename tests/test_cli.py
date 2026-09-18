import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "site-builder" / "scripts" / "state.py"
DESIGN = Path(__file__).parents[1] / "site-design" / "scripts" / "design.py"

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

- **反默认原因：** 仓管员高频登记需单工作台而非多页工作台

## 视觉方向

- **母题：** 以表格为视觉主角密度优先
- **构图命题：** 表格居中占主区新增入口在顶部
- **细节签名：** 数量列等宽数字对齐

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
            self.run_cli("start", root, "--contract-report", report)
            delivered = self.run_cli(
                "verify",
                root,
                "--status",
                "verified",
                "--evidence",
                "新增库存后刷新仍可见",
            )
            self.assertEqual(delivered["next_action"], "report_delivery")

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
            delivered = self.run_cli(
                "verify", root, "--status", "verified", "--evidence", "刷新后仍可见"
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

    def test_reused_quote_rejected_by_cli(self):
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
                expected=2,
            )
            self.assertIn("error", result)
            self.assertIn("quote", result["error"])


if __name__ == "__main__":
    unittest.main()
