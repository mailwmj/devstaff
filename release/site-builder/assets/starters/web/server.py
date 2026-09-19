#!/usr/bin/env python3
"""Loopback development adapter, not an Internet production server."""
import argparse
import hmac
import json
import mimetypes
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote
from domain import import_preview
from store import Store,Conflict


def application(root,data_path=None):
    root=Path(root).resolve(); config=json.loads((root/'site.json').read_text())
    profile=config['profile']; public=root/'public'
    store=None if profile=='content' else Store(data_path or root/'data/site.sqlite')
    failures={}; rate_lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        server_version='SiteLocal/1.2'
        def log_message(self,fmt,*args): pass
        def send(self,status,value=None,content=None,content_type='application/json; charset=utf-8',cookie=None):
            body=json.dumps(value,ensure_ascii=False).encode() if content is None else content
            self.send_response(status)
            for key,val in [('Content-Type',content_type),('Content-Length',str(len(body))),('Cache-Control','no-store'),
                            ('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),
                            ('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'self'; form-action 'self'")]: self.send_header(key,val)
            if cookie: self.send_header('Set-Cookie',cookie)
            self.end_headers(); self.wfile.write(body)
        def body(self):
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json': raise ValueError('JSON content type required')
            try: size=int(self.headers.get('Content-Length','0'))
            except ValueError as exc: raise ValueError('invalid content length') from exc
            if not 0<size<=2100000: raise ValueError('request body missing or too large')
            result=json.loads(self.rfile.read(size))
            if not isinstance(result,dict): raise ValueError('request body must be an object')
            return result
        def token(self):
            try:
                cookie=SimpleCookie(self.headers.get('Cookie','')); return cookie['site_session'].value if 'site_session' in cookie else ''
            except Exception: return ''
        def safe_host(self):
            parsed=urlsplit('http://'+self.headers.get('Host',''))
            return parsed.hostname in ('localhost','127.0.0.1','::1') and parsed.port==self.server.server_port
        def same_origin(self):
            origin=self.headers.get('Origin')
            return self.headers.get('X-Site-Client')=='1' and (not origin or origin=='http://'+self.headers.get('Host',''))
        def user(self,mutation=False):
            if profile=='content': self.send(404,{'error':'This content site has no data service.'}); return None
            session={'owner':'local','csrf':''} if profile=='personal' else store.session(self.token())
            if not session: self.send(401,{'error':'Sign in to use this workspace.'}); return None
            if mutation and (not self.same_origin() or (profile=='shared' and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']))):
                self.send(403,{'error':'Origin or CSRF token was not accepted.'}); return None
            return session
        def do_GET(self):
            try:
                if not self.safe_host(): return self.send(403,{'error':'Loopback Host required.'})
                route=urlsplit(self.path).path
                if route=='/api/health': return self.send(200,{'ok':True,'profile':profile,'environment':'local'})
                if route=='/api/session':
                    if profile=='content': return self.send(200,{'profile':profile})
                    session={'owner':'local','csrf':''} if profile=='personal' else store.session(self.token())
                    return self.send(200,{'profile':profile,'authenticated':bool(session),**(session or {})})
                if route.startswith('/api/'):
                    session=self.user()
                    if not session: return
                    if route=='/api/records': return self.send(200,{'records':store.list(session['owner'])})
                    if route=='/api/export': return self.send(200,store.export(session['owner']))
                    return self.send(404,{'error':'Not found'})
                relative=unquote(route).lstrip('/') or 'index.html'
                if any(p=='..' or p.startswith('.') for p in Path(relative).parts): return self.send(404,{'error':'Not found'})
                file=public
                for part in Path(relative).parts:
                    file/=part
                    if file.is_symlink(): return self.send(404,{'error':'Not found'})
                if not file.resolve().is_relative_to(public.resolve()) or not file.is_file(): return self.send(404,{'error':'Not found'})
                kind=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                return self.send(200,content=file.read_bytes(),content_type=kind+('; charset=utf-8' if kind.startswith('text/') or kind=='application/javascript' else ''))
            except (ValueError,OSError): self.send(400,{'error':'The requested resource could not be read.'})
        def mutate(self,method):
            try:
                if not self.safe_host(): return self.send(403,{'error':'Loopback Host required.'})
                route=urlsplit(self.path).path
                if profile=='shared' and route=='/api/login' and method=='POST':
                    if not self.same_origin(): return self.send(403,{'error':'Origin not accepted'})
                    key=self.client_address[0]
                    with rate_lock:
                        attempts=[t for t in failures.get(key,[]) if time.monotonic()-t<60]
                        if len(attempts)>=8: return self.send(429,{'error':'Too many sign-in attempts. Try again later.'})
                        failures[key]=attempts+[time.monotonic()]
                    data=self.body(); name,password=data.get('username',''),data.get('password','')
                    if not isinstance(name,str) or not isinstance(password,str) or len(name)>80 or len(password)>1024: raise ValueError('invalid sign-in fields')
                    session=store.login(name,password)
                    if not session: return self.send(401,{'error':'Username or password is incorrect.'})
                    with rate_lock: failures.pop(key,None)
                    token=session.pop('token')
                    return self.send(200,session,cookie='site_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
                session=self.user(mutation=True)
                if not session: return
                if route=='/api/logout' and method=='POST':
                    store.logout(self.token()); return self.send(200,{'ok':True},cookie='site_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                owner=session['owner']
                if route=='/api/records' and method=='POST':
                    data=self.body(); return self.send(201,{'record':store.create(owner,data,data.get('idempotency_key'))})
                if route.startswith('/api/records/'):
                    rid=route.rsplit('/',1)[-1]
                    if method=='DELETE':
                        done=store.delete(owner,rid); return self.send(200 if done else 404,{'deleted':done})
                    if method=='PATCH':
                        record=store.update(owner,rid,self.body()); return self.send(200 if record else 404,{'record':record})
                if route in ('/api/import-preview','/api/import') and method=='POST':
                    data=self.body(); args=(data.get('text',''),data.get('format','json'),data.get('mapping'))
                    if route.endswith('preview'): return self.send(200,import_preview(*args))
                    return self.send(200,store.import_data(owner,*args,strategy=data.get('strategy','skip')))
                return self.send(404,{'error':'Not found'})
            except Conflict as exc: self.send(409,{'error':str(exc)})
            except (ValueError,TypeError,KeyError): self.send(400,{'error':'Invalid input. No success is claimed; review the fields or import preview.'})
            except (sqlite3.Error,OSError): self.send(503,{'error':'The operation was not saved. Retry or export a backup.'})
        def do_POST(self): self.mutate('POST')
        def do_PATCH(self): self.mutate('PATCH')
        def do_DELETE(self): self.mutate('DELETE')
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).parent); parser.add_argument('--port',type=int,default=8000); parser.add_argument('--data-path',type=Path)
    args=parser.parse_args()
    if not 0<=args.port<=65535: parser.error('port out of range')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),application(args.root,args.data_path))
    print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'audience':'local','user_access':'unknown'}),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
