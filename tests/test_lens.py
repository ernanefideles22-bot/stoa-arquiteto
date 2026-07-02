"""Lens: validacoes de entrada e caminho feliz com engine mockado."""
import base64


FAKE_IMG = base64.b64encode(b"x" * 4096).decode()


def _mock_engine(monkeypatch, resultado=None):
    import backend.routers.lens as lens_router
    async def fake(image_b64, media_type, mode, contexto=""):
        return resultado or {"descricao": "mock", "campos_cadastro": {"vegetation": "rasteira"}}
    monkeypatch.setattr(lens_router.lens_engine, "analisar_imagem", fake)


def test_analyze_ok(client, monkeypatch):
    _mock_engine(monkeypatch)
    r = client.post("/api/lens/analyze",
                    json={"mode": "terreno", "image_base64": FAKE_IMG})
    assert r.status_code == 200
    assert r.json()["resultado"]["descricao"] == "mock"


def test_modo_invalido_400(client):
    r = client.post("/api/lens/analyze",
                    json={"mode": "raiox", "image_base64": FAKE_IMG})
    assert r.status_code == 400


def test_base64_invalido_400(client):
    r = client.post("/api/lens/analyze",
                    json={"mode": "terreno", "image_base64": "@@nao-e-base64@@"})
    assert r.status_code == 400


def test_imagem_grande_413(client):
    big = base64.b64encode(b"x" * (5 * 1024 * 1024)).decode()
    r = client.post("/api/lens/analyze",
                    json={"mode": "terreno", "image_base64": big})
    assert r.status_code == 413


def test_media_type_invalido_400(client):
    r = client.post("/api/lens/analyze",
                    json={"mode": "terreno", "image_base64": FAKE_IMG,
                          "media_type": "application/pdf"})
    assert r.status_code == 400
