"""
Gerador de grÃ¡ficos e mapas â STOA Civil
Gera SVGs puros (sem matplotlib/scipy/Pillow) para reduzir bundle no Vercel.
"""
import numpy as np
import base64
import math


# ââ Paletas âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

DARK_BG  = "#0f1117"
PANEL_BG = "#1a1d27"
TEXT_CLR = "#e0e0e0"
GRID_CLR = "#2a2d3a"
ACCENT   = "#4fc3f7"

SLOPE_COLORS = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"]
SLOPE_LABELS = ["Plano 0-5%", "Suave 5-15%", "Moderado 15-30%", "Ingreme 30-45%", "Muito Ingreme >45%"]


# ââ Helpers ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def _b64(svg: str) -> str:
    """Converte SVG para data URI base64."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()


def _lerp_color(t: float, colors: list) -> str:
    """Interpola entre uma lista de cores hex dado t em [0,1]."""
    if not colors:
        return "#888888"
    t = max(0.0, min(1.0, t))
    seg = len(colors) - 1
    idx = int(t * seg)
    idx = min(idx, seg - 1)
    t2 = t * seg - idx
    c1 = colors[idx]
    c2 = colors[idx + 1]
    r = int(int(c1[1:3], 16) * (1 - t2) + int(c2[1:3], 16) * t2)
    g = int(int(c1[3:5], 16) * (1 - t2) + int(c2[3:5], 16) * t2)
    b = int(int(c1[5:7], 16) * (1 - t2) + int(c2[5:7], 16) * t2)
    return f"#{r:02x}{g:02x}{b:02x}"


TERRAIN_PALETTE = ["#1a5276", "#1e8449", "#f4d03f", "#ca6f1e", "#784212", "#f0f3f4"]


def _slope_color(slope_pct: float) -> str:
    if slope_pct < 5:   return SLOPE_COLORS[0]
    if slope_pct < 15:  return SLOPE_COLORS[1]
    if slope_pct < 30:  return SLOPE_COLORS[2]
    if slope_pct < 45:  return SLOPE_COLORS[3]
    return SLOPE_COLORS[4]


# ââ Mapa TopogrÃ¡fico (heatmap elevaÃ§Ã£o + declividade) ââââââââââââââââââââââââ

def gerar_mapa_topografico(elevation_grid: dict, topo_metrics: dict, area_ha: float) -> str:
    Z = np.array(elevation_grid["elevations"])
    n = elevation_grid["n"]
    res = elevation_grid.get("resolution_m", 100)

    W, H = 560, 280   # Ã¡rea do mapa (cada painel)
    PAD  = 40
    FULL_W = W * 2 + PAD * 3
    FULL_H = H + PAD * 2 + 30 + 20   # +tÃ­tulo +legenda

    z_min, z_max = float(Z.min()), float(Z.max())
    cell_w = W / n
    cell_h = H / n

    dzdx = np.gradient(Z, axis=1) / max(res, 1)
    dzdy = np.gradient(Z, axis=0) / max(res, 1)
    slope = np.sqrt(dzdx ** 2 + dzdy ** 2) * 100

    rects_elev = []
    rects_slope = []
    for i in range(n):
        for j in range(n):
            x = PAD + j * cell_w
            y = PAD + 30 + i * cell_h
            t = (float(Z[i, j]) - z_min) / (z_max - z_min + 1e-9)
            c_elev  = _lerp_color(t, TERRAIN_PALETTE)
            c_slope = _slope_color(float(slope[i, j]))
            rects_elev.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{c_elev}"/>'
            )
            x2 = PAD * 2 + W + j * cell_w
            rects_slope.append(
                f'<rect x="{x2:.1f}" y="{y:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{c_slope}"/>'
            )

    # Legendas de declividade
    leg_y = PAD + 30 + H + 8
    legend_items = []
    for k, (c, lbl) in enumerate(zip(SLOPE_COLORS, SLOPE_LABELS)):
        lx = PAD * 2 + W + k * 110
        legend_items.append(
            f'<rect x="{lx}" y="{leg_y}" width="12" height="12" fill="{c}"/>'
            f'<text x="{lx+16}" y="{leg_y+10}" fill="{TEXT_CLR}" font-size="9">{lbl}</text>'
        )

    info = (f"Alt min={z_min:.0f}m | max={z_max:.0f}m | "
            f"Desnivel={topo_metrics.get('desnivel','?')}m | "
            f"Decl.media={topo_metrics.get('decl_media','?')}%")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{FULL_W}" height="{FULL_H}" viewBox="0 0 {FULL_W} {FULL_H}">
  <rect width="100%" height="100%" fill="{DARK_BG}"/>
  <text x="{FULL_W//2}" y="22" text-anchor="middle" fill="{TEXT_CLR}" font-family="sans-serif" font-size="13" font-weight="bold">Analise Topografica â {area_ha:.0f} ha</text>
  <text x="{PAD + W//2}" y="{PAD+24}" text-anchor="middle" fill="{TEXT_CLR}" font-family="sans-serif" font-size="10">Elevacao (m)</text>
  <text x="{PAD*2 + W + W//2}" y="{PAD+24}" text-anchor="middle" fill="{TEXT_CLR}" font-family="sans-serif" font-size="10">Declividade (%)</text>
  {"".join(rects_elev)}
  {"".join(rects_slope)}
  <rect x="{PAD}" y="{PAD+30}" width="{W}" height="{H}" fill="none" stroke="{GRID_CLR}" stroke-width="1"/>
  <rect x="{PAD*2+W}" y="{PAD+30}" width="{W}" height="{H}" fill="none" stroke="{GRID_CLR}" stroke-width="1"/>
  {"".join(legend_items)}
  <text x="{FULL_W//2}" y="{FULL_H-4}" text-anchor="middle" fill="{ACCENT}" font-family="sans-serif" font-size="9">{info}</text>
</svg>"""

    return _b64(svg)


# ââ GrÃ¡fico de Pizza â Zonas de Declividade ââââââââââââââââââââââââââââââââââ

def gerar_grafico_zonas(zonas: list) -> str:
    zonas_validas = [z for z in zonas if z.get("percentual", 0) > 0]
    if not zonas_validas:
        return _b64(f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="{DARK_BG}"/><text x="200" y="150" text-anchor="middle" fill="{TEXT_CLR}" font-family="sans-serif">Sem dados</text></svg>')

    W, H = 500, 340
    cx, cy, r = 180, 170, 130

    total = sum(z["percentual"] for z in zonas_validas)
    angle = -math.pi / 2   # comeÃ§a em cima

    slices = []
    legend_items = []
    for k, z in enumerate(zonas_validas):
        frac = z["percentual"] / total
        da   = frac * 2 * math.pi
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx + r * math.cos(angle + da)
        y2 = cy + r * math.sin(angle + da)
        large = 1 if da > math.pi else 0
        color = SLOPE_COLORS[k % len(SLOPE_COLORS)]
        slices.append(
            f'<path d="M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 {large},1 {x2:.2f},{y2:.2f} Z" fill="{color}" stroke="{DARK_BG}" stroke-width="2"/>'
        )
        # percentual no centro do slice
        mid_a = angle + da / 2
        tx = cx + (r * 0.65) * math.cos(mid_a)
        ty = cy + (r * 0.65) * math.sin(mid_a)
        if frac > 0.05:
            slices.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="sans-serif" font-size="10" font-weight="bold">{z["percentual"]:.1f}%</text>'
            )
        # legenda
        lx, ly = 340, 80 + k * 38
        legend_items.append(
            f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{color}"/>'
            f'<text x="{lx+20}" y="{ly+11}" fill="{TEXT_CLR}" font-family="sans-serif" font-size="10">{z["tipo"]}</text>'
            f'<text x="{lx+20}" y="{ly+22}" fill="#aaaaaa" font-family="sans-serif" font-size="9">{z["percentual"]:.1f}% â {z.get("area_m2",0):,.0f} mÂ²</text>'
        )
        angle += da

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="100%" height="100%" fill="{DARK_BG}"/>
  <text x="{W//2}" y="22" text-anchor="middle" fill="{TEXT_CLR}" font-family="sans-serif" font-size="13" font-weight

