import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class BundleTests(unittest.TestCase):
    def test_declared_skill_directories_and_names_match(self):
        manifest = json.loads((ROOT / "skills.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.0.0")
        for name, details in manifest["skills"].items():
            skill_file = ROOT / details["directory"] / "SKILL.md"
            self.assertTrue(skill_file.is_file(), name)
            frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)[1]
            self.assertIn(f"name: {name}", frontmatter)

    def test_relative_markdown_links_resolve(self):
        for document in ROOT.rglob("*.md"):
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                path = (document.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(path.exists(), f"{document}: missing {target}")

    def test_design_knowledge_base_is_packaged(self):
        design = ROOT / "site-design"
        expected_references = {
            "chinese-typography.md",
            "craft-review.md",
            "design-context.md",
            "design-tokens.md",
            "design-toolchain.md",
            "landing-page.md",
            "prototype.md",
            "reference-input.md",
            "surface-brief.md",
            "visual-direction.md",
        }
        self.assertEqual(
            {path.name for path in (design / "references").glob("*.md")},
            expected_references,
        )
        self.assertTrue((design / "assets" / "design" / "tokens.json").is_file())
        self.assertTrue((design / "assets" / "design" / "gallery.html").is_file())
        self.assertTrue((design / "scripts" / "design.py").is_file())
        self.assertTrue((design / "intelligence" / "LICENSE").is_file())

    def test_builder_owns_state_interface(self):
        self.assertTrue((ROOT / "site-builder" / "scripts" / "state.py").is_file())
        self.assertFalse((ROOT / "site_core").exists())

    def test_check_owns_protocol_script(self):
        self.assertTrue((ROOT / "site-check" / "scripts" / "check.py").is_file())


if __name__ == "__main__":
    unittest.main()
