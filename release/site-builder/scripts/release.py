#!/usr/bin/env python3
"""Prepare, authorize and execute local release plans; never auto-publish publicly."""
import json
from pathlib import Path
from site_runtime.common import JsonParser, atomic_json, read_json, error_result
from site_runtime.delivery import plan, authorize, execute


def main():
    parser=JsonParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('artifact',type=Path);p.add_argument('destination',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--scope',choices=['preview','personal','shared','public'],required=True);p.add_argument('--owner',required=True);p.add_argument('--cost',required=True)
    p=sub.add_parser('authorize');p.add_argument('plan',type=Path);p.add_argument('--sha',required=True);p.add_argument('--quote',required=True)
    p=sub.add_parser('execute');p.add_argument('plan',type=Path)
    try:
        a=parser.parse_args()
        if a.command=='plan': result=plan(a.artifact,a.destination,scope=a.scope,owner=a.owner,cost=a.cost);atomic_json(a.out,result)
        elif a.command=='authorize': result=authorize(read_json(a.plan),a.sha,a.quote);atomic_json(a.plan,result)
        else: result=execute(read_json(a.plan))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 1 if result.get('status')=='blocked' else 0
    except (OSError,ValueError) as exc: print(json.dumps(error_result(exc),ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
