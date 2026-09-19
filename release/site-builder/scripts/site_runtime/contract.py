"""One fenced authority. v1 table compatibility; v2 machine targets, prose rationale."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from .common import Problem, metadata_dir, strings

BLOCK = re.compile(r'```(?:site-contract|v3-contract)\r?\n(.*?)\r?\n```', re.DOTALL)
AXES = ('contract', 'static_build', 'core_task', 'negative_path', 'visual_desktop', 'visual_mobile', 'reopen', 'risk')
INDEX_FIELDS = ('scope_refs','required_constraints','pages','sections','responsive','components','assets','copy')
LIST_FIELDS = INDEX_FIELDS + ('acceptance','unresolved_confirm','blocking_missing_assets','intentional_exceptions')
ID = re.compile(r'^[A-Z]{2}-[0-9]{2,}$')


def path(root):
    return metadata_dir(root) / 'design/surface-brief.md'


def parse(text):
    found = list(BLOCK.finditer(text))
    if len(found) != 1:
        raise Problem('CONTRACT_INVALID', 'contract requires exactly one fenced site-contract block')
    try:
        data = json.loads(found[0].group(1))
    except json.JSONDecodeError as exc:
        raise Problem('CONTRACT_INVALID', 'contract block is not valid JSON: ' + str(exc)) from exc
    if not isinstance(data, dict):
        raise Problem('CONTRACT_INVALID', 'contract block must be a JSON object')
    version = data.get('schema_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise Problem('CONTRACT_SCHEMA_UNSUPPORTED', 'unsupported contract schema_version')
    for key in LIST_FIELDS:
        if key in data:
            strings(data[key], key)
            if len(set(data[key])) != len(data[key]):
                raise Problem('DUPLICATE_ID', 'duplicate references in ' + key)
    if version == 2:
        validate_v2(data)
        data['acceptance'] = [t['id'] for t in data['targets']]
    return data


def validate_v2(data):
    if data.get('structure_mode') not in ('single', 'choice'):
        raise Problem('CONTRACT_INVALID', 'structure_mode must be single or choice')
    if data.get('work_type') not in ('new-surface','redesign','existing-system','local-change','flow-state'):
        raise Problem('CONTRACT_INVALID', 'invalid work_type')
    if not isinstance(data.get('task'), str) or not data['task'].strip():
        raise Problem('CONTRACT_INVALID', 'task is required')
    targets = data.get('targets')
    if not isinstance(targets, list) or not targets:
        raise Problem('CONTRACT_INVALID', 'targets must be a nonempty list')
    known = {ref for key in INDEX_FIELDS for ref in data.get(key, [])}
    ids = set()
    for item in targets:
        if not isinstance(item, dict) or not ID.fullmatch(str(item.get('id', ''))) or not item['id'].startswith('VA-'):
            raise Problem('CONTRACT_INVALID', 'invalid target id')
        if item['id'] in ids:
            raise Problem('DUPLICATE_ID', 'duplicate target: ' + item['id'])
        ids.add(item['id'])
        for key in ('target','standard'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise Problem('CONTRACT_INVALID', 'target requires ' + key)
        if item.get('axis') not in AXES[2:] or type(item.get('blocking')) is not bool:
            raise Problem('CONTRACT_INVALID', 'invalid target axis or blocking flag')
        for ref in strings(item.get('refs', []), 'target.refs'):
            if ref not in known:
                raise Problem('BROKEN_REFERENCE', 'target references unknown ID ' + ref)
    if 'core_task' not in {t['axis'] for t in targets}:
        raise Problem('CONTRACT_INVALID', 'v2 requires a core_task target')
    if 'acceptance' in data and data['acceptance'] != [t['id'] for t in targets]:
        raise Problem('DUPLICATE_AUTHORITY', 'v2 acceptance is derived; remove the stale index')
    if data.get('comparison_type','style') not in ('structure','style','interaction'):
        raise Problem('CONTRACT_INVALID', 'invalid comparison_type')


def targets(data, text):
    if data.get('schema_version', 1) == 2:
        exempt = set(data.get('intentional_exceptions', []))
        return [{**item, 'exempt': item['id'] in exempt} for item in data['targets']]
    lines, result, seen = BLOCK.sub('', text).splitlines(), [], set()
    for index, line in enumerate(lines):
        if not line.strip().startswith('|') or '\u68c0\u67e5\u8f74' not in line or '\u53ef\u89c2\u5bdf\u6807\u51c6' not in line:
            continue
        header = [x.strip() for x in line.strip().strip('|').split('|')]
        def col(marker): return next((i for i, cell in enumerate(header) if marker in cell), None)
        ic, ac, tc, bc, sc = col('ID'), col('\u68c0\u67e5\u8f74'), col('\u9875\u9762'), col('\u963b\u65ad'), col('\u53ef\u89c2\u5bdf\u6807\u51c6')
        if None in (ic,ac,tc,sc): continue
        for row in lines[index+2:]:
            if not row.strip().startswith('|'): break
            cells = [x.strip().strip('`').strip() for x in row.strip().strip('|').split('|')]
            if max(ic,ac,tc,sc) >= len(cells): continue
            vid = cells[ic]
            if not vid.startswith('VA-'): continue
            if vid in seen: raise Problem('DUPLICATE_ID', 'duplicate legacy target: ' + vid)
            seen.add(vid)
            if cells[ac] not in AXES[2:]: raise Problem('CONTRACT_INVALID','invalid legacy check axis: ' + cells[ac])
            result.append({'id':vid,'target':cells[tc],'standard':cells[sc],'axis':cells[ac],
                           'blocking':bc is not None and bc<len(cells) and cells[bc].lower()=='yes',
                           'exempt':vid in data.get('intentional_exceptions',[])})
    missing = set(data.get('acceptance',[])) - seen
    if missing: raise Problem('MISSING_ACCEPTANCE_TARGET', 'indexed acceptance missing from table: ' + ', '.join(sorted(missing)))
    return result


def read(file):
    file = Path(file)
    if file.is_symlink(): raise Problem('UNSAFE_PATH', 'contract cannot be a symlink')
    text = file.read_text(encoding='utf-8')
    data = parse(text)
    return hashlib.sha256(text.encode()).hexdigest(), data, targets(data,text)


def migrate(file):
    file = Path(file)
    text = file.read_text(encoding='utf-8')
    data = parse(text)
    if data.get('schema_version') == 2: return {'changed': False}
    target = targets(data,text)
    if not target: raise Problem('MIGRATION_NEEDS_TARGETS', 'legacy contract has no executable acceptance targets')
    data.update(schema_version=2, task=data.get('task') or 'Implement the retained brief core task.', targets=[{k:v for k,v in t.items() if k!='exempt'} for t in target])
    data.pop('acceptance',None)
    validate_v2(data)
    digest = hashlib.sha256(text.encode()).hexdigest()
    backup = file.with_name(file.name + '.' + digest[:12] + '.bak')
    if not backup.exists(): backup.write_bytes(file.read_bytes())
    new = BLOCK.sub(lambda _: '```site-contract\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n```',text)
    file.write_text('<!-- v2 targets are authoritative. Retained legacy tables are historical context. -->\n'+new,encoding='utf-8')
    return {'changed':True,'backup':str(backup),'requires_new_verification':True}
