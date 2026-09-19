import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'release/site-builder/scripts'))
from site_runtime import contract
from site_runtime.common import Problem,metadata_dir,project_file
from site_runtime.preview import register,current
from site_runtime.source import scan,archive_manifest
from site_runtime.delivery import plan,authorize,execute,LocalDirectoryProvider


class RuntimeCoreTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def spec(self):return {'schema_version':2,'task':'save one item','work_type':'new-surface','structure_mode':'single','pages':['PG-01'],'targets':[{'id':'VA-01','target':'PG-01/default','standard':'save and refresh','axis':'core_task','blocking':True,'refs':['PG-01']}]}
    def text(self,d):return '# Title\n```site-contract\n'+json.dumps(d)+'\n```\nProse\n'
    def test_heading_does_not_decide_scope(self):
        t=self.text(self.spec());self.assertEqual(contract.targets(contract.parse(t),t),contract.targets(contract.parse(t.replace('Title','Other')),t))
    def test_schema_references_ids_and_axes_rejected(self):
        for fn in (lambda d:d.update(schema_version=99),lambda d:d['targets'].append(d['targets'][0].copy()),lambda d:d['targets'][0].update(refs=['PG-99']),lambda d:d['targets'][0].update(axis='madeup'),lambda d:d['targets'][0].update(blocking='true')):
            d=self.spec();fn(d)
            with self.assertRaises(Problem):contract.parse(self.text(d))
    def test_multiple_contract_blocks_rejected(self):
        with self.assertRaises(Problem):contract.parse(self.text(self.spec())*2)
    def test_multiple_metadata_directories_rejected(self):
        (self.root/'.site').mkdir();(self.root/'.v3').mkdir()
        with self.assertRaises(Problem):metadata_dir(self.root)
    def test_preview_not_implicitly_reachable_and_versioned(self):
        (self.root/'a.html').write_text('v1');p=register(self.root,'a.html');self.assertEqual(p['user_access'],'unknown');self.assertTrue(current(self.root,p))
        (self.root/'a.html').write_text('v2');self.assertFalse(current(self.root,p))
    def test_public_preview_requires_quote(self):
        (self.root/'a.html').write_text('v1')
        with self.assertRaises(Problem):register(self.root,'a.html',audience='public')
    def test_screenshot_not_interactive(self):
        (self.root/'a.png').write_bytes(b'fixture');self.assertFalse(register(self.root,'a.png',kind='screenshot')['interactive'])
    def test_policy_readonly_database(self):
        (self.root/'.site').mkdir();(self.root/'.site/source-policy.json').write_text(json.dumps({'schema_version':1,'include':['catalog.db'],'exclude':[]}))
        (self.root/'catalog.db').write_bytes(b'1');(self.root/'runtime.db').write_bytes(b'1')
        m,e=scan(self.root,lambda p,t:'state_file' if p[-1].endswith('.db') else None)
        self.assertIn('catalog.db',m);self.assertIn('runtime.db',e);self.assertIn('.site/source-policy.json',m)
    def test_dependency_pruned_before_read(self):
        (self.root/'node_modules/deep').mkdir(parents=True);(self.root/'node_modules/deep/link').symlink_to('/outside');(self.root/'app.js').write_text('ok')
        m,_=scan(self.root,lambda p,t:None);self.assertEqual(list(m),['app.js'])
    def test_symlink_source_rejected(self):
        (self.root/'source').symlink_to('/etc/hosts')
        with self.assertRaises(Problem):scan(self.root,lambda p,t:None)
        with self.assertRaises(Problem):project_file(self.root,'source')
    def test_archive_policy_parity(self):
        entries={'app.js':b'x','catalog.db':b'1','runtime.db':b'2','.site/source-policy.json':json.dumps({'schema_version':1,'include':['catalog.db'],'exclude':[]}).encode()}
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w') as tf:
            for n,b in entries.items():
                info=tarfile.TarInfo(n);info.size=len(b);tf.addfile(info,io.BytesIO(b));f=self.root/n;f.parent.mkdir(exist_ok=True,parents=True);f.write_bytes(b)
        rule=lambda p,t:'state_file' if p[-1].endswith('.db') else None
        self.assertEqual(scan(self.root,rule)[0],archive_manifest(buf.getvalue(),'',rule))


class DeliveryTests(RuntimeCoreTests):
    def release_plan(self,scope='preview'):
        artifact=self.root/'artifact';artifact.mkdir(exist_ok=True);(artifact/'index.html').write_text('one')
        return plan(artifact,self.root/'releases',scope=scope,owner='fixture owner',cost='no hosting cost; local disk only')
    def test_no_authorization_no_copy(self):
        p=self.release_plan()
        with self.assertRaises(Problem):execute(p)
        self.assertFalse((self.root/'releases').exists())
    def test_local_copy_not_public(self):
        p=self.release_plan();r=execute(authorize(p,p['plan_sha256'],'Create this local release'))
        self.assertEqual(r['status'],'local_copy_verified');self.assertFalse(r['public_deployed'])
    def test_public_cannot_use_local_copy(self):
        p=self.release_plan('public')
        with self.assertRaises(Problem):execute(authorize(p,p['plan_sha256'],'Publish this version'))
    def test_changed_artifact_invalidates_authorization(self):
        p=self.release_plan();a=authorize(p,p['plan_sha256'],'copy');(Path(p['artifact'])/'index.html').write_text('two')
        with self.assertRaises(Problem):execute(a)
    def test_smoke_failure_rolls_back_prior(self):
        p=self.release_plan();execute(authorize(p,p['plan_sha256'],'copy'))
        prior=(self.root/'releases/current.json').read_bytes();(Path(p['artifact'])/'index.html').write_text('two')
        p=plan(Path(p['artifact']),self.root/'releases',scope='preview',owner='fixture',cost='local only')
        class Broken(LocalDirectoryProvider):
            def smoke(self,receipt):return {'ok':False}
        result=execute(authorize(p,p['plan_sha256'],'copy'),Broken(p['destination']))
        self.assertEqual(result['status'],'blocked');self.assertEqual((self.root/'releases/current.json').read_bytes(),prior)

if __name__=='__main__':unittest.main()
