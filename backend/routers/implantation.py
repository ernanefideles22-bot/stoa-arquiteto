from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import math

from ..models.database import get_db, Project, Terrain, Topography, Implantation
from ..services import ai_engine

router = APIRouter(prefix="/api/implantation", tags=["implantation"])


class ImplantationRequest(BaseModel):
    project_id: int
    typology: str
    programa: dict


class SelectImplantation(BaseModel):
    project_id: int
    implantation_id: int


@router.post("/generate")
async def generate_implantations(data: ImplantationRequest, db: Session = Depends(get_db)):
    """Gera 3 alternativas de implantacao via IA."""
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(404, "Projeto nao encontrado")

    terrain = db.query(Terrain).filter(Terrain.project_id == data.project_id).first()
    topo    = db.query(Topography).filter(Topography.project_id == data.project_id).first()
    if not terrain or not topo:
        raise HTTPException(400, "Analise de terreno necessaria antes da implantacao")

    terrain_ctx = {
        "address": terrain.address,
        "city": terrain.city, "state": terrain.state,
        "area_ha": terrain.area_ha, "area_m2": terrain.area_m2,
        "typology_intent": data.typology,
    }
    topo_ctx = {
        "alt_min": topo.alt_min, "alt_max": topo.alt_max,
        "desnivel": topo.desnivel, "decl_media": topo.decl_media,
        "decl_max": topo.decl_max,
        "orientacao_predominante": topo.orientacao_predominante,
        "zonas": topo.zonas,
        "area_util_m2": topo.area_util_m2,
        "area_restrita_m2": topo.area_restrita_m2,
    }

    result = await ai_engine.gerar_alternativas_implantacao(
        terrain_ctx, topo_ctx, data.typology, data.programa
    )

    db.query(Implantation).filter(Implantation.project_id == data.project_id).delete()

    saved = []
    for alt in result.get("alternativas", []):
        prog   = alt.get("programa", {})
        scores = alt.get("scores", {})
        imp = Implantation(
            project_id=data.project_id,
            nome=alt.get("nome"),
            descricao=alt.get("conceito"),
            score_tecnico=scores.get("tecnico"),
            score_economico=scores.get("economico"),
            score_ambiental=scores.get("ambiental"),
            score_total=scores.get("viabilidade"),
            num_lotes=prog.get("num_lotes"),
            area_media_lote=prog.get("area_media_lote_m2"),
            area_construida_total=prog.get("area_construida_total_m2"),
            area_verde=prog.get("area_verde_m2"),
            area_vias=prog.get("area_vias_m2"),
            area_equipamentos=prog.get("area_equipamentos_m2"),
            justificativa=alt.get("conceito"),
            vantagens=alt.get("vantagens"),
            desvantagens=alt.get("desvantagens"),
        )
        db.add(imp)
        db.flush()
        saved.append({
            "id": imp.id,
            "nome": imp.nome,
            "descricao": imp.descricao,
            "num_lotes": imp.num_lotes,
            "area_media_lote": imp.area_media_lote,
            "scores": scores,
            "vantagens": imp.vantagens,
            "desvantagens": imp.desvantagens,
            "custo_estimado": alt.get("custo_estimado_infraestrutura"),
            "vgv_estimado": alt.get("vgv_estimado"),
            "prazo_meses": alt.get("prazo_obra_meses"),
        })

    db.commit()
    return {"alternativas": saved, "recomendacao": result.get("recomendacao")}


@router.post("/select")
def select_implantation(data: SelectImplantation, db: Session = Depends(get_db)):
    """Marca uma alternativa como selecionada e gera posicoes dos lotes."""
    db.query(Implantation).filter(
        Implantation.project_id == data.project_id
    ).update({"is_selected": False})

    imp = db.query(Implantation).filter(
        Implantation.id == data.implantation_id,
        Implantation.project_id == data.project_id,
    ).first()
    if not imp:
        raise HTTPException(404, "Implantacao nao encontrada")

    imp.is_selected = True

    # Generate normalized (x, z) grid positions for each lote [0..1]
    n = imp.num_lotes or 0
    if n > 0:
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        lotes_data = [
            {
                "x": round((i % cols + 1) / (cols + 1), 4),
                "z": round((i // cols + 1) / (rows + 1), 4),
                "area": float(imp.area_media_lote or 300),
            }
            for i in range(min(n, 40))
        ]
        imp.lotes = lotes_data

    db.commit()
    return {"ok": True, "selected": imp.nome, "lotes_count": len(imp.lotes) if imp.lotes else 0}


@router.get("/{project_id}")
def get_implantations(project_id: int, db: Session = Depends(get_db)):
    imps = db.query(Implantation).filter(
        Implantation.project_id == project_id
    ).all()
    return [
        {k: v for k, v in i.__dict__.items() if not k.startswith("_")}
        for i in imps
    ]
