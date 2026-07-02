"""Auth: a porta tem que estar trancada — e abrir so pra quem deve."""


def test_health_sempre_publico(client, auth_on):
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_api_sem_token_401(client, auth_on):
    r = client.get("/api/projects")
    assert r.status_code == 401


def test_token_valido_200(client, auth_on):
    from tests.conftest import make_token
    r = client.get("/api/projects", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200


def test_email_fora_da_allowlist_403(client, auth_on):
    from tests.conftest import make_token
    r = client.get("/api/projects",
                   headers={"Authorization": f"Bearer {make_token('intruso@evil.com')}"})
    assert r.status_code == 403


def test_token_expirado_401(client, auth_on):
    from tests.conftest import make_token
    r = client.get("/api/projects",
                   headers={"Authorization": f"Bearer {make_token(exp_offset=-100)}"})
    assert r.status_code == 401


def test_token_lixo_401(client, auth_on):
    r = client.get("/api/projects", headers={"Authorization": "Bearer nao.e.jwt"})
    assert r.status_code == 401


def test_auth_desligada_libera(client):
    assert client.get("/api/projects").status_code == 200
