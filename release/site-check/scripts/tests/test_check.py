"""The delivery gate must not fail open when the spec is gone.

A report is a statement about one tree. These tests check the two ways that
statement can stop being checkable: the contract file is missing, and the
source has moved on. Both must be reported as invalid rather than skipped.
"""

from __future__ import annotations

import importlib.util
import json
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
        check=False,
    )
    payload = json.loads(completed.stdout)
    expected = 1 if args[0] == "validate-report" and payload.get("valid") is False else 0
    if completed.returncode != expected:
        raise AssertionError(completed.stderr or completed.stdout)
    return payload


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


if __name__ == "__main__":
    unittest.main()
