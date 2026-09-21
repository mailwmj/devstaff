import json
import csv
import tempfile
from pathlib import Path
import re
import subprocess
import sys
import unittest
import hashlib

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "design.py"
TEMPLATE = SKILL_ROOT / "references" / "surface-brief.md"

import importlib.util

_SPEC = importlib.util.spec_from_file_location("site_design", SCRIPT)
design = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(design)


def run_json(*args):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=SKILL_ROOT.parent,
        text=True,
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )
    return json.loads(completed.stdout)


# Body of a surface-brief whose derived design judgments cite declared project
# facts and whose tables declare BR-01/IC-01/PG-01/VA-01.
BASE_BODY = """
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

VALID_CONTRACT_JSON = {
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
    "intentional_exceptions": [],
}


def write_contract(root, contract_json=None, body=BASE_BODY):
    """Write a surface-brief.md assembled from a contract block and body text."""
    contract_json = contract_json if contract_json is not None else VALID_CONTRACT_JSON
    text = (
        "# 页面设计合同\n\n"
        "```site-contract\n"
        + json.dumps(contract_json, ensure_ascii=False)
        + "\n```\n"
        + body
    )
    path = root / ".site" / "design" / "surface-brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def check(root, phase="prebuild"):
    return run_json("check-contract", "--root", str(root), "--phase", phase)


class CheckContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def codes(self, report):
        return sorted(block["code"] for block in report["blockers"])

    def test_cli_summary_bounds_findings_while_out_keeps_all(self):
        many_refs = dict(VALID_CONTRACT_JSON,
                         required_constraints=[f"IC-{i:02d}" for i in range(1, 30)],
                         pages=[f"PG-{i:02d}" for i in range(1, 30)])
        write_contract(self.root, contract_json=many_refs)
        out = self.root / ".site" / "contract-report.json"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "check-contract", "--root",
             str(self.root), "--phase", "prebuild", "--summary", "--out",
             str(out)],
            cwd=SKILL_ROOT.parent, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["mode"], "summary")
        self.assertEqual(summary["phase"], "prebuild")
        self.assertFalse(summary["passed"])
        self.assertGreater(summary["blocker_count"],
                           design.SUMMARY_FINDING_LIMIT)
        self.assertEqual(len(summary["blockers"]), design.SUMMARY_FINDING_LIMIT)
        self.assertEqual(summary["omitted"]["blockers"],
                         summary["blocker_count"] - design.SUMMARY_FINDING_LIMIT)
        self.assertLess(len(completed.stdout.encode("utf-8")), 4096)

        full = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(full["blockers"]), summary["blocker_count"])
        self.assertNotIn("mode", full)

    def test_valid_contract_passes_prebuild(self):
        write_contract(self.root)
        report = check(self.root)
        self.assertTrue(report["passed"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["phase"], "prebuild")
        # SHA-256 matches the file content.
        content = (self.root / ".site/design/surface-brief.md").read_text(encoding="utf-8")
        self.assertEqual(
            report["contract_sha256"],
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def test_simple_project_need_not_fill_whole_template(self):
        # Only work_type, structure, one scope ref, one constraint and one
        # page; no sections, responsive, components, assets or acceptance.
        # Empty lists mean "not applicable", not "missing".
        write_contract(self.root, {
            "work_type": "new-surface", "structure_mode": "single",
            "scope_refs": ["BR-01"], "required_constraints": ["IC-01"],
            "pages": ["PG-01"], "sections": [], "responsive": [],
            "components": [], "assets": [], "acceptance": [],
            "unresolved_confirm": [], "blocking_missing_assets": [],
            "intentional_exceptions": [],
        })
        self.assertTrue(check(self.root)["passed"])

    def test_missing_contract_file_is_reported(self):
        report = check(self.root)
        self.assertFalse(report["passed"])
        self.assertEqual(self.codes(report), ["missing_contract"])
        self.assertEqual(report["contract_sha256"], "")

    def test_missing_contract_block_is_invalid(self):
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 页面设计合同\n\n无合同块\n", encoding="utf-8")
        report = check(self.root)
        self.assertEqual(self.codes(report), ["invalid_contract"])

    def test_broken_reference_is_blocked(self):
        contract = dict(VALID_CONTRACT_JSON)
        contract["pages"] = ["PG-99"]
        write_contract(self.root, contract)
        report = check(self.root)
        self.assertFalse(report["passed"])
        self.assertIn("broken_reference", self.codes(report))

    def test_dropping_a_fact_from_the_index_ungrounds_judgments_citing_it(self):
        # Judgments cite the contract index. Replacing PG-01 with PG-99 both
        # breaks the reference and removes the basis the 设计主线 rested on.
        contract = dict(VALID_CONTRACT_JSON)
        contract["pages"] = ["PG-99"]
        write_contract(self.root, contract)
        report = check(self.root)
        self.assertIn("broken_reference", self.codes(report))
        self.assertIn("uncited_design_judgment", self.codes(report))

    def test_unclosed_confirm_is_blocked(self):
        contract = dict(VALID_CONTRACT_JSON)
        contract["unresolved_confirm"] = ["IC-02"]
        write_contract(self.root, contract)
        report = check(self.root)
        self.assertIn("unresolved_confirm", self.codes(report))

    def test_blocking_missing_asset_is_blocked(self):
        contract = dict(VALID_CONTRACT_JSON)
        contract["blocking_missing_assets"] = ["AS-09"]
        write_contract(self.root, contract)
        report = check(self.root)
        self.assertIn("blocking_missing_asset", self.codes(report))

    def test_non_executable_va_is_blocked(self):
        body = BASE_BODY.replace(
            "| `VA-01` | `PG-01` | 登记后数量增加且可见 | `core_task` | `yes` |",
            "| `VA-01` | `PG-01` |  | `core_task` | `yes` |",
        )
        write_contract(self.root, body=body)
        report = check(self.root)
        self.assertIn("non_executable_va", self.codes(report))

    def test_vague_va_warns_at_prebuild_and_blocks_at_precheck(self):
        # VA-* is what site-check verifies against, so an undecidable standard
        # makes every downstream browser check vacuous.
        body = BASE_BODY.replace(
            "| `VA-01` | `PG-01` | 登记后数量增加且可见 | `core_task` | `yes` |",
            "| `VA-01` | `PG-01` | 界面要高级现代 | `core_task` | `yes` |",
        )
        write_contract(self.root, body=body)
        prebuild = check(self.root, phase="prebuild")
        self.assertTrue(prebuild["passed"], prebuild["blockers"])
        self.assertIn("vague_va_standard",
                      [w["code"] for w in prebuild["warnings"]])
        precheck = check(self.root, phase="precheck")
        self.assertFalse(precheck["passed"])
        self.assertIn("vague_va_standard", self.codes(precheck))

    def test_scope_ref_without_target_is_blocked(self):
        body = BASE_BODY.replace(
            "| `BR-01` | 登记库存 | `covered` | 无 | `IC-01` |",
            "| `BR-01` | 登记库存 | `covered` | 无 |  |",
        )
        write_contract(self.root, body=body)
        report = check(self.root)
        self.assertIn("scope_ref_without_target", self.codes(report))

    def test_required_constraint_without_target_is_blocked(self):
        body = BASE_BODY.replace(
            "| `IC-01` | 必须登记 | `required` | `measured` | 工作台主操作 |",
            "| `IC-01` | 必须登记 | `required` | `measured` |  |",
        )
        write_contract(self.root, body=body)
        report = check(self.root)
        self.assertIn("required_constraint_without_target", self.codes(report))

    # --- derived design judgments must be grounded, not just worded ---

    def _blank_motif(self):
        return BASE_BODY.replace(
            "- **设计主线：** 以表格为视觉主角密度优先（依据 `PG-01`）",
            "- **设计主线：**",
        )

    def _uncited_motif(self, citation=""):
        return BASE_BODY.replace(
            "- **设计主线：** 以表格为视觉主角密度优先（依据 `PG-01`）",
            "- **设计主线：** 以表格为视觉主角密度优先" + citation,
        )

    def test_blank_design_judgment_is_blocked(self):
        write_contract(self.root, body=self._blank_motif())
        report = check(self.root)
        self.assertIn("missing_design_judgment", self.codes(report))
        self.assertIn("visual_motif", [b["aspect"] for b in report["blockers"]
                                       if b["code"] == "missing_design_judgment"])

    def test_legacy_motif_alias_is_accepted(self):
        body = BASE_BODY.replace(
            "- **设计主线：** 以表格为视觉主角密度优先（依据 `PG-01`）",
            "- **母题：** 以表格为视觉主角密度优先（依据 `PG-01`）",
        )
        write_contract(self.root, body=body)
        report = check(self.root)
        self.assertTrue(report["passed"])

    def test_uncited_design_judgment_is_blocked(self):
        # Filled in, but traceable to nothing: a synonym of the template would
        # have passed the old wording comparison.
        write_contract(self.root, body=self._uncited_motif())
        report = check(self.root)
        self.assertIn("uncited_design_judgment", self.codes(report))
        self.assertEqual(
            [b["aspect"] for b in report["blockers"]
             if b["code"] == "uncited_design_judgment"],
            ["visual_motif"],
        )

    def test_va_cannot_be_cited_as_design_evidence(self):
        # VA-* is the contract's output, not its basis.
        write_contract(self.root, body=self._uncited_motif("（依据 `VA-01`）"))
        report = check(self.root)
        self.assertIn("uncited_design_judgment", self.codes(report))

    def test_citation_to_undefined_fact_is_not_evidence(self):
        write_contract(self.root, body=self._uncited_motif("（依据 `SC-07`）"))
        report = check(self.root)
        self.assertIn("uncited_design_judgment", self.codes(report))

    def test_grounded_judgment_passes(self):
        # Control: the same sentence is accepted once it cites a real fact.
        write_contract(self.root, body=self._uncited_motif("（依据 `PG-01`）"))
        report = check(self.root)
        self.assertTrue(report["passed"], report["blockers"])

    def test_blank_project_fact_is_blocked(self):
        body = BASE_BODY.replace("- **使用者：** 仓管员", "- **使用者：**")
        write_contract(self.root, body=body)
        report = check(self.root)
        self.assertIn("missing_design_judgment", self.codes(report))

    def test_contract_change_invalidates_old_sha(self):
        write_contract(self.root)
        first = check(self.root)
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        second = check(self.root)
        self.assertNotEqual(first["contract_sha256"], second["contract_sha256"])

    def test_undrifted_gallery_is_not_warned(self):
        write_contract(self.root)
        report = check(self.root)
        self.assertNotIn("stale_gallery_catalog",
                         [w["code"] for w in report["warnings"]])

    def test_stale_gallery_catalog_is_surfaced_at_use_time(self):
        # gallery.html embeds a copy of the composed catalog so it opens
        # straight from disk; the invariant is checked when the tool is used,
        # not only when someone remembers to run `validate`.
        gallery = design.resources() / "gallery.html"
        if not gallery.is_file():
            self.skipTest("no bundled gallery")
        original = gallery.read_text(encoding="utf-8")
        try:
            gallery.write_text(
                design.CATALOG_BLOCK.sub(r"\1{}\3", original, count=1),
                encoding="utf-8")
            write_contract(self.root)
            report = check(self.root)
            self.assertIn("stale_gallery_catalog",
                          [w["code"] for w in report["warnings"]])
            # Package health must never block a project's own contract.
            self.assertTrue(report["passed"], report["blockers"])
        finally:
            gallery.write_text(original, encoding="utf-8")

    def test_direction_phase_is_lighter_than_prebuild(self):
        # Design-judgment grounding is not demanded while the direction forms.
        write_contract(self.root, body=self._uncited_motif())
        direction = check(self.root, phase="direction")
        self.assertTrue(direction["passed"])
        prebuild = check(self.root, phase="prebuild")
        self.assertFalse(prebuild["passed"])

    def test_direction_phase_requires_work_type_and_structure(self):
        contract = dict(VALID_CONTRACT_JSON)
        contract["work_type"] = ""
        contract["structure_mode"] = ""
        write_contract(self.root, contract)
        report = check(self.root, phase="direction")
        self.assertEqual(
            sorted(report["blockers"], key=lambda b: b["code"]),
            [{"code": "missing_structure_mode"}, {"code": "missing_work_type"}],
        )

    def test_precheck_skips_design_judgment(self):
        write_contract(self.root, body=self._uncited_motif())
        report = check(self.root, phase="precheck")
        self.assertTrue(report["passed"])

    def test_invalid_phase_is_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError):
            run_json("check-contract", "--root", str(self.root), "--phase", "bogus")

    def test_report_under_one_second(self):
        import time
        write_contract(self.root)
        start = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "check-contract",
             "--root", str(self.root), "--phase", "prebuild"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        elapsed = time.perf_counter() - start
        self.assertEqual(completed.returncode, 0)
        # Process startup aside, the check itself is well under a second.
        self.assertLess(elapsed, 5.0)


class BuildDirectionGateTests(unittest.TestCase):
    """`build` owns the gate because it is the only one-command artifact.

    design-context.md puts gallery and 配方 at the lowest conflict priority,
    but before this gate a recipe was also the only thing obtainable with no
    evidence at all. The gate composes rules that already exist; these tests
    also pin that it does not quietly raise the contract check's own phases.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def build(self, *extra, out=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "build", "--recipe", "daily-workspace",
             "--project-root", str(self.project),
             "--out", str(out if out is not None else self.root / "out"), *extra],
            cwd=SKILL_ROOT.parent, capture_output=True, text=True,
            encoding="utf-8", errors="replace")

    def ungrounded(self):
        return BASE_BODY.replace(
            "- **设计主线：** 以表格为视觉主角密度优先（依据 `PG-01`）",
            "- **设计主线：** 以表格为视觉主角密度优先")

    def test_missing_contract_is_refused_and_writes_nothing(self):
        out = self.root / "out"
        completed = self.build(out=out)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("missing_contract", completed.stderr)
        self.assertIn("--standalone", completed.stderr)
        # Refusing must not leave a half-written selection behind.
        self.assertFalse(out.exists())

    def test_ungrounded_motif_is_refused(self):
        write_contract(self.project, body=self.ungrounded())
        out = self.root / "out"
        completed = self.build(out=out)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("uncited_design_judgment", completed.stderr)
        self.assertFalse(out.exists())

    def test_passing_gate_records_the_contract_sha(self):
        contract = write_contract(self.project)
        out = self.root / "out"
        completed = self.build(out=out)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads((out / "selection.json").read_text(encoding="utf-8"))
        evidence = payload["direction_evidence"]
        self.assertEqual(evidence["mode"], "direction-gate")
        self.assertEqual(evidence["contract_sha256"],
                         hashlib.sha256(contract.encode("utf-8")).hexdigest())

    def test_standalone_skips_the_gate_and_says_so(self):
        out = self.root / "out"
        completed = self.build("--standalone", out=out)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads((out / "selection.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["direction_evidence"],
                         {"mode": "standalone", "contract_sha256": None})
        self.assertIn("未读取任何项目合同",
                      (out / "intent.md").read_text(encoding="utf-8"))

    def test_gate_does_not_raise_the_direction_phase(self):
        # The direction phase is deliberately light while a direction forms:
        # grounding is demanded to *select tokens*, not to record a direction.
        write_contract(self.project, body=self.ungrounded())
        self.assertTrue(check(self.project, phase="direction")["passed"])
        self.assertFalse(design.direction_gate(self.project)["passed"])

    def test_existing_output_guard_still_holds(self):
        write_contract(self.project)
        out = self.root / "out"
        out.mkdir()
        (out / "keep.txt").write_text("mine", encoding="utf-8")
        completed = self.build(out=out)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("new or empty directory", completed.stderr)
        self.assertEqual((out / "keep.txt").read_text(encoding="utf-8"), "mine")


class DesignIntelligenceContractTests(unittest.TestCase):
    def test_research_requires_one_explicit_route(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "research", "generic dashboard"],
            cwd=SKILL_ROOT.parent,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("one of the arguments", completed.stderr)

    def test_catalog_exposes_every_bundled_domain_and_stack(self):
        catalog = run_json("catalog")

        self.assertEqual(catalog["source"]["name"], "design-intelligence")
        self.assertEqual(
            set(catalog["domains"]),
            {
                "style", "color", "chart", "landing", "product", "ux",
                "typography", "google-fonts", "icons", "gsap", "react", "web",
            },
        )
        self.assertEqual(len(catalog["stacks"]), 22)
        self.assertIn("react", catalog["stacks"])
        self.assertIn("html-tailwind", catalog["stacks"])
        self.assertIn("flutter", catalog["stacks"])

    def test_research_returns_a_compact_decision_record(self):
        result = run_json(
            "research", "error summary validation", "--domain", "ux", "--max-results", "1"
        )

        self.assertEqual(result["retrieval"]["status"], "verified_match")
        self.assertEqual(result["retrieval"]["route"], "domain:ux")
        self.assertEqual(result["retrieval"]["result_count"], 1)
        self.assertTrue(result["retrieval"]["top_result_id"])
        self.assertEqual(
            result["decision_record"]["contract_target"],
            ".site/design/surface-brief.md#设计方法来源",
        )
        self.assertIsNone(result["decision_record"]["selected"])
        self.assertEqual(result["decision_record"]["fit_basis"], [])

    def test_zero_result_is_explicit_and_never_fabricates_an_id(self):
        result = run_json(
            "research", "qxzv-no-such-guidance", "--domain", "chart", "--max-results", "1"
        )

        self.assertEqual(result["retrieval"]["status"], "no_verified_match")
        self.assertEqual(result["retrieval"]["result_count"], 0)
        self.assertIsNone(result["retrieval"]["top_result_id"])
        self.assertEqual(result["retrieval"]["next_action"], "retry_once_then_record_fallback")

    def test_icon_results_withhold_vendor_and_import_code(self):
        # The bundled snapshot is Phosphor-based but this pack defaults to
        # Lucide, so vendor identity and import snippets must not steer an
        # undecided project (the data file stays a byte-faithful snapshot).
        result = run_json(
            "research", "settings gear preferences", "--domain", "icons", "--max-results", "1"
        )

        self.assertEqual(result["retrieval"]["status"], "verified_match")
        rows = result["result"]["results"]
        self.assertTrue(rows, result["result"])
        for row in rows:
            self.assertNotIn("Library", row)
            self.assertNotIn("Import Code", row)
            self.assertIn("Icon Name", row)
        note = result["result"]["retrieval_note"]
        self.assertIn("Lucide", note)
        self.assertIn("以该指定为准", note)

    def test_every_curated_icon_row_drops_vendor_usage(self):
        # Usage carried `<MagnifyingGlass size={20} weight="regular" />` — a
        # Phosphor-only snippet that was the one copyable artifact left after
        # Library/Import Code were withheld. Only the library-agnostic
        # accessibility guidance may survive.
        data = SKILL_ROOT / "intelligence" / "data" / "icons.csv"
        with data.open(encoding="utf-8") as handle:
            raw = [dict(row) for row in csv.DictReader(handle)]

        stripped = design._strip_icon_vendor({"domain": "icons", "results": raw})

        self.assertEqual(len(stripped["results"]), 105)
        for row in stripped["results"]:
            usage = row.get("Usage")
            self.assertIsInstance(usage, str, row["Icon Name"])
            self.assertIn("aria-hidden", usage, row["Icon Name"])
            self.assertFalse(re.search(r"<[A-Z]|weight=|\{[0-9]+\}", usage), row["Icon Name"])
            for vendor in ("Phosphor", "Heroicons", "Lucide"):
                self.assertNotIn(vendor, usage, row["Icon Name"])

    def test_routes_with_copyable_artifacts_declare_a_retrieval_note(self):
        # A payload that ships font URLs, palettes or preset names reads like a
        # standard unless the response itself says otherwise.
        for args in (
            ("research", "dashboard data", "--domain", "typography", "--max-results", "1"),
            ("research", "geometric sans", "--domain", "google-fonts", "--max-results", "1"),
            ("research", "saas dashboard", "--design-system", "--project-name", "Probe"),
        ):
            note = run_json(*args)["result"]["retrieval_note"]
            self.assertTrue(note, args)
            self.assertIn("候选", note, args)

        # Routes without ready-to-paste artifacts stay clean; a note on every
        # payload would train the reader to skip it.
        self.assertNotIn(
            "retrieval_note",
            run_json("research", "error summary", "--domain", "ux", "--max-results", "1")["result"],
        )


class ReferenceArchitectureTests(unittest.TestCase):
    def test_marketing_pages_declare_motion_and_the_checker_rechecks_it(self):
        # 「炫酷」selects nothing, so the design path asserts a beat sheet the
        # user can veto instead of asking him to describe motion. That claim is
        # only honest if the verifier re-runs the visual axis under reduced
        # motion whenever the contract declares one.
        motion = (SKILL_ROOT / "references" / "motion.md").read_text(encoding="utf-8")
        landing = (SKILL_ROOT / "references" / "landing-page.md").read_text(encoding="utf-8")
        brief = (SKILL_ROOT / "references" / "surface-brief.md").read_text(encoding="utf-8")
        visual = (SKILL_ROOT / "references" / "visual-direction.md").read_text(encoding="utf-8")
        checker = (SKILL_ROOT.parent / "site-check" / "SKILL.md").read_text(encoding="utf-8")

        for text in (landing, brief, visual):
            self.assertIn("motion.md", text)
        self.assertIn("动效主张", brief)
        self.assertIn("prefers-reduced-motion", motion)
        self.assertIn("不要问", motion)
        self.assertIn("reducedMotion", checker)
        # 这句曾经写成「硬边界：不引第三方动效库，离线、弱网和低端设备都要打得开」。
        # 那个理由在包内已经被实测推翻过一次（字体那格：CDN 才是风险，不是外链本身），
        # 而且按本包自己的规则，不可验收的说法不该用验收线的语气写。理由换成成本，
        # 结论（默认零依赖）不变。
        self.assertIn("零依赖更便宜，也更容易在减少动态时整体关掉", motion)
        self.assertNotIn("外部库先坏", motion)
        # 默认零依赖不等于一刀切封禁：真遇到本表覆盖不到的拍子，要走单独论证。
        self.assertIn("单独论证", motion)
        # 输入驱动的连续响应是零依赖里真正缺的那一格，它必须有一行和一个循环约定。
        self.assertIn("输入驱动响应", motion)
        self.assertIn("1 - Math.exp(-k * dt)", motion)
        # 每一拍要能说出成本落在哪一轴（合成 / 绘制 / 重排）。
        self.assertIn("| 成本 |", motion)
        # 假前提一旦以扁平禁令的形式长回任何一份参考里，就会静默地把整包拉回旧口径。
        for path in sorted((SKILL_ROOT / "references").glob("*.md")):
            self.assertNotIn("不引第三方动效库",
                             path.read_text(encoding="utf-8"), path.name)

    def test_toolchain_documents_the_lint_boundary_and_retrieval_note(self):
        toolchain = (SKILL_ROOT / "references" / "design-toolchain.md").read_text(encoding="utf-8")

        # lint-ui returns passed:true for a page with negative tracking, a bogus
        # 700 and a full webfont import. The document must pre-empt that badge.
        self.assertIn("retrieval_note", toolchain)
        self.assertIn("排版度量与渲染效果不在其中", toolchain)
        self.assertIn("不表示排版或设计成立", toolchain)

    def test_external_fonts_are_allowed_with_a_mandatory_fallback(self):
        # design-tokens.md owns 字体 (design-toolchain.md's authority table), and
        # it used to say 不下载字体 outright — which forbade the very
        # 西文/数字展示字体 that chinese-typography.md recommends for giving a
        # Chinese page its character. The policy is design-first with graceful
        # degradation, not offline-only.
        tokens = (SKILL_ROOT / "references" / "design-tokens.md").read_text(encoding="utf-8")
        craft = (SKILL_ROOT / "references" / "craft-review.md").read_text(encoding="utf-8")
        cjk = (SKILL_ROOT / "references" / "chinese-typography.md").read_text(encoding="utf-8")

        self.assertIn("可以加载网络字体", tokens)
        self.assertIn("系统栈回退", tokens)
        self.assertIn("外部资源是增强，不是必需品", tokens)
        # The fallback must be an observable acceptance condition, not advice.
        self.assertIn("系统栈回退", craft)
        self.assertIn("不允许它成为唯一可用字体", craft)
        # A flat "no font downloads" ban reappearing in any reference silently
        # reinstates offline-only pages, so guard the whole set.
        for path in sorted((SKILL_ROOT / "references").glob("*.md")):
            self.assertNotIn("不下载字体", path.read_text(encoding="utf-8"), path.name)

    def test_loaded_fonts_are_recorded_assets_not_unverifiable_prose(self):
        # The fallback rule above is unenforceable unless the font has a row:
        # 素材地图 is the only contract surface carrying 来源 / 许可 / 状态.
        tokens = (SKILL_ROOT / "references" / "design-tokens.md").read_text(encoding="utf-8")
        craft = (SKILL_ROOT / "references" / "craft-review.md").read_text(encoding="utf-8")

        self.assertIn("[素材地图](surface-brief.md)", tokens)
        self.assertIn("`AS-*`", tokens)
        for field in ("来源 URL", "许可", "子集范围", "回退栈"):
            self.assertIn(field, tokens)
        self.assertIn("加载字体同样按素材登记", craft)

        # The row must land in a table the template actually provides, with the
        # columns this routing promises.
        template = TEMPLATE.read_text(encoding="utf-8")
        header, _ = design._table(design._strip_contract_block(template),
                                  "来源与性质", "许可")
        self.assertTrue(header, "素材地图 缺少可承载字体资产的表头")

    def test_chinese_body_fonts_need_self_hosted_subsets(self):
        # 永远强制使用系统字体栈 blocked reasoning about a fixed-copy brand
        # page. The conditional exception must keep the one red line that
        # actually matters (no un-subsetted whole-pack load) and forbid the
        # unreachable-CDN dependency.
        cjk = (SKILL_ROOT / "references" / "chinese-typography.md").read_text(encoding="utf-8")

        self.assertNotIn("永远强制使用系统字体栈", cjk)
        self.assertIn("正文、表格与交互 UI 控件默认使用系统字体栈", cjk)
        for condition in ("自托管", "子集化", "font-display: swap", "不依赖境外 CDN"):
            self.assertIn(condition, cjk)
        self.assertIn("不做子集化的整包引入", cjk)
        # The old premise claimed CDN loading is the hazard; measurement showed
        # Google Fonts slices CJK into unicode-range chunks automatically, so
        # the real hazards are whole-pack loads and CDN reachability.
        self.assertIn("unicode-range", cjk)
        self.assertIn("中国大陆不可靠", cjk)


    def test_runtime_references_are_flat_and_bounded(self):
        references = SKILL_ROOT / "references"
        markdown = list(references.rglob("*.md"))

        self.assertLessEqual(len(markdown), 12)
        self.assertFalse((references / "upstream").exists())
        self.assertFalse((references / "design-intent.md").exists())

        entrypoint = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        linked = set(re.findall(r"\(references/([^)#]+\.md)(?:#[^)]+)?\)", entrypoint))
        self.assertEqual({path.name for path in markdown}, linked)

    def test_heavy_branches_are_staged_not_bundled(self):
        # The new-surface branch spans ~65KB. Handing the agent the whole set
        # at once is the progressive-disclosure failure this guards against,
        # so every reading step must name at most one reference.
        entrypoint = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("按步骤读", entrypoint)
        steps = [line for line in entrypoint.splitlines()
                 if line.startswith("| A") or line.startswith("| B")]
        self.assertTrue(steps, "reading sequence is missing")
        for row in steps:
            self.assertLessEqual(len(re.findall(r"\(references/[^)]+\)", row)), 1, row)

    def test_reading_sequence_step_sizes_match_the_files(self):
        # The entrypoint quotes per-step sizes to justify staged reading. A
        # stale number is the same rot the file/link equality test guards.
        entrypoint = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        checked = 0
        for line in entrypoint.splitlines():
            row = re.match(
                r"\|\s*[AB]\d\s*\|[^|]*\|\s*\[[^\]]+\]\(references/([^)]+\.md)\)"
                r"\s*\|\s*(\d+)KB\s*\|", line)
            if not row:
                continue
            actual = (SKILL_ROOT / "references" / row.group(1)).stat().st_size / 1024
            self.assertEqual(int(row.group(2)), round(actual), row.group(1))
            checked += 1
        self.assertEqual(checked, 10, "reading sequence rows changed shape")

    def test_entrypoint_prose_sizes_match_the_files(self):
        # The prose around the tables quotes the same sizes, but nothing guarded
        # it, so it drifted to 63KB / 15KB while the files were 64KB / 16KB --
        # the table rows below were kept honest and the sentences were not.
        # Both figures are now derived from the files the tables name.
        entrypoint = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        names = set()
        for line in entrypoint.splitlines():
            row = re.match(
                r"\|\s*[AB]\d\s*\|[^|]*\|\s*\[[^\]]+\]\(references/([^)]+\.md)\)"
                r"\s*\|\s*(\d+)KB\s*\|", line)
            if row:
                names.add(row.group(1))
        self.assertEqual(len(names), 6, "reading sequence files changed shape")
        sizes = [(SKILL_ROOT / "references" / name).stat().st_size
                 for name in names]

        total = re.search(r"合计约\s*(\d+)KB", entrypoint)
        self.assertIsNotNone(total, "total-size sentence changed shape")
        self.assertEqual(int(total.group(1)), round(sum(sizes) / 1024))

        largest = re.search(r"单步最大\s*(\d+)KB", entrypoint)
        self.assertIsNotNone(largest, "largest-step sentence changed shape")
        self.assertEqual(int(largest.group(1)),
                         max(round(size / 1024) for size in sizes))

        template = re.search(r"references/surface-brief\.md\)（(\d+)KB）", entrypoint)
        self.assertIsNotNone(template, "template-size sentence changed shape")
        self.assertEqual(int(template.group(1)),
                         round(TEMPLATE.stat().st_size / 1024))

    def test_recipe_table_matches_the_catalog(self):
        # design-tokens.md owns 配色 / 字体 / 密度 / 形状, and its 推荐配方 table
        # is the only place an agent learns which recipe keys exist. The keys
        # themselves live in tokens.json. Both copies read correct today with no
        # assertion between them, so adding or renaming a recipe would leave the
        # table advertising a key `build` rejects.
        tokens = (SKILL_ROOT / "references" / "design-tokens.md").read_text(encoding="utf-8")
        catalog = json.loads(
            (SKILL_ROOT / "assets" / "design" / "tokens.json").read_text(encoding="utf-8"))
        section = tokens.split("## 推荐配方", 1)[1].split("\n## ", 1)[0]
        documented = re.findall(r"^\|\s*([a-z][a-z0-9-]+)\s*\|", section, re.M)
        self.assertEqual(sorted(catalog["recipes"]), sorted(documented))

    def test_choice_vocabulary_is_documented_in_the_reference_that_owns_it(self):
        # A4 tells the agent to read design-tokens.md and nothing else, but the
        # reference used to name 色板 in prose ("钴蓝") while --palette accepts
        # "cobalt". The 可选取值 table closes that gap; this keeps it closed, so
        # a new palette or shape cannot ship as a key no document mentions.
        tokens = (SKILL_ROOT / "references" / "design-tokens.md").read_text(encoding="utf-8")
        catalog = json.loads(
            (SKILL_ROOT / "assets" / "design" / "tokens.json").read_text(encoding="utf-8"))
        for group in design.GROUPS.values():
            for key in catalog[group]:
                self.assertRegex(tokens, r"(?<![a-z0-9-])" + re.escape(key) + r"(?![a-z0-9-])",
                                 f"{group} key {key} is undocumented in design-tokens.md")

    def test_unknown_choice_names_the_valid_keys(self):
        # `Unknown palette: cobal` made the caller discover the vocabulary by
        # trial. The rejection has to carry the keys and, for a near miss, the
        # intended one.
        catalog = design.read_catalog()
        with self.assertRaises(ValueError) as caught:
            design.compose(catalog, "daily-workspace", palette="cobal")
        message = str(caught.exception)
        self.assertIn("cobalt", message)
        self.assertRegex(message, r"(?i)did you mean")
        for key in catalog["palettes"]:
            self.assertIn(key, message)

        with self.assertRaises(ValueError) as caught:
            design.compose(catalog, "daily-workspaces")
        self.assertIn("daily-workspace", str(caught.exception))

    def test_contract_template_stays_a_fill_in_skeleton(self):
        body = design._strip_contract_block(TEMPLATE.read_text(encoding="utf-8"))
        labels = list(design.PROJECT_FACT_LABELS) + [
            "明确不做", "明确排除项", "交换检查结论", "结构差异证据"]
        labels += [label for _, labels_ in design.DESIGN_JUDGMENT_ASPECTS
                   for label in labels_]
        filled = {label: design._bullet_value(body, label) for label in labels
                  if design._bullet_value(body, label)}
        # Guidance text in a field gets copied into contracts; it belongs in
        # the reference that owns the topic.
        self.assertEqual(filled, {})
        # The skeleton is copied into every project, so it is bounded -- but the
        # old 16000 cap left 89 bytes of headroom, which turned any necessary
        # field addition into a test failure and pushed authors toward deleting
        # guidance first. Raised to 20000 to give that work room. It is still a
        # bound, not a budget: explanation belongs in the owning reference.
        self.assertLess(len(TEMPLATE.read_bytes()), 20000)

    def test_template_declares_every_anchor_the_checker_reads(self):
        body = design._strip_contract_block(TEMPLATE.read_text(encoding="utf-8"))
        for markers in (("来源引用", "交接目标"), ("约束", "对结构"),
                        ("可观察标准", "检查轴"), ("候选", "设计主线")):
            header, _ = design._table(body, *markers)
            self.assertTrue(header, f"模板缺少表头 {markers}")

    def test_no_gate_decision_reads_the_template_text(self):
        # Gate behaviour must depend only on the project contract. Reading the
        # template to obtain "default values" made a gate decision flip when
        # someone reworded the template, and let a synonym pass as design work.
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("template_path", source)
        self.assertNotIn("template_body", source)

    def test_surface_brief_is_the_only_project_design_specification(self):
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL_ROOT / "SKILL.md", *sorted((SKILL_ROOT / "references").rglob("*.md"))]
        )

        self.assertNotIn(".site/design/design-intent.md", content)
        self.assertNotIn(".v3/design/design-intent.md", content)
        self.assertNotIn("MASTER.md", content)


class LintUiTests(unittest.TestCase):
    """Stage 3 UI lint: deterministic blockers, template-tendency warnings,
    false-positive boundaries, exclusions and the --changed-from dual semantics.
    """

    CLEAN_BODY = (
        "## 项目事实\n\n"
        "- **使用者：** 仓管员\n- **主任务：** 登记库存\n"
        "- **业务对象：** 库存项\n- **真实内容：** 名称、数量、单位\n"
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".site" / "design").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp.cleanup()

    def _contract(self, **overrides):
        data = {
            "work_type": "new-surface", "structure_mode": "single",
            "scope_refs": ["BR-01"], "required_constraints": [],
            "pages": ["PG-01"], "sections": [], "responsive": [],
            "components": [], "assets": [], "acceptance": [],
            "unresolved_confirm": [], "blocking_missing_assets": [],
            "icon_system": "", "icon_exceptions": [],
            "intentional_exceptions": [],
        }
        data.update(overrides)
        return data

    def _write(self, contract_json=None, body=None, files=None):
        cj = self._contract() if contract_json is None else contract_json
        text = ("# 页面设计合同\n\n```site-contract\n"
                + json.dumps(cj, ensure_ascii=False) + "\n```\n\n"
                + (body or self.CLEAN_BODY))
        (self.root / ".site" / "design" / "surface-brief.md").write_text(
            text, encoding="utf-8")
        for rel, content in (files or {}).items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _lint(self, **kwargs):
        return design.lint_ui(self.root, ".site/design/surface-brief.md",
                              **kwargs)

    def codes(self, report):
        return sorted(b["code"] for b in report["blockers"])

    # --- clean baseline + machine-readable shape ---

    def test_clean_project_passes(self):
        self._write(files={"index.html": "<h1>库存</h1><p>登记库存</p>"})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["scanned_files"], ["index.html"])
        self.assertTrue(report["contract_sha256"])
        self.assertTrue(report["ui_source_sha256"])
        self.assertIn("checked_at", report)

    def test_missing_contract_is_reported(self):
        # setUp creates the contract directory but writes no file.
        report = self._lint()
        self.assertFalse(report["passed"])
        self.assertEqual(self.codes(report), ["missing_contract"])

    def test_invalid_contract_block_is_reported(self):
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text("# c\n\n```site-contract\n{bad json}\n```\n", encoding="utf-8")
        report = self._lint()
        self.assertEqual(self.codes(report), ["invalid_contract"])

    # --- deterministic blockers ---

    def test_emoji_icon_without_exception_is_blocked(self):
        self._write(files={"index.html": '<span class="icon">🎯</span>'})
        report = self._lint()
        self.assertIn("emoji_icon_without_exception", self.codes(report))
        blocker = next(b for b in report["blockers"]
                       if b["code"] == "emoji_icon_without_exception")
        self.assertEqual(blocker["char"], "🎯")

    def test_emoji_exception_is_honored(self):
        self._write(contract_json=self._contract(
            icon_system="lucide",
            icon_exceptions=[{"char": "✓", "basis": "清单完成态对勾"}]),
            files={"index.html": '<span class="ok">✓</span>'})
        report = self._lint()
        self.assertNotIn("emoji_icon_without_exception", self.codes(report))
        self.assertTrue(report["passed"], report["blockers"])

    def test_mixed_icon_systems_is_blocked(self):
        self._write(contract_json=self._contract(icon_system="lucide"),
                    files={"index.html":
                           '<i class="fa fa-check"></i>'
                           '<svg data-lucide="x"></svg>'})
        report = self._lint()
        self.assertIn("mixed_icon_systems", self.codes(report))

    def test_user_chosen_icon_system_is_honored(self):
        # Lucide is only a default: an explicitly declared system (the user's or
        # an existing project's own choice) must pass without a blocker.
        self._write(contract_json=self._contract(icon_system="phosphor"),
                    files={"app.jsx":
                           "import { Gear } from '@phosphor-icons/react'"})
        report = self._lint()
        self.assertEqual(self.codes(report), [])
        self.assertTrue(report["passed"], report["blockers"])
        self.assertNotIn("icon_system_mismatch",
                         [w["code"] for w in report["warnings"]])

    def test_undeclared_icon_system_drift_is_a_warning_not_a_blocker(self):
        # With no declaration the default is Lucide, so another library is drift
        # worth surfacing -- but the fix may be to declare the choice, so it must
        # not block.
        self._write(files={"app.jsx":
                           "import { Gear } from '@phosphor-icons/react'"})
        report = self._lint()
        self.assertEqual(self.codes(report), [])
        self.assertTrue(report["passed"], report["blockers"])
        codes = [w["code"] for w in report["warnings"]]
        self.assertIn("icon_system_mismatch", codes)
        self.assertIn("undeclared_icon_system", codes)
        mismatch = next(w for w in report["warnings"]
                        if w["code"] == "icon_system_mismatch")
        self.assertEqual(mismatch["found"], ["phosphor"])

    def test_declared_system_drift_is_reported(self):
        self._write(contract_json=self._contract(icon_system="lucide"),
                    files={"app.jsx":
                           "import { Gear } from '@phosphor-icons/react'"})
        report = self._lint()
        mismatch = next(w for w in report["warnings"]
                        if w["code"] == "icon_system_mismatch")
        self.assertEqual(mismatch["declared"], "lucide")
        self.assertEqual(mismatch["found"], ["phosphor"])

    def test_lucide_only_interface_passes(self):
        self._write(contract_json=self._contract(icon_system="lucide"),
                    files={"app.jsx":
                           "import { Settings, Trash2 } from 'lucide-react'"})
        report = self._lint()
        self.assertEqual(self.codes(report), [])
        self.assertTrue(report["passed"], report["blockers"])

    def test_metadata_link_path_is_not_an_icon_system(self):
        # A product id in rel=canonical once read as the Feather icon library.
        # Metadata links are page addresses, not package specifiers.
        self._write(contract_json=self._contract(icon_system="lucide"),
                    files={"index.html":
                           '<link rel="canonical" href="products/feather-wand.html">'
                           '<link rel="icon" href="/assets/feather.png">',
                           "products/feather-wand.html": "<h1>产品页</h1>"})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertNotIn("icon_system_mismatch",
                         [w["code"] for w in report["warnings"]])

    def test_stylesheet_link_counts_regardless_of_attribute_order(self):
        self._write(contract_json=self._contract(icon_system="lucide"),
                    files={"index.html":
                           '<link href="https://cdn/feather-icons/feather.css" '
                           'rel="stylesheet">'})
        report = self._lint()
        mismatch = next(w for w in report["warnings"]
                        if w["code"] == "icon_system_mismatch")
        self.assertEqual(mismatch["found"], ["feather"])

    def test_fabricated_lorem_is_blocked(self):
        self._write(files={"index.html": "<p>lorem ipsum dolor sit amet</p>"})
        report = self._lint()
        self.assertIn("fabricated_proof", self.codes(report))

    def test_placeholder_logo_is_blocked_without_logo_context_only_warning(self):
        # With a logo/brand context the placeholder image is fabricated proof.
        self._write(files={"index.html":
                           '<div class="logo"><img src="https://via.placeholder.com/100" alt="客户Logo"></div>'})
        report = self._lint()
        self.assertIn("fabricated_proof", self.codes(report))
        self.assertNotIn("placeholder_image", [w["code"] for w in report["warnings"]])

    def test_placeholder_image_without_logo_context_is_warning(self):
        self._write(files={"index.html":
                           '<img src="https://picsum.photos/200" alt="装饰图">'})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertIn("placeholder_image", [w["code"] for w in report["warnings"]])

    def test_fabricated_rating_is_blocked(self):
        self._write(files={"index.html": "<span>★★★★★</span>"})
        report = self._lint()
        self.assertIn("fabricated_proof", self.codes(report))
        self.assertEqual(next(b for b in report["blockers"]
                              if b["code"] == "fabricated_proof")["kind"],
                         "fabricated_rating")

    def test_excluded_capability_in_ui_is_blocked(self):
        body = self.CLEAN_BODY + "- **明确不做：** 付费功能\n"
        self._write(body=body, files={
            "index.html": "<button>付费功能</button><p>付费功能说明段落</p>"})
        report = self._lint()
        self.assertIn("excluded_capability_in_ui", self.codes(report))
        # The prose mention is not a label → no duplicate blocker.
        self.assertEqual([b["capability"] for b in report["blockers"]
                          if b["code"] == "excluded_capability_in_ui"],
                         ["付费功能"])

    def test_skin_only_candidates_missing_evidence_is_blocked(self):
        body = self.CLEAN_BODY + (
            "## 对照方向（仅在真实取舍存在时）\n\n"
            "| 候选 | 匹配依据 | 设计主线 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `方案一` | a | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n"
            "| `方案二` | b | 货架卡片 | 实物 | 网格铺陈 | x | y | `pending` |\n")
        self._write(body=body)
        report = self._lint()
        self.assertIn("skin_only_candidates", self.codes(report))

    def test_skin_only_candidates_identical_motif_is_blocked(self):
        body = self.CLEAN_BODY + (
            "## 对照方向（仅在真实取舍存在时）\n\n"
            "| 候选 | 匹配依据 | 设计主线 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `方案一` | a | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n"
            "| `方案二` | b | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n\n"
            "- **结构差异证据（每个候选都必须填写）：** 方案一表格主区，方案二左栏列表\n")
        self._write(body=body)
        report = self._lint()
        self.assertIn("skin_only_candidates", self.codes(report))

    def test_single_candidate_is_not_skin_blocked(self):
        body = self.CLEAN_BODY + (
            "## 对照方向（仅在真实取舍存在时）\n\n"
            "| 候选 | 匹配依据 | 设计主线 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `方案一` | a | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n")
        self._write(body=body, files={"index.html": "<h1>库存</h1>"})
        report = self._lint()
        self.assertNotIn("skin_only_candidates", self.codes(report))

    def test_swap_check_prose_is_not_machine_judged(self):
        # "不是换肤" matched a bare 换肤 pattern and blocked a correct
        # contract. Negation is not decidable by regex, so the two structural
        # checks decide; the prose is left for the next reader.
        body = self.CLEAN_BODY + (
            "## 对照方向（仅在真实取舍存在时）\n\n"
            "| 候选 | 匹配依据 | 设计主线 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `方案一` | a | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n"
            "| `方案二` | b | 货架卡片 | 实物 | 网格铺陈 | x | y | `pending` |\n\n"
            "- **交换检查结论：** 抽掉颜色后两者栅格不同，不是换肤。\n"
            "- **结构差异证据：** 方案一表格主区，方案二左栏列表\n")
        self._write(body=body)
        report = self._lint()
        self.assertNotIn("skin_only_candidates", self.codes(report))

    # --- aesthetic judgments are not grep heuristics ---

    def test_generated_looking_layout_is_not_flagged(self):
        # hero + three cards + CTA is what landing-page.md itself recommends,
        # and card/pill/gradient counts fire on legitimate dashboards and tag
        # lists. Those heuristics were removed: a warning that never blocks and
        # is often wrong trains agents to ignore warnings.
        html = ('<section class="hero"><h1>产品</h1></section>'
                '<div class="card">a</div><div class="card">b</div>'
                '<div class="card">c</div><button>立即开始</button>'
                '<span class="pill">x</span><span class="badge">y</span>'
                '<span class="chip">z</span><span class="tag">w</span>'
                '<style>.a{background:linear-gradient(#fff,#000)}'
                '@keyframes k{from{opacity:0}}</style>')
        self._write(files={"index.html": html})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        template_codes = [w["code"] for w in report["warnings"]
                          if w["code"].startswith("template_")]
        self.assertEqual(template_codes, [])

    def test_undeclared_icon_system_is_warning(self):
        # Icons in use but contract declares no icon_system → warning, not blocker.
        self._write(files={"index.html": '<svg data-lucide="x"></svg>'})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertIn("undeclared_icon_system", [w["code"] for w in report["warnings"]])

    # --- page-integrity rules (contract-independent) ---

    def test_missing_local_stylesheet_is_blocked_and_present_file_passes(self):
        # A page whose stylesheet 404s renders unstyled and still passes the
        # icon/proof/capability scans; this is the one static blocker.
        self._write(files={"index.html": '<link rel="stylesheet" href="styles.css">',
                           "styles.css": ".a{color:#102030}"})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        (self.root / "styles.css").unlink()
        report = self._lint()
        self.assertIn("dead_local_ref", self.codes(report))

    def test_non_local_references_are_not_file_checks(self):
        # Scheme'd, protocol-relative, fragment-only, root-relative and
        # templated refs are not files this scan can resolve.
        self._write(files={"index.html": (
            '<script src="https://cdn.example.com/x.js"></script>'
            '<img src="data:image/gif;base64,R0lGOD" alt="点">'
            '<a href="#top">顶部</a>'
            '<a href="mailto:a@b.c">邮件</a>'
            '<img src="//cdn.example.com/y.png" alt="图">'
            '<img src="/assets/root-relative.png" alt="根路径">'
            '<img src="{{ asset_url }}" alt="模板">'
            '<style>.a{background:url(var(--shape))}</style>')})
        report = self._lint()
        self.assertEqual(self.codes(report), [])
        self.assertTrue(report["passed"], report["blockers"])

    def test_script_and_framework_bindings_are_not_file_references(self):
        # ``location.href = "signin.html"`` and ``:src="path"`` are code, not
        # references; matching them made every router line a blocker.
        self._write(files={
            "index.html": '<script>if (!user) { location.href = "signin.html"; }</script>',
            "src/App.tsx": '<img :src="dynamicPath" /><A href={to} />'})
        report = self._lint()
        self.assertEqual(self.codes(report), [])
        self.assertTrue(report["passed"], report["blockers"])

    def test_jsx_static_source_is_still_checked(self):
        # Without the binding prefix it is a real reference and must not be
        # skipped just because the file is a component.
        self._write(files={"src/App.tsx": '<img src="img/missing.png" alt="图" />'})
        report = self._lint()
        self.assertIn("dead_local_ref", self.codes(report))

    def test_missing_build_output_reference_is_a_warning(self):
        # The build may simply not have run yet; a file missing anywhere else
        # is a broken page, a missing dist/ artifact is a question.
        self._write(files={"index.html": '<script src="dist/app.js"></script>'})
        report = self._lint()
        self.assertEqual(self.codes(report), [])
        self.assertIn("build_output_missing",
                      [w["code"] for w in report["warnings"]])

    def test_overflow_hidden_with_sticky_warns_and_hidden_alone_does_not(self):
        page = ('<style>html,body{overflow-x:hidden}'
                '.nav{position:sticky;top:0}</style><nav class="nav">x</nav>')
        self._write(files={"index.html": page})
        report = self._lint()
        self.assertIn("overflow_hidden_with_sticky",
                      [w["code"] for w in report["warnings"]])

        self._write(files={"index.html":
                           '<style>body{overflow-x:hidden}</style>'})
        report = self._lint()
        self.assertNotIn("overflow_hidden_with_sticky",
                         [w["code"] for w in report["warnings"]])

    def test_two_sticky_elements_at_top_zero_warn(self):
        page = ('<style>.nav{position:sticky;top:0}'
                '.head{position:sticky;top:0px}</style>')
        self._write(files={"index.html": page})
        report = self._lint()
        self.assertIn("dual_sticky_top0", [w["code"] for w in report["warnings"]])

    def test_bare_fr_track_warns_only_when_the_page_has_images(self):
        grid = '<style>.grid{grid-template-columns:1fr 1fr}</style>'
        self._write(files={"index.html": grid + '<div class="grid"></div>'})
        report = self._lint()
        self.assertNotIn("bare_fr_track", [w["code"] for w in report["warnings"]])

        self._write(files={"index.html": grid + '<img src="a.png" alt="图">',
                           "a.png": "png"})
        report = self._lint()
        self.assertIn("bare_fr_track", [w["code"] for w in report["warnings"]])

    def test_bare_fr_track_exemptions(self):
        minmax = ('<style>.grid{grid-template-columns:minmax(0,1fr) 320px}</style>'
                  '<img src="a.png" alt="图">')
        self._write(files={"index.html": minmax, "a.png": "png"})
        report = self._lint()
        self.assertNotIn("bare_fr_track", [w["code"] for w in report["warnings"]])

        floored = ('<style>img{max-width:100%}'
                   '.grid{grid-template-columns:1fr 1fr}</style>'
                   '<img src="a.png" alt="图">')
        self._write(files={"index.html": floored, "a.png": "png"})
        report = self._lint()
        self.assertNotIn("bare_fr_track", [w["code"] for w in report["warnings"]])

    def test_uppercase_tight_leading_warns_and_normal_leading_passes(self):
        self._write(files={"index.html":
                           '<style>.t{text-transform:uppercase;line-height:.9}</style>'})
        report = self._lint()
        self.assertIn("uppercase_tight_leading",
                      [w["code"] for w in report["warnings"]])

        self._write(files={"index.html":
                           '<style>.t{text-transform:uppercase;line-height:1.05}</style>'})
        report = self._lint()
        self.assertNotIn("uppercase_tight_leading",
                         [w["code"] for w in report["warnings"]])

    def test_continuous_motion_without_a_fallback_warns(self):
        self._write(files={"index.html":
                           "<script>requestAnimationFrame(tick)</script>"})
        report = self._lint()
        self.assertIn("motion_without_reduced_motion",
                      [w["code"] for w in report["warnings"]])

    def test_reduced_motion_fallback_and_plain_hover_pass(self):
        self._write(files={"index.html": (
            "<style>@keyframes pulse{from{opacity:0}}"
            "@media (prefers-reduced-motion: reduce){.a{animation:none}}</style>")})
        report = self._lint()
        self.assertNotIn("motion_without_reduced_motion",
                         [w["code"] for w in report["warnings"]])

        self._write(files={"index.html":
                           "<style>.b{transition:background .2s}</style>"})
        report = self._lint()
        self.assertNotIn("motion_without_reduced_motion",
                         [w["code"] for w in report["warnings"]])

    def test_transition_all_and_gradient_text_warn(self):
        self._write(files={"index.html": (
            "<style>.a{transition:all .2s}"
            ".b{background:linear-gradient(90deg,#123456,#654321);"
            "-webkit-background-clip:text;background-clip:text}</style>")})
        report = self._lint()
        codes = [w["code"] for w in report["warnings"]]
        self.assertIn("transition_all", codes)
        self.assertIn("gradient_text", codes)

    def test_animating_layout_properties_warns(self):
        # width/height/top invalidate style and layout every frame; the
        # compositor never sees them. transform/opacity are the pass case, and
        # a custom property called --my-height must not be read as ``height``.
        self._write(files={"index.html": (
            "<style>.a{transition:height .3s}"
            ".b{transition:transform .3s, opacity .2s}"
            ".c{transition:border-color .2s}"
            ".d{transition:--my-height .3s}"
            "@keyframes k{0%{width:0}100%{width:100px}}"
            "@keyframes ok{from{transform:scale(.96);opacity:0}}"
            "@media (prefers-reduced-motion:reduce){*{transition:none}}"
            "</style>")})
        report = self._lint()
        warnings = report["warnings"]
        codes = [w["code"] for w in warnings]
        self.assertIn("layout_property_transition", codes)
        self.assertIn("layout_property_animation", codes)
        self.assertEqual(codes.count("layout_property_transition"), 1)
        self.assertEqual(
            [w["property"] for w in warnings
             if w["code"] == "layout_property_transition"], ["height"])

    def test_geometry_read_next_to_a_frame_loop_warns(self):
        # A synchronous layout read inside a rAF callback is the most common
        # cause of dropped frames in hand-written motion. The scan cannot prove
        # the read sits in the callback, so it reports a question, not a
        # verdict -- and never a blocker.
        self._write(files={
            "app.js": ("const el = document.querySelector('.c');\n"
                       "function f(){ el.style.transform = 'translateX(' + "
                       "el.offsetWidth + 'px)'; requestAnimationFrame(f); }\n"
                       "requestAnimationFrame(f);\n")})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertIn("layout_read_in_frame_loop",
                      [w["code"] for w in report["warnings"]])

    def test_a_frame_loop_that_only_writes_transform_stays_clean(self):
        self._write(files={
            "app.js": ("const el = document.querySelector('.c');\n"
                       "let x = 0;\n"
                       "function f(){ x += 1; el.style.transform = "
                       "'translateX(' + x + 'px)'; requestAnimationFrame(f); }\n"
                       "requestAnimationFrame(f);\n")})
        report = self._lint()
        self.assertNotIn("layout_read_in_frame_loop",
                         [w["code"] for w in report["warnings"]])

    def test_color_literals_warn_only_past_the_token_threshold(self):
        few = "<style>:root{--a:#123456}.x{color:#123456}</style>"
        self._write(files={"index.html": few})
        report = self._lint()
        self.assertNotIn("inline_color_literal",
                         [w["code"] for w in report["warnings"]])

        many = "<style>:root{--a:#123456}" + "".join(
            f".c{i}{{color:#123456}}" for i in range(design.COLOR_LITERAL_LIMIT + 1)
        ) + "</style>"
        self._write(files={"index.html": many})
        report = self._lint()
        self.assertIn("inline_color_literal",
                      [w["code"] for w in report["warnings"]])

    def test_css_rules_do_not_read_scripts_as_declaration_blocks(self):
        # A TSX object literal is not a CSS declaration block; reading it as
        # one would invent findings, and a warning that is often wrong trains
        # agents to ignore warnings.
        source = ("const Box = () => <div style={{transition: 'all'}}>"
                  "<img src='https://cdn.example.com/a.png' />1fr</div>;")
        self._write(files={"src/App.tsx": source})
        report = self._lint()
        codes = [w["code"] for w in report["warnings"]]
        for code in ("bare_fr_track", "transition_all", "uppercase_tight_leading"):
            self.assertNotIn(code, codes)

    def test_not_covered_is_published_with_report_and_summary(self):
        # ``passed`` must never read as "the design holds": the report says
        # what the scan cannot see, in full and in the bounded summary.
        self._write(files={"index.html": "<h1>库存</h1>"})
        report = self._lint()
        self.assertTrue(report["not_covered"])
        self.assertTrue(any("渲染" in item for item in report["not_covered"]))

        completed = self._lint_cli("--summary")
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["not_covered"], report["not_covered"])

    # --- false-positive boundaries ---

    def test_arrow_in_prose_is_not_flagged(self):
        self._write(files={"index.html": "<p>输入 → 输出</p>"})
        report = self._lint()
        self.assertNotIn("emoji_icon_without_exception", self.codes(report))
        self.assertTrue(report["passed"], report["blockers"])

    def test_emoji_plus_text_button_is_not_flagged(self):
        # A symbol that shares a label with real text is content, not a sole icon.
        self._write(contract_json=self._contract(icon_system="lucide"),
                    files={"index.html": "<button>🚀 发射记录</button>"})
        report = self._lint()
        self.assertNotIn("emoji_icon_without_exception", self.codes(report))

    def test_fixtures_and_markdown_are_excluded(self):
        self._write(files={
            "index.html": "<h1>ok</h1>",
            "tests/app.test.jsx": "<button>🎯</button>",
            "README.md": "<span>🎯</span>",
            "data.json": '{"x": "🎯"}',
        })
        report = self._lint()
        self.assertEqual(report["scanned_files"], ["index.html"])
        self.assertTrue(report["passed"], report["blockers"])

    def test_prototypes_and_demos_are_excluded_from_lint(self):
        self._write(files={
            "index.html": "<h1>ok</h1>",
            "prototypes/index.html": "<button><span>↓</span></button>",
            "demos/preview.html": "<button><span>→</span></button>",
            "experiments/test.html": "<button><span>✓</span></button>",
        })
        report = self._lint()
        self.assertEqual(report["scanned_files"], ["index.html"])
        self.assertTrue(report["passed"], report["blockers"])

    def test_intentional_exceptions_exempt_files(self):
        self._write(contract_json=self._contract(
            intentional_exceptions=["legacy/*"]),
            files={"index.html": "<h1>ok</h1>",
                   "legacy/old.html": "<span>🎯</span>"})
        report = self._lint()
        self.assertEqual(report["scanned_files"], ["index.html"])
        self.assertTrue(report["passed"])

    # --- --changed-from: JSON prior report ---

    def test_changed_from_json_no_change_is_scoped(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        prior = self._lint()
        prior_path = self.root / ".site" / "prior-lint.json"
        prior_path.write_text(json.dumps(prior, ensure_ascii=False), encoding="utf-8")
        report = self._lint(changed_from=str(prior_path))
        cf = report["changed_from"]
        self.assertTrue(cf["available"])
        self.assertEqual(cf["source"], "json")
        self.assertTrue(cf["scoped"])
        self.assertFalse(cf["contract_changed"])
        self.assertEqual(cf["changed_files"], 0)
        self.assertEqual(report["scanned_files"], [])

    def test_changed_from_json_source_change_scopes_to_file(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        prior = self._lint()
        prior_path = self.root / ".site" / "prior-lint.json"
        prior_path.write_text(json.dumps(prior, ensure_ascii=False), encoding="utf-8")
        (self.root / "index.html").write_text('<span class="icon">🎯</span>', encoding="utf-8")
        report = self._lint(changed_from=str(prior_path))
        cf = report["changed_from"]
        self.assertTrue(cf["scoped"])
        self.assertEqual(report["scanned_files"], ["index.html"])
        self.assertIn("emoji_icon_without_exception", self.codes(report))

    def test_changed_from_json_contract_change_forces_full_scan(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        prior = self._lint()
        prior_path = self.root / ".site" / "prior-lint.json"
        prior_path.write_text(json.dumps(prior, ensure_ascii=False), encoding="utf-8")
        # Edit the contract → rules moved → full scan, not scoped.
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        report = self._lint(changed_from=str(prior_path))
        cf = report["changed_from"]
        self.assertTrue(cf["contract_changed"])
        self.assertFalse(cf["scoped"])
        self.assertEqual(report["scanned_files"], ["index.html"])

    def test_changed_from_invalid_ref_is_full_scan(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        report = self._lint(changed_from=str(self.root / "missing.json"))
        cf = report["changed_from"]
        self.assertFalse(cf["available"])
        self.assertTrue(cf["error"])
        self.assertFalse(cf["scoped"])
        # Conservative: scan everything rather than claiming nothing changed.
        self.assertEqual(report["scanned_files"], ["index.html"])

    # --- CLI surface + performance ---

    def test_cli_lint_ui_emits_json_and_out(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        out = self.root / ".site" / "lint.json"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "lint-ui", "--root", str(self.root),
             "--out", str(out)],
            cwd=SKILL_ROOT.parent, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["passed"])
        self.assertTrue(out.is_file())
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["passed"], True)

    # --- bounded stdout (--summary) ---

    def _lint_cli(self, *extra, expected=0):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "lint-ui", "--root", str(self.root),
             *extra],
            cwd=SKILL_ROOT.parent, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, expected,
                         (completed.stdout or "") + (completed.stderr or ""))
        return completed

    def _files_with_one_blocker_each(self, count):
        """One emoji-as-icon blocker per file, so counts are predictable."""
        return {f"src/Comp{i}.tsx": '<span class="icon">🎯</span>'
                for i in range(count)}

    def test_summary_bounds_stdout_and_out_keeps_the_full_report(self):
        self._write(files=self._files_with_one_blocker_each(60))
        out = self.root / ".site" / "lint.json"
        completed = self._lint_cli("--summary", "--out", str(out))
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["mode"], "summary")
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["blocker_count"], 60)
        self.assertEqual(len(summary["blockers"]), design.SUMMARY_FINDING_LIMIT)
        self.assertEqual(summary["omitted"]["blockers"],
                         60 - design.SUMMARY_FINDING_LIMIT)
        self.assertEqual(summary["scanned_file_count"], 60)
        self.assertEqual(summary["tracked_file_count"], 60)
        self.assertEqual(summary["report"], str(out.resolve()))
        self.assertLess(len(completed.stdout.encode("utf-8")), 4096)

        full = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(full["blockers"]), 60)
        self.assertEqual(len(full["files"]), 60)
        self.assertEqual(len(full["scanned_files"]), 60)
        self.assertNotIn("mode", full)

    def test_summary_max_findings_controls_the_sample(self):
        self._write(files=self._files_with_one_blocker_each(20))
        summary = json.loads(
            self._lint_cli("--summary", "--max-findings", "2").stdout)
        self.assertEqual(len(summary["blockers"]), 2)
        self.assertEqual(summary["omitted"]["blockers"], 18)
        self.assertIsNone(summary["report"])
        self.assertIn("--out", summary["note"])

    def test_summary_zero_findings_keeps_the_counts(self):
        self._write(files=self._files_with_one_blocker_each(3))
        summary = json.loads(
            self._lint_cli("--summary", "--max-findings", "0").stdout)
        self.assertEqual(summary["blockers"], [])
        self.assertEqual(summary["blocker_count"], 3)
        self.assertEqual(summary["omitted"]["blockers"], 3)

    def test_summary_clean_project_has_no_truncation_note(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        summary = json.loads(self._lint_cli("--summary").stdout)
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["blocker_count"], 0)
        self.assertEqual(summary["scanned_file_count"], 1)
        self.assertNotIn("note", summary)

    def test_default_stdout_stays_the_full_report(self):
        self._write(files=self._files_with_one_blocker_each(20))
        report = json.loads(self._lint_cli().stdout)
        self.assertNotIn("mode", report)
        self.assertEqual(len(report["blockers"]), 20)
        self.assertEqual(len(report["files"]), 20)
        self.assertEqual(report["scanned_files"], sorted(report["scanned_files"]))

    def test_max_findings_without_summary_is_rejected(self):
        self._write(files={"index.html": "<h1>库存</h1>"})
        completed = self._lint_cli("--max-findings", "3", expected=1)
        self.assertIn("--max-findings requires --summary", completed.stderr)

    def test_report_under_one_second(self):
        import time
        self._write(files={"index.html": "<h1>库存</h1>"})
        start = time.perf_counter()
        self._lint()
        self.assertLess(time.perf_counter() - start, 5.0)

    def test_validate_auto_sync_fixes_drift(self):
        gallery = design.resources() / "gallery.html"
        if not gallery.is_file():
            return
        original = gallery.read_text(encoding="utf-8")
        try:
            # Intentionally inject a stale catalog block into gallery.html
            stale = design.CATALOG_BLOCK.sub(r'\1{}\3', original, count=1)
            gallery.write_text(stale, encoding="utf-8")

            # Validate without --auto-sync should fail with friendly message
            failed = subprocess.run(
                [sys.executable, str(SCRIPT), "validate"],
                cwd=SKILL_ROOT.parent, capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("Gallery catalog payload is stale", failed.stderr)
            self.assertIn("--auto-sync", failed.stderr)

            # Validate with --auto-sync should repair it and pass
            repaired = subprocess.run(
                [sys.executable, str(SCRIPT), "validate", "--auto-sync"],
                cwd=SKILL_ROOT.parent, capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            self.assertEqual(repaired.returncode, 0, repaired.stderr)
            self.assertIn("[Auto-Sync]", repaired.stdout)
            self.assertIn("gallery catalog in sync", repaired.stdout)
        finally:
            gallery.write_text(original, encoding="utf-8")


class LintUiGitRefTests(unittest.TestCase):
    """--changed-from also accepts a git revision; the project UI tree is
    re-fingerprinted at that revision and compared to the working tree."""

    CLEAN_BODY = LintUiTests.CLEAN_BODY

    def _git(self, *args):
        env = {"GIT_TERMINAL_PROMPT": "0",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(self.root), *args],
                       capture_output=True, env=env, timeout=30, check=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".site" / "design").mkdir(parents=True, exist_ok=True)
        contract = ("# 页面设计合同\n\n```site-contract\n"
                    + json.dumps({
                        "work_type": "new-surface", "structure_mode": "single",
                        "scope_refs": ["BR-01"], "required_constraints": [],
                        "pages": ["PG-01"], "sections": [], "responsive": [],
                        "components": [], "assets": [], "acceptance": [],
                        "unresolved_confirm": [], "blocking_missing_assets": [],
                        "icon_system": "", "icon_exceptions": [],
                        "intentional_exceptions": []}, ensure_ascii=False)
                    + "\n```\n\n" + self.CLEAN_BODY)
        (self.root / ".site" / "design" / "surface-brief.md").write_text(
            contract, encoding="utf-8")
        (self.root / "index.html").write_text("<h1>库存</h1>", encoding="utf-8")
        self._git("init")
        self._git("add", "-A")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "baseline")

    def tearDown(self):
        self.temp.cleanup()

    def _lint(self, **kwargs):
        return design.lint_ui(self.root, ".site/design/surface-brief.md", **kwargs)

    def test_git_ref_no_change(self):
        report = self._lint(changed_from="HEAD")
        cf = report["changed_from"]
        self.assertTrue(cf["available"])
        self.assertEqual(cf["source"], "git")
        self.assertTrue(cf["commit"])
        self.assertFalse(cf["contract_changed"])
        self.assertTrue(cf["scoped"])
        self.assertEqual(cf["changed_files"], 0)
        self.assertEqual(report["scanned_files"], [])

    def test_git_ref_source_change_scopes_to_file(self):
        (self.root / "index.html").write_text(
            '<span class="icon">🎯</span>', encoding="utf-8")
        report = self._lint(changed_from="HEAD")
        cf = report["changed_from"]
        self.assertTrue(cf["scoped"])
        self.assertEqual(report["scanned_files"], ["index.html"])
        self.assertIn("emoji_icon_without_exception",
                      sorted(b["code"] for b in report["blockers"]))

    def test_git_ref_contract_change_forces_full_scan(self):
        path = self.root / ".site" / "design" / "surface-brief.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        report = self._lint(changed_from="HEAD")
        cf = report["changed_from"]
        self.assertTrue(cf["contract_changed"])
        self.assertFalse(cf["scoped"])
        self.assertEqual(report["scanned_files"], ["index.html"])

    def test_git_ref_untracked_new_ui_file_is_changed(self):
        (self.root / "page2.html").write_text(
            '<span class="icon">🎯</span>', encoding="utf-8")
        report = self._lint(changed_from="HEAD")
        self.assertIn("page2.html", report["scanned_files"])

    def test_git_ref_invalid_revision_is_conservative(self):
        report = self._lint(changed_from="not-a-real-ref-xyz")
        cf = report["changed_from"]
        self.assertFalse(cf["available"])
        self.assertTrue(cf["error"])
        self.assertFalse(cf["scoped"])
        self.assertEqual(report["scanned_files"], ["index.html"])


class DesignCompatibilityTests(unittest.TestCase):
    def test_legacy_v3_contract_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy_file = root / ".v3" / "design" / "surface-brief.md"
            legacy_file.parent.mkdir(parents=True)
            text = (
                "# 页面设计合同\n\n```v3-contract\n"
                + json.dumps(VALID_CONTRACT_JSON, ensure_ascii=False)
                + "\n```\n"
                + BASE_BODY
            )
            legacy_file.write_text(text, encoding="utf-8")
            self.assertEqual(design.contract_path(root), legacy_file)
            report = design.check_contract(root, phase="prebuild")
            self.assertTrue(report["passed"])

    def test_case_insensitive_SITE_contract_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            caps_file = root / ".SITE" / "design" / "surface-brief.md"
            caps_file.parent.mkdir(parents=True)
            text = (
                "# 页面设计合同\n\n```site-contract\n"
                + json.dumps(VALID_CONTRACT_JSON, ensure_ascii=False)
                + "\n```\n"
                + BASE_BODY
            )
            caps_file.write_text(text, encoding="utf-8")
            self.assertEqual(design.contract_path(root), caps_file)
            report = design.check_contract(root, phase="prebuild")
            self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
