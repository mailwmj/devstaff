#!/usr/bin/env python3
"""Detect local prerequisites. Never installs software or claims user reachability."""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from site_runtime.common import JsonParser,error_result


def diagnose(root,bundle=None):
    root=Path(root).resolve(); bundle=Path(bundle) if bundle else Path(__file__).resolve().parents[2]
    rows=[]
    def row(name,ok,recovery='',**extra): rows.append({'name':name,'status':'available' if ok else 'unavailable','recovery':recovery,**extra})
    row('python',sys.version_info>=(3,10),'Install Python >=3.10.',version=sys.version.split()[0])
    for name in ('site-builder','site-brief','site-design','site-check'):
        row(name,(bundle/name/'SKILL.md').is_file(),'Reinstall the complete sibling bundle.')
    protocol=next((p for p in (bundle/'site-protocol/AGENTS.md',bundle/'AGENTS.md',bundle/'site-builder/references/AGENTS.md') if p.is_file()),None)
    row('shared_protocol',protocol is not None,'Install shared instructions.',path=str(protocol) if protocol else None)
    writable=False
    try:
        with tempfile.TemporaryFile(dir=root) as f: f.write(b'probe'); writable=True
    except OSError: pass
    row('project_read_write',writable,'Choose an existing writable directory.')
    row('node_optional',shutil.which('node') is not None,'Only needed by projects that use Node.')
    browser=next((shutil.which(x) for x in ('chromium','chromium-browser','google-chrome') if shutil.which(x)),None)
    row('browser_binary',browser is not None,'Use a supported browser adapter.',path=browser)
    row('playwright_optional',importlib.util.find_spec('playwright') is not None,'Explicitly install requirements-browser.txt for browser tests.')
    rows.append({'name':'user_preview_access','status':'unknown','recovery':'Use a host preview surface or obtain user confirmation for this artifact.'})
    required={'python','site-builder','site-brief','site-design','site-check','shared_protocol','project_read_write'}
    return {'ok':all(r['status']=='available' for r in rows if r['name'] in required),'checks':rows,'host_adapter':'generic-local','user_access_verified':False}


def main():
    try:
        parser=JsonParser(description=__doc__); parser.add_argument('root',type=Path); args=parser.parse_args()
        result=diagnose(args.root); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['ok'] else 1
    except (ValueError,OSError) as exc:
        print(json.dumps(error_result(exc),ensure_ascii=False)); return 2
if __name__=='__main__': raise SystemExit(main())
