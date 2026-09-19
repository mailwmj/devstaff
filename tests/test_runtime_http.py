"""Actual local HTTP requests and server persistence; synthetic accounts only."""
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'release/site-builder/scripts'))
from scaffold import scaffold

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'app';scaffold(self.root,'shared','Fixture')
        sys.path.insert(0,str(self.root))
        for n in ('store','domain'):sys.modules.pop(n,None)
        spec=importlib.util.spec_from_file_location('fixture_server',self.root/'server.py');self.server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.server_module)
        self.store=self.server_module.Store(self.root/'data/site.sqlite');self.password='synthetic-long-password'
        self.store.add_user('alice',self.password);self.store.add_user('bob',self.password)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),self.server_module.application(self.root))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();sys.path.remove(str(self.root));self.tmp.cleanup()
    def request(self,path,method='GET',body=None,headers=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json','X-Site-Client':'1',**(headers or {})})
        try:result=urllib.request.urlopen(req,timeout=5)
        except urllib.error.HTTPError as e:result=e
        data=result.read();return result.status,json.loads(data) if result.headers.get('Content-Type','').startswith('application/json') else data,result.headers
    def login(self,name):
        status,data,headers=self.request('/api/login','POST',{'username':name,'password':self.password});self.assertEqual(status,200)
        return {'Cookie':headers['Set-Cookie'].split(';')[0],'X-CSRF-Token':data['csrf']}
    def test_anonymous_denied(self):self.assertEqual(self.request('/api/records')[0],401)
    def test_direct_cross_account_requests_denied(self):
        a=self.login('alice');b=self.login('bob');_,d,_=self.request('/api/records','POST',{'title':'private','idempotency_key':'one'},a)
        self.assertEqual(self.request('/api/records',headers=b)[1]['records'],[])
        self.assertEqual(self.request('/api/records/'+d['record']['id'],'PATCH',{'status':'done'},b)[0],404)
        self.assertEqual(self.request('/api/records/'+d['record']['id'],'DELETE',headers=b)[0],404)
    def test_csrf_wrong_origin_and_host_denied(self):
        a=self.login('alice')
        for changed in ({'X-CSRF-Token':'wrong'},{'Origin':'https://outside.invalid'},{'Host':'outside.invalid'}):
            self.assertEqual(self.request('/api/records','POST',{'title':'x','idempotency_key':'one'},{**a,**changed})[0],403)
    def test_idempotency_over_http_and_refresh(self):
        a=self.login('alice');data={'title':'one','amount':'0.29','idempotency_key':'key'}
        self.assertEqual(self.request('/api/records','POST',data,a)[0],201);self.assertEqual(self.request('/api/records','POST',data,a)[0],201)
        self.assertEqual(len(self.request('/api/records',headers=a)[1]['records']),1)
        self.assertEqual(self.store.list('alice')[0]['amount_minor'],29)
    def test_static_cannot_read_database(self):
        self.assertEqual(self.request('/data/site.sqlite')[0],404)
        self.assertEqual(self.request('/%2e%2e/site.json')[0],404)
    def test_invalid_import_does_not_write(self):
        a=self.login('alice');data={'format':'csv','text':'title,amount\ngood,1.00\nbad,NaN\n'}
        self.assertFalse(self.request('/api/import-preview','POST',data,a)[1]['valid']);self.assertEqual(self.request('/api/import','POST',data,a)[0],400);self.assertEqual(self.store.list('alice'),[])

if __name__=='__main__':unittest.main()
