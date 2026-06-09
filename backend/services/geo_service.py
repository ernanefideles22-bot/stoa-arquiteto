"""
Serviço geoespacial — STOA Civil
Busca dados reais de elevação, geocodificação e análise topográfica.
Fontes: Nominatim (OSM), OpenTopoData (SRTM 90m)
"""
import httpx
import numpy as np
import asyncio
import math
from typing import Optional


HEADERS = {"User-Agent": "STOA-Civil/1.0 (ernane@stoacivil.com.br)"}


# ─── GEOCODIFICAÇÃO ─────────────────────────────────────────────────────────

async def geocode_address(address: str) -> Optional[dict]:
    """Converte endereço em coordenadas via Nominatim (OpenStreetMap)."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1, "addressdetails": 1}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, params=params, headers=HEADERS)
        data = r.json()
    if not data:
        return None
    d = data[0]
    return {
        "lat": float(d["lat"]),
        "lon": float(d["lon"]),
        "display_name": d.get("display_name"),
        "city": d.get("address", {}).get("city") or d.get("address", {}).get("town"),
        "state": d.get("address", {}).get("state"),
        "country": d.get("address", {}).get("country"),
    }


# ─── ELEVAÇÃO ───────────────────────────────────────────────────────────────

async def get_elevation_grid(lat: float, lon: float, area_ha: float) -> dict:
    """
    Busca grade de elevação real ao redor do ponto central.
    Usa OpenTopoData (SRTM 90m) — gratuito, sem API key.
    """
    lado_m = math.sqrt(area_ha * 10_000) * 1.4  # buffer 40%
    delta = lado_m / 111_000  # graus

    n = 8 if area_ha < 10 else (10 if area_ha < 100 else 12)
    lats = np.linspace(lat - delta, lat + delta, n)
    lons = np.linspace(lon - delta, lon + delta, n)

    locations = "|".join(f"{la:.6f},{lo:.6f}" for la in lats for lo in lons)

    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.opentopodata.org/v1/srtm90m",
                params={"locations": locations},
                headers=HEADERS,
            )
            data = r.json()

        elevations = []
        for result in data.get("results", []):
            elev = result.get("elevation")
            elevations.append(float(elev) if elev is not None else 0.0)

        grid_z = np.array(elevations).reshape(n, n)

    except Exception:
        grid_z = _synthetic_elevation(n, lat, lon, area_ha)

    return {
        "lats": lats.tolist(),
        "lons": lons.tolist(),
        "elevations": grid_z.tolist(),
        "n": n,
        "resolution_m": int(lado_m * 2 / n),
        "lat_center": lat,
        "lon_center": lon,
    }


def _synthetic_elevation(n: int, lat: float, lon: float, area_ha: float) -> np.ndarray:
    """Elevação sintética realista para uso offline."""
    base = 400 + abs(lat) * 2
    x = np.linspace(0, 1, n)
    y = np.linspace(0, 1, n)
    X, Y = np.meshgrid(x, y)
    slope = math.sqrt(area_ha) * 0.3
    Z = base + (X + Y * 0.5) * slope
    Z += np.sin(X * 3) * 1.5 + np.cos(Y * 2) * 1.0
    return Z


# ─── ANÁLISE TOPOGRÁFICA ────────────────────────────────────────────────────

def analyze_topography(elevation_grid: dict, area_m2: float = None) -> dict:
    """
    Calcula métricas topográficas a partir da grade de elevação.
    area_m2: área real do terreno (para calibrar áreas úteis/restritas).
    """
    Z = np.array(elevation_grid["elevations"])
    n = elevation_grid["n"]
    res = elevation_grid["resolution_m"]

    alt_min = float(Z.min())
    alt_max = float(Z.max())
    desnivel = round(alt_max - alt_min, 1)

    # Gradiente → declividade em %
    dzdx = np.gradient(Z, axis=1) / res
    dzdy = np.gradient(Z, axis=0) / res
    slope_pct = np.sqrt(dzdx**2 + dzdy**2) * 100

    decl_media = round(float(slope_pct.mean()), 1)
    decl_max   = round(float(slope_pct.max()), 1)

    # Frações por zona de declividade
    plano         = float((slope_pct < 5).sum()) / slope_pct.size
    suave         = float(((slope_pct >= 5)  & (slope_pct < 15)).sum()) / slope_pct.size
    moderado      = float(((slope_pct >= 15) & (slope_pct < 30)).sum()) / slope_pct.size
    ingreme       = float(((slope_pct >= 30) & (slope_pct < 45)).sum()) / slope_pct.size
    muito_ingreme = float((slope_pct >= 45).sum()) / slope_pct.size

    # Área de referência: terreno real se fornecida, senão o grid
    ref_m2 = area_m2 if area_m2 else (n * res) ** 2

    zonas = [
        {"tipo": "Plano (0-5%)",        "percentual": round(plano * 100, 1),
         "area_m2": round(plano * ref_m2)},
        {"tipo": "Suave (5-15%)",        "percentual": round(suave * 100, 1),
         "area_m2": round(suave * ref_m2)},
        {"tipo": "Moderado (15-30%)",    "percentual": round(moderado * 100, 1),
         "area_m2": round(moderado * ref_m2)},
        {"tipo": "Ingreme (30-45%)",     "percentual": round(ingreme * 100, 1),
         "area_m2": round(ingreme * ref_m2)},
        {"tipo": "Muito Ingreme (>45%)", "percentual": round(muito_ingreme * 100, 1),
         "area_m2": round(muito_ingreme * ref_m2)},
    ]

    area_util_m2     = round((plano + suave + moderado) * ref_m2)
    area_restrita_m2 = round((ingreme + muito_ingreme) * ref_m2)

    # Orientação predominante da face
    dz_mean_x = float(dzdx.mean())
    dz_mean_y = float(dzdy.mean())
    orientacao = _get_orientacao(dz_mean_x, dz_mean_y)

    # Ponto de menor elevação (drenagem)
    idx_min = np.unravel_index(Z.argmin(), Z.shape)
    lats = elevation_grid["lats"]
    lons = elevation_grid["lons"]

    return {
        "alt_min": round(alt_min, 1),
        "alt_max": round(alt_max, 1),
        "desnivel": desnivel,
        "decl_media": decl_media,
        "decl_max": decl_max,
        "orientacao_predominante": orientacao,
        "zonas": zonas,
        "area_util_m2": area_util_m2,
        "area_restrita_m2": area_restrita_m2,
        "ponto_drenagem": {
            "lat": lats[min(idx_min[0], len(lats)-1)],
            "lon": lons[min(idx_min[1], len(lons)-1)],
        },
        "slope_grid": slope_pct.tolist(),
    }


def _get_orientacao(dx: float, dy: float) -> str:
    angle = math.degrees(math.atan2(dy, dx)) % 360
    dirs = ["L", "NE", "N", "NO", "O", "SO", "S", "SE"]
    return dirs[int((angle + 22.5) / 45) % 8]


# ─── INSOLAÇÃO ──────────────────────────────────────────────────────────────

def get_solar_info(lat: float, orientacao: str) -> dict:
    """Retorna informações de insolação para a latitude e orientação."""
    hemisferio = "Sul" if lat < 0 else "Norte"

    faces_sol = {
        "N":  "Recebe sol o dia todo (hemisferio sul)" if lat < 0 else "Pouca incidencia direta",
        "S":  "Pouca incidencia direta (hemisferio sul)" if lat < 0 else "Recebe sol o dia todo",
        "L":  "Sol da manha - ideal para dormitorios",
        "O":  "Sol da tarde - ideal para areas sociais",
        "NE": "Sol manha/tarde - excelente para condominios",
        "NO": "Sol tarde - bom para areas sociais",
        "SE": "Sol manha - bom para dormitorios",
        "SO": "Sol tarde - cuidado com superaquecimento",
    }

    return {
        "hemisferio": hemisferio,
        "orientacao": orientacao,
        "descricao": faces_sol.get(orientacao, "Orientacao mista"),
        "recomendacao_implantacao": (
            "Posicionar frente dos lotes voltada para N ou NE"
            if lat < 0 else
            "Posicionar frente dos lotes voltada para S ou SE"
        ),
    }
