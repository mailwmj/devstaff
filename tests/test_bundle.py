import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "release"

SKILL_NAMES = ("site-brief", "site-builder", "site-check", "site-design")


def packaged_paths():
    """Paths declared by the release manifest, relative to the release root."""
    lines = (RELEASE / "package-files.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


class BundleTests(unittest.TestCase):
    def test_release_directory_is_the_only_distribution_root(self):
        self.assertTrue((RELEASE / "metadata.json").is_file())
        self.assertTrue((RELEASE / "agent" / "Agent.md").is_file())
        for name in SKILL_NAMES:
            self.assertTrue((RELEASE / "skills" / name / "SKILL.md").is_file(), name)
            self.assertFalse((ROOT / name).exists(), f"{name} must not sit at the repository root")

    def test_declared_skill_names_match_frontmatter(self):
        # The platform package keeps the skills under skills/; SKILL.md
        # frontmatter is where each directory's name is declared.
        for name in SKILL_NAMES:
            skill_file = RELEASE / "skills" / name / "SKILL.md"
            frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)[1]
            self.assertIn(f"name: {name}", frontmatter)

    def test_package_manifest_lists_existing_files(self):
        listed = packaged_paths()
        self.assertIn("metadata.json", listed)
        self.assertIn("agent/Agent.md", listed)
        self.assertIn("skills/site-check/scripts/check.py", listed)
        for rel in listed:
            self.assertTrue((RELEASE / rel).is_file(), f"missing packaged file: {rel}")

    def test_relative_markdown_links_resolve(self):
        for document in ROOT.rglob("*.md"):
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                path = (document.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(path.exists(), f"{document}: missing {target}")

    def test_design_knowledge_base_is_packaged(self):
        design = RELEASE / "skills" / "site-design"
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
        self.assertTrue((design / "assets" / "design" / "preview-shell.html").is_file())
        self.assertTrue((design / "scripts" / "design.py").is_file())
        self.assertTrue((design / "intelligence" / "LICENSE").is_file())

    def test_builder_owns_state_interface(self):
        self.assertTrue((RELEASE / "skills" / "site-builder" / "scripts" / "state.py").is_file())
        self.assertFalse((ROOT / "site_core").exists())

    def test_check_owns_protocol_script(self):
        self.assertTrue((RELEASE / "skills" / "site-check" / "scripts" / "check.py").is_file())


if __name__ == "__main__":
    unittest.main()
