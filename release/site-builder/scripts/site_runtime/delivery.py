"""Version-bound release plans and a tested local-directory provider.

The provider API distinguishes deployment, smoke-check and rollback. Local copy
is never reported as a publicly accessible website. External providers must
implement these three actions and obtain their own explicit authorization.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from .common import Problem, atomic_json, read_json, sha256_file


def tree_digest(root: Path) -> str:
    root=Path(root).resolve(); h=hashlib.sha256()
    if not root.is_dir(): raise Problem('MISSING_ARTIFACT','release artifact directory does not exist')
    for file in sorted(root.rglob('*')):
        if file.is_symlink(): raise Problem('UNSAFE_ARTIFACT','release artifacts cannot contain symlinks')
        if file.is_file():
            relative=file.relative_to(root).as_posix()
            if file.name.startswith('.env') or file.suffix in ('.sqlite','.db','.pem','.key'):
                raise Problem('SENSITIVE_RELEASE_FILE','do not publish runtime data or secrets: '+relative)
            h.update(relative.encode()); h.update(b'\0'); h.update(bytes.fromhex(sha256_file(file)))
    return h.hexdigest()


def plan(artifact: Path, destination: Path, *, scope: str, owner: str, cost: str, provider='local-directory') -> dict:
    if scope not in ('preview','personal','shared','public'): raise Problem('INVALID_SCOPE','unsupported delivery scope')
    if not owner.strip() or not cost.strip(): raise Problem('RELEASE_DETAILS_REQUIRED','resource owner and cost disclosure are required')
    artifact,destination=Path(artifact).resolve(),Path(destination).resolve()
    if destination==artifact or destination.is_relative_to(artifact) or artifact.is_relative_to(destination):
        raise Problem('UNSAFE_RELEASE_DESTINATION','release store and artifact must not overlap')
    payload={'schema_version':1,'artifact':str(artifact),'artifact_sha256':tree_digest(artifact),
             'destination':str(destination),'scope':scope,'resource_owner':owner,'cost_disclosure':cost,
             'provider':provider,'backup_strategy':'retain previous immutable release; rollback pointer on failed smoke check',
             'credentials':'not included in plan or logs','authorization':None}
    payload['plan_sha256']=plan_digest(payload)
    return payload


def plan_digest(payload):
    frozen={k:v for k,v in payload.items() if k not in ('authorization','plan_sha256')}
    return hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest()


def authorize(payload: dict, expected_sha: str, quote: str) -> dict:
    if expected_sha!=plan_digest(payload) or payload.get('plan_sha256')!=expected_sha:
        raise Problem('STALE_RELEASE_PLAN','plan changed; inspect and approve the new version')
    if not isinstance(quote,str) or not quote.strip(): raise Problem('AUTHORIZATION_REQUIRED','explicit operation-specific authorization is required')
    return {**payload,'authorization':{'plan_sha256':expected_sha,'quote':quote.strip()}}


class LocalDirectoryProvider:
    name='local-directory'
    public=False
    def __init__(self,destination): self.destination=Path(destination)
    def deploy(self,artifact,version):
        target=self.destination/'releases'/version
        if target.exists():
            if tree_digest(target)!=version: raise Problem('RELEASE_CORRUPTED','existing immutable release differs')
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            staging=Path(tempfile.mkdtemp(prefix='.release-',dir=target.parent))
            try:
                shutil.copytree(artifact,staging,dirs_exist_ok=True)
                if tree_digest(staging)!=version: raise Problem('ARTIFACT_CHANGED','artifact changed while copying')
                os.replace(staging,target)
            finally:
                if staging.exists(): shutil.rmtree(staging)
        pointer=self.destination/'current.json'
        prior=read_json(pointer) if pointer.exists() else None
        atomic_json(pointer,{'version':version,'path':str(target)})
        return {'version':version,'path':str(target),'prior':prior,'entry':str(target/'index.html')}
    def smoke(self,receipt):
        target=Path(receipt['path'])
        return {'ok':(target/'index.html').is_file() and tree_digest(target)==receipt['version'],
                'kind':'local_file_integrity','user_access':'not_verified','public_access':False}
    def rollback(self,receipt):
        pointer=self.destination/'current.json'
        if receipt['prior'] is None:
            if pointer.exists(): pointer.unlink()
        else: atomic_json(pointer,receipt['prior'])
        return {'restored':receipt['prior'],'kind':'local_pointer'}


def execute(payload: dict, provider=None) -> dict:
    authorization=payload.get('authorization') or {}
    digest=plan_digest(payload)
    if payload.get('plan_sha256')!=digest or authorization.get('plan_sha256')!=digest or not authorization.get('quote'):
        raise Problem('AUTHORIZATION_REQUIRED','approve this exact release plan before executing')
    artifact=Path(payload['artifact'])
    if tree_digest(artifact)!=payload['artifact_sha256']: raise Problem('ARTIFACT_CHANGED','build changed after authorization')
    provider=provider or LocalDirectoryProvider(payload['destination'])
    if provider.name!=payload['provider']: raise Problem('PROVIDER_MISMATCH','execution provider differs from approved plan')
    if payload['scope']=='public' and not provider.public:
        raise Problem('PUBLIC_PROVIDER_UNAVAILABLE','local directory copy does not publish a website',
                      'Configure a reviewed real provider and obtain fresh authorization; no operation was executed.')
    receipt=provider.deploy(artifact,payload['artifact_sha256'])
    try:
        smoke=provider.smoke(receipt)
        if not isinstance(smoke,dict) or smoke.get('ok') is not True:
            raise Problem('RELEASE_ENTRY_FAILED','deployment completed but entry smoke check failed')
    except Exception as exc:
        try: rollback=provider.rollback(receipt)
        except Exception as rollback_exc:
            raise Problem('ROLLBACK_FAILED','smoke check and rollback failed; preserve release store and inspect: '+str(rollback_exc)) from exc
        return {'status':'blocked','error':str(exc),'rollback':rollback,'public_deployed':False}
    return {'status':'local_copy_verified' if not provider.public else 'provider_smoke_passed',
            'receipt':receipt,'smoke':smoke,'public_deployed':bool(provider.public),
            'limitations':['Local file integrity is not proof of user reachability.'] if not provider.public else []}
