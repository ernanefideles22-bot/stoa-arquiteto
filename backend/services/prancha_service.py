"""
Prancha tecnica (SVG) do parcelamento gerado pelo parcel_engine.

Elementos de prancha de projeto: lotes numerados, vias, areas verdes,
seta de norte, escala grafica, selo com quadro de areas. SVG e vetorial:
amplia sem perder qualidade e o navegador renderiza direto.
"""
import base64
import datetime

_C = {
    "fundo": "#f7f5ef", "borda": "#2b2b2b", "via": "#d8d4cb", "via_borda": "#9a958a",
    "lote": "#ffffff", "lote_borda": "#5b8db8", "verde": "#b5d4a7", "verde_borda": "#6f9c5c",
    "texto": "#2b2b2b", "texto2": "#6b675e", "selo": "#ffffff",
}


def _esc(v):
    return f"{v:.1f}"


def gerar_prancha_svg(geometria: dict, projeto_nome: str = "", cidade: str = "") -> str:
    L = geometria["L"]
    W, H = 1400, 1000            # prancha paisagem
    margem = 60
    area_desenho = min(W - 2 * margem - 300, H - 2 * margem)  # 300 = coluna do selo
    esc = area_desenho / L       # px por metro
    ox, oy = margem, margem + (H - 2 * margem - L * esc) / 2

    def X(x): return ox + x * esc
    def Y(y): return oy + (L - y) * esc   # y do plano local cresce pro norte

    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'font-family="Arial, sans-serif">')
    p.append(f'<rect width="{W}" height="{H}" fill="{_C["fundo"]}"/>')

    # terreno
    p.append(f'<rect x="{X(0)}" y="{Y(L)}" width="{L*esc:.1f}" height="{L*esc:.1f}" '
             f'fill="#eee9df" stroke="{_C["borda"]}" stroke-width="2.5" stroke-dasharray="10 5"/>')

    # verdes
    for v in geometria["verdes"]:
        p.append(f'<rect x="{X(v["x"])}" y="{Y(v["y"]+v["h"])}" width="{v["w"]*esc:.1f}" '
                 f'height="{v["h"]*esc:.1f}" fill="{_C["verde"]}" stroke="{_C["verde_borda"]}" stroke-width="0.7"/>')

    # vias
    for v in geometria["vias"]:
        p.append(f'<rect x="{X(v["x"])}" y="{Y(v["y"]+v["h"])}" width="{v["w"]*esc:.1f}" '
                 f'height="{v["h"]*esc:.1f}" fill="{_C["via"]}" stroke="{_C["via_borda"]}" stroke-width="0.6"/>')

    # lotes
    fs = max(7.0, min(13.0, 9.0 * esc / 0.6))
    for l in geometria["lotes"]:
        p.append(f'<rect x="{X(l["x"])}" y="{Y(l["y"]+l["h"])}" width="{l["w"]*esc:.1f}" '
                 f'height="{l["h"]*esc:.1f}" fill="{_C["lote"]}" stroke="{_C["lote_borda"]}" stroke-width="0.9"/>')
        cx, cy = X(l["x"] + l["w"] / 2), Y(l["y"] + l["h"] / 2)
        p.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{fs:.1f}" fill="{_C["texto"]}" '
                 f'text-anchor="middle" font-weight="bold">{l["num"]}</text>')
        p.append(f'<text x="{cx:.1f}" y="{cy + fs:.1f}" font-size="{fs*0.72:.1f}" '
                 f'fill="{_C["texto2"]}" text-anchor="middle">{l["area"]:.0f}m²</text>')

    # norte
    nx, ny = X(L) + 45, Y(L) + 30
    p.append(f'<g transform="translate({nx},{ny})">'
             f'<polygon points="0,-24 8,10 0,4 -8,10" fill="{_C["borda"]}"/>'
             f'<text x="0" y="26" font-size="14" text-anchor="middle" font-weight="bold">N</text></g>')

    # escala grafica (barra de 0 ate ~L/4 arredondado)
    passo = max(10, round(L / 8 / 10) * 10)
    bx, by = X(0), Y(0) + 34
    p.append(f'<g font-size="11" fill="{_C["texto"]}">')
    for i in range(4):
        cor = _C["borda"] if i % 2 == 0 else "#ffffff"
        p.append(f'<rect x="{bx + i*passo*esc:.1f}" y="{by}" width="{passo*esc:.1f}" height="7" '
                 f'fill="{cor}" stroke="{_C["borda"]}" stroke-width="0.8"/>')
        p.append(f'<text x="{bx + i*passo*esc:.1f}" y="{by - 4}" text-anchor="middle">{i*passo}</text>')
    p.append(f'<text x="{bx + 4*passo*esc:.1f}" y="{by - 4}" text-anchor="middle">{4*passo} m</text>')
    p.append('</g>')

    # selo / quadro de areas
    s = geometria["stats"]
    sx, sy, sw = W - margem - 290, margem, 290
    linhas = [
        ("PROJETO", projeto_nome or "Estudo de implantacao"),
        ("LOCAL", cidade or "-"),
        ("DATA", datetime.date.today().strftime("%d/%m/%Y")),
        ("", ""),
        ("QUADRO DE AREAS", ""),
        ("Area total", f'{s["area_total_m2"]:,.0f} m²'.replace(",", ".")),
        ("Lotes ({})".format(s["num_lotes"]), f'{s["area_lotes_m2"]:,.0f} m² ({s["aproveitamento_pct"]}%)'.replace(",", ".")),
        ("Vias", f'{s["area_vias_m2"]:,.0f} m²'.replace(",", ".")),
        ("Verde/preservacao", f'{s["area_verde_m2"]:,.0f} m²'.replace(",", ".")),
        ("Area media do lote", f'{s["area_media_lote_m2"]:,.0f} m²'.replace(",", ".")),
        ("", ""),
        ("", "Gerado pelo STOA Civil — estudo preliminar."),
        ("", "Sujeito a levantamento topografico e"),
        ("", "aprovacao por profissional habilitado (CAU/CREA)."),
    ]
    alt = 22 * len(linhas) + 24
    p.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{alt}" fill="{_C["selo"]}" '
             f'stroke="{_C["borda"]}" stroke-width="1.5"/>')
    yy = sy + 26
    for chave, valor in linhas:
        if chave == "QUADRO DE AREAS":
            p.append(f'<text x="{sx+12}" y="{yy}" font-size="13" font-weight="bold">{chave}</text>')
        elif chave:
            p.append(f'<text x="{sx+12}" y="{yy}" font-size="11.5" fill="{_C["texto2"]}">{chave}</text>')
            p.append(f'<text x="{sx+sw-12}" y="{yy}" font-size="11.5" text-anchor="end" '
                     f'font-weight="bold">{valor}</text>')
        elif valor:
            p.append(f'<text x="{sx+12}" y="{yy}" font-size="9.5" fill="{_C["texto2"]}">{valor}</text>')
        yy += 22

    # legenda
    ly = sy + alt + 26
    for cor, borda, nome in [(_C["lote"], _C["lote_borda"], "Lote"),
                             (_C["via"], _C["via_borda"], "Via (12 m)"),
                             (_C["verde"], _C["verde_borda"], "Verde / preservacao (>30%)")]:
        p.append(f'<rect x="{sx}" y="{ly-11}" width="16" height="12" fill="{cor}" stroke="{borda}"/>')
        p.append(f'<text x="{sx+24}" y="{ly}" font-size="11.5">{nome}</text>')
        ly += 22

    p.append('</svg>')
    return "".join(p)


def prancha_b64(geometria: dict, projeto_nome: str = "", cidade: str = "") -> str:
    svg = gerar_prancha_svg(geometria, projeto_nome, cidade)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()
