import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("site_install", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_install_uses_official_skill_names_and_includes_design_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            result = installer.install(ROOT, destination)
            self.assertEqual(
                result["skills"],
                ["site-brief", "site-builder", "site-check", "site-design"],
            )
            self.assertTrue((destination / "site-builder" / "scripts" / "state.py").is_file())
            self.assertTrue(
                (destination / "site-check" / "scripts" / "check.py").is_file()
            )
            self.assertTrue(
                (destination / "site-design" / "references" / "surface-brief.md").is_file()
            )
            self.assertTrue(
                (destination / "site-design" / "intelligence" / "VERSION").is_file()
            )

    def test_existing_bundle_requires_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            installer.install(ROOT, destination)
            with self.assertRaises(ValueError):
                installer.install(ROOT, destination)
            installer.install(ROOT, destination, replace=True)


if __name__ == "__main__":
    unittest.main()
