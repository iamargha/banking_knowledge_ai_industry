import secrets
from fastapi import Header, HTTPException, Depends
from .config import settings

# Replace this dependency with OIDC/JWT validation (e.g. Entra ID) before any shared deployment.
# Never accept department/classification claims directly from an untrusted request header.
def require_demo_identity(x_api_key: str | None = Header(default=None, alias='X-API-Key')) -> dict:
    if settings.environment != 'local':
        raise HTTPException(status_code=503, detail='Production identity provider is not configured')
    #if not settings.app_api_key or not x_api_key or not secrets.compare_digest(x_api_key, settings.app_api_key):
    #    raise HTTPException(status_code=401, detail='Invalid credentials')
    return {'sub': 'local-demo-user', 'departments': ['PUBLIC', 'OPERATIONS', 'RISK', 'COMPLIANCE', 'HR'], 'clearance': 'INTERNAL'}

Identity = Depends(require_demo_identity)
