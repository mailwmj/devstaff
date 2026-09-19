import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "release"
SPEC = importlib.util.spec_from_file_location("site_install", RELEASE / "install.py")
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_install_uses_official_skill_names_and_includes_design_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            result = installer.install(RELEASE, destination)
            self.assertEqual(
                result["skills"],
                ["site-brief", "site-builder", "site-check", "site-design"],
            )
            self.assertEqual(result["instruction_file"],
                             str((destination / "site-builder/references/AGENTS.md").resolve()))
            self.assertEqual(Path(result["instruction_file"]).read_bytes(),
                             (RELEASE / "AGENTS.md").read_bytes())
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
            installer.install(RELEASE, destination)
            with self.assertRaises(ValueError):
                installer.install(RELEASE, destination)
            installer.install(RELEASE, destination, replace=True)

    def test_installed_builder_finds_the_installed_protocol_script(self):
        # verify --report is gated on check.py; if the two skills stop being
        # installed as siblings, that gate must fail loudly rather than
        # silently accepting any report.
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            installer.install(RELEASE, destination)
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
