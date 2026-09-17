import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "design.py"


def run_json(*args):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=SKILL_ROOT.parent,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


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

        self.assertEqual(catalog["source"]["name"], "ui-ux-pro-max")
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
            ".v3/design/surface-brief.md#设计方法来源",
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

        self.assertNotIn(".v3/design/design-intent.md", content)
        self.assertNotIn("MASTER.md", content)


if __name__ == "__main__":
    unittest.main()
