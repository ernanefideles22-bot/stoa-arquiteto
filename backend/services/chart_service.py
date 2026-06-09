"""
Gerador de graficos - STOA Civil
Gera SVGs puros sem matplotlib.
"""
import base64
import math

DARK_BG = "#0f1117"
TEXT_CLR = "#e0e0e0"
ACCENT = "#4fc3f7"
SLOPE_COLORS = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"]
TERRAIN_PALETTE = ["#1a5276", "#1e8449", "#f4d03f", "#ca6f1e", "#784212", "#f0f3f4"]


def _b64(svg):
    enc = base64.b64encode(svg.encode("utf-8")).decode()
    return "data:image/svg+xml;base64," + enc


def _lerp_color(t, colors):
    t = max(0.0, min(1.0, t))
    n = len(colors) - 1
    i = int(t * n)
    i = min(i, n - 1)
    f = t * n - i
    c0 = colors[i].lstrip("#")
    c1 = colors[i + 1].lstrip("#")
    r = int(int(c0[0:2], 16) * (1 - f) + int(c1[0:2], 16) * f)
    g = int(int(c0[2:4], 16) * (1 - f) + int(c1[2:4], 16) * f)
    b = int(int(c0[4:6], 16) * (1 - f) + int(c1[4:6], 16) * f)
    return "#%02x%02x%02x" % (r, g, b)


def _slope_color(slope_pct):
    if slope_pct < 5:
        return SLOPE_COLORS[0]
    elif slope_pct < 15:
        return SLOPE_COLORS[1]
    elif slope_pct < 30:
        return SLOPE_COLORS[2]
    elif slope_pct < 45:
        return SLOPE_COLORS[3]
    return SLOPE_COLORS[4]


def gerar_mapa_topografico(elevation_grid, topo_metrics, area_ha):
    W = 600
    H = 400
    rows = elevation_grid.get("rows", 10)
    cols = elevation_grid.get("cols", 10)
    data = elevation_grid.get("data", [])
    alt_min = topo_metrics.get("alt_min", 0)
    alt_max = topo_metrics.get("alt_max", 100)
    alt_range = max(alt_max - alt_min, 1)
    cell_w = (W - 80) / max(cols, 1)
    cell_h = (H - 80) / max(rows, 1)

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H))
    out.append('<rect width="100%%" height="100%%" fill="%s"/>' % DARK_BG)
    out.append('<text x="20" y="24" fill="%s" font-family="sans-serif" font-size="13" font-weight="bold">Mapa Topografico - %.1f ha</text>' % (ACCENT, area_ha))

    for idx, val in enumerate(data):
        row = idx // cols
        col = idx % cols
        t = (val - alt_min) / alt_range
        color = _lerp_color(t, TERRAIN_PALETTE)
        x = 40 + col * cell_w
        y = 40 + row * cell_h
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="%s" stroke-width="0.5"/>' % (x, y, cell_w, cell_h, color, DARK_BG))

    out.append('<text x="20" y="%d" fill="#888" font-family="sans-serif" font-size="10">Alt: %dm - %dm</text>' % (H - 8, round(alt_min), round(alt_max)))
    out.append('</svg>')
    return _b64("".join(out))


def gerar_grafico_zonas(zonas):
    W = 500
    H = 340
    cx = 180
    cy = 170
    r = 130
    colors = ["#4fc3f7", "#81c784", "#ffb74d", "#e57373", "#ba68c8", "#4db6ac"]

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H))
    out.append('<rect width="100%%" height="100%%" fill="%s"/>' % DARK_BG)
    out.append('<text x="20" y="24" fill="%s" font-family="sans-serif" font-size="13" font-weight="bold">Distribuicao de Zonas</text>' % ACCENT)

    if not zonas:
        out.append('<text x="%d" y="%d" fill="%s" font-family="sans-serif" font-size="14" text-anchor="middle">Sem dados</text>' % (W // 2, H // 2, TEXT_CLR))
        out.append('</svg>')
        return _b64("".join(out))

    total = sum(z.get("percentual", 0) for z in zonas) or 1
    angle = -math.pi / 2

    for i, z in enumerate(zonas):
        pct = z.get("percentual", 0) / total
        da = pct * 2 * math.pi
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx + r * math.cos(angle + da)
        y2 = cy + r * math.sin(angle + da)
        large = 1 if da > math.pi else 0
        color = colors[i % len(colors)]
        out.append('<path d="M%d,%d L%.1f,%.1f A%d,%d 0 %d,1 %.1f,%.1f Z" fill="%s" stroke="%s" stroke-width="1.5"/>' % (cx, cy, x1, y1, r, r, large, x2, y2, color, DARK_BG))

        lx = 340
        ly = 60 + i * 36
        tipo = z.get("tipo", "")[:18]
        pct_val = z.get("percentual", 0)
        area_val = z.get("area_m2", 0)
        out.append('<rect x="%d" y="%d" width="12" height="12" fill="%s"/>' % (lx, ly, color))
        out.append('<text x="%d" y="%d" fill="%s" font-family="sans-serif" font-size="10">%s</text>' % (lx + 16, ly + 10, TEXT_CLR, tipo))
        out.append('<text x="%d" y="%d" fill="#aaa" font-family="sans-serif" font-size="9">%.1f%% - %.0f m2</text>' % (lx + 16, ly + 22, pct_val, area_val))
        angle += da

    out.append('</svg>')
    return _b64("".join(out))


def gerar_grafico_financeiro(financial):
    W = 600
    H = 380

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H))
    out.append('<rect width="100%%" height="100%%" fill="%s"/>' % DARK_BG)
    out.append('<text x="20" y="28" fill="%s" font-family="sans-serif" font-size="13" font-weight="bold">Analise Financeira</text>' % ACCENT)

    if not financial:
        out.append('<text x="%d" y="%d" fill="%s" font-family="sans-serif" font-size="14" text-anchor="middle">Sem dados financeiros</text>' % (W // 2, H // 2, TEXT_CLR))
        out.append('</svg>')
        return _b64("".join(out))

    custo_total = financial.get("custo_total", 0)
    vgv = financial.get("vgv", 0)
    lucro = financial.get("lucro_bruto", 0)
    margem = financial.get("margem_bruta", 0)
    roi = financial.get("roi", 0)

    items = [("Custo Total", custo_total, "#e74c3c"), ("VGV", vgv, "#2ecc71"), ("Lucro Bruto", lucro, "#4fc3f7")]
    max_val = max(abs(v) for _, v, _ in items) or 1
    bar_h = 50
    bar_gap = 30
    bar_x = 160

    for i, item in enumerate(items):
        label = item[0]
        val = item[1]
        color = item[2]
        bw = max(4, int((abs(val) / max_val) * (W - bar_x - 40)))
        by = 60 + i * (bar_h + bar_gap)
        mid_y = by + bar_h // 2 + 5
        val_m = round(val / 1e6, 2)
        out.append('<text x="%d" y="%d" fill="%s" font-family="sans-serif" font-size="11" text-anchor="end">%s</text>' % (bar_x - 8, mid_y, TEXT_CLR, label))
        out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" rx="3"/>' % (bar_x, by, bw, bar_h, color))
        out.append('<text x="%d" y="%d" fill="%s" font-family="sans-serif" font-size="11">R$ %.2fM</text>' % (bar_x + bw + 8, mid_y, TEXT_CLR, val_m))

    metrics_y = 310
    out.append('<text x="60" y="%d" fill="#aaa" font-family="sans-serif" font-size="11">Margem Bruta:</text>' % metrics_y)
    out.append('<text x="170" y="%d" fill="%s" font-family="sans-serif" font-size="13" font-weight="bold">%.1f%%</text>' % (metrics_y, ACCENT, margem))
    out.append('<text x="280" y="%d" fill="#aaa" font-family="sans-serif" font-size="11">ROI:</text>' % metrics_y)
    out.append('<text x="320" y="%d" fill="%s" font-family="sans-serif" font-size="13" font-weight="bold">%.1f%%</text>' % (metrics_y, ACCENT, roi))
    out.append('</svg>')
    return _b64("".join(out))
