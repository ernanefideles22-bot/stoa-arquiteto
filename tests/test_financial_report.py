"""Financeiro + Relatorio: regressao do bug original do PDF zerado (PR #1/#2)."""
import base64
import json

from backend.models.database import Terrain, Topography, Implantation


RESULT_IA = {
    "custos": {"infraestrutura_loteamento": 2_000_000, "total": 5_000_000},
    "receitas": {"vgv_total": 18_700_000, "preco_medio_por_lote": 467_500},
    "resultado": {"lucro_bruto": 6_696_250, "margem_bruta_percent": 35.8,
                  "roi_percent": 55.8, "payback_meses": 18},
    "cenarios": {"base": {"vgv": 18_700_000, "margem": 35.8}},
    "recomendacoes_financeiras": ["rec 1", "rec 2"],
    "alertas": ["alerta 1"],
    "fluxo_caixa_anual": [], "cronograma_financeiro": {},
}


def _setup(client, projeto, db, monkeypatch):
    pid = projeto["id"]
    db.add(Terrain(project_id=pid, city="Nova Lima", state="MG", area_ha=5.0))
    db.add(Topography(project_id=pid))
    db.add(Implantation(project_id=pid, nome="alt", is_selected=True,
                        num_lotes=40, area_media_lote=650.0))
    db.commit()

    import backend.routers.financial as fin_router
    async def fake_viab(*a, **k):
        return dict(RESULT_IA)
    monkeypatch.setattr(fin_router.ai_engine, "calcular_viabilidade", fake_viab)
    monkeypatch.setattr(fin_router.chart_service, "gerar_grafico_financeiro",
                        lambda *_: "data:image/svg+xml;base64,")
    return pid


def test_financial_grava_colunas_e_json_valido(client, projeto, db, monkeypatch):
    pid = _setup(client, projeto, db, monkeypatch)
    r = client.post("/api/financial/analyze", json={"project_id": pid, "cenario": "base"})
    assert r.status_code == 200

    fin = client.get(f"/api/financial/{pid}").json()
    assert fin["vgv"] == 18_700_000
    assert fin["roi"] == 55.8
    assert fin["payback_meses"] == 18
    # O bug original: analise_ia era str(lista) e quebrava o json.loads
    parsed = json.loads(fin["analise_ia"])
    assert parsed["recomendacoes_financeiras"] == ["rec 1", "rec 2"]
    assert parsed["alertas"] == ["alerta 1"]


def test_report_pdf_com_numeros(client, projeto, db, monkeypatch):
    pid = _setup(client, projeto, db, monkeypatch)
    client.post("/api/financial/analyze", json={"project_id": pid, "cenario": "base"})

    import backend.routers.report as rep_router
    async def fake_resumo(_):
        return "Resumo executivo de teste."
    monkeypatch.setattr(rep_router.ai_engine, "gerar_resumo_executivo", fake_resumo)

    r = client.post("/api/report/generate", json={"project_id": pid})
    assert r.status_code == 200
    data = r.json()
    assert data["has_financeiro"] is True
    pdf = base64.b64decode(data["pdf_base64"])
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 2000


def test_report_debug_fields_ocultos_em_producao(client, projeto, db, monkeypatch):
    pid = _setup(client, projeto, db, monkeypatch)
    import backend.routers.report as rep_router
    async def resumo_quebrado(_):
        raise RuntimeError("erro-interno-da-ia com-detalhe-sensivel")
    monkeypatch.setattr(rep_router.ai_engine, "gerar_resumo_executivo", resumo_quebrado)

    r = client.post("/api/report/generate", json={"project_id": pid})
    assert r.status_code == 200
    data = r.json()
    assert data["debug_resumo_error"] is None            # gated
    assert "com-detalhe-sensivel" not in data["resumo_executivo"]
