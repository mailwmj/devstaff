#!/usr/bin/env python3
"""Generate one tested stdlib Web foundation with an explicit capability profile."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from site_runtime.common import JsonParser,Problem,error_result

PROFILES=('content','personal','shared')


def scaffold(destination,profile,title,source=None):
    destination=Path(destination).absolute()
    if profile not in PROFILES: raise Problem('UNKNOWN_PROFILE','unknown starter profile')
    if not isinstance(title,str) or not title.strip(): raise Problem('MISSING_TITLE','title cannot be empty')
    if destination.exists() or destination.is_symlink(): raise Problem('DESTINATION_EXISTS','refusing to overwrite an existing project','Use revise on existing projects, or choose a new directory.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    source=source or Path(__file__).resolve().parents[1]/'assets/starters/web'
    staging=Path(tempfile.mkdtemp(prefix='.site-scaffold-',dir=destination.parent))
    try:
        for item in Path(source).iterdir():
            if item.name=='__pycache__': continue
            if item.is_dir(): shutil.copytree(item,staging/item.name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            else: shutil.copy2(item,staging/item.name)
        config={'schema_version':1,'profile':profile,'stack':'python-stdlib-vanilla-web','runtime':'Python >=3.10','bind':'127.0.0.1',
                'public_deployment':'static_export' if profile=='content' else 'requires_production_adapter'}
        (staging/'site.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
        content={'title':title.strip(),'brand':title.strip(),'profile':profile,
                 'eyebrow':'\u4ece\u4e00\u4ef6\u5177\u4f53\u7684\u4e8b\u5f00\u59cb',
                 'description':'\u5148\u5b8c\u6210\u6838\u5fc3\u4efb\u52a1\uff0c\u518d\u6309\u5b9e\u9645\u9700\u8981\u8c03\u6574\u3002',
                 'sections':[{'title':'\u8bf4\u6e05\u4f60\u7684\u670d\u52a1','body':'\u8fd9\u662f\u5f85\u7f16\u8f91\u7684\u5185\u5bb9\u4f4d\u7f6e\uff0c\u8bf7\u6362\u6210\u771f\u5b9e\u4fe1\u606f\u3002'}],
                 'contact':'\u8bf7\u5728 public/content.json \u586b\u5199\u771f\u5b9e\u8054\u7cfb\u65b9\u5f0f\u3002',
                 'footer':'\u5f53\u524d\u4e3a\u672c\u5730\u7248\u672c\uff0c\u5c1a\u672a\u516c\u5f00\u53d1\u5e03\u3002'}
        (staging/'public/content.json').write_text(json.dumps(content,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if profile=='content':
            html=(staging/'public/index.html').read_text(encoding='utf-8')
            start=html.index('<section id="login-panel"'); end=html.index('</main>',start)
            (staging/'public/index.html').write_text(html[:start]+html[end:],encoding='utf-8')
            script="""'use strict';
fetch('content.json').then(r=>{if(!r.ok)throw new Error('Content unavailable');return r.json();}).then(c=>{
for(const id of ['title','brand'])document.getElementById(id).textContent=c[id]||c.title;
document.title=c.title;for(const id of ['eyebrow','description','contact'])document.getElementById(id).textContent=c[id]||'';
document.getElementById('footer-note').textContent=c.footer||'';document.getElementById('content-panel').hidden=false;
for(const s of c.sections||[]){const a=document.createElement('article');a.className='content-card';const h=document.createElement('h2');h.textContent=s.title;const p=document.createElement('p');p.textContent=s.body;a.append(h,p);document.getElementById('content-cards').append(a);}
}).catch(e=>{document.getElementById('message').textContent=String(e);document.getElementById('message').dataset.kind='error';});
"""
            (staging/'public/app.js').write_text(script,encoding='utf-8')
        (staging/'.gitignore').write_text('data/\ndist/\n__pycache__/\n*.pyc\n.env\n',encoding='utf-8')
        (staging/'README.md').write_text('# '+title.strip()+'\n\nProfile: `'+profile+'`. Runtime dependencies: Python standard library.\n\n'
            'Start: `python3 server.py --port 8000` (loopback only). Check: `python3 manage.py check`. Test: `python3 manage.py test`. Build: `python3 manage.py build --out dist`.\n\n'
            'Edit `public/content.json` for content and `public/styles.css` for semantic tokens. Do not regenerate a project to change one value.\n\n'
            'Personal/shared records live in `data/site.sqlite` on the server computer. Refresh or closing the browser does not erase records; changing devices does not automatically sync. Export JSON in the UI before clearing or moving data.\n\n'
            'Shared profile: create real accounts via `python3 manage.py add-user NAME`; passwords are prompted, not bundled. Server queries enforce per-owner access. This foundation is owner-private storage on a shared backend, not organization-wide collaboration.\n\n'
            'Backup: `python3 manage.py backup backups/site.sqlite`. Restore with the service stopped: retain the current database, validate a backup, replace the database and remove stale WAL/SHM files belonging to the stopped instance, then restart and verify counts. Never overwrite the only backup.\n\n'
            'Content profile can be hosted as static assets. Data profiles need an explicitly configured production server/TLS/provider adapter and security review before Internet exposure. The stdlib development server must not be exposed publicly. No hosting account or paid resource is created.\n',encoding='utf-8')
        os.replace(staging,destination)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return {'created':str(destination),'profile':profile,'entry':'python3 server.py --port 8000','content_entry':'public/content.json','public_deployed':False}


def main():
    try:
        p=JsonParser(description=__doc__); p.add_argument('destination',type=Path); p.add_argument('--profile',choices=PROFILES,required=True); p.add_argument('--title',required=True)
        args=p.parse_args(); print(json.dumps(scaffold(args.destination,args.profile,args.title),ensure_ascii=False,indent=2)); return 0
    except (ValueError,OSError) as exc: print(json.dumps(error_result(exc),ensure_ascii=False)); return 2
if __name__=='__main__': raise SystemExit(main())
