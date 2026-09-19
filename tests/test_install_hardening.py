"""Installation failure/recovery tests using small synthetic release fixtures."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('install_hardening', ROOT / 'release/install.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
NAMES = ['site-builder', 'site-brief', 'site-design', 'site-check']


class InstallHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'release'
        self.dest = Path(self.temp.name) / 'installed'
        self.root.mkdir()
        self.config = {'version': '1.1', 'bundle': 'test-site-skills',
                       'skills': {name: {'directory': name} for name in NAMES}}
        self.write_config()
        (self.root / 'AGENTS.md').write_text('# Shared instructions v1\n', encoding='utf-8')
        for name in NAMES:
            folder = self.root / name
            folder.mkdir()
            (folder / 'SKILL.md').write_text(f'---\nname: {name}\n---\nInstructions\n', encoding='utf-8')
            (folder / 'VERSION').write_text('old\n', encoding='utf-8')

    def write_config(self):
        (self.root / 'skills.json').write_text(json.dumps(self.config), encoding='utf-8')

    def snapshot(self):
        return {str(path.relative_to(self.dest)): path.read_bytes()
                for name in NAMES for path in (self.dest / name).rglob('*') if path.is_file()}

    def test_instruction_file_survives_removing_source(self):
        result = installer.install(self.root, self.dest)
        shutil.rmtree(self.root)
        instructions = Path(result['instruction_file'])
        self.assertTrue(instructions.is_relative_to(self.dest))
        self.assertEqual(instructions.read_text(), '# Shared instructions v1\n')

    def test_host_agents_file_is_not_overwritten(self):
        self.dest.mkdir()
        host = self.dest / 'AGENTS.md'
        host.write_text('User-owned project rules\n', encoding='utf-8')
        installer.install(self.root, self.dest)
        self.assertEqual(host.read_text(), 'User-owned project rules\n')

    def test_replace_requires_explicit_flag(self):
        installer.install(self.root, self.dest)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            installer.install(self.root, self.dest)
        self.assertEqual(self.snapshot(), before)

    def test_replace_updates_shared_instructions(self):
        installer.install(self.root, self.dest)
        (self.root / 'AGENTS.md').write_text('# Shared instructions v2\n', encoding='utf-8')
        result = installer.install(self.root, self.dest, replace=True)
        self.assertEqual(Path(result['instruction_file']).read_text(), '# Shared instructions v2\n')

    def test_replace_failure_restores_every_old_file(self):
        installer.install(self.root, self.dest)
        before = self.snapshot()
        for name in NAMES:
            (self.root / name / 'VERSION').write_text('new\n', encoding='utf-8')
        original = installer.os.replace

        def fail_second_skill(source, target):
            source = Path(source)
            if source.parent.name == 'new' and source.name == 'site-brief':
                raise OSError('injected replacement failure')
            return original(source, target)

        with mock.patch.object(installer.os, 'replace', side_effect=fail_second_skill):
            with self.assertRaisesRegex(OSError, 'injected'):
                installer.install(self.root, self.dest, replace=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.dest / installer.LOCK_NAME).exists())
        self.assertFalse(list(self.dest.glob('site-skills-*')))

    def test_first_install_failure_leaves_no_partial_bundle(self):
        original = installer.os.replace

        def fail_second_skill(source, target):
            if Path(source).name == 'site-brief':
                raise OSError('injected first-install failure')
            return original(source, target)

        with mock.patch.object(installer.os, 'replace', side_effect=fail_second_skill):
            with self.assertRaises(OSError):
                installer.install(self.root, self.dest)
        self.assertFalse(any((self.dest / name).exists() for name in NAMES))
        self.assertFalse((self.dest / installer.LOCK_NAME).exists())

    def test_incomplete_rollback_retains_recovery_and_lock(self):
        installer.install(self.root, self.dest)
        original = installer.os.replace

        def fail_and_prevent_one_restore(source, target):
            source = Path(source)
            if source.name == 'site-brief' and source.parent.name in ('new', 'backup'):
                raise OSError('injected move failure')
            return original(source, target)

        with mock.patch.object(installer.os, 'replace', side_effect=fail_and_prevent_one_restore):
            with self.assertRaisesRegex(RuntimeError, 'rollback incomplete'):
                installer.install(self.root, self.dest, replace=True)
        self.assertTrue((self.dest / installer.LOCK_NAME).exists())
        recovery = list(self.dest.glob('site-skills-*/recovery.json'))
        self.assertEqual(len(recovery), 1)
        backup = recovery[0].parent / 'backup/site-brief/VERSION'
        self.assertEqual(backup.read_text(), 'old\n')

    def test_existing_lock_blocks_install_without_touching_content(self):
        self.dest.mkdir()
        (self.dest / installer.LOCK_NAME).write_text('interrupted install', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'locked'):
            installer.install(self.root, self.dest)
        self.assertFalse(any((self.dest / name).exists() for name in NAMES))

    def test_missing_instructions_fails_before_creating_destination(self):
        (self.root / 'AGENTS.md').unlink()
        with self.assertRaises(ValueError):
            installer.install(self.root, self.dest)
        self.assertFalse(self.dest.exists())

    def test_unsafe_skill_name_is_rejected(self):
        self.config['skills']['../escape'] = {'directory': 'site-brief'}
        self.write_config()
        with self.assertRaises(ValueError):
            installer.install(self.root, self.dest)
        self.assertFalse(self.dest.exists())

    def test_unsafe_source_directory_is_rejected(self):
        self.config['skills']['site-brief']['directory'] = '../release/site-brief'
        self.write_config()
        with self.assertRaises(ValueError):
            installer.install(self.root, self.dest)
        self.assertFalse(self.dest.exists())

    def test_install_into_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            installer.install(self.root, self.root, replace=True)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            installer.install(self.root, self.root / 'site-brief/nested')
        self.assertTrue((self.root / 'site-brief/SKILL.md').exists())

    def test_symlink_in_release_is_rejected(self):
        target = Path(self.temp.name) / 'outside.txt'
        target.write_text('do not copy', encoding='utf-8')
        try:
            (self.root / 'site-brief/link').symlink_to(target)
        except OSError:
            self.skipTest('symlinks not available')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            installer.install(self.root, self.dest)

    def test_installed_scripts_work_after_source_is_removed(self):
        for name, script in (('site-builder', 'state.py'), ('site-check', 'check.py')):
            folder = self.root / name / 'scripts'
            folder.mkdir()
            shutil.copy2(ROOT / 'release' / name / 'scripts' / script, folder / script)
        installer.install(self.root, self.dest)
        shutil.rmtree(self.root)
        script = self.dest / 'site-builder/scripts/state.py'
        spec = importlib.util.spec_from_file_location('installed_state_hardening', script)
        installed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installed)
        project = Path(self.temp.name) / 'project'
        project.mkdir()
        self.assertEqual(installed.init(project, 'guided')['stage'], 'discovering')
        self.assertEqual(installed._check_script(), self.dest / 'site-check/scripts/check.py')
        contract = project / '.site/design/surface-brief.md'
        contract.parent.mkdir()
        contract.write_text('```site-contract\n{}\n```\n', encoding='utf-8')
        (project / 'index.html').write_text('<h1>Test</h1>', encoding='utf-8')
        fingerprint = installed._plan_fingerprint(project)
        self.assertEqual(len(fingerprint['source_sha256']), 64)
        self.assertEqual(len(fingerprint['contract_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
