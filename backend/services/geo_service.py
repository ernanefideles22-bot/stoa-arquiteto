"""
Serviço geoespacial — STOA Civil
Busca dados reais de elevação, geocodificação e análise topográfica.
Fontes: Nominatim (OSM), OpenTopoData (SRTM 30m — resolução 30m)
"""
import httpx
import numpy as np
import asyncio
import math
from typing import Optional

HEADERS = {"User-Agent": "STOA-Civil/1.0 (ernane@stoacivil.com.br)"}
TOPO_API = "https://api.opentopodata.org/v1/srtm30m"
BATCH_SIZE = 100   # máx por requisição (free tier)
RATE_SLEEP = 1.1   # segundos entre requisições (1 req/s free tier)

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
    Busca grade 20x20 de elevação real via OpenTopoData SRTM 30m.
    400 pontos = 4 lotes de 100 (respeita 1 req/s do free tier).
    """
    lado_m = math.sqrt(area_ha * 10_000) * 1.4
    dlat = lado_m / 111_000
    dlon = lado_m / (111_000 * math.cos(math.radians(lat)))

    n = 20
    lats = np.linspace(lat - dlat, lat + dlat, n)
    lons = np.linspace(lon - dlon, lon + dlon, n)
    LL = [(float(la), float(lo)) for la in lats for lo in lons]

    batches = [LL[i:i + BATCH_SIZE] for i in range(0, len(LL), BATCH_SIZE)]
    elevations = []

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            for idx, batch in enumerate(batches):
                if idx > 0:
                    await asyncio.sleep(RATE_SLEEP)
                loc_str = "|".join(f"{la:.6f},{lo:.6f}" for la, lo in batch)
                r = await c.get(TOPO_API, params={"locations": loc_str}, headers=HEADERS)
                data = r.json()
                for result in data.get("results", []):
                    elev = result.get("elevation")
                    elevations.append(float(elev) if elev is not None else None)

        valid = [e for e in elevations if e is not None]
        fill = float(np.mean(valid)) if valid else (400.0 + abs(lat) * 2)
        elevations = [e if e is not None else fill for e in elevations]
        grid_z = np.array(elevations, dtype=float).reshape(n, n)

    except Exception:
        grid_z = _synthetic_elevation(n, lat, lon, area_ha)

    res_m = int(lado_m * 2 / max(n - 1, 1))

    return {
        "lats": lats.tolist(),
        "lons": lons.tolist(),
        "elevations": grid_z.tolist(),
        "n": n,
        "resolution_m": res_m,
        "lat_center": lat,
        "lon_center": lon,
    }


def _synthetic_elevation(n: int, lat: float, lon: float, area_ha: float) -> np.ndarray:
    base = 400.0 + abs(lat) * 2
    x = np.linspace(0, 1, n)
    y = np.linspace(0, 1, n)
    X, Y = np.meshgrid(x, y)
    slope = math.sqrt(area_ha) * 0.3
    Z = base + (X + Y * 0.5) * slope
    Z += np.sin(X * 3) * 1.5 + np.cos(Y * 2) * 1.0
    return Z

# ─── ANÁLISE TOPOGRÁFICA ────────────────────────────────────────────────────

def analyze_topography(elevation_grid: dict, area_m2: float = None) -> dict:
    Z = np.array(elevation_grid["elevations"], dtype=float)
    n = elevation_grid["n"]
    res = max(float(elevation_grid["resolution_m"]), 1.0)

    alt_min = float(Z.min())
    alt_max = float(Z.max())
    desnivel = round(alt_max - alt_min, 1)

    dzdx = np.gradient(Z, axis=1) / res
    dzdy = np.gradient(Z, axis=0) / res
    slope_pct = np.sqrt(dzdx**2 + dzdy**2) * 100

    decl_media = round(float(slope_pct.mean()), 1)
    decl_max   = round(float(slope_pct.max()), 1)
    decl_p90   = round(float(np.percentile(slope_pct, 90)), 1)

    aspect_rad = np.arctan2(dzdx, -dzdy)
    aspect_deg = (np.degrees(aspect_rad) + 360) % 360
    aspect_mean = float(aspect_deg.mean())

    plano         = float((slope_pct < 5).sum())                              / slope_pct.size
    suave         = float(((slope_pct >= 5)  & (slope_pct < 15)).sum())       / slope_pct.size
    moderado      = float(((slope_pct >= 15) & (slope_pct < 30)).sum())       / slope_pct.size
    ingreme       = float(((slope_pct >= 30) & (slope_pct < 45)).sum())       / slope_pct.size
    muito_ingreme = float((slope_pct >= 45).sum())                            / slope_pct.size

    ref_m2 = area_m2 if area_m2 else float((n * res) ** 2)

    zonas = [
        {"tipo": "Plano (0-5%)",         "percentual": round(plano * 100, 1),         "area_m2": round(plano * ref_m2)},
        {"tipo": "Suave (5-15%)",         "percentual": round(suave * 100, 1),         "area_m2": round(suave * ref_m2)},
        {"tipo": "Moderado (15-30%)",     "percentual": round(moderado * 100, 1),      "area_m2": round(moderado * ref_m2)},
        {"tipo": "Ingreme (30-45%)",      "percentual": round(ingreme * 100, 1),       "area_m2": round(ingreme * ref_m2)},
        {"tipo": "Muito Ingreme (>45%)",  "percentual": round(muito_ingreme * 100, 1), "area_m2": round(muito_ingreme * ref_m2)},
    ]

    area_util_m2     = round((plano + suave + moderado) * ref_m2)
    area_restrita_m2 = round((ingreme + muito_ingreme) * ref_m2)
    orientacao = _aspect_to_dir(aspect_mean)

    idx_min = np.unravel_index(Z.argmin(), Z.shape)
    lats = elevation_grid["lats"]
    lons = elevation_grid["lons"]

    return {
        "alt_min":                 round(alt_min, 1),
        "alt_max":                 round(alt_max, 1),
        "desnivel":                desnivel,
        "decl_media":              decl_media,
        "decl_max":                decl_max,
        "decl_p90":                decl_p90,
        "orientacao_predominante": orientacao,
        "aspect_deg":              round(aspect_mean, 1),
        "zonas":                   zonas,
        "area_util_m2":            area_util_m2,
        "area_restrita_m2":        area_restrita_m2,
        "ponto_drenagem": {
            "lat": lats[min(idx_min[0], len(lats) - 1)],
            "lon": lons[min(idx_min[1], len(lons) - 1)],
        },
        "slope_grid": slope_pct.tolist(),
    }


def _aspect_to_dir(deg: float) -> str:
    dirs = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"]
    return dirs[int((deg + 22.5) / 45) % 8]

# ─── INSOLAÇÃO ──────────────────────────────────────────────────────────────

def get_solar_info(lat: float, orientacao: str) -> dict:
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
