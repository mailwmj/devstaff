"""Preview manifests distinguish local access from user access and exact artifact version."""
from urllib.parse import urlsplit
from .common import Problem,atomic_json,metadata_dir,project_file,sha256_file


def register(root,artifact,kind='file',url=None,audience='local',user_evidence='',public_quote=''):
    if kind not in ('embedded','url','file','screenshot'): raise Problem('INVALID_PREVIEW_KIND','unsupported preview kind')
    if audience not in ('local','restricted','public'): raise Problem('INVALID_PREVIEW_AUDIENCE','unsupported preview audience')
    file=project_file(root,artifact,True)
    if url:
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise Problem('INVALID_PREVIEW_URL','use an HTTP(S) URL without credentials, query secrets or fragment')
    if kind=='url' and not url: raise Problem('MISSING_PREVIEW_URL','URL preview requires a URL')
    if audience=='public' and not public_quote.strip(): raise Problem('PUBLIC_PREVIEW_UNAUTHORIZED','public preview needs specific authorization')
    data={'schema_version':1,'kind':kind,'artifact':artifact,'artifact_sha256':sha256_file(file),'url':url,'audience':audience,
          'agent_access':'not_checked','user_access':'reported' if user_evidence.strip() else 'unknown',
          'user_evidence':user_evidence.strip(),'interactive':kind!='screenshot',
          'public_authorization_quote':public_quote.strip() or None,
          'limitations':['A file path or agent-local URL does not prove the user can open this exact version.']}
    atomic_json(metadata_dir(root)/'preview.json',data)
    return data


def current(root,manifest): return sha256_file(project_file(root,manifest['artifact'],True))==manifest.get('artifact_sha256')
