import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from domain import minor_units,import_preview
from store import Store,Conflict


class DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'site.db')
    def tearDown(self): self.tmp.cleanup()
    def test_decimal_minor_units(self):
        self.assertEqual(minor_units('0.29'),29)
        for value in ('NaN','Infinity','1.001','-1',True):
            with self.assertRaises(ValueError): minor_units(value)
    def test_persist_reopen(self):
        self.store.create('a',{'title':'course','amount':'1.20'},'first')
        self.assertEqual(Store(self.store.path).list('a')[0]['amount_minor'],120)
    def test_idempotency(self):
        a=self.store.create('a',{'title':'course'},'key'); b=self.store.create('a',{'title':'course'},'key')
        self.assertEqual(a['id'],b['id'])
        with self.assertRaises(Conflict): self.store.create('a',{'title':'other'},'key')
    def test_update_amount(self):
        r=self.store.create('a',{'title':'course','amount':'1.20'},'k')
        self.assertEqual(self.store.update('a',r['id'],{'amount':'2.30'})['amount_minor'],230)
    def test_owner_boundary(self):
        r=self.store.create('a',{'title':'private'},'key')
        self.assertEqual(self.store.list('b'),[])
        self.assertIsNone(self.store.update('b',r['id'],{'status':'done'})); self.assertFalse(self.store.delete('b',r['id']))
        self.assertEqual(len(self.store.list('a')),1)
    def test_export_import_roundtrip(self):
        self.store.create('a',{'title':'course','amount':'12.30','date':'2026-09-19'},'one')
        text=json.dumps(self.store.export('a')); self.assertEqual(self.store.import_data('b',text,'json')['written'],1)
        self.assertEqual(self.store.list('b')[0]['amount_minor'],1230); self.assertEqual(self.store.import_data('b',text,'json')['skipped'],1)
    def test_bad_csv_no_partial_write(self):
        text='Name,Price\ncourse,12.30\nbroken,NaN\n'; mapping={'title':'Name','amount':'Price'}
        self.assertFalse(import_preview(text,'csv',mapping)['valid'])
        with self.assertRaises(ValueError): self.store.import_data('a',text,'csv',mapping)
        self.assertEqual(self.store.list('a'),[])
    def test_duplicate_import_rolls_back(self):
        data={'schema_version':1,'records':[{'external_id':'old','title':'exists'}]}
        self.store.import_data('a',json.dumps(data),'json'); data['records'].insert(0,{'external_id':'new','title':'new'})
        with self.assertRaises(Conflict): self.store.import_data('a',json.dumps(data),'json',strategy='reject')
        self.assertEqual(len(self.store.list('a')),1)
    def test_backup(self):
        self.store.create('a',{'title':'one'},'one'); dest=Path(self.tmp.name)/'backup.db'; self.store.backup(dest)
        self.assertEqual(Store(dest).list('a')[0]['title'],'one')
        with self.assertRaises(ValueError): self.store.backup(dest)
    def test_sessions(self):
        self.store.add_user('a','a-long-fixture-password'); self.assertIsNone(self.store.login('a','wrong'))
        s=self.store.login('a','a-long-fixture-password'); self.assertEqual(self.store.session(s['token'])['owner'],'a')
        self.store.logout(s['token']); self.assertIsNone(self.store.session(s['token']))
if __name__=='__main__': unittest.main()
