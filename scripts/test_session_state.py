"""Regression checks for derived, non-authoritative session recovery hints."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site-brief' / 'scripts'))
spec = importlib.util.spec_from_file_location('session_gate', ROOT / 'site-brief' / 'scripts' / 'state.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class SessionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.metadata = self.root / '.site'
        self.metadata.mkdir()
        (self.root / 'index.html').write_text('<title>Example</title>')
        self.state = {
            'schema_version': 2, 'project_id': 'example', 'revision': 1,
            'stage': 'concept_review', 'next_action': 'Ask for the first slice',
            'concept_confirmed': False,
        }
        gate.write_json(self.metadata / 'state.json', self.state)

    def show(self):
        return gate.action_show(self.root, None)

    def test_successful_transition_writes_resume_hint_not_consent(self):
        self.state['next_action'] = 'Confirm the selected direction'
        self.state['concept_consent'] = {'quote': 'Private user wording'}
        gate.save_state(self.root, self.state, 'confirm-concept')
        snapshot = json.loads((self.metadata / 'session-state.json').read_text())
        self.assertEqual(snapshot['revision'], 2)
        self.assertEqual(snapshot['project_id'], 'example')
        self.assertEqual(snapshot['project_root'], str(self.root))
        self.assertEqual(snapshot['last_action'], 'confirm-concept')
        self.assertEqual(snapshot['next_action'], self.state['next_action'])
        self.assertNotIn('Private user wording', json.dumps(snapshot))
        self.assertNotIn('concept_confirmed', snapshot)
        self.assertEqual(self.show()['session_state']['status'], 'current')

    def test_show_is_read_only_with_missing_or_damaged_snapshot(self):
        before = (self.metadata / 'state.json').read_bytes()
        self.assertEqual(self.show()['session_state']['status'], 'missing')
        self.assertFalse((self.metadata / 'session-state.json').exists())
        (self.metadata / 'session-state.json').write_text('{broken')
        result = self.show()
        self.assertEqual(result['session_state']['status'], 'invalid')
        self.assertEqual(result['stage'], 'concept_review')
        self.assertEqual((self.metadata / 'session-state.json').read_text(), '{broken')
        self.assertEqual((self.metadata / 'state.json').read_bytes(), before)

    def test_forged_or_stale_hint_cannot_override_actual_gates(self):
        gate.save_state(self.root, self.state, 'claim')
        path = self.metadata / 'session-state.json'
        for field, value in [('stage', 'delivered'), ('revision', 0), ('project_id', 'other')]:
            snapshot = json.loads(path.read_text())
            snapshot[field] = value
            gate.write_json(path, snapshot)
            result = self.show()
            self.assertEqual(result['session_state']['status'], 'stale')
            self.assertEqual(result['stage'], 'concept_review')
            self.assertFalse(result['state']['concept_confirmed'])
            gate.save_state(self.root, self.state, 'claim')

    def test_snapshot_write_failure_does_not_invalidate_state_transition(self):
        original = gate.write_json

        def write(path, data):
            if path.name == 'session-state.json':
                raise PermissionError('read-only resume hint')
            original(path, data)

        with patch.object(gate, 'write_json', side_effect=write), patch.object(sys, 'stderr') as stderr:
            gate.save_state(self.root, self.state, 'claim')
            self.assertTrue(stderr.write.called)
        self.assertEqual(gate.load_state(self.root)['revision'], 2)
        self.assertEqual(gate.load_state(self.root)['last_action'], 'claim')

    def test_revision_conflict_does_not_write_state_or_hint(self):
        before = (self.metadata / 'state.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Revision conflict'):
            gate.save_state(self.root, self.state, 'confirm-concept', expect_revision=0)
        self.assertEqual((self.metadata / 'state.json').read_bytes(), before)
        self.assertFalse((self.metadata / 'session-state.json').exists())

    def test_invalid_or_missing_authoritative_state_never_uses_hint(self):
        gate.save_state(self.root, self.state, 'claim')
        (self.metadata / 'state.json').write_text('{broken')
        with self.assertRaisesRegex(ValueError, 'Damaged project state'):
            self.show()
        (self.metadata / 'state.json').unlink()
        with self.assertRaisesRegex(ValueError, 'No .site/state.json'):
            self.show()

    def test_hint_is_excluded_from_both_freeze_fingerprints(self):
        spec = importlib.util.spec_from_file_location('session_check', ROOT / 'site-check' / 'scripts' / 'check.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        before = gate.fingerprint(self.root)
        gate.save_state(self.root, self.state, 'claim')
        self.assertEqual(gate.fingerprint(self.root), before)
        self.assertEqual(checker.fingerprint(self.root), before)

    def test_symlinked_snapshot_is_not_read_or_replaced(self):
        target = self.root / 'unrelated.json'
        target.write_text('{"preserve": true}')
        (self.metadata / 'session-state.json').symlink_to(target)
        with patch.object(sys, 'stderr'):
            gate.save_state(self.root, self.state, 'claim')
        self.assertTrue((self.metadata / 'session-state.json').is_symlink())
        self.assertEqual(target.read_text(), '{"preserve": true}')
        self.assertEqual(self.show()['session_state']['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
