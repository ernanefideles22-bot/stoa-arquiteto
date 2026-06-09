from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..models.database import get_db, Project, Terrain, Topography, Implantation, Architecture, Financial
from ..services import ai_engine, chart_service

router = APIRouter(prefix="/api/financial", tags=["financial"])


class FinancialRequest(BaseModel):
    project_id: int
    cenario: Optional[str] = "base"
    custo_terreno: Optional[float] = 0


@router.post("/analyze")
async def analyze_financial(data: FinancialRequest, db: Session = Depends(get_db)):
    project   = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(404, "Projeto não encontrado")

    terrain = db.query(Terrain).filter(Terrain.project_id == data.project_id).first()
    imp = db.query(Implantation).filter(
        Implantation.project_id == data.project_id,
        Implantation.is_selected == True
    ).first()

    if not imp:
        # Usar a melhor implantação disponível
        imp = db.query(Implantation).filter(
            Implantation.project_id == data.project_id
        ).order_by(Implantation.score_total.desc()).first()

    if not imp:
        raise HTTPException(400, "Gere e selecione uma implantação antes da análise financeira")

    arch = db.query(Architecture).filter(Architecture.project_id == data.project_id).first()

    terrain_ctx = {
        "city": terrain.city if terrain else "",
        "state": terrain.state if terrain else "",
        "area_ha": terrain.area_ha if terrain else 0,
        "typology_intent": project.typology,
    }
    imp_ctx = {
        "nome": imp.nome,
        "num_lotes": imp.num_lotes,
        "area_media_lote_m2": imp.area_media_lote,
        "area_construida_total_m2": imp.area_construida_total,
        "area_vias_m2": imp.area_vias,
        "custo_estimado_infraestrutura": "",
    }
    arch_ctx = {}
    if arch:
        arch_ctx = {
            "sistema_estrutural": arch.memorial or "",
            "estimativa_custo_m2": "",
        }

    result = await ai_engine.calcular_viabilidade(terrain_ctx, imp_ctx, arch_ctx, data.cenario)

    custos = result.get("custos", {})
    receitas = result.get("receitas", {})
    resultado = result.get("resultado", {})

    # Sobrescrever custo terreno se fornecido
    if data.custo_terreno and data.custo_terreno > 0:
        custos["terreno"] = data.custo_terreno
        total = sum(v for k, v in custos.items() if k not in ("total", "contingencia_percent") and isinstance(v, (int, float)))
        custos["total"] = total
        resultado["lucro_bruto"] = receitas.get("vgv_total", 0) - total
        if receitas.get("vgv_total", 0) > 0:
            resultado["margem_bruta_percent"] = round(
                resultado["lucro_bruto"] / receitas["vgv_total"] * 100, 1
            )

    # Gerar gráfico — passar dict com as chaves que chart_service espera
    chart_input = {
        "custo_total": custos.get("total", 0),
        "vgv": receitas.get("vgv_total", 0),
        "lucro_bruto": resultado.get("lucro_bruto", 0),
        "margem_bruta": resultado.get("margem_bruta_percent", 0),
        "roi": resultado.get("roi_percent", 0),
    }
    img_financeiro = chart_service.gerar_grafico_financeiro(chart_input)

    # Salvar
    fin = db.query(Financial).filter(Financial.project_id == data.project_id).first()
    if not fin:
        fin = Financial(project_id=data.project_id)
        db.add(fin)

    fin.custo_terreno          = custos.get("terreno", data.custo_terreno)
    fin.custo_infraestrutura   = custos.get("infraestrutura_loteamento")
    fin.custo_construcao       = custos.get("construcao")
    fin.custo_projetos         = custos.get("projetos_aprovacoes")
    fin.custo_marketing        = custos.get("marketing_vendas")
    fin.custo_financeiro       = custos.get("financeiro_juros")
    fin.custo_total            = custos.get("total")
    fin.custo_por_lote         = result.get("custo_por_lote")
    fin.custo_por_m2           = result.get("custo_por_m2_construido")
    fin.vgv                    = receitas.get("vgv_total")
    fin.preco_medio_lote       = receitas.get("preco_medio_por_lote")
    fin.preco_m2_venda         = receitas.get("preco_m2_venda")
    fin.lucro_bruto            = resultado.get("lucro_bruto")
    fin.margem_bruta           = resultado.get("margem_bruta_percent")
    fin.roi                    = resultado.get("roi_percent")
    fin.payback_meses          = resultado.get("payback_meses")
    fin.fluxo_caixa            = result.get("fluxo_caixa_anual")
    fin.cronograma_obra        = result.get("cronograma_financeiro")
    fin.analise_ia             = str(result.get("recomendacoes_financeiras", []))
    fin.cenarios               = result.get("cenarios")

    db.commit()

    return {
        **result,
        "img_financeiro": img_financeiro,
    }


@router.get("/{project_id}")
def get_financial(project_id: int, db: Session = Depends(get_db)):
    fin = db.query(Financial).filter(Financial.project_id == project_id).first()
    if not fin:
        raise HTTPException(404, "Análise financeira não encontrada")
    return {k: v for k, v in fin.__dict__.items() if not k.startswith("_")}
