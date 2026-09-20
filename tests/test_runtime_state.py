"""Exercise new state schema and immutable report consumption using real files."""
import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

state=module('state_v12','release/site-builder/scripts/state.py')
check=module('check_v12','release/site-check/scripts/check.py')
design=module('design_v12','release/site-design/scripts/design.py')

class NewStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);state.init(self.root,'guided')
    def tearDown(self):self.tmp.cleanup()
    def brief(self,**overrides):
        data={'facts':{'audience':{'value':'single user','source':'user'},
                       'main_task':{'value':'save an item','source':'user'}},
              'assumptions':[],'exclusions':['no cloud sync']}
        data.update(overrides)
        path=self.root/'.site/brief.md';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('# Brief\n\n```brief\n'+json.dumps(data)+'\n```\n',encoding='utf-8')
        return path
    def contract(self):
        d={'schema_version':2,'task':'save an item','work_type':'new-surface','structure_mode':'single','pages':['PG-01'],
           'targets':[{'id':'VA-01','target':'PG-01','standard':'save and reload one item','axis':'core_task','blocking':True,'refs':['PG-01']}]}
        p=state.contract_path(self.root);p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# Task\n```site-contract\n'+json.dumps(d)+'\n```\n')
        (self.root/'index.html').write_text('<h1>Save item</h1>')
    def assess(self):
        """Schema 3 confirms a direction only after the user picks a candidate."""
        state.discover(self.root,'choice','two candidate structures',[],['工作台A','工作台B'])
        return state.select_structure(self.root,'工作台A','use workspace A')
    def build(self):
        self.assess()
        self.brief()
        state.decide(self.root,'save an item','simple workspace','yes',[],[])
        self.contract();p=self.root/'.site/prebuild.json';p.write_text(json.dumps(design.check_contract(self.root,'prebuild')))
        state.start(self.root,contract_report=p)
    def report(self,**overrides):
        plan=check.plan(self.root)
        data={'project_root':str(self.root),'mode':plan['mode'],'overall':'verified','independent':False,
              'contract_sha256':plan['contract_sha256'],'source_sha256':plan['source_sha256'],'round_id':plan.get('round_id'),
              'axes':{a:{'status':'verified','observed':'test fixture '+a} for a in plan['required_axes']},'evidence':['original evidence'],'limitations':[]}
        data.update(overrides);p=self.root/'.site/report.json';p.write_text(json.dumps(data));return p
    def test_default_schema_and_action_contract(self):
        p=state.preflight_state(state.read_state(self.root),self.root);self.assertEqual(p['schema_revision'],3)
        self.assertIn('decide',p['blocked_actions']);self.assertIn('discover',p['blocked_actions'])
        self.assertEqual(p['action']['id'],p['next_action']);self.assertIn('recovery',p['action'])
        self.assertEqual(p['user_gate'],'brief_questions');self.assertTrue(p['action']['needs_user'])
        self.brief()
        after=state.preflight_state(state.read_state(self.root),self.root)
        self.assertIsNone(after['user_gate']);self.assertIn('discover',after['allowed_actions'])
    def test_preflight_stops_for_the_brief_questions(self):
        p=state.preflight_state(state.read_state(self.root),self.root)
        self.assertEqual(p['user_gate'],'brief_questions')
        self.assertEqual(p['action']['owner'],'site-brief')
        self.assertEqual(p['action']['missing_inputs'],['.site/brief.md'])
        self.assertIn('brief_record',p['missing'])
        self.assertIn('implementation_plan',p['action']['forbidden_outputs'])
    def test_decide_refuses_without_the_recorded_brief(self):
        state.discover(self.root,'choice','two candidates',[],['A','B'])
        with self.assertRaises(state.RuntimeProblem) as caught:
            state.decide(self.root,'task','direction','yes',[],[])
        self.assertEqual(caught.exception.code,'BRIEF_REQUIRED')
        self.assertEqual(state.read_state(self.root)['stage'],'discovering')
    def test_schema_3_refuses_a_single_structure_assessment(self):
        before=state.state_path(self.root).read_bytes()
        with self.assertRaises(state.RuntimeProblem) as caught:
            state.discover(self.root,'single','no disagreement',[],[])
        self.assertEqual(caught.exception.code,'STRUCTURE_CHOICE_REQUIRED')
        self.assertEqual(before,state.state_path(self.root).read_bytes())
    def test_schema_3_single_state_cannot_be_confirmed(self):
        self.brief()
        payload=state.read_state(self.root)
        payload['discovery']['structure'].update(mode='single',reason='hand edited',selected=None)
        state.write_state(self.root,payload)
        p=state.preflight_state(state.read_state(self.root),self.root)
        self.assertIn('structure_assessment',p['missing'])
        self.assertNotIn('decide',p['allowed_actions'])
    def test_assumed_fact_must_record_that_it_was_asked(self):
        self.brief(facts={'brand':{'value':'placeholder','source':'assumed'}},
                   assumptions=['brand is a placeholder'])
        state.discover(self.root,'choice','two candidates',[],['A','B'])
        with self.assertRaises(state.RuntimeProblem) as caught:
            state.decide(self.root,'task','direction','yes',[],[])
        self.assertEqual(caught.exception.code,'BRIEF_REQUIRED')
    def test_confirmation_binds_the_brief_hash(self):
        self.brief();self.assess()
        state.decide(self.root,'task','direction','yes',[],[])
        confirmation=state.read_state(self.root)['decision']['confirmation']
        self.assertEqual(confirmation['brief_sha256'],
                         hashlib.sha256((self.root/'.site/brief.md').read_bytes()).hexdigest())
    def test_legacy_schema2_keeps_its_old_gate(self):
        legacy=Path(self.tmp.name)/'legacy';legacy.mkdir();state.init(legacy,'guided',schema_revision=2)
        p=state.preflight_state(state.read_state(legacy),legacy)
        self.assertIsNone(p['user_gate'])
        self.assertEqual(state.decide(legacy,'task','direction','yes',[],[])['stage'],'decided')
    def test_migration_seeds_a_marked_brief(self):
        legacy=Path(self.tmp.name)/'migrated';legacy.mkdir();state.init(legacy,'guided',schema_revision=2)
        state.decide(legacy,'task','direction','yes',[],[])
        result=state.migrate_state(legacy)
        self.assertIn('migration_brief',result)
        self.assertEqual(state._brief_block(legacy)['migrated_from'],'schema_revision_2')
        state.revise(legacy,'scope','new scope');state.discover(legacy,'choice','two workspaces',[],['A','B'])
        state.select_structure(legacy,'A','use A')
        self.assertEqual(state.decide(legacy,'task2','direction2','yes2',[],[])['stage'],'decided')
    def test_cli_reports_brief_required_as_json_error(self):
        p=subprocess.run([sys.executable,str(ROOT/'release/site-builder/scripts/state.py'),'decide',str(self.root),
                          '--task','t','--direction','d','--quote','q'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        payload=json.loads(p.stdout);self.assertEqual(payload['code'],'BRIEF_REQUIRED');self.assertIn('recovery',payload)
    def test_choice_requires_distinct_candidates_and_selection(self):
        self.brief()
        for candidates in ([],['a'],['a','a']):
            before=state.state_path(self.root).read_bytes()
            with self.assertRaises(ValueError):state.discover(self.root,'choice','different tasks',[],candidates)
            self.assertEqual(before,state.state_path(self.root).read_bytes())
        state.discover(self.root,'choice','different tasks',[],['a','b'])
        with self.assertRaises(ValueError):state.decide(self.root,'task','direction','yes',[],[])
        self.assertIn('select-structure',state.preflight_state(state.read_state(self.root),self.root)['allowed_actions'])
        state.select_structure(self.root,'a','yes')
        self.assertEqual(state.decide(self.root,'task','direction','yes',[],[])['stage'],'decided')
    def test_automatic_check_no_fake_user_quote(self):
        self.build();p=state.begin_check(self.root)
        self.assertEqual(p['verification']['phase'],'checking');self.assertIsNone(p['verification']['review_quote']);self.assertTrue(p['verification']['round_id'])
        self.assertEqual(state.verify(self.root,self.report())['stage'],'delivered')
    def test_new_report_requires_round_identity(self):
        self.build();state.begin_check(self.root)
        with self.assertRaises(ValueError):state.verify(self.root,self.report(round_id='old-round'))
    def test_three_local_revisions_preserve_direction(self):
        self.build();state.begin_check(self.root);state.verify(self.root,self.report())
        original=state.read_state(self.root)['decision']
        for n in range(3):
            p=state.revise(self.root,'local','button copy only')
            self.assertEqual(p['stage'],'building');self.assertEqual(state.read_state(self.root)['decision'],original)
            (self.root/'index.html').write_text('<h1>item '+str(n)+'</h1>');state.begin_check(self.root);state.verify(self.root,self.report())
        self.assertEqual(state.read_state(self.root)['revision'],3)
    def test_feature_preserves_direction_but_requires_scope_confirmation(self):
        self.build();p=state.revise(self.root,'feature','add a detail page')
        self.assertEqual(p['stage'],'discovering');self.assertEqual(p['decision']['direction'],'simple workspace');self.assertFalse(p['decision']['confirmed'])
    def test_permissions_escalate_even_without_public_scope(self):
        self.build();p=state.revise(self.root,'feature','shared records',risks=['permissions'])
        self.assertEqual(p['mode'],'strict')
    def test_report_read_once_cannot_swap_evidence(self):
        self.build();state.begin_check(self.root);p=self.report();original=state._check_verdict
        def swap(root,payload):
            verdict=original(root,payload)
            changed=json.loads(p.read_text());changed['evidence']=['replacement lie'];p.write_text(json.dumps(changed));return verdict
        with patch.object(state,'_check_verdict',swap):result=state.verify(self.root,p)
        self.assertEqual(result['verification']['evidence'],['original evidence'])
    def test_state_change_while_checking_rejected(self):
        self.build();state.begin_check(self.root);p=self.report();original=state._check_verdict
        def swap(root,payload):
            v=original(root,payload);s=state.read_state(root);s['mode']='strict';state.write_state(root,s);return v
        with patch.object(state,'_check_verdict',swap):
            with self.assertRaises(ValueError):state.verify(self.root,p)
    def test_core_limited_cannot_be_usable_delivery(self):
        self.build();state.begin_check(self.root);p=self.report(overall='limited',limitations=['core not fully run']);d=json.loads(p.read_text());d['axes']['core_task']['status']='limited';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):state.verify(self.root,p)
    def test_public_scope_not_automatically_financial_risk(self):
        p=state.set_policy(self.root,'public',[])
        self.assertEqual(p['mode'],'guided');self.assertEqual(p['delivery']['scope'],'public')
    def test_explicit_legacy_migration_preserves_decision(self):
        self.build();s=state.read_state(self.root);s['schema_revision']=2;state.write_state(self.root,s)
        p=state.migrate_state(self.root);self.assertEqual(p['schema_revision'],3);self.assertTrue(Path(p['migration_backup']).is_file());self.assertEqual(p['decision']['direction'],'simple workspace')
    def test_cli_unknown_is_json_error(self):
        p=subprocess.run([sys.executable,str(ROOT/'release/site-builder/scripts/state.py'),'not-a-command'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertIn('recovery',json.loads(p.stdout))
    def test_validator_exit_codes(self):
        self.build();state.begin_check(self.root);p=self.report();command=[sys.executable,str(ROOT/'release/site-check/scripts/check.py'),'validate-report',str(self.root),str(p)]
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
        p.write_text('{}');self.assertEqual(subprocess.run(command,capture_output=True).returncode,1)
        result=subprocess.run([sys.executable,str(ROOT/'release/site-check/scripts/check.py'),'no'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertIn('code',json.loads(result.stdout))

if __name__=='__main__':unittest.main()
