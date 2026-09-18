import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "release"

SKILL_NAMES = ("site-brief", "site-builder", "site-check", "site-design")


class BundleTests(unittest.TestCase):
    def test_release_directory_is_the_only_distribution_root(self):
        for entry in ("skills.json", "install.py", "AGENTS.md"):
            self.assertTrue((RELEASE / entry).is_file(), entry)
            self.assertFalse((ROOT / entry).exists(), f"{entry} must not sit at the repository root")
        for name in SKILL_NAMES:
            self.assertTrue((RELEASE / name).is_dir(), name)
            self.assertFalse((ROOT / name).exists(), f"{name} must not sit at the repository root")

    def test_declared_skill_directories_and_names_match(self):
        manifest = json.loads((RELEASE / "skills.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.0.0")
        for name, details in manifest["skills"].items():
            self.assertEqual(details["directory"], name)
            skill_file = RELEASE / details["directory"] / "SKILL.md"
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
        design = RELEASE / "site-design"
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
        self.assertTrue((RELEASE / "site-builder" / "scripts" / "state.py").is_file())
        self.assertFalse((ROOT / "site_core").exists())

    def test_check_owns_protocol_script(self):
        self.assertTrue((RELEASE / "site-check" / "scripts" / "check.py").is_file())


if __name__ == "__main__":
    unittest.main()
