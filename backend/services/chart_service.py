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
    """
    Gera SVG com dois paineis: mapa de elevacao (esquerdo) + mapa de declividade (direito).
    Inclui linhas de contorno aproximadas (deteccao de cruzamentos entre celulas).
    """
    W, H = 760, 440
    PAD = 30
    PW, PH = 310, 310
    P1X, P1Y = PAD + 10, 65
    P2X, P2Y = PAD + PW + 70, 65

    rows = elevation_grid.get("rows", 20)
    cols = elevation_grid.get("cols", 20)
    data_flat = elevation_grid.get("data", [])

    # Montar grade 2D de elevacao
    Z = []
    for r in range(rows):
        row_data = data_flat[r * cols: (r + 1) * cols]
        Z.append(row_data)

    alt_min = topo_metrics.get("alt_min", 0)
    alt_max = topo_metrics.get("alt_max", 100)
    alt_range = max(alt_max - alt_min, 1.0)

    # slope_grid ja vem como lista 2D de analyze_topography
    slope_2d = topo_metrics.get("slope_grid", [])

    cell_w = PW / max(cols, 1)
    cell_h = PH / max(rows, 1)

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H))
    out.append('<rect width="100%%" height="100%%" fill="%s"/>' % DARK_BG)

    # Titulo
    out.append('<text x="20" y="28" fill="%s" font-family="monospace" font-size="13" font-weight="bold">ANALISE TOPOGRAFICA — %.1f ha  |  SRTM 30m</text>' % (ACCENT, area_ha))
    out.append('<text x="20" y="46" fill="#666" font-family="monospace" font-size="10">Grade 20x20 — dados reais de elevacao (OpenTopoData)</text>')

    # ===== PAINEL ESQUERDO: ELEVACAO =====
    out.append('<text x="%d" y="%d" fill="#999" font-family="monospace" font-size="10">MAPA DE ELEVACAO</text>' % (P1X, P1Y - 8))

    # Celulas de elevacao
    for r in range(rows):
        for c in range(cols):
            val = Z[r][c] if r < len(Z) and c < len(Z[r]) else alt_min
            t = (val - alt_min) / alt_range
            color = _lerp_color(t, TERRAIN_PALETTE)
            x = P1X + c * cell_w
            y = P1Y + r * cell_h
            out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>' % (
                x, y, cell_w + 0.6, cell_h + 0.6, color))

    # Linhas de contorno: detectar cruzamentos entre celulas adjacentes
    n_contours = 7
    contour_levels = [alt_min + (i + 1) * alt_range / (n_contours + 1) for i in range(n_contours)]

    for level in contour_levels:
        # Bordas verticais (entre colunas): cruzamento horizontal
        for r in range(rows):
            for c in range(cols - 1):
                v0 = Z[r][c] if r < len(Z) and c < len(Z[r]) else alt_min
                v1 = Z[r][c + 1] if r < len(Z) and c + 1 < len(Z[r]) else alt_min
                if (v0 <= level < v1) or (v1 <= level < v0):
                    ex = P1X + (c + 1) * cell_w
                    ey1 = P1Y + r * cell_h
                    ey2 = P1Y + (r + 1) * cell_h
                    out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="white" stroke-width="0.8" opacity="0.45"/>' % (
                        ex, ey1, ex, ey2))
        # Bordas horizontais (entre linhas): cruzamento vertical
        for r in range(rows - 1):
            for c in range(cols):
                v0 = Z[r][c] if r < len(Z) and c < len(Z[r]) else alt_min
                v1 = Z[r + 1][c] if r + 1 < len(Z) and c < len(Z[r + 1]) else alt_min
                if (v0 <= level < v1) or (v1 <= level < v0):
                    ex1 = P1X + c * cell_w
                    ex2 = P1X + (c + 1) * cell_w
                    ey = P1Y + (r + 1) * cell_h
                    out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="white" stroke-width="0.8" opacity="0.45"/>' % (
                        ex1, ey, ex2, ey))

    # Labels de elevacao nos cantos
    corner_labels = [(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)]
    for (lr, lc) in corner_labels:
        val = Z[lr][lc] if lr < len(Z) and lc < len(Z[lr]) else alt_min
        lx = P1X + lc * cell_w + (4 if lc == 0 else -4)
        ly = P1Y + lr * cell_h + (12 if lr == 0 else -3)
        anchor = "start" if lc == 0 else "end"
        out.append('<text x="%.1f" y="%.1f" fill="white" font-family="monospace" font-size="9" text-anchor="%s" opacity="0.9">%.0fm</text>' % (
            lx, ly, anchor, val))

    # Barra de legenda de elevacao (gradiente simulado)
    leg_x = P1X
    leg_y = P1Y + PH + 10
    leg_w = PW
    leg_h = 8
    seg = leg_w // len(TERRAIN_PALETTE)
    for i, color in enumerate(TERRAIN_PALETTE):
        out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (
            leg_x + i * seg, leg_y, seg + 1, leg_h, color))
    out.append('<text x="%d" y="%d" fill="#aaa" font-family="monospace" font-size="9">%.0fm</text>' % (leg_x, leg_y + 20, alt_min))
    out.append('<text x="%d" y="%d" fill="#aaa" font-family="monospace" font-size="9" text-anchor="end">%.0fm</text>' % (leg_x + leg_w, leg_y + 20, alt_max))

    # Rosa dos ventos
    cx_r = P1X + PW - 18
    cy_r = P1Y + 18
    out.append('<circle cx="%.1f" cy="%.1f" r="14" fill="#1a1a2e" stroke="#444" stroke-width="1" opacity="0.85"/>' % (cx_r, cy_r))
    out.append('<text x="%.1f" y="%.1f" fill="white" font-family="sans-serif" font-size="9" text-anchor="middle" font-weight="bold">N</text>' % (cx_r, cy_r - 6))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="white" stroke-width="1.5" opacity="0.9"/>' % (cx_r, cy_r - 4, cx_r, cy_r + 6))
    out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" opacity="0.9"/>' % (
        cx_r, cy_r - 4, cx_r - 3, cy_r + 2, cx_r + 3, cy_r + 2, ACCENT))

    # ===== PAINEL DIREITO: DECLIVIDADE =====
    out.append('<text x="%d" y="%d" fill="#999" font-family="monospace" font-size="10">MAPA DE DECLIVIDADE</text>' % (P2X, P2Y - 8))

    for r in range(rows):
        for c in range(cols):
            sv = 0.0
            if slope_2d and r < len(slope_2d):
                row_s = slope_2d[r]
                if isinstance(row_s, list) and c < len(row_s):
                    sv = float(row_s[c])
            color = _slope_color(sv)
            x = P2X + c * cell_w
            y = P2Y + r * cell_h
            out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>' % (
                x, y, cell_w + 0.6, cell_h + 0.6, color))

    # Legenda de declividade
    slope_classes = [
        (SLOPE_COLORS[0], "Plano", "0-5%"),
        (SLOPE_COLORS[1], "Suave", "5-15%"),
        (SLOPE_COLORS[2], "Moder.", "15-30%"),
        (SLOPE_COLORS[3], "Ingreme", "30-45%"),
        (SLOPE_COLORS[4], "M.Ing.", ">45%"),
    ]
    leg2_x = P2X
    leg2_y = P1Y + PH + 10
    for i, (sc, sl, sr) in enumerate(slope_classes):
        lx = leg2_x + i * 63
        out.append('<rect x="%d" y="%d" width="10" height="10" fill="%s"/>' % (lx, leg2_y, sc))
        out.append('<text x="%d" y="%d" fill="#ccc" font-family="monospace" font-size="9">%s</text>' % (lx + 13, leg2_y + 8, sl))
        out.append('<text x="%d" y="%d" fill="#777" font-family="monospace" font-size="8">%s</text>' % (lx + 13, leg2_y + 18, sr))

    # ===== BARRA DE METRICAS NA BASE =====
    metrics_y = H - 10
    decl_media = topo_metrics.get("decl_media", 0)
    decl_p90   = topo_metrics.get("decl_p90", topo_metrics.get("decl_max", 0))
    orient     = topo_metrics.get("orientacao_predominante", "?")
    desnivel   = topo_metrics.get("desnivel", 0)
    area_util  = topo_metrics.get("area_util_m2", 0)

    stats = [
        ("Alt.Min",   "%.0fm"  % alt_min),
        ("Alt.Max",   "%.0fm"  % alt_max),
        ("Desnivel",  "%.1fm"  % desnivel),
        ("Decl.Med",  "%.1f%%" % decl_media),
        ("Decl.P90",  "%.1f%%" % decl_p90),
        ("Orientacao", orient),
        ("Area Util", "%dm2"   % area_util),
    ]
    for i, (k, v) in enumerate(stats):
        sx = 10 + i * 107
        out.append('<text x="%d" y="%d" fill="#555" font-family="monospace" font-size="8">%s</text>' % (sx, metrics_y - 10, k))
        out.append('<text x="%d" y="%d" fill="%s" font-family="monospace" font-size="11" font-weight="bold">%s</text>' % (sx, metrics_y, ACCENT, v))

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
        out.append('<path d="M%d,%d L%.1f,%.1f A%d,%d 0 %d,1 %.1f,%.1f Z" fill="%s" stroke="%s" stroke-width="1.5"/>' % (
            cx, cy, x1, y1, r, r, large, x2, y2, color, DARK_BG))

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
