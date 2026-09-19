"""Same inclusion rules for worktrees and historical archives; hard directories pruned."""
from __future__ import annotations
import fnmatch
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from .common import Problem, metadata_dir, sha256_file

HARD = {'.git','node_modules','__pycache__','.playwright-cli'}
BUILD = {'dist','build','.cache','.next','coverage'}


def parse_policy(value):
    if value is None: return {'include':[],'exclude':[]}
    if not isinstance(value,dict) or type(value.get('schema_version')) is not int or value['schema_version']!=1:
        raise Problem('SOURCE_POLICY_INVALID','unsupported source policy')
    for key in ('include','exclude'):
        entries = value.get(key,[])
        if not isinstance(entries,list) or any(not isinstance(x,str) or not x.strip() or x.startswith('/') or '..' in Path(x).parts for x in entries):
            raise Problem('SOURCE_POLICY_INVALID','invalid '+key)
        value[key]=entries
    return value


def policy(root):
    file=metadata_dir(root)/'source-policy.json'
    if file.is_symlink(): raise Problem('UNSAFE_PATH','source policy cannot be a symlink')
    return parse_policy(json.loads(file.read_bytes()) if file.is_file() else None),file


def matches(name, patterns): return any(fnmatch.fnmatchcase(name,p) for p in patterns)


def exclusion(parts,config,rule,toolchain=()):
    # Overrides cannot expose dependencies, bookkeeping or build outputs.
    if any(p in HARD or p.lower() in ('.site','.v3') for p in parts): return 'tooling'
    if parts and parts[0] in BUILD: return 'runtime_or_build'
    base=rule(parts,toolchain)
    rel='/'.join(parts)
    if base=='tooling': return base
    if matches(rel,config['include']): return None
    if matches(rel,config['exclude']): return 'explicit_policy'
    return base


def scan(root,source_rule,toolchain=()):
    root=Path(root).resolve()
    config,file=policy(root)
    manifest,excluded={},[]
    def fail(exc): raise Problem('SOURCE_UNREADABLE',str(exc)) from exc
    for directory,dirs,files in os.walk(root,followlinks=False,onerror=fail):
        parent=Path(directory); rel_parent=parent.relative_to(root)
        keep=[]
        for name in sorted(dirs):
            rel=(rel_parent/name).as_posix()
            if name in HARD or name.lower() in ('.site','.v3') or (rel_parent==Path('.') and name in toolchain): continue
            if rel_parent==Path('.') and name in BUILD:
                excluded.append(rel+'/'); continue
            if (parent/name).is_symlink(): raise Problem('SOURCE_SYMLINK','source directory symlink: '+rel)
            keep.append(name)
        dirs[:]=keep
        for name in sorted(files):
            source=parent/name; relative=source.relative_to(root)
            why=exclusion(relative.parts,config,source_rule,toolchain)
            if why:
                if why!='tooling': excluded.append(relative.as_posix())
                continue
            if source.is_symlink(): raise Problem('SOURCE_SYMLINK','source file symlink: '+relative.as_posix())
            manifest[relative.as_posix()]=sha256_file(source)
    if file.is_file(): manifest[file.relative_to(root).as_posix()]=sha256_file(file)
    return dict(sorted(manifest.items())),sorted(excluded)


def archive_manifest(payload,prefix,source_rule,checker_root=None):
    """Historical policy and toolchain declarations come from that revision, not HEAD."""
    entries={}; links=[]
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:') as archive:
        for member in archive:
            name=member.name
            if prefix:
                if not name.startswith(prefix): continue
                name=name[len(prefix):]
            if not name: continue
            parts=Path(name).parts
            if name.startswith('/') or '..' in parts: raise Problem('UNSAFE_ARCHIVE','unsafe Git archive path')
            if member.issym() or member.islnk(): links.append(name)
            elif member.isfile():
                file=archive.extractfile(member)
                entries[name]=file.read()
    metadata={Path(n).parts[0] for n in entries if Path(n).parts[0].lower() in ('.site','.v3')}
    if len(metadata)>1: raise Problem('STATE_PATH_CONFLICT','multiple historical metadata directories')
    md=next(iter(metadata),'.site'); policy_name=md+'/source-policy.json'
    config=parse_policy(json.loads(entries[policy_name]) if policy_name in entries else None)
    toolchain=[]
    if 'skills.json' in entries:
        data=json.loads(entries['skills.json'])
        for v in data.get('skills',{}).values():
            directory=v.get('directory') if isinstance(v,dict) else None
            if isinstance(directory,str) and directory and '/' not in directory and directory!=checker_root:
                toolchain.append(directory)
    for name in links:
        if exclusion(Path(name).parts,config,source_rule,toolchain) is None:
            raise Problem('SOURCE_SYMLINK','historical source symlink: '+name)
    result={n:hashlib.sha256(b).hexdigest() for n,b in entries.items() if exclusion(Path(n).parts,config,source_rule,toolchain) is None}
    if policy_name in entries: result[policy_name]=hashlib.sha256(entries[policy_name]).hexdigest()
    return dict(sorted(result.items()))
