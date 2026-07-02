"""
Fixtures da suite do STOA.

Principios:
- ZERO rede: IA (Anthropic) e geo-APIs sao mockadas; banco e SQLite local.
- Auth desligada por padrao (AUTH_ENABLED=false); os testes de auth ligam
  explicitamente e injetam uma chave ES256 forjada no cache de JWKS.
"""
import os
import sys
import time
import pathlib

# Precisa acontecer ANTES de importar backend.* (database.py le no import)
_DB_PATH = pathlib.Path(__file__).parent / "_test_stoa.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["AUTH_ENABLED"] = "false"
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-teste-nao-usado")

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from backend.models.database import (Base, engine, SessionLocal, Project,
                                     Terrain, Topography, Implantation,
                                     Financial, Report)
import backend.main as main_mod


@pytest.fixture(scope="session")
def app():
    Base.metadata.create_all(bind=engine)
    yield main_mod.app
    Base.metadata.drop_all(bind=engine)
    if _DB_PATH.exists():
        _DB_PATH.unlink()


@pytest.fixture()
def client(app):
    os.environ["AUTH_ENABLED"] = "false"
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db(app):
    """Cada teste comeca com o banco vazio."""
    yield
    db = SessionLocal()
    for model in (Report, Financial, Implantation, Topography, Terrain, Project):
        db.query(model).delete()
    db.commit()
    db.close()


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def projeto(client):
    r = client.post("/api/projects", json={
        "name": "Teste", "client": "Cliente", "typology": "condominio_loteamento"})
    assert r.status_code == 200
    return r.json()


# ── Auth: chave ES256 local simulando o Supabase ──────────────────────────
from cryptography.hazmat.primitives.asymmetric import ec
import jwt as pyjwt

_PRIV = ec.generate_private_key(ec.SECP256R1())


def make_token(email="ernanefideles22@gmail.com", exp_offset=3600, aud="authenticated"):
    return pyjwt.encode(
        {"email": email, "sub": "u-test", "aud": aud,
         "exp": int(time.time()) + exp_offset},
        _PRIV, algorithm="ES256", headers={"kid": "kid-teste"})


@pytest.fixture()
def auth_on():
    """Liga a auth e injeta a chave forjada no cache de JWKS."""
    from backend.services import auth as auth_mod
    auth_mod._jwks_cache.update(
        keys={"kid-teste": _PRIV.public_key()}, fetched_at=time.time() + 1e9)
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ALLOWED_EMAILS"] = "ernanefideles22@gmail.com"
    yield
    os.environ["AUTH_ENABLED"] = "false"
