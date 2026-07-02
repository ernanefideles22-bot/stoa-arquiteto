"""Projetos: CRUD, flags do fluxo e o DELETE que ja quebrou uma vez."""
from backend.models.database import SessionLocal, Terrain, Implantation, Financial, Topography


def test_criar_e_listar(client, projeto):
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert any(p["id"] == projeto["id"] for p in r.json())


def test_flags_do_fluxo(client, projeto, db):
    pid = projeto["id"]
    r = client.get(f"/api/projects/{pid}").json()
    assert r["has_terrain"] is False and r["has_financial"] is False

    db.add(Terrain(project_id=pid, city="X"))
    db.add(Implantation(project_id=pid, nome="a", is_selected=False, score_total=7.0))
    db.commit()
    r = client.get(f"/api/projects/{pid}").json()
    assert r["has_terrain"] is True
    assert r["has_implantation"] is True
    assert r["has_implantation_selected"] is False   # gerada != selecionada

    db.query(Implantation).update({"is_selected": True})
    db.commit()
    r = client.get(f"/api/projects/{pid}").json()
    assert r["has_implantation_selected"] is True


def test_delete_projeto_com_filhos(client, projeto, db):
    """Regressao do bug do PR #2: FK sem cascade estourava 500."""
    pid = projeto["id"]
    db.add(Terrain(project_id=pid, city="X"))
    db.add(Topography(project_id=pid))
    db.add(Financial(project_id=pid, vgv=1.0))
    db.commit()

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert client.get(f"/api/projects/{pid}").status_code == 404
    s = SessionLocal()
    assert s.query(Terrain).filter_by(project_id=pid).count() == 0
    assert s.query(Financial).filter_by(project_id=pid).count() == 0
    s.close()


def test_delete_inexistente_404(client):
    assert client.delete("/api/projects/99999").status_code == 404


def test_erro_500_nao_vaza_traceback(client, projeto, monkeypatch):
    """Regressao do vazamento: 500 nunca pode expor traceback em producao."""
    import backend.routers.projects as pr
    def explode(*a, **k):
        raise RuntimeError("segredo-interno postgres.abc")
    monkeypatch.setattr(pr, "_serialize", explode)
    r = client.get("/api/projects")
    assert r.status_code == 500
    body = r.text
    assert "segredo-interno" not in body and "Traceback" not in body
