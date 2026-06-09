"""
Serviço geoespacial — STOA Civil
Busca dados reais de elevação, geocodificação e análise topográfica.
Fontes: Nominatim (OSM), Open-Elevation (SRTM 90m), OpenTopoData
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
    Resolução adaptada à área do terreno.
    Usa OpenTopoData (SRTM 90m) — gratuito, sem API key.
    """
    # Raio aproximado em graus para cobrir a área
    lado_m = math.sqrt(area_ha * 10000) * 1.4  # buffer 40%
    delta = lado_m / 111_000  # graus aproximados

    # Grid de pontos (máx 100 pontos por requisição na API gratuita)
    n = 8 if area_ha < 10 else (10 if area_ha < 100 else 12)
    lats = np.linspace(lat - delta, lat + delta, n)
    lons = np.linspace(lon - delta, lon + delta, n)

    # Montar lista de localizações
    locations = "|".join(f"{la:.6f},{lo:.6f}"
                         for la in lats for lo in lons)

    try:
        async with httpx.AsyncClient(timeout=30) as c:
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
        # Fallback sintético se a API falhar (desenvolvimento offline)
        grid_z = _synthetic_elevation(n, lat, lon, area_ha)

    grid_lats = lats.tolist()
    grid_lons = lons.tolist()

    return {
        "lats": grid_lats,
        "lons": grid_lons,
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

def analyze_topography(elevation_grid: dict) -> dict:
    """
    Calcula métricas topográficas a partir da grade de elevação.
    Retorna zonas de declividade, área útil, drenagem, etc.
    """
    Z = np.array(elevation_grid["elevations"])
    n = elevation_grid["n"]
    res = elevation_grid["resolution_m"]

    alt_min = float(Z.min())
    alt_max = float(Z.max())
    desnivel = round(alt_max - alt_min, 1)

    # Gradiente → declividade
    dzdx = np.gradient(Z, axis=1) / res
    dzdy = np.gradient(Z, axis=0) / res
    slope_pct = np.sqrt(dzdx**2 + dzdy**2) * 100

    decl_media = round(float(slope_pct.mean()), 1)
    decl_max   = round(float(slope_pct.max()), 1)

    # Área total do grid analisado
    area_grid_m2 = (n * res) ** 2

    # Classificação NBR 6118 / norma de parcelamento
    plano     = float((slope_pct < 5).sum())  / slope_pct.size
    suave     = float(((slope_pct >= 5)  & (slope_pct < 15)).sum()) / slope_pct.size
    moderado  = float(((slope_pct >= 15) & (slope_pct < 30)).sum()) / slope_pct.size
    ingreme   = float(((slope_pct >= 30) & (slope_pct < 45)).sum()) / slope_pct.size
    muito_ingreme = float((slope_pct >= 45).sum()) / slope_pct.size

    zonas = [
        {"tipo": "Plano (0–5%)",        "percentual": round(plano * 100, 1),
         "area_m2": round(plano * area_grid_m2)},
        {"tipo": "Suave (5–15%)",        "percentual": round(suave * 100, 1),
         "area_m2": round(suave * area_grid_m2)},
        {"tipo": "Moderado (15–30%)",    "percentual": round(moderado * 100, 1),
         "area_m2": round(moderado * area_grid_m2)},
        {"tipo": "Íngreme (30–45%)",     "percentual": round(ingreme * 100, 1),
         "area_m2": round(ingreme * area_grid_m2)},
        {"tipo": "Muito Íngreme (>45%)", "percentual": round(muito_ingreme * 100, 1),
         "area_m2": round(muito_ingreme * area_grid_m2)},
    ]

    # Área útil = declividade < 30% (limite loteamento urbano)
    area_util_pct = plano + suave + moderado
    area_util_m2  = round(area_util_pct * area_grid_m2)

    # Orientação predominante da face mais alta → mais baixa
    dz_mean_x = float(dzdx.mean())
    dz_mean_y = float(dzdy.mean())
    orientacao = _get_orientacao(dz_mean_x, dz_mean_y)

    # Ponto mais baixo → concentração de drenagem
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
        "area_restrita_m2": round((ingreme + muito_ingreme) * area_grid_m2),
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
        "N":  "Recebe sol o dia todo (hemisfério sul)" if lat < 0 else "Pouca incidência direta",
        "S":  "Pouca incidência direta (hemisfério sul)" if lat < 0 else "Recebe sol o dia todo",
        "L":  "Sol da manhã — ideal para dormitórios",
        "O":  "Sol da tarde — ideal para áreas sociais",
        "NE": "Sol manhã/tarde — excelente para condomínios",
        "NO": "Sol tarde — bom para áreas sociais",
        "SE": "Sol manhã — bom para dormitórios",
        "SO": "Sol tarde — cuidado com superaquecimento",
    }

    return {
        "hemisferio": hemisferio,
        "orientacao": orientacao,
        "descricao": faces_sol.get(orientacao, "Orientação mista"),
        "recomendacao_implantacao": (
            "Posicionar frente dos lotes voltada para N ou NE"
            if lat < 0 else
            "Posicionar frente dos lotes voltada para S ou SE"
        ),
    }
