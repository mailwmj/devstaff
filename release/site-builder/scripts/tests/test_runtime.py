"""Packaged new-schema smoke tests: no repository-root files required."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
from site_runtime.common import metadata_dir,Problem
from site_runtime.preview import register

class InstalledRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        spec=importlib.util.spec_from_file_location('installed_runtime_state',SCRIPTS/'state.py');self.state=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.state)
    def tearDown(self):self.tmp.cleanup()
    def brief(self,**overrides):
        data={'facts':{'audience':{'value':'single user','source':'user'}},
              'assumptions':[],'exclusions':['no cloud sync']}
        data.update(overrides)
        path=self.root/'.site/brief.md';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('# Brief\n\n```brief\n'+json.dumps(data)+'\n```\n',encoding='utf-8')
        return path
    def test_new_state_stops_for_the_brief_questions(self):
        result=self.state.init(self.root,'guided');self.assertEqual(result['schema_revision'],3)
        self.assertEqual(result['user_gate'],'brief_questions');self.assertTrue(result['action']['needs_user'])
        self.assertIn('discover',result['blocked_actions'])
    def test_new_state_requires_assessment_after_the_brief(self):
        self.state.init(self.root,'guided');self.brief()
        preflight=self.state.preflight_state(self.state.read_state(self.root),self.root)
        self.assertIn('discover',preflight['allowed_actions'])
        with self.assertRaises(self.state.RuntimeProblem) as caught:
            self.state.decide(self.root,'task','direction','yes',[],[])
        self.assertEqual(caught.exception.code,'STRUCTURE_DECISION_REQUIRED')
    def test_decide_requires_the_recorded_brief(self):
        self.state.init(self.root,'guided');self.state.discover(self.root,'single','one task',[],[])
        with self.assertRaises(self.state.RuntimeProblem) as caught:
            self.state.decide(self.root,'task','direction','yes',[],[])
        self.assertEqual(caught.exception.code,'BRIEF_REQUIRED')
    def test_same_words_can_confirm_distinct_objects(self):
        self.state.init(self.root,'guided');self.brief()
        self.state.discover(self.root,'choice','real alternatives',[],['A','B']);self.state.select_structure(self.root,'A','yes')
        self.assertEqual(self.state.decide(self.root,'task','direction','yes',[],[])['stage'],'decided')
    def test_conflicting_metadata_fails(self):
        (self.root/'.site').mkdir();(self.root/'.v3').mkdir()
        with self.assertRaises(Problem):metadata_dir(self.root)
    def test_preview_does_not_claim_user_access(self):
        (self.root/'preview.html').write_text('fixture');result=register(self.root,'preview.html');self.assertEqual(result['user_access'],'unknown')
    def test_old_state_migration_has_backup(self):
        self.state.init(self.root,'guided',schema_revision=2);result=self.state.migrate_state(self.root)
        self.assertTrue(Path(result['migration_backup']).is_file());self.assertEqual(result['schema_revision'],3)
        self.assertTrue((self.root/'.site/brief.md').is_file())
if __name__=='__main__':unittest.main()
