#!/usr/bin/env python3
"""Small project metadata operations; no upload, deployment or automatic migration."""
import json
from pathlib import Path
from site_runtime.common import JsonParser, error_result
from site_runtime.preview import register
from site_runtime.contract import migrate, path


def main():
    parser = JsonParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('preview'); p.add_argument('root', type=Path); p.add_argument('artifact')
    p.add_argument('--kind', default='file', choices=['file','url','embedded','screenshot'])
    p.add_argument('--url'); p.add_argument('--audience', default='local', choices=['local','restricted','public'])
    p.add_argument('--user-evidence', default=''); p.add_argument('--public-quote', default='')
    p = sub.add_parser('migrate-contract'); p.add_argument('root', type=Path)
    try:
        args = parser.parse_args()
        if args.command == 'preview': result = register(args.root,args.artifact,kind=args.kind,url=args.url,audience=args.audience,user_evidence=args.user_evidence,public_quote=args.public_quote)
        else: result = migrate(path(args.root))
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError) as exc:
        print(json.dumps(error_result(exc),ensure_ascii=False)); return 2

if __name__=='__main__': raise SystemExit(main())
