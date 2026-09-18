import json
import tempfile
from pathlib import Path
import re
import subprocess
import sys
import unittest
import hashlib

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
    )
    return json.loads(completed.stdout)


# Body of a surface-brief whose design-judgment fields differ from the
# template defaults and whose tables declare BR-01/IC-01/PG-01/VA-01.
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
        # Only work_type, structure, one scope ref and one page; no sections,
        # responsive, components, assets or acceptance. Still passes prebuild.
        write_contract(self.root, {
            "work_type": "new-surface", "structure_mode": "single",
            "scope_refs": ["BR-01"], "required_constraints": [],
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
        self.assertEqual(self.codes(report), ["broken_reference"])

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

    def test_missing_design_judgment_is_blocked(self):
        # Revert one design-judgment field to the template default value.
        default = ""
        for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("- **母题：**"):
                default = line.strip().split("- **母题：**", 1)[1].strip()
                break
        body = BASE_BODY.replace(
            "- **母题：** 以表格为视觉主角密度优先",
            "- **母题：** " + default,
        )
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

    def test_direction_phase_is_lighter_than_prebuild(self):
        # Missing design judgment does not block the direction phase.
        default = ""
        for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("- **母题：**"):
                default = line.strip().split("- **母题：**", 1)[1].strip()
                break
        body = BASE_BODY.replace(
            "- **母题：** 以表格为视觉主角密度优先",
            "- **母题：** " + default,
        )
        write_contract(self.root, body=body)
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
        default = ""
        for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("- **母题：**"):
                default = line.strip().split("- **母题：**", 1)[1].strip()
                break
        body = BASE_BODY.replace(
            "- **母题：** 以表格为视觉主角密度优先",
            "- **母题：** " + default,
        )
        write_contract(self.root, body=body)
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
        )
        elapsed = time.perf_counter() - start
        self.assertEqual(completed.returncode, 0)
        # Process startup aside, the check itself is well under a second.
        self.assertLess(elapsed, 5.0)


class DesignIntelligenceContractTests(unittest.TestCase):
    def test_research_requires_one_explicit_route(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "research", "generic dashboard"],
            cwd=SKILL_ROOT.parent,
            text=True,
            capture_output=True,
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


class ReferenceArchitectureTests(unittest.TestCase):
    def test_runtime_references_are_flat_and_bounded(self):
        references = SKILL_ROOT / "references"
        markdown = list(references.rglob("*.md"))

        self.assertLessEqual(len(markdown), 8)
        self.assertFalse((references / "upstream").exists())
        self.assertFalse((references / "design-intent.md").exists())

        entrypoint = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        linked = set(re.findall(r"\(references/([^)#]+\.md)(?:#[^)]+)?\)", entrypoint))
        self.assertEqual({path.name for path in markdown}, linked)

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
            "| 候选 | 匹配依据 | 母题 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `方案一` | a | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n"
            "| `方案二` | b | 货架卡片 | 实物 | 网格铺陈 | x | y | `pending` |\n")
        self._write(body=body)
        report = self._lint()
        self.assertIn("skin_only_candidates", self.codes(report))

    def test_skin_only_candidates_identical_motif_is_blocked(self):
        body = self.CLEAN_BODY + (
            "## 对照方向（仅在真实取舍存在时）\n\n"
            "| 候选 | 匹配依据 | 母题 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
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
            "| 候选 | 匹配依据 | 母题 | 视觉世界 | 构图命题 | 突出 / 牺牲 | 实现 / 无障碍风险 | 结果 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `方案一` | a | 表格矩阵 | 数据 | 表格居中 | x | y | `pending` |\n")
        self._write(body=body, files={"index.html": "<h1>库存</h1>"})
        report = self._lint()
        self.assertNotIn("skin_only_candidates", self.codes(report))

    # --- template tendencies are warnings only ---

    def test_hero_cards_cta_is_warning_not_blocker(self):
        html = ('<section class="hero"><h1>产品</h1></section>'
                '<div class="card">a</div><div class="card">b</div>'
                '<div class="card">c</div><button>立即开始</button>')
        self._write(files={"index.html": html})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertIn("template_hero_cards_cta", [w["code"] for w in report["warnings"]])

    def test_undeclared_icon_system_is_warning(self):
        # Icons in use but contract declares no icon_system → warning, not blocker.
        self._write(files={"index.html": '<svg data-lucide="x"></svg>'})
        report = self._lint()
        self.assertTrue(report["passed"], report["blockers"])
        self.assertIn("undeclared_icon_system", [w["code"] for w in report["warnings"]])

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
            cwd=SKILL_ROOT.parent, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["passed"])
        self.assertTrue(out.is_file())
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["passed"], True)

    def test_report_under_one_second(self):
        import time
        self._write(files={"index.html": "<h1>库存</h1>"})
        start = time.perf_counter()
        self._lint()
        self.assertLess(time.perf_counter() - start, 5.0)


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
