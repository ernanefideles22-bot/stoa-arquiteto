"""
Autenticacao via Supabase Auth (JWT).

O frontend autentica com supabase-js e manda o access_token em
Authorization: Bearer. Aqui o token e verificado com a chave PUBLICA do
projeto Supabase (JWKS, ES256) — nao precisa de secret no ambiente.

Env vars:
  AUTH_ENABLED     — "false" desliga a exigencia de login (default: true).
  SUPABASE_URL     — URL do projeto (default: producao do STOA).
  ALLOWED_EMAILS   — lista separada por virgula de emails autorizados.
                     Sem isso, QUALQUER pessoa que se cadastrasse teria acesso
                     aos dados — auth sem allowlist nao protege nada num app
                     single-tenant. Default: dono do projeto.
"""
import os
import time
import logging

import httpx
import jwt
from jwt import PyJWK
from fastapi import Header, HTTPException

logger = logging.getLogger("stoa")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ankrlomafgitalnbfhlk.supabase.co").rstrip("/")
_DEFAULT_ALLOWED = "ernanefideles22@gmail.com"

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL = 3600.0


def _auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "true").lower() != "false"


def _allowed_emails() -> set:
    raw = os.getenv("ALLOWED_EMAILS", _DEFAULT_ALLOWED)
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _get_signing_keys() -> dict:
    """Baixa e cacheia o JWKS do Supabase (kid -> chave)."""
    now = time.time()
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < _JWKS_TTL:
        return _jwks_cache["keys"]
    resp = httpx.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=10)
    resp.raise_for_status()
    keys = {k["kid"]: PyJWK(k).key for k in resp.json()["keys"] if "kid" in k}
    _jwks_cache.update(keys=keys, fetched_at=now)
    return keys


async def require_user(authorization: str = Header(default="")) -> dict:
    """Dependency do FastAPI: valida o Bearer token e devolve os claims."""
    if not _auth_enabled():
        return {"email": "auth-disabled@local", "sub": "anonymous"}

    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login necessario")
    token = authorization[7:].strip()

    try:
        kid = jwt.get_unverified_header(token).get("kid")
        keys = _get_signing_keys()
        key = keys.get(kid)
        if key is None:
            # kid desconhecido: forca refresh unico do JWKS (rotacao de chave)
            _jwks_cache["fetched_at"] = 0.0
            key = _get_signing_keys().get(kid)
        if key is None:
            raise HTTPException(401, "Token com chave desconhecida")
        claims = jwt.decode(token, key=key, algorithms=["ES256", "RS256"], audience="authenticated")
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessao expirada — faca login novamente")
    except Exception as e:
        logger.warning("Token invalido: %s", e)
        raise HTTPException(401, "Token invalido")

    email = (claims.get("email") or "").lower()
    if email not in _allowed_emails():
        raise HTTPException(403, "Este email nao esta autorizado a usar o STOA")
    return claims
