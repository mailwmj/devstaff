import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("v3_install", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_install_uses_versioned_skill_names_and_includes_design_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            result = installer.install(ROOT, destination)
            self.assertEqual(
                result["skills"],
                ["site-brief-v3", "site-builder-v3", "site-check-v3", "site-design-v3"],
            )
            self.assertTrue((destination / "site-builder-v3" / "scripts" / "state.py").is_file())
            self.assertTrue(
                (destination / "site-check-v3" / "scripts" / "check.py").is_file()
            )
            self.assertTrue(
                (destination / "site-design-v3" / "references" / "surface-brief.md").is_file()
            )
            self.assertTrue(
                (destination / "site-design-v3" / "intelligence" / "VERSION").is_file()
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
