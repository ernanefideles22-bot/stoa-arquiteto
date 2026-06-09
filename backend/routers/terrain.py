from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from ..models.database import get_db, Project, Terrain, Topography
from ..services import geo_service, ai_engine, chart_service

router = APIRouter(prefix="/api/terrain", tags=["terrain"])


class TerrainSave(BaseModel):
    project_id: int
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    area_ha: float
    topografia: Optional[str] = "ondulado"
    vegetacao: Optional[str] = "rasteira"
    acesso: Optional[str] = "via pavimentada"
    infraestrutura: Optional[List[str]] = []
    zoneamento: Optional[str] = None
    notas: Optional[str] = None
    typology_intent: Optional[str] = None


class TerrainAnalyze(BaseModel):
    project_id: int


@router.post("/save")
async def save_terrain(data: TerrainSave, db: Session = Depends(get_db)):
    """
    Passo 1: salva dados do terreno e geocodifica endereco.
    Rapido (~3s), sem analise de elevacao nem IA.
    """
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(404, "Projeto nao encontrado")

    lat, lon = data.lat, data.lon
    address_display = data.address or ""
    city, state = data.city, data.state

    # Geocodificar se nao tiver coordenadas
    if not lat and data.address:
        try:
            geo = await geo_service.geocode_address(
                f"{data.address}, {data.city or ''}, {data.state or ''}, Brasil"
            )
            if geo:
                lat, lon = geo["lat"], geo["lon"]
                city = city or geo.get("city")
                state = state or geo.get("state")
                address_display = geo.get("display_name", data.address)
        except Exception:
            pass

    area_m2 = data.area_ha * 10_000

    terrain_db = db.query(Terrain).filter(Terrain.project_id == data.project_id).first()
    if not terrain_db:
        terrain_db = Terrain(project_id=data.project_id)
        db.add(terrain_db)

    terrain_db.address = address_display or data.address
    terrain_db.city = city
    terrain_db.state = state
    terrain_db.lat = lat
    terrain_db.lon = lon
    terrain_db.area_ha = data.area_ha
    terrain_db.area_m2 = area_m2
    terrain_db.topografia = data.topografia
    terrain_db.vegetacao = data.vegetacao
    terrain_db.acesso = data.acesso
    terrain_db.infraestrutura = data.infraestrutura
    terrain_db.zoneamento = data.zoneamento
    terrain_db.notas = data.notas
    db.commit()

    return {
        "status": "saved",
        "lat": lat,
        "lon": lon,
        "address": terrain_db.address,
        "area_ha": data.area_ha,
        "area_m2": area_m2,
    }


@router.post("/analyze")
async def analyze_terrain(data: TerrainAnalyze, db: Session = Depends(get_db)):
    """
    Passo 2: busca elevacao real + analise por IA.
    Mais lento (~30s), requer maxDuration:60 no Vercel Pro.
    """
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(404, "Projeto nao encontrado")

    terrain_db = db.query(Terrain).filter(Terrain.project_id == data.project_id).first()
    if not terrain_db:
        raise HTTPException(400, "Salve os dados do terreno primeiro")
    if not terrain_db.lat:
        raise HTTPException(400, "Coordenadas nao encontradas. Informe endereco ou clique no mapa.")

    lat, lon = terrain_db.lat, terrain_db.lon
    area_m2 = terrain_db.area_m2 or (terrain_db.area_ha * 10_000)

    # Grade de elevacao (SRTM via OpenTopoData, fallback sintetico)
    elevation_grid = await geo_service.get_elevation_grid(lat, lon, terrain_db.area_ha)

    # Metricas topograficas
    topo_metrics = geo_service.analyze_topography(elevation_grid, area_m2=area_m2)

    # Insolacao
    solar = geo_service.get_solar_info(lat, topo_metrics["orientacao_predominante"])

    # Contexto para IA
    terrain_ctx = {
        "address": terrain_db.address,
        "city": terrain_db.city,
        "state": terrain_db.state,
        "area_ha": terrain_db.area_ha,
        "area_m2": area_m2,
        "typology_intent": terrain_db.notas or project.typology,
        "vegetacao": terrain_db.vegetacao,
        "acesso": terrain_db.acesso,
        "infraestrutura": terrain_db.infraestrutura or [],
        "zoneamento": terrain_db.zoneamento,
    }
    ia_result = await ai_engine.analisar_terreno(terrain_ctx, topo_metrics)

    # Converter grade para formato do chart_service
    n = elevation_grid["n"]
    flat_elevations = [val for row in elevation_grid["elevations"] for val in row]
    chart_grid = {"rows": n, "cols": n, "data": flat_elevations}

    img_topo = chart_service.gerar_mapa_topografico(chart_grid, topo_metrics, terrain_db.area_ha)
    img_zonas = chart_service.gerar_grafico_zonas(topo_metrics["zonas"])

    # Salvar topografia
    topo_db = db.query(Topography).filter(Topography.project_id == data.project_id).first()
    if not topo_db:
        topo_db = Topography(project_id=data.project_id)
        db.add(topo_db)

    topo_db.elevation_grid = elevation_grid
    topo_db.alt_min = topo_metrics["alt_min"]
    topo_db.alt_max = topo_metrics["alt_max"]
    topo_db.desnivel = topo_metrics["desnivel"]
    topo_db.decl_media = topo_metrics["decl_media"]
    topo_db.decl_max = topo_metrics["decl_max"]
    topo_db.orientacao_predominante = topo_metrics["orientacao_predominante"]
    topo_db.zonas = topo_metrics["zonas"]
    topo_db.area_util_m2 = topo_metrics["area_util_m2"]
    topo_db.area_restrita_m2 = topo_metrics["area_restrita_m2"]
    topo_db.direcao_drenagem = [topo_metrics["ponto_drenagem"]]
    topo_db.img_topografia = img_topo
    topo_db.img_declividade = img_zonas
    topo_db.analise_ia = ia_result.get("resumo")
    topo_db.pontos_fortes = ia_result.get("pontos_fortes")
    topo_db.restricoes = ia_result.get("restricoes")
    topo_db.recomendacoes = ia_result.get("recomendacoes")
    db.commit()

    return {
        "status": "ok",
        "terrain": {
            "lat": lat, "lon": lon,
            "address": terrain_db.address,
            "area_ha": terrain_db.area_ha,
            "area_m2": area_m2,
        },
        "topography": {
            **topo_metrics,
            "solar": solar,
            "img_topografia": img_topo,
            "img_zonas": img_zonas,
        },
        "ia": ia_result,
    }


@router.get("/{project_id}")
def get_terrain(project_id: int, db: Session = Depends(get_db)):
    t = db.query(Terrain).filter(Terrain.project_id == project_id).first()
    topo = db.query(Topography).filter(Topography.project_id == project_id).first()
    if not t:
        raise HTTPException(404, "Terreno nao cadastrado")
    return {
        "terrain": {k: v for k, v in t.__dict__.items() if not k.startswith("_")},
        "topography": {k: v for k, v in topo.__dict__.items() if not k.startswith("_")} if topo else None,
    }
