#!/usr/bin/env python3
"""Run every suite, validate the exact committed release, and package evidence."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.verification'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--browser',action='store_true');parser.add_argument('--browser-executable');a=parser.parse_args()
    OUT.mkdir(exist_ok=True);results=[]
    def run(name,command,cwd=ROOT,expected=0,timeout=240):
        proc=subprocess.run([str(x) for x in command],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        (OUT/(name+'.log')).write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
        item={'name':name,'command':[str(x) for x in command],'exit_code':proc.returncode,'expected_exit_code':expected,'passed':proc.returncode==expected}
        results.append(item);print(json.dumps(item),flush=True)
        if proc.returncode!=expected:print((proc.stdout+'\n'+proc.stderr)[-22000:],flush=True)
        return proc
    for name,path in (('unit','tests'),('design','release/site-design/scripts/tests'),('builder','release/site-builder/scripts/tests'),('checker','release/site-check/scripts/tests')):
        run(name,[sys.executable,'-m','unittest','discover','-s',path,'-p','test_*.py'])
    run('design-assets',[sys.executable,'release/site-design/scripts/design.py','validate'])
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    # Package actual Git bytes, not an untracked worktree approximation.
    run('release-archive',['git','archive','--format=zip','HEAD:release','--output',dist/'skill.zip'])
    run('project-archive',['git','archive','--format=zip','HEAD','--output',dist/'devstaff-project.zip'])
    with tempfile.TemporaryDirectory(prefix='devstaff-full-release-') as td:
        temp=Path(td);source=temp/'source';installed=temp/'installed';project=temp/'workspace';project.mkdir()
        with zipfile.ZipFile(dist/'skill.zip') as archive:archive.extractall(source)
        run('clean-install',[sys.executable,source/'install.py',installed])
        shutil.rmtree(source)
        run('doctor-source-removed',[sys.executable,installed/'site-builder/scripts/doctor.py',project])
        for name in ('site-builder','site-check','site-design'):
            run('installed-'+name,[sys.executable,'-m','unittest','discover','-s',installed/name/'scripts/tests','-p','test_*.py'],cwd=temp)
        for profile in ('content','personal','shared'):
            app=temp/profile
            run('scaffold-'+profile,[sys.executable,installed/'site-builder/scripts/scaffold.py',app,'--profile',profile,'--title','Synthetic '+profile+' fixture'])
            run('starter-check-'+profile,[sys.executable,app/'manage.py','check'])
            run('starter-test-'+profile,[sys.executable,app/'manage.py','test'])
            run('starter-build-'+profile,[sys.executable,app/'manage.py','build'])
            run('starter-no-overwrite-'+profile,[sys.executable,installed/'site-builder/scripts/scaffold.py',app,'--profile',profile,'--title','Must not overwrite'],expected=2)
            if a.browser:
                command=[sys.executable,installed/'site-check/scripts/run.py',app,'--output',OUT/('browser-'+profile),'--standalone']
                if a.browser_executable:command+=['--browser-executable',a.browser_executable]
                run('browser-'+profile,command,timeout=180)
        if a.browser:
            command=[sys.executable,installed/'site-check/scripts/run.py',temp/'personal','--output',OUT/'browser-zero-match','--standalone','--selector','#does-not-exist']
            if a.browser_executable:command+=['--browser-executable',a.browser_executable]
            run('browser-zero-match',command,expected=1,timeout=90)
    result={'commit':commit,'python':sys.version,'platform':sys.platform,'results':results,'passed':all(r['passed'] for r in results),
            'browser_requested':a.browser,'limitations':['Scripted synthetic integration is not a user study.','Visual screenshot review is separate from browser assertion success.','Real cloud deployment and unsupported host/OS adapters were not exercised.']}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
