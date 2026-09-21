"""The delivery gate must not fail open when the spec is gone.

A report is a statement about one tree. These tests check the two ways that
statement can stop being checkable: the contract file is missing, and the
source has moved on. Both must be reported as invalid rather than skipped.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "check.py"
CONTRACT_REL = ".site/design/surface-brief.md"
CONTRACT_TEXT = "# 合同\n\n```site-contract\n{\"mode\": \"guided\"}\n```\n\n正文\n"

_SPEC = importlib.util.spec_from_file_location("site_check", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check)


def run_json(*args):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(completed.stdout)


class MissingContractTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir(parents=True)
        contract = self.root / CONTRACT_REL
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text(CONTRACT_TEXT, encoding="utf-8")
        (self.root / "index.html").write_text("<h1>预约演示</h1>\n", encoding="utf-8")
        # Outside the project: a report written into the tree would join the
        # manifest it is supposed to describe and invalidate itself.
        self.report_path = Path(self._tmp.name) / "report.json"

    def tearDown(self):
        self._tmp.cleanup()

    def matching_report(self) -> dict:
        plan = run_json("plan", str(self.root), "--contract", CONTRACT_REL)
        return {
            "project_root": str(self.root.resolve()),
            "mode": "guided",
            "overall": "verified",
            "independent": False,
            "contract_sha256": plan["contract_sha256"],
            "source_sha256": plan["source_sha256"],
            "source_manifest": plan["source_manifest"],
            "axes": {
                axis: {"status": "verified", "observed": "查了 3 个对象"}
                for axis in plan["required_axes"]
            },
            "evidence": ["核心任务走通，1 条记录"],
            "limitations": [],
        }

    def validate(self, report: dict) -> dict:
        self.report_path.write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )
        return run_json("validate-report", str(self.root), str(self.report_path))

    def test_a_matching_report_validates(self):
        verdict = self.validate(self.matching_report())
        self.assertTrue(verdict["valid"], verdict.get("errors"))
        self.assertTrue(verdict["hash"]["source_valid"])
        self.assertTrue(verdict["hash"]["contract_valid"])

    def test_deleting_the_contract_invalidates_the_report(self):
        report = self.matching_report()
        (self.root / CONTRACT_REL).unlink()
        verdict = self.validate(report)
        self.assertFalse(verdict["valid"])
        self.assertIn("contract", " ".join(verdict["errors"]))
        self.assertIsNone(verdict["hash"]["contract_valid"])

    def test_a_moved_source_tree_invalidates_the_report(self):
        report = self.matching_report()
        (self.root / "index.html").write_text("<h1>改过的</h1>\n", encoding="utf-8")
        verdict = self.validate(report)
        self.assertFalse(verdict["valid"])
        self.assertFalse(verdict["hash"]["source_valid"])
        self.assertTrue(verdict["invalidated_axes"])


class ProtocolHardeningTest(unittest.TestCase):
    """Malformed inputs are rejected, never silently normalised."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir(parents=True)
        contract = self.root / CONTRACT_REL
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text(CONTRACT_TEXT, encoding="utf-8")
        (self.root / "index.html").write_text("<h1>预约演示</h1>\n", encoding="utf-8")
        self.report_path = Path(self._tmp.name) / "report.json"

    def tearDown(self):
        self._tmp.cleanup()

    def matching_report(self, **overrides):
        plan = run_json("plan", str(self.root), "--contract", CONTRACT_REL)
        report = {
            "project_root": str(self.root.resolve()),
            "mode": "guided",
            "overall": "verified",
            "independent": False,
            "contract_sha256": plan["contract_sha256"],
            "source_sha256": plan["source_sha256"],
            "axes": {
                axis: {"status": "verified", "observed": "查了 3 个对象"}
                for axis in plan["required_axes"]
            },
            "evidence": ["核心任务走通，1 条记录"],
            "limitations": [],
        }
        report.update(overrides)
        return report

    def validate(self, report):
        self.report_path.write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )
        return run_json("validate-report", str(self.root), str(self.report_path))

    def test_independent_must_be_a_json_boolean(self):
        verdict = self.validate(self.matching_report(independent="false"))
        self.assertFalse(verdict["valid"])
        self.assertIn("independent must be a JSON boolean", " ".join(verdict["errors"]))
        self.assertFalse(verdict["independent"])

    def test_strict_project_rejects_a_guided_report(self):
        state_path = self.root / ".site" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"version": 3, "mode": "strict", "stage": "building"}),
            encoding="utf-8",
        )
        verdict = self.validate(self.matching_report())
        self.assertFalse(verdict["valid"])
        self.assertIn("strict", " ".join(verdict["errors"]))

    def test_corrupt_state_is_an_error_not_guided(self):
        report = self.matching_report()
        state_path = self.root / ".site" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            check.read_mode(self.root)
        self.assertFalse(self.validate(report)["valid"])

    def test_static_not_run_blocks_the_browser(self):
        report = self.matching_report()
        report["axes"]["static_build"] = {"status": "not_run"}
        verdict = self.validate(report)
        self.assertTrue(verdict["browser_blocked"])
        self.assertFalse(verdict["valid"])

    def test_failed_vas_must_be_a_list_of_strings(self):
        report = self.matching_report()
        report["axes"]["core_task"] = {"status": "blocked", "failed_vas": "VA-01"}
        verdict = self.validate(report)
        self.assertFalse(verdict["valid"])
        self.assertIn("failed_vas", " ".join(verdict["errors"]))

    def test_missing_project_root_is_rejected_from_inside_the_project(self):
        report = self.matching_report()
        del report["project_root"]
        self.report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        previous = os.getcwd()
        try:
            os.chdir(self.root)
            verdict = check.validate_report(self.root, str(self.report_path))
        finally:
            os.chdir(previous)
        self.assertFalse(verdict["valid"])
        self.assertIn("project_root", " ".join(verdict["errors"]))

    def test_evidence_shape_is_checked(self):
        verdict = self.validate(self.matching_report(evidence="核心任务走通"))
        self.assertFalse(verdict["valid"])
        self.assertIn("evidence must be a list", " ".join(verdict["errors"]))

    def test_toolchain_dirs_tolerates_broken_declarations(self):
        declaration = self.root / "skills.json"
        declaration.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(check.toolchain_dirs(self.root), ())

    def test_plan_autodetects_the_contract(self):
        plan = run_json("plan", str(self.root))
        self.assertTrue(plan["contract_sha256"])
        self.assertEqual(plan["contract_path"], CONTRACT_REL)

    def test_va_table_cross_check(self):
        contract = self.root / CONTRACT_REL
        contract.write_text(
            '# 合同\n\n```site-contract\n{"acceptance": ["VA-01", "VA-99"]}\n```\n\n'
            "## 视觉验收标准\n\n"
            "| ID | 页面 / 状态 / 视口 | 可观察标准 | 检查轴 | 阻断 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| `VA-01` | `PG-01` | 可见 | `core_task` | `yes` |\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            check.read_contract_file(contract)

    def test_malformed_inputs_never_traceback(self):
        self.report_path.write_text("[1, 2, 3]", encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-report",
             str(self.root), str(self.report_path)],
            text=True, capture_output=True, encoding="utf-8", errors="replace",
        )
        self.assertNotIn("Traceback", completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["valid"])


class PlanOutputTest(unittest.TestCase):
    """What plan calls product source, and how it prints it.

    ``data/`` under the project root is not guessed as runtime state: a static
    site's ``data/products.json`` is content, and excluding the directory made
    a report about the site independent of that content. Runtime files are
    still excluded by suffix. The full manifest is available in --out while
    --summary keeps stdout bounded.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir(parents=True)
        contract = self.root / CONTRACT_REL
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text(CONTRACT_TEXT, encoding="utf-8")
        (self.root / "index.html").write_text("<h1>预约演示</h1>\n", encoding="utf-8")
        (self.root / "data").mkdir()
        (self.root / "data" / "products.json").write_text(
            '{"price": 10}\n', encoding="utf-8")
        (self.root / "data" / "inventory.db").write_bytes(b"state")

    def tearDown(self):
        self._tmp.cleanup()

    def test_content_under_root_data_is_product_source(self):
        plan = run_json("plan", str(self.root), "--contract", CONTRACT_REL)
        self.assertIn("data/products.json", plan["source_manifest"])
        self.assertNotIn("data/inventory.db", plan["source_manifest"])
        self.assertIn("data/inventory.db", plan["source_excluded"])

    def test_summary_is_bounded_and_out_carries_the_manifest(self):
        summary = run_json("plan", str(self.root), "--contract", CONTRACT_REL,
                           "--summary")
        self.assertEqual(summary["mode"], "summary")
        self.assertNotIn("source_manifest", summary)
        self.assertEqual(summary["source_files"], 2)  # index.html + products.json
        out = Path(self._tmp.name) / "plan.json"
        run_json("plan", str(self.root), "--contract", CONTRACT_REL,
                 "--out", str(out), "--summary")
        full = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("source_manifest", full)
        self.assertEqual(summary["source_sha256"], full["source_sha256"])


if __name__ == "__main__":
    unittest.main()
