"""Focused regressions for optional transcript anchors and check evidence."""

import importlib.util
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site-brief' / 'scripts'))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


consent = load_module('site_consent_test', ROOT / 'site-brief' / 'scripts' / 'state_consent.py')
state = load_module('site_state_test', ROOT / 'site-brief' / 'scripts' / 'state.py')
check = load_module('site_check_test', ROOT / 'site-check' / 'scripts' / 'check.py')


class AnchorTests(unittest.TestCase):
    def test_unknown_transcript_shape_downgrades_but_missing_quote_in_known_shape_rejects(self):
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / 'session.jsonl'
            transcript.write_text('host-specific binary-ish records')
            unknown = consent.build_consent(SimpleNamespace(quote='Proceed', anchor=str(transcript)))
            self.assertEqual(unknown['basis'], 'agent-reported')
            self.assertIn('format', unknown['anchor_note'])

            transcript.write_text('{"role":"user","content":"Stop"}\n')
            with self.assertRaisesRegex(ValueError, 'quote was not found'):
                consent.build_consent(SimpleNamespace(quote='Proceed', anchor=str(transcript)))

    def test_gzip_transcript_matches_user_quote_without_optional_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / 'session.jsonl.gz'
            transcript.write_bytes(gzip.compress(b'{"role":"user","content":"Proceed"}\n'))
            with patch.dict(sys.modules, {'zstandard': None}):
                recorded = consent.build_consent(SimpleNamespace(quote='Proceed', anchor=str(transcript)))
            self.assertEqual(recorded['basis'], 'quote-matched')

    def test_missing_optional_zstd_decoder_names_the_cause(self):
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / 'session.jsonl.zstd'
            transcript.write_bytes(b'\x28\xb5\x2f\xfd')
            with patch.dict(sys.modules, {'zstandard': None}):
                path, readable, note = consent.locate_anchor(str(transcript), temporary)
            self.assertEqual(path, transcript.resolve())
            self.assertFalse(readable)
            self.assertIn('zstandard', note)
            self.assertIn('agent-reported', note)
            self.assertNotIn('host format this tool cannot read', note)
            with patch.dict(sys.modules, {'zstandard': None}):
                recorded = consent.build_consent(SimpleNamespace(quote='OK', anchor=str(transcript)))
            self.assertEqual(recorded['basis'], 'agent-reported')


class StaticEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / '.site').mkdir()
        (self.root / 'index.html').write_text('<!doctype html><title>Test</title><p>Ready</p>')

    def static_result(self):
        return check.finalize(self.root, check.static_check(self.root))

    def matrix(self, static_id):
        payload = {
            'profile': 'targeted',
            'profile_reason': 'Check a changed static page',
            'browser': {'available': False, 'limitation': 'No browser is needed for this static fixture'},
            'items': [
                {'id': 'static', 'axis': 'static_build', 'status': 'passed', 'blocking': True,
                 'evidence': {'kind': 'check', 'summary': 'Static references pass', 'checks': [static_id]}},
                {'id': 'core', 'axis': 'core_task', 'status': 'passed', 'blocking': True,
                 'evidence': {'kind': 'artifact', 'summary': 'Page output', 'paths': ['index.html']}},
            ],
        }
        return check.finalize(self.root, check.matrix_check(self.root, payload))

    def test_static_result_supports_matrix_and_delivery(self):
        result = self.static_result()
        self.assertEqual(result['status'], 'passed')
        matrix = self.matrix(result['check_id'])
        self.assertEqual(matrix['status'], 'passed', matrix.get('evidence_failures'))
        self.assertEqual(matrix['items'][0]['evidence']['items'][0]['check_id'], result['check_id'])

        current_state = {'stage': 'verifying', 'visual_required': False, 'revision': 1}
        args = SimpleNamespace(check=matrix['check_id'], expect_revision=None)
        with patch.object(state, 'load_state', return_value=current_state), \
             patch.object(state, 'require_lease'), patch.object(state, 'gate_reasons', return_value=[]), \
             patch.object(state, 'save_state'), patch.object(state, 'clear_lease'), \
             patch.object(state, '_consent_replay', return_value=[]):
            delivery = state.action_deliver(self.root, args)
        self.assertEqual(delivery['stage'], 'delivered')
        self.assertFalse(delivery['delivery']['verification']['browser']['available'])
        self.assertEqual(delivery['delivery']['verification']['counts']['not_run'], 0)

    def test_failed_and_stale_static_results_cannot_support_pass(self):
        (self.root / 'index.html').write_text('<img src="missing.png">')
        failed = self.static_result()
        self.assertEqual(failed['status'], 'failed')
        failed_matrix = self.matrix(failed['check_id'])
        self.assertEqual(failed_matrix['status'], 'failed')
        self.assertIn('not a passing static', str(failed_matrix['evidence_failures']))

        (self.root / 'index.html').write_text('<p>Ready</p>')
        passed = self.static_result()
        (self.root / 'index.html').write_text('<p>Changed</p>')
        stale_matrix = self.matrix(passed['check_id'])
        self.assertEqual(stale_matrix['status'], 'failed')
        self.assertIn('different source', str(stale_matrix['evidence_failures']))

    def test_delivery_rechecks_referenced_static_result(self):
        result = self.static_result()
        matrix = self.matrix(result['check_id'])
        stored = self.root / result['artifact']
        data = json.loads(stored.read_text())
        data['status'] = 'failed'
        stored.write_text(json.dumps(data))
        problems = state.verify_delivery_evidence(self.root, matrix)
        self.assertTrue(any('check evidence' in problem for problem in problems), problems)

    def test_existing_command_evidence_remains_supported(self):
        result = check.finalize(self.root, check.run_check(self.root, [sys.executable, '-c', 'pass'], 5))
        payload = {
            'profile': 'targeted', 'profile_reason': 'Existing command evidence',
            'browser': {'available': False, 'limitation': 'Command-only regression fixture'},
            'items': [
                {'id': 'build', 'axis': 'static_build', 'status': 'passed', 'blocking': True,
                 'evidence': {'kind': 'command', 'summary': 'Build passed', 'commands': [result['check_id']]}},
                {'id': 'core', 'axis': 'core_task', 'status': 'passed', 'blocking': True,
                 'evidence': {'kind': 'artifact', 'summary': 'Page output', 'paths': ['index.html']}},
            ],
        }
        self.assertEqual(check.matrix_check(self.root, payload)['status'], 'passed')


class BrowserCapabilityMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / '.site').mkdir()
        (self.root / 'evidence.txt').write_text('verified')

    def item(self, identifier, axis, status='passed', blocking=True):
        evidence = (
            {'kind': 'artifact', 'summary': identifier, 'paths': ['evidence.txt']}
            if status == 'passed'
            else {'kind': 'declared', 'summary': 'No real browser is available'}
        )
        return {
            'id': identifier,
            'axis': axis,
            'status': status,
            'blocking': blocking,
            'evidence': evidence,
        }

    def full_items(self, browser_available):
        items = [
            self.item('static', 'static_build'),
            self.item('core', 'core_task'),
        ]
        for axis in ('visual_desktop', 'visual_mobile', 'reopen'):
            items.append(self.item(
                axis,
                axis,
                status='passed' if browser_available else 'not_run',
                blocking=browser_available,
            ))
        return items

    def test_full_profile_requires_explicit_browser_capability(self):
        payload = {
            'profile': 'full',
            'profile_reason': 'New site acceptance',
            'items': self.full_items(browser_available=False),
        }
        with self.assertRaisesRegex(ValueError, 'browser.available'):
            check.matrix_check(self.root, payload)

    def test_full_profile_can_pass_without_browser_when_browser_axes_are_disclosed(self):
        payload = {
            'profile': 'full',
            'profile_reason': 'New static site; browser automation is unavailable',
            'browser': {'available': False, 'limitation': 'Host has no controllable browser'},
            'items': self.full_items(browser_available=False),
        }
        result = check.matrix_check(self.root, payload)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['counts']['not_run'], 3)
        self.assertFalse(result['browser']['available'])

    def test_full_profile_without_browser_can_supply_delivery_evidence(self):
        payload = {
            'profile': 'full',
            'profile_reason': 'Static site with browser limitations disclosed',
            'browser': {'available': False, 'limitation': 'Host has no controllable browser'},
            'items': self.full_items(browser_available=False),
        }
        matrix = check.finalize(self.root, check.matrix_check(self.root, payload))
        current_state = {'stage': 'verifying', 'visual_required': False, 'revision': 1}
        args = SimpleNamespace(check=matrix['check_id'], expect_revision=None)
        with patch.object(state, 'load_state', return_value=current_state), \
             patch.object(state, 'require_lease'), patch.object(state, 'gate_reasons', return_value=[]), \
             patch.object(state, 'save_state'), patch.object(state, 'clear_lease'), \
             patch.object(state, '_consent_replay', return_value=[]):
            delivery = state.action_deliver(self.root, args)
        self.assertEqual(delivery['stage'], 'delivered')
        self.assertFalse(delivery['delivery']['verification']['browser']['available'])
        self.assertEqual(delivery['delivery']['verification']['counts']['not_run'], 3)

    def test_available_browser_keeps_all_full_axes_blocking(self):
        items = self.full_items(browser_available=True)
        items[-1]['blocking'] = False
        payload = {
            'profile': 'full',
            'profile_reason': 'New site with browser automation',
            'browser': {'available': True, 'provider': 'host-browser'},
            'items': items,
        }
        with self.assertRaisesRegex(ValueError, 'missing required blocking axes: reopen'):
            check.matrix_check(self.root, payload)

    def test_missing_browser_does_not_excuse_unverified_core_task(self):
        items = self.full_items(browser_available=False)
        items[1] = self.item('core', 'core_task', status='not_run', blocking=True)
        payload = {
            'profile': 'full',
            'profile_reason': 'Interactive task cannot be verified without a browser',
            'browser': {'available': False, 'limitation': 'Host has no controllable browser'},
            'items': items,
        }
        result = check.matrix_check(self.root, payload)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['blocking_not_passed'], ['core'])

    def test_unavailable_browser_rejects_blocking_browser_axis_claims(self):
        items = self.full_items(browser_available=False)
        items.append(self.item('screenshot-claim', 'visual_desktop', status='passed', blocking=True))
        payload = {
            'profile': 'full',
            'profile_reason': 'Screenshot-only review cannot prove a browser axis',
            'browser': {'available': False, 'limitation': 'Only a screenshot was supplied'},
            'items': items,
        }
        with self.assertRaisesRegex(ValueError, 'browser-dependent axes must be non-blocking'):
            check.matrix_check(self.root, payload)


if __name__ == '__main__':
    unittest.main()
