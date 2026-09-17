import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CHECK = ROOT / "site-check" / "scripts" / "check.py"
SPEC = importlib.util.spec_from_file_location("v3_check", CHECK)
check = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check)

# A contract with three VAs spanning core_task / visual_desktop / visual_mobile
# so the protocol can scope a mobile-only visual failure to its own VA.
CONTRACT = """# 页面设计合同

```v3-contract
{
  "work_type": "new-surface",
  "structure_mode": "single",
  "acceptance": ["VA-01", "VA-02", "VA-03"],
  "unresolved_confirm": [],
  "blocking_missing_assets": [],
  "intentional_exceptions": []
}
```

## 视觉验收标准

| ID | 页面 / 状态 / 视口 | 可观察标准 | 检查轴 | 阻断 |
| --- | --- | --- | --- | --- |
| `VA-01` | `PG-01` | 登记后数量增加且可见 | `core_task` | `yes` |
| `VA-02` | `PG-01` / 桌面 | 桌面布局重心与首屏 | `visual_desktop` | `yes` |
| `VA-03` | `PG-01` / 375px | 窄屏信息保真 | `visual_mobile` | `yes` |
"""


class _ProjectBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        path = self.root / ".v3" / "design" / "surface-brief.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CONTRACT, encoding="utf-8")
        (self.root / "index.html").write_text("<html></html>", encoding="utf-8")
        self.plan = check.plan(self.root, ".v3/design/surface-brief.md")

    def tearDown(self):
        self.temp.cleanup()

    def _write_report(self, report, name="report.json"):
        path = self.root / ".v3" / name
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return path

    def _guided_report(self, **overrides):
        report = {
            "project_root": str(self.root.resolve()),
            "mode": "guided",
            "contract_sha256": self.plan["contract_sha256"],
            "source_sha256": self.plan["source_sha256"],
            "overall": "verified",
            "evidence": ["核心任务通过"],
            "limitations": [],
            "independent": False,
            "axes": {
                "contract": {"status": "verified"},
                "static_build": {"status": "verified"},
                "core_task": {"status": "verified", "failed_vas": []},
                "negative_path": {"status": "verified"},
                "visual_desktop": {"status": "verified", "failed_vas": []},
                "visual_mobile": {"status": "verified", "failed_vas": []},
            },
        }
        report.update(overrides)
        return report

    def _validate(self, report, name="report.json"):
        path = self._write_report(report, name)
        return check.validate_report(self.root, str(path))


class PlanTests(_ProjectBase):
    def test_plan_generation(self):
        result = self.plan
        self.assertEqual(result["mode"], "guided")
        self.assertEqual([level["level"] for level in result["levels"]],
                         ["L0", "L1", "L2", "L3", "L4", "L5"])
        self.assertEqual(result["levels"][0]["axes"], ["contract"])
        self.assertTrue(result["levels"][0]["browser"] is False)
        self.assertTrue(result["levels"][3]["browser"] is True)
        for axis in ("contract", "static_build", "core_task",
                     "negative_path", "visual_desktop", "visual_mobile"):
            self.assertIn(axis, result["required_axes"])
        # risk/reopen are guided-optional and not declared by any VA here.
        self.assertNotIn("risk", result["required_axes"])
        self.assertNotIn("reopen", result["required_axes"])
        self.assertTrue(result["contract_sha256"])
        self.assertTrue(result["source_sha256"])
        self.assertNotEqual(result["contract_sha256"], result["source_sha256"])
        self.assertEqual([va["id"] for va in result["acceptance"]],
                         ["VA-01", "VA-02", "VA-03"])
        self.assertTrue(result["rules"]["static_failure_blocks_browser"])

    def test_plan_changed_from_invalidates_on_contract_change(self):
        prior = self._write_report(self.plan, "prior.json")
        path = self.root / ".v3" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = check.plan(self.root, ".v3/design/surface-brief.md", changed_from=str(prior))
        self.assertTrue(result["changed_from"]["contract_changed"])
        self.assertFalse(result["changed_from"]["source_changed"])
        self.assertEqual(result["changed_from"]["invalidated_axes"], list(check.AXES))

    def test_plan_changed_from_invalidates_on_source_change(self):
        prior = self._write_report(self.plan, "prior.json")
        (self.root / "index.html").write_text("<html><body></body></html>", encoding="utf-8")
        result = check.plan(self.root, ".v3/design/surface-brief.md", changed_from=str(prior))
        self.assertTrue(result["changed_from"]["source_changed"])
        self.assertFalse(result["changed_from"]["contract_changed"])
        invalidated = result["changed_from"]["invalidated_axes"]
        self.assertIn("static_build", invalidated)
        self.assertIn("core_task", invalidated)
        self.assertIn("visual_mobile", invalidated)
        self.assertNotIn("contract", invalidated)

    def test_plan_changed_from_unavailable_ref_is_honest(self):
        result = check.plan(self.root, ".v3/design/surface-brief.md",
                            changed_from=str(self.root / "missing.json"))
        # An REF that is neither a readable report nor a resolvable git
        # revision is reported machine-readably and, per the protocol's
        # "never silently shrink coverage" rule, conservatively upgrades to
        # the guided-core floor rather than claiming nothing changed.
        self.assertFalse(result["changed_from"]["available"])
        self.assertTrue(result["changed_from"]["error"])
        self.assertEqual(result["changed_from"]["invalidated_axes"],
                         list(check.GUIDED_CORE))


class GitRefTests(_ProjectBase):
    """--changed-from also accepts a git revision; the project subtree is
    re-fingerprinted at that revision and compared to the working tree."""

    def _git(self, *args):
        import subprocess
        env = {"GIT_TERMINAL_PROMPT": "0",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(self.root), *args],
                        capture_output=True, env=env, timeout=30, check=True)

    def setUp(self):
        super().setUp()
        # Commit the plan's contract + source so HEAD is a usable baseline.
        self._git("init")
        self._git("add", "-A")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "baseline")
        # Re-derive the plan against the now-committed working tree.
        self.plan = check.plan(self.root, ".v3/design/surface-brief.md")

    def test_git_ref_no_change(self):
        result = check.plan(self.root, ".v3/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["available"])
        self.assertEqual(cf["source"], "git")
        self.assertTrue(cf["commit"])
        self.assertFalse(cf["contract_changed"])
        self.assertFalse(cf["source_changed"])
        self.assertEqual(cf["invalidated_axes"], [])

    def test_git_ref_source_only_change(self):
        (self.root / "index.html").write_text(
            "<html><body>changed</body></html>", encoding="utf-8")
        result = check.plan(self.root, ".v3/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["source_changed"])
        self.assertFalse(cf["contract_changed"])
        invalidated = cf["invalidated_axes"]
        self.assertIn("static_build", invalidated)
        self.assertIn("core_task", invalidated)
        self.assertIn("visual_mobile", invalidated)
        self.assertNotIn("contract", invalidated)
        self.assertEqual(invalidated, list(check.SOURCE_INVALIDATES))

    def test_git_ref_contract_change(self):
        path = self.root / ".v3" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = check.plan(self.root, ".v3/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["contract_changed"])
        # The contract lives under .v3 (ignored by the source scan), so a
        # contract-only edit must not also trip the source gate.
        self.assertFalse(cf["source_changed"])
        self.assertEqual(cf["invalidated_axes"], list(check.AXES))

    def test_git_ref_contract_added_since_ref(self):
        # Baseline ref predates the contract: the contract is absent at ref but
        # present now, which must conservatively invalidate every axis (never
        # silently drop L0).
        contract = self.root / ".v3" / "design" / "surface-brief.md"
        contents = contract.read_text(encoding="utf-8")
        contract.unlink()
        self._git("add", "-A")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "no-contract")
        contract.write_text(contents, encoding="utf-8")
        result = check.plan(self.root, ".v3/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["available"])
        self.assertTrue(cf["contract_changed"])
        self.assertEqual(cf["invalidated_axes"], list(check.AXES))

    def test_git_ref_invalid_revision_is_conservative(self):
        result = check.plan(self.root, ".v3/design/surface-brief.md",
                            changed_from="not-a-real-ref-xyz")
        cf = result["changed_from"]
        self.assertFalse(cf["available"])
        self.assertTrue(cf["error"])
        self.assertEqual(cf["invalidated_axes"], list(check.GUIDED_CORE))


class ValidateReportTests(_ProjectBase):
    def test_valid_guided_verified_report(self):
        result = self._validate(self._guided_report())
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["overall"], "verified")
        self.assertTrue(result["hash"]["contract_valid"])
        self.assertTrue(result["hash"]["source_valid"])

    def test_guided_allows_limited(self):
        report = self._guided_report(
            overall="limited", limitations=["尚未检查移动端"],
            evidence=["核心任务通过", "移动端未验"])
        report["axes"]["visual_mobile"] = {"status": "limited", "failed_vas": []}
        result = self._validate(report)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["overall"], "limited")

    def test_limited_without_limitations_is_invalid(self):
        report = self._guided_report(overall="limited", limitations=[])
        report["axes"]["visual_mobile"] = {"status": "limited", "failed_vas": []}
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("limitations" in e for e in result["errors"]))

    def test_static_failure_blocks_browser(self):
        report = self._guided_report()
        report["axes"]["static_build"] = {"status": "blocked"}
        for axis in ("core_task", "negative_path", "visual_desktop", "visual_mobile"):
            report["axes"][axis] = {"status": "not_run"}
        report["overall"] = "blocked"
        report["evidence"] = ["构建失败"]
        report["limitations"] = ["构建未通过"]
        result = self._validate(report)
        self.assertTrue(result["browser_blocked"])
        self.assertTrue(result["valid"], result["errors"])

    def test_static_failure_with_browser_axis_run_is_invalid(self):
        report = self._guided_report()
        report["axes"]["static_build"] = {"status": "blocked"}
        # core_task ran despite the static gate failing.
        report["axes"]["core_task"] = {"status": "verified", "failed_vas": []}
        report["overall"] = "blocked"
        report["evidence"] = ["构建失败"]
        report["limitations"] = ["构建未通过"]
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not_run" in e for e in result["errors"]))

    def test_mobile_single_axis_failure_reverifies_affected_va_only(self):
        report = self._guided_report()
        report["axes"]["visual_mobile"] = {"status": "blocked", "failed_vas": ["VA-03"]}
        report["axes"]["visual_desktop"] = {"status": "verified", "failed_vas": []}
        report["overall"] = "blocked"
        report["evidence"] = ["窄屏信息丢失"]
        report["limitations"] = ["移动端未通过"]
        result = self._validate(report)
        self.assertIn("visual_mobile", result["reverify"])
        self.assertNotIn("visual_desktop", result["reverify"])
        self.assertEqual(result["reverify_vas"],
                         [{"axis": "visual_mobile", "va": "VA-03"}])

    def test_hash_invalidation_on_source_change(self):
        (self.root / "index.html").write_text(
            "<html><body>changed</body></html>", encoding="utf-8")
        result = self._validate(self._guided_report())
        self.assertFalse(result["valid"])
        self.assertIn("core_task", result["invalidated_axes"])
        self.assertIn("static_build", result["invalidated_axes"])
        self.assertNotIn("contract", result["invalidated_axes"])

    def test_hash_invalidation_on_contract_change(self):
        path = self.root / ".v3" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = self._validate(self._guided_report())
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalidated_axes"], list(check.AXES))

    def test_overall_must_match_axis_results(self):
        report = self._guided_report(overall="verified")
        report["axes"]["core_task"] = {"status": "blocked", "failed_vas": ["VA-01"]}
        # overall says verified but an axis is blocked.
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("does not match" in e for e in result["errors"]))

    def test_unreadable_report_is_machine_readable_error(self):
        bad = self.root / ".v3" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        result = check.validate_report(self.root, str(bad))
        self.assertFalse(result["valid"])
        self.assertTrue(result["errors"])


class StrictModeTests(_ProjectBase):
    def _strict_report(self, **overrides):
        report = self._guided_report()
        report["mode"] = "strict"
        report["independent"] = True
        report["axes"]["reopen"] = {"status": "verified"}
        report["axes"]["risk"] = {"status": "verified"}
        report.update(overrides)
        return report

    def test_strict_verified_with_independent_is_valid(self):
        result = self._validate(self._strict_report())
        self.assertTrue(result["valid"], result["errors"])

    def test_strict_scope_requires_reopen_and_risk(self):
        (self.root / ".v3" / "state.json").write_text(
            json.dumps({"version": 3, "mode": "strict", "stage": "building"}), encoding="utf-8")
        strict_plan = check.plan(self.root, ".v3/design/surface-brief.md")
        self.assertIn("reopen", strict_plan["required_axes"])
        self.assertIn("risk", strict_plan["required_axes"])
        self.assertNotIn("risk", self.plan["required_axes"])

    def test_strict_rejects_limited(self):
        report = self._strict_report(overall="limited", limitations=["未独立检查"],
                                     independent=False)
        report["axes"]["visual_mobile"] = {"status": "limited", "failed_vas": []}
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("strict" in e for e in result["errors"]))

    def test_strict_verified_requires_independent(self):
        report = self._strict_report(independent=False)
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("independent" in e for e in result["errors"]))

    def test_strict_missing_risk_axis_is_invalid(self):
        report = self._strict_report(independent=True)
        del report["axes"]["risk"]
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("risk" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
