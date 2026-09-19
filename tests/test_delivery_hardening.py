"""Regression tests for policy authority and verification-round identity.

The fixtures use the actual state/check scripts and real project files. They
bypass the design step only: this suite tests delivery gates, not UI quality.
Run against the previous source with DEVSTAFF_TEST_ROOT for a red/green check.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(os.environ.get('DEVSTAFF_TEST_ROOT', Path(__file__).resolve().parents[1]))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load('hardening_check', ROOT / 'release/site-check/scripts/check.py')
state = load('hardening_state', ROOT / 'release/site-builder/scripts/state.py')


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.root.mkdir()
        state.init(self.root, 'guided', schema_revision=2)
        self.contract = self.root / '.site/design/surface-brief.md'
        self.contract.parent.mkdir(parents=True)
        self.contract.write_text('# Contract\n```site-contract\n{}\n```\n', encoding='utf-8')
        self.source = self.root / 'index.html'
        self.source.write_text('<h1>Inventory</h1>\n', encoding='utf-8')
        self.report_path = self.root / '.site/report.json'

    def set_mode(self, mode):
        payload = state.read_state(self.root)
        payload['mode'] = mode
        state.write_state(self.root, payload)

    def report(self):
        plan = check.plan(self.root)
        return {
            'project_root': str(self.root), 'mode': plan['mode'],
            'overall': 'verified', 'independent': plan['mode'] == 'strict',
            'contract_sha256': plan['contract_sha256'],
            'source_sha256': plan['source_sha256'],
            'source_manifest': plan['source_manifest'],
            'axes': {axis: {'status': 'verified', 'observed': 'Fixture observation'}
                     for axis in plan['required_axes']},
            'evidence': ['Fixture core task completed'], 'limitations': [],
        }

    def save_report(self, report):
        self.report_path.write_text(json.dumps(report), encoding='utf-8')
        return self.report_path

    def validate(self, report):
        return check.validate_report(self.root, self.save_report(report))

    def open_round(self):
        payload = state.read_state(self.root)
        payload['stage'] = 'building'
        payload['decision'].update(confirmed=True, task='Inventory', direction='Table', quote='Use this')
        state.write_state(self.root, payload)
        state.handoff(self.root)
        state.begin_check(self.root, 'This version is ready to test')


class ReportPolicyTests(ProjectFixture):
    def test_guided_matching_report_still_valid(self):
        result = self.validate(self.report())
        self.assertTrue(result['valid'], result['errors'])

    def test_strict_matching_report_still_valid(self):
        self.set_mode('strict')
        result = self.validate(self.report())
        self.assertTrue(result['valid'], result['errors'])

    def test_report_cannot_downgrade_project_mode(self):
        report = self.report()
        report['independent'] = True
        self.set_mode('strict')
        result = self.validate(report)
        self.assertFalse(result['valid'])
        self.assertIn('mode', ' '.join(result['errors']))
        self.assertIn('risk', ' '.join(result['errors']))
        self.assertIn('reopen', ' '.join(result['errors']))

    def test_report_mode_must_match_in_both_directions(self):
        report = self.report()
        report['mode'] = 'strict'
        report['independent'] = True
        for axis in ('risk', 'reopen'):
            report['axes'][axis] = {'status': 'verified', 'observed': 'Fixture observation'}
        self.assertFalse(self.validate(report)['valid'])

    def test_string_false_is_not_independent(self):
        for mode in ('guided', 'strict'):
            with self.subTest(mode=mode):
                self.set_mode(mode)
                report = self.report()
                report['independent'] = 'false'
                result = self.validate(report)
                self.assertFalse(result['valid'])
                self.assertIs(result['independent'], False)
                self.assertIn('boolean', ' '.join(result['errors']))

    def test_non_boolean_independence_values_are_rejected(self):
        for value in (1, 0, 'true', '', [], {}, None):
            with self.subTest(value=value):
                report = self.report()
                report['independent'] = value
                self.assertFalse(self.validate(report)['valid'])

    def test_not_run_is_not_masked_by_limited(self):
        report = self.report()
        report['axes']['core_task'] = {'status': 'not_run'}
        report['axes']['negative_path'] = {'status': 'limited'}
        report.update(overall='limited', limitations=['Some coverage missing'])
        result = self.validate(report)
        self.assertFalse(result['valid'])
        self.assertIn('blocked', ' '.join(result['errors']))

    def test_not_run_plus_limited_can_be_recorded_as_blocked(self):
        report = self.report()
        report['axes']['core_task'] = {'status': 'not_run'}
        report['axes']['negative_path'] = {'status': 'limited'}
        report.update(overall='blocked', limitations=['Core task has not run'])
        result = self.validate(report)
        self.assertTrue(result['valid'], result['errors'])

    def test_valid_limited_report_is_not_globally_banned(self):
        report = self.report()
        report['axes']['negative_path'] = {'status': 'limited'}
        report.update(overall='limited', limitations=['Second negative path unavailable'])
        result = self.validate(report)
        self.assertTrue(result['valid'], result['errors'])

    def test_empty_and_non_text_evidence_are_rejected(self):
        for evidence in ([''], ['   '], [1], [None], [{}], 'passed'):
            with self.subTest(evidence=evidence):
                report = self.report()
                report['evidence'] = evidence
                self.assertFalse(self.validate(report)['valid'])

    def test_limited_requires_meaningful_limitations(self):
        for limitations in ([''], [None], [1], 'missing'):
            with self.subTest(limitations=limitations):
                report = self.report()
                report['axes']['negative_path'] = {'status': 'limited'}
                report.update(overall='limited', limitations=limitations)
                self.assertFalse(self.validate(report)['valid'])

    def test_observed_must_be_nonempty_text(self):
        for observed in (1, {}, ['passed'], True, None, ''):
            with self.subTest(observed=observed):
                report = self.report()
                report['axes']['core_task']['observed'] = observed
                self.assertFalse(self.validate(report)['valid'])

    def test_missing_state_retains_legacy_guided_default(self):
        state.state_path(self.root).unlink()
        self.assertEqual(check.read_mode(self.root), 'guided')
        self.assertTrue(self.validate(self.report())['valid'])

    def test_corrupt_state_never_defaults_to_guided(self):
        report = self.report()
        state.state_path(self.root).write_text('{broken', encoding='utf-8')
        result = self.validate(report)
        self.assertFalse(result['valid'])
        with self.assertRaises(ValueError):
            check.plan(self.root)

    def test_non_object_state_is_a_structured_error(self):
        report = self.report()
        state.state_path(self.root).write_text('[]', encoding='utf-8')
        self.assertFalse(self.validate(report)['valid'])
        with self.assertRaises(ValueError):
            state.read_state(self.root)

    def test_invalid_state_mode_is_rejected(self):
        report = self.report()
        payload = state.read_state(self.root)
        payload['mode'] = 'strcit'
        state.write_state(self.root, payload)
        self.assertFalse(self.validate(report)['valid'])

    def test_multiple_state_files_are_not_silently_selected(self):
        report = self.report()
        other = self.root / '.v3'
        other.mkdir()
        (other / 'state.json').write_text('{"mode":"strict"}', encoding='utf-8')
        self.assertFalse(self.validate(report)['valid'])

    def test_mixed_case_state_directory_preserves_strict_mode(self):
        self.set_mode('strict')
        (self.root / '.site').rename(self.root / '.Site')
        self.assertEqual(check.read_mode(self.root), 'strict')

    def test_unknown_schema_revision_is_rejected_by_both_tools(self):
        for revision in (0, 4, 99, '2', True, None):
            with self.subTest(revision=revision):
                path = self.root / '.site/state.json'
                payload = json.loads(path.read_text())
                payload['schema_revision'] = revision
                path.write_text(json.dumps(payload), encoding='utf-8')
                with self.assertRaises(ValueError):
                    state.read_state(self.root)
                with self.assertRaises(ValueError):
                    check.read_mode(self.root)

    def test_supported_legacy_schema_still_reads(self):
        payload = state.read_state(self.root)
        payload.pop('schema_revision')
        state.write_state(self.root, payload)
        self.assertEqual(state.read_state(self.root)['mode'], 'guided')
        self.assertEqual(check.read_mode(self.root), 'guided')

    def test_cli_reports_corrupt_state_without_traceback(self):
        state.state_path(self.root).write_text('[]', encoding='utf-8')
        proc = subprocess.run([sys.executable, str(ROOT / 'release/site-builder/scripts/state.py'),
                               'preflight', str(self.root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('error', json.loads(proc.stdout))
        self.assertNotIn('Traceback', proc.stderr)


class VerificationIdentityTests(ProjectFixture):
    def test_unchanged_guided_round_delivers(self):
        self.open_round()
        result = state.verify(self.root, self.save_report(self.report()))
        self.assertEqual(result['stage'], 'delivered')

    def test_unchanged_strict_round_delivers(self):
        self.set_mode('strict')
        self.open_round()
        result = state.verify(self.root, self.save_report(self.report()))
        self.assertEqual(result['stage'], 'delivered')

    def test_strict_delivery_cannot_use_guided_report(self):
        self.set_mode('strict')
        self.open_round()
        report = self.report()
        report['mode'] = 'guided'
        del report['axes']['risk']
        del report['axes']['reopen']
        with self.assertRaises(ValueError):
            state.verify(self.root, self.save_report(report))
        self.assertEqual(state.read_state(self.root)['verification']['phase'], 'checking')

    def test_source_change_and_fresh_report_cannot_reuse_approved_round(self):
        self.open_round()
        self.source.write_text('<h1>Different build</h1>\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed during'):
            state.verify(self.root, self.save_report(self.report()))
        self.assertEqual(state.read_state(self.root)['stage'], 'building')

    def test_contract_change_and_fresh_report_cannot_reuse_round(self):
        self.open_round()
        self.contract.write_text(self.contract.read_text() + '\nChanged spec\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed during'):
            state.verify(self.root, self.save_report(self.report()))

    def test_source_edit_during_report_validation_is_detected(self):
        self.open_round()
        report_path = self.save_report(self.report())
        original = state._load_check_report

        def load_then_edit(path, root):
            result = original(path, root)
            self.source.write_text('<h1>Edited during validation</h1>\n', encoding='utf-8')
            return result

        with mock.patch.object(state, '_load_check_report', side_effect=load_then_edit):
            with self.assertRaisesRegex(ValueError, 'changed during report validation'):
                state.verify(self.root, report_path)

    def test_journal_edit_does_not_invalidate_round(self):
        self.open_round()
        journal = self.root / '.site/journal.md'
        journal.write_text(journal.read_text() + '\nObserved one item\n', encoding='utf-8')
        self.assertEqual(state.verify(self.root, self.save_report(self.report()))['stage'], 'delivered')

    def test_failed_round_can_be_cancelled_and_correctly_restarted(self):
        self.open_round()
        self.source.write_text('<h1>Fixed</h1>\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            state.verify(self.root, self.save_report(self.report()))
        state.cancel_check(self.root, 'Source changed')
        state.handoff(self.root)
        state.begin_check(self.root, 'Check the fixed version')
        self.assertEqual(state.verify(self.root, self.save_report(self.report()))['stage'], 'delivered')

    def test_truthy_prebuild_pass_is_not_a_pass(self):
        report = {'project_root': str(self.root), 'phase': 'prebuild',
                  'contract_sha256': state._contract_sha256(self.root), 'passed': 'false'}
        path = self.root / '.site/prebuild.json'
        path.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'did not pass'):
            state._validate_contract_report(self.root, state.read_state(self.root), path)


if __name__ == '__main__':
    unittest.main()
