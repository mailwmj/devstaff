from pathlib import Path
import ast
root = Path.cwd()
p = root/'tests/test_delivery_hardening.py'
s=p.read_text()
assert 'for revision in (0, 3, 99,' in s
p.write_text(s.replace('for revision in (0, 3, 99,', 'for revision in (0, 4, 99,', 1))
p=root/'release/site-design/scripts/design.py'
s=p.read_text()
a=s.index('def _iter_ui_files(root):'); b=s.index('\ndef _ui_manifest_sha256',a)
s=s[:a]+'''def _iter_ui_files(root):
    """Prune ignored directories without classifying by absolute parent names."""
    root = Path(root)
    def fail(exc):
        raise ValueError('UI source unreadable: ' + str(exc)) from exc
    ignored = LINT_IGNORE_DIRS | LINT_FIXTURE_DIR_PARTS
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        dirs[:] = sorted(name for name in dirs if name not in ignored)
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError('UI source symlink is unsupported')
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root)
            if any(part in ignored for part in relative.parts[:-1]):
                continue
            if LINT_FIXTURE_NAME_RE.search(path.name):
                continue
            if path.suffix.lower() not in LINT_UI_EXTENSIONS:
                continue
            if path.is_symlink():
                raise ValueError('UI source symlink is unsupported')
            yield path

''' + s[b:]
ast.parse(s);p.write_text(s)
p=root/'release/site-check/scripts/run.py'
s=p.read_text()
s=s.replace('browser=context=None\n', 'browser=context=page=None\n    responses=[]\n',1)
s=s.replace("page=context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))", "page=context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))\n        page.on('response',lambda response:responses.append({'path':response.url.split('?')[0].removeprefix(url),'status':response.status}) if '/api/' in response.url else None)")
s=s.replace("page.locator('#login-form button').click(); expect(page.locator('#workspace')).to_be_visible()", "with page.expect_response(lambda response: response.url == url+'/api/login' and response.request.method == 'POST') as pending_login:\n                page.locator('#login-form button').click()\n            login_response=pending_login.value\n            if login_response.status != 200:\n                raise AssertionError('UI sign-in failed with HTTP '+str(login_response.status))\n            expect(page.locator('#workspace')).to_be_visible()")
needle="    finally:\n        if context:\n            try: context.tracing.stop"
replacement="""    except Exception as exc:
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
            try: context.tracing.stop"""
assert needle in s
s=s.replace(needle,replacement,1)
ast.parse(s);p.write_text(s)
print('Applied schema compatibility, scanner boundaries and browser diagnosis fixes')
