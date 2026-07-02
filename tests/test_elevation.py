"""Elevation p/ o viewer 3D: regressao do fix do PR #1 (implantacao selecionada)."""
import json
from backend.models.database import Terrain, Topography, Implantation


def _setup(db, pid, selecionada=True):
    db.add(Terrain(project_id=pid, area_ha=5.0, lat=-19.98, lon=-43.84))
    db.add(Topography(project_id=pid, elevation_grid=json.dumps({"n": 2, "elevations": [[1, 2], [3, 4]]})))
    db.add(Implantation(project_id=pid, nome="primeira-gerada", is_selected=False,
                        score_total=9.9, num_lotes=99,
                        lotes=json.dumps([{"tipo": "lote", "area": 1}])))
    db.add(Implantation(project_id=pid, nome="escolhida", is_selected=selecionada,
                        score_total=5.0, num_lotes=40,
                        lotes=json.dumps([{"tipo": "lote", "area": 650}] * 2)))
    db.commit()


def test_usa_implantacao_selecionada(client, projeto, db):
    """Antes do fix, .first() pegava uma implantacao arbitraria — nao a escolhida."""
    pid = projeto["id"]
    _setup(db, pid, selecionada=True)
    r = client.get(f"/api/terrain/{pid}/elevation")
    assert r.status_code == 200
    assert r.json()["num_lotes"] == 40          # a selecionada, nao a de maior score


def test_fallback_maior_score_sem_selecao(client, projeto, db):
    pid = projeto["id"]
    _setup(db, pid, selecionada=False)
    r = client.get(f"/api/terrain/{pid}/elevation")
    assert r.status_code == 200
    assert r.json()["num_lotes"] == 99          # fallback: maior score_total
