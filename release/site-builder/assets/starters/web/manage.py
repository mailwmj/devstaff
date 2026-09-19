#!/usr/bin/env python3
"""Local maintenance. No public deployment, default credentials or overwritten backups."""
import argparse
import ast
import getpass
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from store import Store
ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('check'); sub.add_parser('test')
    p=sub.add_parser('build'); p.add_argument('--out',type=Path,default=ROOT/'dist')
    p=sub.add_parser('add-user'); p.add_argument('username')
    p=sub.add_parser('backup'); p.add_argument('destination',type=Path)
    args=parser.parse_args()
    if args.command=='check':
        for file in ROOT.glob('*.py'): ast.parse(file.read_text(encoding='utf-8'),filename=str(file))
        content=json.loads((ROOT/'public/content.json').read_text(encoding='utf-8'))
        if not isinstance(content,dict) or not content.get('title'): raise ValueError('content.json requires a title')
        if shutil.which('node'): subprocess.run(['node','--check',str(ROOT/'public/app.js')],check=True)
        print(json.dumps({'ok':True,'checks':['python_syntax','content_schema','javascript_syntax' if shutil.which('node') else 'javascript_not_run'],
                          'typecheck':'not_applicable_plain_python_js; runtime validation and tests apply'}))
    elif args.command=='test': return subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests')],cwd=ROOT).returncode
    elif args.command=='build':
        config=json.loads((ROOT/'site.json').read_text())
        if args.out.exists(): raise ValueError('build destination exists; choose a fresh directory')
        if args.out.resolve().is_relative_to((ROOT/'public').resolve()): raise ValueError('build output cannot be inside its inputs')
        shutil.copytree(ROOT/'public',args.out)
        print(json.dumps({'output':str(args.out),'profile':config['profile'],'backend_required':config['profile']!='content'}))
    elif args.command=='add-user':
        if json.loads((ROOT/'site.json').read_text())['profile']!='shared': raise ValueError('only shared profile has accounts')
        password=getpass.getpass('Password (12+ characters): ')
        if password!=getpass.getpass('Confirm password: '): raise ValueError('passwords differ')
        Store(ROOT/'data/site.sqlite').add_user(args.username,password); print('User created. No password logged.')
    elif args.command=='backup':
        Store(ROOT/'data/site.sqlite').backup(args.destination); print(json.dumps({'backup':str(args.destination)}))
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError,sqlite3.Error,subprocess.SubprocessError) as exc:
        print(json.dumps({'error':str(exc)})); raise SystemExit(2)
