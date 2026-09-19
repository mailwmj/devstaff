#!/usr/bin/env python3
"""Real browser adapter for the bundled stdlib starter, using isolated synthetic data.

No production URL or database is accepted. Screenshots do not imply visual approval.
This runner never self-certifies independent verification.
"""
from __future__ import annotations
import importlib.util
import json
import os
import queue
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SIBLINGS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SIBLINGS/'site-builder/scripts'))
from site_runtime.common import JsonParser,Problem,atomic_json,error_result,metadata_dir

AXES=('contract','static_build','core_task','negative_path','visual_desktop','visual_mobile','reopen','risk')
PROBES={'starter.core':'core_task','starter.negative':'negative_path','starter.reopen':'reopen','starter.desktop':'visual_desktop','starter.mobile':'visual_mobile','starter.risk':'risk'}


def load_module(name,file):
    spec=importlib.util.spec_from_file_location(name,file); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def checked(command,cwd):
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,encoding='utf-8',timeout=90,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    return {'command':command,'exit_code':result.returncode,'stdout':result.stdout[-12000:],'stderr':result.stderr[-12000:]}


def server_entry(process):
    channel=queue.Queue(); threading.Thread(target=lambda:channel.put(process.stdout.readline()),daemon=True).start()
    try: line=channel.get(timeout=20)
    except queue.Empty as exc: raise Problem('SERVER_START_TIMEOUT','server did not report entry URL') from exc
    if not line: raise Problem('SERVER_START_FAILED','server exited before reporting an entry URL')
    return json.loads(line)['url']


def browser_probes(p,copy,output,profile,axes,probe_results,browser_executable,selector):
    from playwright.sync_api import expect
    password=secrets.token_urlsafe(20)
    if profile=='shared':
        setup="from pathlib import Path; from store import Store; import sys; s=Store(Path('data/site.sqlite')); s.add_user('fixture-a',sys.stdin.readline().strip());s.add_user('fixture-b',sys.stdin.readline().strip())"
        result=subprocess.run([sys.executable,'-c',setup],cwd=copy,input=password+'\n'+password+'\n',text=True,capture_output=True,timeout=30)
        if result.returncode: raise Problem('FIXTURE_SETUP_FAILED','could not create synthetic accounts')
    process=subprocess.Popen([sys.executable,'server.py','--port','0'],cwd=copy,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    browser=context=page=None
    responses=[]
    try:
        url=server_entry(process)
        browser=p.chromium.launch(headless=True,**({'executable_path':browser_executable} if browser_executable else {}))
        context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        context.tracing.start(screenshots=True,snapshots=True,sources=True)
        page=context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('response',lambda response:responses.append({'path':response.url.split('?')[0].removeprefix(url),'status':response.status}) if '/api/' in response.url else None)
        page.goto(url,wait_until='networkidle')
        expect(page.locator(selector)).to_have_count(1,timeout=5000)
        expect(page.locator(selector)).to_be_visible()
        probe_results.append({'id':'root','subjects':page.locator(selector).count(),'result':'passed'})
        if profile=='shared':
            page.locator('#login-form input[name="username"]').fill('fixture-a')
            page.locator('#login-form input[name="password"]').fill(password)
            with page.expect_response(lambda response: response.url == url+'/api/login' and response.request.method == 'POST') as pending_login:
                page.locator('#login-form button').click()
            login_response=pending_login.value
            if login_response.status != 200:
                raise AssertionError('UI sign-in failed with HTTP '+str(login_response.status))
            expect(page.locator('#workspace')).to_be_visible()
        if profile=='content':
            expect(page.locator('#content-panel')).to_be_visible(); expect(page.locator('#title')).not_to_be_empty()
            if page.locator('#record-form').count(): raise AssertionError('content profile has dormant data controls')
            axes['core_task']={'status':'verified','observed':'content title, sections and contact rendered without fake data controls'}
            if context.request.get(url+'/missing-fixture-page').status!=404: raise AssertionError('unknown route did not return 404')
            axes['negative_path']={'status':'verified','observed':'unknown route returns 404'}
            page.reload(wait_until='networkidle'); expect(page.locator('#content-panel')).to_be_visible()
            axes['reopen']={'status':'verified','observed':'static content retained after reload'}
            axes['risk']={'status':'verified','observed':'static fixture exposes no data form; no production service accessed'}
        else:
            expect(page.locator('#empty')).to_be_visible()
            page.locator('#record-form input[name="title"]').fill('Fixture course record')
            page.locator('#record-form input[name="amount"]').fill('12.30')
            page.locator('#record-form button[type="submit"]').click()
            expect(page.locator('#records .record')).to_have_count(1); expect(page.locator('#total')).to_contain_text('12.30')
            axes['core_task']={'status':'verified','observed':'one record submitted through UI, server result rendered with total 12.30'}
            page.reload(wait_until='networkidle'); expect(page.locator('#records .record')).to_have_count(1)
            axes['reopen']={'status':'verified','observed':'browser reload retained the persisted record'}
            page.route('**/api/records',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"fixture storage failure"}') if route.request.method=='POST' else route.continue_())
            page.locator('#record-form input[name="title"]').fill('Must not appear saved')
            page.locator('#record-form button[type="submit"]').click()
            expect(page.locator('#message')).to_have_attribute('data-kind','error'); expect(page.locator('#records .record')).to_have_count(1)
            expect(page.locator('#record-form input[name="title"]')).to_have_value('Must not appear saved')
            page.unroute('**/api/records')
            axes['negative_path']={'status':'verified','observed':'injected save failure showed error, retained input, and did not add a saved row'}
            if profile=='shared':
                mine=context.request.get(url+'/api/records').json()['records'][0]
                other=browser.new_context()
                try:
                    if other.request.get(url+'/api/records').status!=401: raise AssertionError('anonymous access allowed')
                    login=other.request.post(url+'/api/login',data={'username':'fixture-b','password':password},headers={'X-Site-Client':'1'})
                    if login.status!=200: raise AssertionError('second login failed')
                    csrf=login.json()['csrf']
                    if other.request.get(url+'/api/records').json()['records']: raise AssertionError('cross-owner list leaked')
                    changed=other.request.patch(url+'/api/records/'+mine['id'],data={'status':'done'},headers={'X-Site-Client':'1','X-CSRF-Token':csrf})
                    if changed.status!=404: raise AssertionError('cross-owner direct update allowed')
                finally: other.close()
                axes['risk']={'status':'verified','observed':'anonymous reads denied; second account cannot list or directly update first account record'}
            else: axes['risk']={'status':'verified','observed':'fixture uses loopback and a separate temporary database; no original data touched'}
        for width,axis,name in ((1440,'visual_desktop','desktop.png'),(375,'visual_mobile','mobile.png'),(320,'visual_mobile','narrow.png')):
            page.set_viewport_size({'width':width,'height':1000})
            if page.evaluate('document.documentElement.scrollWidth > innerWidth + 1'): raise AssertionError('horizontal overflow at '+str(width))
            page.screenshot(path=str(output/name),full_page=True)
            axes[axis]={'status':'limited','observed':'rendered at '+str(width)+'px without page overflow; screenshot '+name,
                        'limitation':'A reviewer must inspect hierarchy, focus, content and applicable component states.'}
        if errors: raise AssertionError('uncaught browser errors: '+'; '.join(errors))
        probe_results.append({'id':'browser','subjects':1,'result':'passed','profile':profile})
    except Exception as exc:
        diagnostic={'profile':profile,'error':str(exc)[:2000],'api_responses':responses[-12:]}
        if page:
            try:
                diagnostic['visible_message']=page.locator('#message').inner_text(timeout=1000)[:1000]
                diagnostic['cookie_count']=len(context.cookies())
                page.screenshot(path=str(output/'failure.png'),full_page=True)
            except Exception:
                diagnostic['page_capture']='unavailable'
        atomic_json(output/'diagnostic.json',diagnostic)
        raise AssertionError(json.dumps(diagnostic,ensure_ascii=False)) from exc
    finally:
        if context:
            try: context.tracing.stop(path=str(output/'trace.zip'))
            finally: context.close()
        if browser: browser.close()
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)


def execute(root,output,browser_executable=None,selector='#main',standalone=False):
    root,output=Path(root).resolve(),Path(output).resolve()
    config=json.loads((root/'site.json').read_bytes()); profile=config.get('profile')
    if config.get('stack')!='python-stdlib-vanilla-web' or profile not in ('content','personal','shared'):
        raise Problem('UNSUPPORTED_RUNNER_PROFILE','this runner supports only the bundled stdlib Web starter')
    if output.is_relative_to(root) and not output.is_relative_to(metadata_dir(root)): raise Problem('OUTPUT_IN_SOURCE','evidence must be under .site or outside source')
    if output.exists(): raise Problem('OUTPUT_EXISTS','use a fresh evidence directory')
    output.mkdir(parents=True)
    plan=protocol=None; axes={a:{'status':'not_run'} for a in AXES}; evidence=[]; limitations=[]; commands=[]; probes=[]
    if not standalone:
        protocol=load_module('site_check_runner_protocol',Path(__file__).with_name('check.py'))
        plan=protocol.plan(root); atomic_json(output/'plan.json',plan)
        design=load_module('site_design_runner',SIBLINGS/'site-design/scripts/design.py')
        contract_result=design.check_contract(root,'precheck'); atomic_json(output/'contract.json',contract_result)
        axes['contract']={'status':'verified' if contract_result['passed'] else 'blocked','observed':'actual design check-contract precheck result in contract.json'}
    else:
        axes['contract']={'status':'verified','observed':'standalone starter fixture, not a product contract approval'}
    with tempfile.TemporaryDirectory(prefix='site-check-isolated-') as td:
        copy=Path(td)/'app'; copy.mkdir()
        for name in ('server.py','manage.py','domain.py','store.py','site.json','public','tests'):
            source=root/name
            if source.is_symlink() or (source.is_dir() and any(p.is_symlink() for p in source.rglob('*'))):
                raise Problem('SOURCE_SYMLINK','starter snapshot cannot contain symlinks')
            if source.is_dir(): shutil.copytree(source,copy/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            elif source.is_file(): shutil.copy2(source,copy/name)
        for command in ([sys.executable,'manage.py','check'],[sys.executable,'manage.py','test']): commands.append(checked(command,copy))
        axes['static_build']={'status':'verified' if all(c['exit_code']==0 for c in commands) else 'blocked','observed':'actual starter syntax/content checks and unit tests in commands.json'}
        if any(axes[a]['status']=='blocked' for a in ('contract','static_build')):
            limitations.append('Static gates failed; browser was not started.')
        else:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p: browser_probes(p,copy,output,profile,axes,probes,browser_executable,selector)
                evidence.append('Real browser probes ran on an isolated copy with synthetic data; see probes.json and screenshots.')
            except ImportError:
                limitations.append('Playwright unavailable; browser axes were not run.')
            except Exception as exc:
                limitations.append('Browser probe failed: '+str(exc)[:1500])
                axis='core_task' if axes['core_task']['status']=='not_run' else 'negative_path'
                axes[axis]={'status':'blocked','observed':str(exc)[:1000]}; probes.append({'id':'browser','result':'failed'})
    if plan:
        for target in plan.get('acceptance',[]):
            if PROBES.get(target.get('probe'))!=target['axis']:
                axes[target['axis']]={'status':'not_run'}; limitations.append('No bound executable probe for '+target['id']+'. An actual checker must inspect it.')
        after=protocol.plan(root)
        if any(after[k]!=plan[k] for k in ('source_sha256','contract_sha256','mode','round_id')):
            raise Problem('VERSION_CHANGED','project changed while isolated probes ran')
    required=plan['required_axes'] if plan else list(AXES[:-1])
    statuses=[axes[a]['status'] for a in required]
    overall='blocked' if any(s in ('blocked','not_run') for s in statuses) else ('limited' if 'limited' in statuses else 'verified')
    limitations.extend(axes[a]['limitation'] for a in AXES if 'limitation' in axes[a])
    if plan and plan['mode']=='strict': limitations.append('Independent checker context is required; this runner is not independent.')
    report={'project_root':str(root),'mode':plan['mode'] if plan else 'guided','overall':overall,'independent':False,'axes':axes,
            'evidence':evidence or ['actual execution recorded in commands.json and probes.json'],'limitations':list(dict.fromkeys(limitations)),
            'runner':'stdlib-web-v1','standalone':standalone,'environment':'isolated copy with synthetic data; original database never opened'}
    if plan: report.update({k:plan[k] for k in ('source_sha256','contract_sha256','source_manifest','round_id')})
    atomic_json(output/'commands.json',{'commands':commands}); atomic_json(output/'probes.json',{'probes':probes})
    atomic_json(output/'report.json',report)
    return report


def main():
    try:
        p=JsonParser(description=__doc__); p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--browser-executable');p.add_argument('--selector',default='#main');p.add_argument('--standalone',action='store_true')
        a=p.parse_args(); result=execute(a.root,a.output,a.browser_executable,a.selector,a.standalone)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 1 if result['overall']=='blocked' else 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc: print(json.dumps(error_result(exc),ensure_ascii=False));return 2
if __name__=='__main__': raise SystemExit(main())
