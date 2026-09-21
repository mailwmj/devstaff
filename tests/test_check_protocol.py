import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CHECK = ROOT / "release" / "skills" / "site-check" / "scripts" / "check.py"
SPEC = importlib.util.spec_from_file_location("site_check", CHECK)
check = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check)

# A contract with three VAs spanning core_task / visual_desktop / visual_mobile
# so the protocol can scope a mobile-only visual failure to its own VA.
CONTRACT = """# 页面设计合同

```site-contract
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


def _measured(what, **extra):
    """A passing axis: just what it examined."""
    entry = {"status": "verified", "observed": what}
    entry.update(extra)
    return entry


class _ProjectBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CONTRACT, encoding="utf-8")
        (self.root / "index.html").write_text("<html></html>", encoding="utf-8")
        self.plan = check.plan(self.root, ".site/design/surface-brief.md")

    def tearDown(self):
        self.temp.cleanup()

    def _write_report(self, report, name="report.json"):
        path = self.root / ".site" / name
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
                "contract": _measured("合同块与 3 条 VA"),
                "static_build": _measured("构建与类型检查"),
                "core_task": _measured("登记链路", failed_vas=[]),
                "negative_path": _measured("空数量提交"),
                "visual_desktop": _measured("1440px 首屏", failed_vas=[]),
                "visual_mobile": _measured("375px 首屏", failed_vas=[]),
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

    def test_plan_changed_from_reports_contract_change(self):
        prior = self._write_report(self.plan, "prior.json")
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md", changed_from=str(prior))
        cf = result["changed_from"]
        self.assertTrue(cf["contract_changed"])
        self.assertFalse(cf["source_changed"])
        # The plan reports the fact; it does not decide which axes to re-run.
        self.assertNotIn("invalidated_axes", cf)
        self.assertEqual(cf["changed_files"], {"added": [], "removed": [],
                                               "modified": [], "truncated": False})

    def test_plan_changed_from_reports_source_change(self):
        prior = self._write_report(self.plan, "prior.json")
        (self.root / "index.html").write_text("<html><body></body></html>", encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md", changed_from=str(prior))
        cf = result["changed_from"]
        self.assertTrue(cf["source_changed"])
        self.assertFalse(cf["contract_changed"])
        self.assertEqual(cf["changed_files"]["modified"], ["index.html"])
        self.assertEqual(cf["changed_files"]["added"], [])

    def test_plan_changed_from_unavailable_ref_is_honest(self):
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from=str(self.root / "missing.json"))
        # An REF that is neither a readable report nor a resolvable git
        # revision is reported machine-readably instead of guessing a scope.
        # The report gate still refuses anything that does not match this tree.
        cf = result["changed_from"]
        self.assertFalse(cf["available"])
        self.assertTrue(cf["error"])
        self.assertIsNone(cf["changed_files"])

    def test_plan_reports_what_it_excluded(self):
        (self.root / "data").mkdir()
        (self.root / "data" / "inventory.db").write_bytes(b"state")
        (self.root / "data" / "products.json").write_text('{"price": 10}', encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "data.json").write_text("{}", encoding="utf-8")
        (self.root / "notes.log").write_text("x", encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md")
        self.assertIn("data/inventory.db", result["source_excluded"])
        self.assertIn("notes.log", result["source_excluded"])
        # A product directory that merely happens to be called data/ stays in:
        # a static site's data/products.json is content, and excluding the
        # whole directory made reports independent of it. Only the runtime
        # suffix rule keeps data/inventory.db out.
        self.assertIn("data/products.json", result["source_manifest"])
        self.assertNotIn("data/products.json", result["source_excluded"])
        self.assertIn("src/data.json", result["source_manifest"])
        self.assertNotIn("src/data.json", result["source_excluded"])
        self.assertEqual(result["source_files"], len(result["source_manifest"]))

    def test_nested_state_file_is_excluded_at_any_depth(self):
        """1.1 matches state-file suffixes at every depth, not just the root.

        The 1.0 rule kept a nested ``.sqlite`` in the fingerprint as product
        source; now any runtime file the product writes while in use is
        excluded, wherever it sits. The rule is about the suffix, so nested
        product source still counts.
        """
        (self.root / "src").mkdir()
        database = self.root / "src" / "catalog.sqlite"
        database.write_bytes(b"v1")
        plan = check.plan(self.root)
        self.assertNotIn("src/catalog.sqlite", plan["source_manifest"])
        self.assertIn("src/catalog.sqlite", plan["source_excluded"])
        before = plan["source_sha256"]
        database.write_bytes(b"v2")
        self.assertEqual(check.plan(self.root)["source_sha256"], before,
                         "a nested state file must not change the fingerprint")

        product = self.root / "src" / "catalog.json"
        product.write_text("{}", encoding="utf-8")
        with_product = check.plan(self.root)["source_sha256"]
        product.write_text('{"items": 1}', encoding="utf-8")
        self.assertNotEqual(check.plan(self.root)["source_sha256"], with_product,
                            "nested product source still belongs in the fingerprint")

    def test_runtime_state_does_not_invalidate_a_report(self):
        # The failure this replaces: the shopkeeper sells one bottle, the
        # database changes, and every axis is invalidated.
        baseline = check.plan(self.root, ".site/design/surface-brief.md")
        report = self._validate(self._guided_report())
        self.assertTrue(report["valid"], report["errors"])
        (self.root / "data").mkdir()
        (self.root / "data" / "inventory.db").write_bytes(b"sold one bottle")
        after = check.plan(self.root, ".site/design/surface-brief.md")
        self.assertEqual(after["source_sha256"], baseline["source_sha256"])
        self.assertTrue(self._validate(self._guided_report())["valid"])

    def test_plan_auto_detects_the_contract_when_no_flag_is_given(self):
        """--contract defaults to None so plan detects the contract path.

        A hardcoded argparse default made the auto-detect branch unreachable
        through the CLI and quietly pinned the default layout.
        """
        parser = check.build_parser()
        args = parser.parse_args(["plan", str(self.root)])
        self.assertIsNone(args.contract)
        result = check.plan(self.root, args.contract)
        self.assertTrue(result["contract_sha256"])

    def test_editing_a_check_script_is_a_source_change(self):
        # Check scripts are evidence, not bookkeeping: changing one invalidates
        # the report it produced, because the PASS came from the old script.
        (self.root / "app").mkdir()
        (self.root / "app" / "check.mjs").write_text("run()", encoding="utf-8")
        prior = check.plan(self.root, ".site/design/surface-brief.md")
        (self.root / "app" / "check.mjs").write_text("run(2)", encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from=self._write_report(prior, "prior.json"))
        self.assertEqual(result["changed_from"]["changed_files"]["modified"],
                         ["app/check.mjs"])


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
        self.plan = check.plan(self.root, ".site/design/surface-brief.md")

    def test_git_ref_no_change(self):
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["available"])
        self.assertEqual(cf["source"], "git")
        self.assertTrue(cf["commit"])
        self.assertFalse(cf["contract_changed"])
        self.assertFalse(cf["source_changed"])
        self.assertEqual(cf["changed_files"], {"added": [], "removed": [],
                                               "modified": [], "truncated": False})

    def test_git_ref_source_only_change(self):
        (self.root / "index.html").write_text(
            "<html><body>changed</body></html>", encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["source_changed"])
        self.assertFalse(cf["contract_changed"])
        self.assertEqual(cf["changed_files"]["modified"], ["index.html"])
        self.assertEqual(result["source_sha256"],
                         check.source_sha256(self.root))

    def test_git_ref_lists_added_and_removed_files(self):
        (self.root / "extra.css").write_text("body{}", encoding="utf-8")
        (self.root / "index.html").unlink()
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]["changed_files"]
        self.assertEqual(cf["added"], ["extra.css"])
        self.assertEqual(cf["removed"], ["index.html"])
        self.assertEqual(cf["modified"], [])

    def test_git_ref_contract_change(self):
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["contract_changed"])
        # The contract lives under .site (ignored by the source scan), so a
        # contract-only edit must not also trip the source gate.
        self.assertFalse(cf["source_changed"])
        self.assertEqual(cf["changed_files"]["modified"], [])

    def test_git_ref_contract_added_since_ref(self):
        # Baseline ref predates the contract: the contract is absent at ref but
        # present now, which must conservatively count as a contract change
        # (never silently drop L0).
        contract = self.root / ".site" / "design" / "surface-brief.md"
        contents = contract.read_text(encoding="utf-8")
        contract.unlink()
        self._git("add", "-A")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "no-contract")
        contract.write_text(contents, encoding="utf-8")
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from="HEAD")
        cf = result["changed_from"]
        self.assertTrue(cf["available"])
        self.assertTrue(cf["contract_changed"])

    def test_git_ref_invalid_revision_is_honest(self):
        result = check.plan(self.root, ".site/design/surface-brief.md",
                            changed_from="not-a-real-ref-xyz")
        cf = result["changed_from"]
        self.assertFalse(cf["available"])
        self.assertTrue(cf["error"])
        self.assertIsNone(cf["changed_files"])


class ValidateReportTests(_ProjectBase):
    def test_valid_guided_verified_report(self):
        result = self._validate(self._guided_report())
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["overall"], "verified")
        self.assertTrue(result["hash"]["contract_valid"])
        self.assertTrue(result["hash"]["source_valid"])

    def test_verified_axis_needs_to_say_what_it_measured(self):
        report = self._guided_report()
        report["axes"]["visual_desktop"] = {"status": "verified"}
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("what was observed" in e for e in result["errors"]))

    def test_runtime_state_does_not_invalidate_a_report(self):
        (self.root / "data").mkdir()
        (self.root / "data" / "inventory.db").write_bytes(b"state")
        result = self._validate(self._guided_report())
        self.assertTrue(result["valid"], result["errors"])

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
        report["axes"]["core_task"] = _measured("登记链路", failed_vas=[])
        report["overall"] = "blocked"
        report["evidence"] = ["构建失败"]
        report["limitations"] = ["构建未通过"]
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not_run" in e for e in result["errors"]))

    def test_mobile_single_axis_failure_reverifies_affected_va_only(self):
        report = self._guided_report()
        report["axes"]["visual_mobile"] = {"status": "blocked", "failed_vas": ["VA-03"]}
        report["axes"]["visual_desktop"] = _measured("1440px 首屏", failed_vas=[])
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
        path = self.root / ".site" / "design" / "surface-brief.md"
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
        bad = self.root / ".site" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        result = check.validate_report(self.root, str(bad))
        self.assertFalse(result["valid"])
        self.assertTrue(result["errors"])

    def test_missing_contract_is_invalid(self):
        """1.1 refuses to validate a report when the contract cannot be read.

        Skipping the fingerprint comparison here used to accept any stale
        report once the contract file was gone, which turned a missing spec
        into a passing delivery.
        """
        contract = self.root / ".site" / "design" / "surface-brief.md"
        contract.unlink()
        result = self._validate(self._guided_report())
        self.assertFalse(result["valid"])
        self.assertTrue(any("contract is missing or unreadable" in e for e in result["errors"]),
                        result["errors"])

    def test_strict_project_rejects_a_guided_report(self):
        """A strict project's check report must say strict.

        The cross-check is one-way: a guided report cannot deliver a strict
        project, while a strict report written when the project was guided is
        not retroactively invalid. 1.1 left this to state.py's verify and the
        protocol accepted either mode, which made the strict gate bypassable
        by declaring guided.
        """
        (self.root / ".site" / "state.json").write_text(
            json.dumps({"version": 3, "mode": "strict", "stage": "building"}),
            encoding="utf-8",
        )
        report = self._guided_report(mode="guided")
        result = self._validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("project state is strict" in e for e in result["errors"]),
            result["errors"],
        )

    def test_guided_project_does_not_reject_a_strict_report(self):
        report = self._guided_report()
        report["mode"] = "strict"
        report["independent"] = True
        report["axes"]["reopen"] = _measured("刷新后数据保持")
        report["axes"]["risk"] = _measured("密钥与公开数据面")
        result = self._validate(report)
        self.assertTrue(result["valid"], result["errors"])

    def test_independent_must_be_a_json_boolean(self):
        """A JSON boolean, not a truthy stand-in.

        1.1 normalised with bool(), so the string "false" counted as
        independent -- exactly the value a hand-written report reaches for
        when it means "no". The gate must read what the JSON type says.
        """
        guided = self._validate(self._guided_report(independent="false"))
        self.assertFalse(guided["valid"])
        self.assertTrue(any("independent must be a JSON boolean" in e
                            for e in guided["errors"]), guided["errors"])
        self.assertFalse(guided["independent"])

        strict = self._guided_report(mode="strict", independent="false")
        strict["axes"]["reopen"] = _measured("刷新后数据保持")
        strict["axes"]["risk"] = _measured("密钥与公开数据面")
        rejected = self._validate(strict, name="strict.json")
        self.assertFalse(rejected["valid"])
        self.assertTrue(any("independent must be a JSON boolean" in e
                            for e in rejected["errors"]), rejected["errors"])

        strict["independent"] = True
        accepted = self._validate(strict, name="strict-ok.json")
        self.assertTrue(accepted["valid"], accepted["errors"])
        self.assertTrue(accepted["independent"])


class ValidateReportShapeTests(_ProjectBase):
    """Malformed report/state shapes are errors, never silent defaults."""

    def test_project_root_missing_is_invalid_even_from_inside_the_project(self):
        report = self._guided_report()
        del report["project_root"]
        path = self._write_report(report)
        previous = os.getcwd()
        try:
            os.chdir(self.root)
            result = check.validate_report(self.root, str(path))
        finally:
            os.chdir(previous)
        self.assertFalse(result["valid"])
        self.assertTrue(any("project_root" in e for e in result["errors"]),
                        result["errors"])

    def test_read_mode_guided_without_a_state_file(self):
        self.assertEqual(check.read_mode(self.root), "guided")

    def test_read_mode_reports_a_broken_state(self):
        state_path = self.root / ".site" / "state.json"
        cases = {
            "invalid utf-8": b"\xff\xfe\x00\x01",
            "broken json": b"{not json",
            "not an object": b"[1, 2, 3]",
            "illegal mode": b'{"mode": "off"}',
        }
        for label, payload in cases.items():
            with self.subTest(label=label):
                state_path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    check.read_mode(self.root)
        state_path.unlink()

    def test_validate_report_surfaces_a_broken_state(self):
        (self.root / ".site" / "state.json").write_text("{not json", encoding="utf-8")
        result = self._validate(self._guided_report())
        self.assertFalse(result["valid"])
        self.assertTrue(any("project state" in e for e in result["errors"]),
                        result["errors"])

    def test_toolchain_dirs_tolerates_broken_declarations(self):
        declaration = self.root / "skills.json"
        declaration.write_bytes(b"\xff\xfe")
        self.assertEqual(check.toolchain_dirs(self.root), ())
        declaration.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(check.toolchain_dirs(self.root), ())

    def test_source_manifest_value_error_is_reported_not_raised(self):
        original = check.source_manifest
        check.source_manifest = lambda root: (_ for _ in ()).throw(ValueError("boom"))
        try:
            result = self._validate(self._guided_report())
        finally:
            check.source_manifest = original
        self.assertFalse(result["valid"])
        self.assertTrue(any("source tree is unreadable" in e for e in result["errors"]),
                        result["errors"])

    def test_failed_vas_must_be_a_list_of_non_empty_strings(self):
        report = self._guided_report()
        report["axes"]["visual_mobile"] = {"status": "blocked", "failed_vas": "VA-03"}
        result = self._validate(report, name="vas-string.json")
        self.assertFalse(result["valid"])
        self.assertTrue(any("failed_vas must be a list" in e for e in result["errors"]),
                        result["errors"])

        report["axes"]["visual_mobile"] = {"status": "blocked", "failed_vas": [3, ""]}
        result = self._validate(report, name="vas-int.json")
        self.assertFalse(result["valid"])
        self.assertTrue(any("failed_vas entries" in e for e in result["errors"]),
                        result["errors"])

    def test_static_not_run_blocks_the_browser_axes(self):
        report = self._guided_report()
        report["axes"]["static_build"] = {"status": "not_run"}
        result = self._validate(report)
        self.assertTrue(result["browser_blocked"])
        self.assertFalse(result["valid"])
        self.assertTrue(any("not_run" in e for e in result["errors"]), result["errors"])

    def test_evidence_and_limitations_shapes_are_checked(self):
        report = self._guided_report(evidence="核心任务通过")
        result = self._validate(report, name="evidence-string.json")
        self.assertFalse(result["valid"])
        self.assertTrue(any("evidence must be a list" in e for e in result["errors"]),
                        result["errors"])

        report = self._guided_report(evidence=["核心任务通过", 7])
        result = self._validate(report, name="evidence-int.json")
        self.assertFalse(result["valid"])
        self.assertTrue(any("evidence entries" in e for e in result["errors"]),
                        result["errors"])

        report = self._guided_report(limitations=[None])
        result = self._validate(report, name="limitations-null.json")
        self.assertFalse(result["valid"])
        self.assertTrue(any("limitations entries" in e for e in result["errors"]),
                        result["errors"])

    def test_verified_observed_must_be_a_non_empty_string(self):
        report = self._guided_report()
        report["axes"]["core_task"] = {"status": "verified", "observed": 7}
        result = self._validate(report, name="observed-int.json")
        self.assertFalse(result["valid"])
        self.assertTrue(any("what was observed" in e for e in result["errors"]),
                        result["errors"])

    def test_malformed_reports_stay_machine_readable_without_traceback(self):
        bad = self.root / ".site" / "malformed.json"
        bad.write_text('{"axes": "nope", "failed_vas": {"x": 1}}', encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(CHECK), "validate-report", str(self.root), str(bad)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["valid"])


class StrictModeTests(_ProjectBase):
    def _strict_report(self, **overrides):
        (self.root / ".site" / "state.json").write_text(
            json.dumps({"version": 3, "mode": "strict", "stage": "building"}),
            encoding="utf-8",
        )
        report = self._guided_report()
        report["mode"] = "strict"
        report["independent"] = True
        report["axes"]["reopen"] = _measured("刷新后数据保持")
        report["axes"]["risk"] = _measured("密钥与公开数据面")
        report.update(overrides)
        return report

    def test_strict_verified_with_independent_is_valid(self):
        result = self._validate(self._strict_report())
        self.assertTrue(result["valid"], result["errors"])

    def test_strict_scope_requires_reopen_and_risk(self):
        (self.root / ".site" / "state.json").write_text(
            json.dumps({"version": 3, "mode": "strict", "stage": "building"}), encoding="utf-8")
        strict_plan = check.plan(self.root, ".site/design/surface-brief.md")
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


class CheckCompatibilityTests(unittest.TestCase):
    def test_legacy_v3_contract_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / ".v3" / "design" / "surface-brief.md"
            path.parent.mkdir(parents=True)
            path.write_text(CONTRACT, encoding="utf-8")
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            plan = check.plan(root)
            self.assertEqual(plan["contract_path"], ".v3/design/surface-brief.md")
            self.assertTrue(plan["contract_sha256"])

    def test_case_insensitive_SITE_contract_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / ".SITE" / "design" / "surface-brief.md"
            path.parent.mkdir(parents=True)
            path.write_text(CONTRACT, encoding="utf-8")
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            plan = check.plan(root)
            self.assertEqual(plan["contract_path"].lower(), ".site/design/surface-brief.md")
            self.assertTrue(plan["contract_sha256"])


class VaParsingGuardTests(unittest.TestCase):
    """The contract JSON and the parsed VA table must agree.

    A drifted table header parses to zero rows; treating that as "no VAs"
    silently drops every axis the contract declared.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".site" / "design").mkdir(parents=True)
        (self.root / "index.html").write_text("<html></html>", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _contract(self, acceptance, axis="core_task", va_id="VA-01", va_row=True):
        rows = ("| `%s` | `PG-01` | 登记后可见 | `%s` | `yes` |\n" % (va_id, axis)
                if va_row else "")
        text = (
            "# 合同\n\n```site-contract\n{\n  \"acceptance\": %s\n}\n```\n\n"
            "## 视觉验收标准\n\n"
            "| ID | 页面 / 状态 / 视口 | 可观察标准 | 检查轴 | 阻断 |\n"
            "| --- | --- | --- | --- | --- |\n" % json.dumps(acceptance, ensure_ascii=False)
        ) + rows
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_acceptance_naming_a_missing_va_is_rejected(self):
        path = self._contract(["VA-01", "VA-99"])
        with self.assertRaises(ValueError) as caught:
            check.read_contract_file(path)
        self.assertIn("VA-99", str(caught.exception))

    def test_acceptance_naming_an_illegal_axis_is_rejected(self):
        path = self._contract(["VA-01"], axis="visual")
        with self.assertRaises(ValueError):
            check.read_contract_file(path)

    def test_empty_acceptance_is_legal(self):
        path = self._contract([])
        _sha, _data, vas = check.read_contract_file(path)
        self.assertEqual([va["id"] for va in vas], ["VA-01"])

    def test_empty_acceptance_without_a_table_is_legal(self):
        path = self._contract([], va_row=False)
        _sha, _data, vas = check.read_contract_file(path)
        self.assertEqual(vas, [])

    def test_backticked_va_without_a_parsable_table_is_rejected(self):
        text = ("# 合同\n\n```site-contract\n{\"acceptance\": []}\n```\n\n"
                "正文提到 `VA-01` 但没有验收表。\n")
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(ValueError):
            check.read_contract_file(path)


if __name__ == "__main__":
    unittest.main()
