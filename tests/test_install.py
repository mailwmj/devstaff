import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "release"
INSTALLER = RELEASE / "install.py"


@unittest.skipUnless(
    INSTALLER.is_file(),
    "install.py was replaced by the platform package format (agent/ + skills/ + "
    "metadata.json); restore the installer and this test together if it returns",
)
class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("site_install", INSTALLER)
        assert spec is not None and spec.loader is not None
        cls.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.installer)

    def test_install_uses_official_skill_names_and_includes_design_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            result = self.installer.install(RELEASE, destination)
            self.assertEqual(
                result["skills"],
                ["site-brief", "site-builder", "site-check", "site-design"],
            )
            self.assertEqual(result["instruction_file"], str((RELEASE / "AGENTS.md").resolve()))
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
            self.installer.install(RELEASE, destination)
            with self.assertRaises(ValueError):
                self.installer.install(RELEASE, destination)
            self.installer.install(RELEASE, destination, replace=True)

    def test_installed_builder_finds_the_installed_protocol_script(self):
        # verify --report is gated on check.py; if the two skills stop being
        # installed as siblings, that gate must fail loudly rather than
        # silently accepting any report.
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            self.installer.install(RELEASE, destination)
            state_file = destination / "site-builder" / "scripts" / "state.py"
            spec = importlib.util.spec_from_file_location("installed_state", state_file)
            installed = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(installed)
            resolved = installed._check_script()
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved,
                             (destination / "site-check" / "scripts" / "check.py").resolve())


if __name__ == "__main__":
    unittest.main()
