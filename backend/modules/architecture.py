"""
Módulo de projeto arquitetônico — STOA Civil
Gera planta 2D (SVG) e dados 3D para visualização no browser.
"""
import json
import os
import math
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ── Gerador de planta SVG ────────────────────────────────────────────────────

def gerar_planta_svg(comodos: list, largura_total: float, comprimento_total: float,
                     titulo: str = "Planta Baixa") -> str:
    """
    Gera SVG de planta baixa a partir de lista de cômodos.
    comodos: [{nome, x, y, largura, altura, tipo}]
    Coordenadas em metros — escala automática para 700x500px.
    """
    MARGIN = 40
    SVG_W, SVG_H = 780, 560
    escala = min((SVG_W - 2 * MARGIN) / largura_total,
                 (SVG_H - 2 * MARGIN - 30) / comprimento_total)

    cores = {
        "quarto":    "#dce8f0", "sala":      "#fef9e7", "cozinha":   "#fdebd0",
        "banheiro":  "#d5f5e3", "garagem":   "#e8e8e8", "varanda":   "#fff3cd",
        "lavanderia":"#f0e6ff", "circulacao":"#f5f5f5", "escritorio":"#e8f4f8",
        "default":   "#f0f0f0",
    }
    cor_texto = "#2c3e50"
    cor_parede = "#2c3e50"

    svglines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}" font-family="Arial,sans-serif">',
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="#1a1a2e"/>',
        # Grid de fundo
        f'<defs><pattern id="grid" width="{escala}" height="{escala}" patternUnits="userSpaceOnUse">'
        f'<path d="M {escala} 0 L 0 0 0 {escala}" fill="none" stroke="#2a2a4a" stroke-width="0.5"/>'
        f'</pattern></defs>',
        f'<rect x="{MARGIN}" y="{MARGIN}" '
        f'width="{largura_total * escala}" height="{comprimento_total * escala}" '
        f'fill="url(#grid)" stroke="none"/>',
    ]

    # Cômodos
    for c in comodos:
        tipo = c.get("tipo", "default").lower()
        cor = cores.get(tipo, cores["default"])
        px = MARGIN + c["x"] * escala
        py = MARGIN + c["y"] * escala
        pw = c["largura"] * escala
        ph = c["altura"] * escala

        svglines.append(
            f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
            f'fill="{cor}" stroke="{cor_parede}" stroke-width="2" rx="1"/>'
        )
        # Nome do cômodo
        cx, cy = px + pw / 2, py + ph / 2
        area = c["largura"] * c["altura"]
        svglines.append(
            f'<text x="{cx:.1f}" y="{cy - 6:.1f}" text-anchor="middle" '
            f'font-size="11" font-weight="bold" fill="{cor_texto}">{c["nome"]}</text>'
        )
        svglines.append(
            f'<text x="{cx:.1f}" y="{cy + 10:.1f}" text-anchor="middle" '
            f'font-size="9" fill="{cor_texto}">{area:.1f} m²</text>'
        )

        # Porta simulada (linha no centro da parede inferior)
        porta_x = px + pw * 0.3
        svglines.append(
            f'<line x1="{porta_x:.1f}" y1="{py + ph:.1f}" '
            f'x2="{porta_x + 14:.1f}" y2="{py + ph:.1f}" '
            f'stroke="#e74c3c" stroke-width="3"/>'
        )

    # Contorno externo
    svglines.append(
        f'<rect x="{MARGIN}" y="{MARGIN}" '
        f'width="{largura_total * escala:.1f}" height="{comprimento_total * escala:.1f}" '
        f'fill="none" stroke="{cor_parede}" stroke-width="3"/>'
    )

    # Cotas
    _cota(svglines, MARGIN, MARGIN + comprimento_total * escala + 15,
          MARGIN + largura_total * escala, MARGIN + comprimento_total * escala + 15,
          f"{largura_total:.1f}m")
    _cota(svglines, MARGIN - 15, MARGIN,
          MARGIN - 15, MARGIN + comprimento_total * escala,
          f"{comprimento_total:.1f}m", vertical=True)

    # Indicador Norte
    svglines += _norte(MARGIN + largura_total * escala + 20, MARGIN + 30)

    # Título e escala
    svglines.append(
        f'<text x="{SVG_W // 2}" y="{SVG_H - 8}" text-anchor="middle" '
        f'font-size="13" font-weight="bold" fill="#aaa">{titulo} '
        f'— Escala 1:{int(100 / escala * 10) * 10}</text>'
    )

    svglines.append("</svg>")
    return "\n".join(svglines)


def _cota(lines, x1, y1, x2, y2, texto, vertical=False):
    lines.append(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="#7f8c8d" stroke-width="1" stroke-dasharray="4,3"/>'
    )
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    rot = f'transform="rotate(-90,{mx:.1f},{my:.1f})"' if vertical else ""
    lines.append(
        f'<text x="{mx:.1f}" y="{my - 3:.1f}" text-anchor="middle" '
        f'font-size="9" fill="#7f8c8d" {rot}>{texto}</text>'
    )


def _norte(x, y):
    return [
        f'<circle cx="{x}" cy="{y}" r="18" fill="#2a2a4a" stroke="#7f8c8d" stroke-width="1"/>',
        f'<text x="{x}" y="{y - 6}" text-anchor="middle" font-size="12" '
        f'font-weight="bold" fill="white">N</text>',
        f'<line x1="{x}" y1="{y - 4}" x2="{x}" y2="{y + 12}" '
        f'stroke="white" stroke-width="1.5"/>',
        f'<polygon points="{x},{y-14} {x-5},{y+2} {x+5},{y+2}" fill="white" opacity="0.6"/>',
    ]


# ── Gerador de dados 3D (Three.js) ──────────────────────────────────────────

def gerar_dados_3d(comodos: list, largura_total: float, comprimento_total: float,
                   pavimentos: int = 1, pe_direito: float = 2.8) -> dict:
    """Gera estrutura JSON para renderização 3D no Three.js."""
    meshes = []

    # Chão
    meshes.append({
        "tipo": "chao",
        "x": largura_total / 2, "y": 0, "z": comprimento_total / 2,
        "largura": largura_total, "altura": 0.15, "profundidade": comprimento_total,
        "cor": "#8B7355",
    })

    cores_3d = {
        "quarto": "#90CAF9", "sala": "#FFCC80", "cozinha": "#A5D6A7",
        "banheiro": "#80DEEA", "garagem": "#BDBDBD", "varanda": "#FFF176",
        "default": "#E0E0E0",
    }

    for pav in range(pavimentos):
        base_y = pav * pe_direito

        for c in comodos:
            tipo = c.get("tipo", "default").lower()
            cor = cores_3d.get(tipo, cores_3d["default"])
            cx = c["x"] + c["largura"] / 2
            cz = c["y"] + c["altura"] / 2

            # Paredes (4 faces por cômodo)
            meshes.append({
                "tipo": "comodo",
                "nome": c["nome"],
                "x": cx, "y": base_y + pe_direito / 2, "z": cz,
                "largura": c["largura"], "altura": pe_direito, "profundidade": c["altura"],
                "cor": cor,
                "pavimento": pav + 1,
            })

        # Laje/Cobertura no último pavimento
        if pav == pavimentos - 1:
            meshes.append({
                "tipo": "laje",
                "x": largura_total / 2, "y": base_y + pe_direito + 0.1,
                "z": comprimento_total / 2,
                "largura": largura_total, "altura": 0.2,
                "profundidade": comprimento_total,
                "cor": "#CFD8DC",
            })

    return {
        "meshes": meshes,
        "dimensoes": {
            "largura": largura_total,
            "comprimento": comprimento_total,
            "altura_total": pavimentos * pe_direito,
        },
        "pe_direito": pe_direito,
        "pavimentos": pavimentos,
    }


# ── IA: gerador de layout de cômodos ────────────────────────────────────────

async def gerar_layout_ia(params: dict, analise_terreno: dict = None) -> dict:
    """
    Recebe requisitos e retorna layout de cômodos posicionados no terreno.
    """
    contexto_terreno = ""
    if analise_terreno:
        contexto_terreno = f"""
Análise do terreno:
- Área útil estimada: {analise_terreno.get('area_util_estimada', 'n/d')} m²
- Posicionamento ideal: {analise_terreno.get('melhor_posicionamento', 'n/d')}
- Orientação: {analise_terreno.get('orientacao_ideal_construcao', 'n/d')}
"""

    prompt = f"""Você é um arquiteto especialista. Crie um layout funcional e bem distribuído para uma edificação com:
- Área construída: {params['area_construida']} m²
- Pavimentos: {params['pavimentos']}
- Quartos: {params['num_quartos']}
- Banheiros: {params['num_banheiros']}
- Garagem: {'sim' if params.get('tem_garagem') else 'não'}
- Piscina: {'sim' if params.get('tem_piscina') else 'não'}
- Varanda: {'sim' if params.get('tem_varanda') else 'não'}
- Estilo: {params.get('estilo', 'moderno')}
- Observações: {params.get('requisitos_extra', 'nenhuma')}
{contexto_terreno}

Retorne um JSON com:
{{
  "largura_total": número em metros (dimensão X da planta),
  "comprimento_total": número em metros (dimensão Y da planta),
  "comodos": [
    {{
      "nome": "nome do cômodo",
      "tipo": "quarto|sala|cozinha|banheiro|garagem|varanda|lavanderia|circulacao|escritorio",
      "x": posição X em metros (canto superior esquerdo),
      "y": posição Y em metros (canto superior esquerdo),
      "largura": largura em metros,
      "altura": comprimento em metros
    }}
  ],
  "descricao": "descrição técnica do projeto em 3 parágrafos",
  "destaques": ["lista de pontos fortes do projeto"]
}}

IMPORTANTE: os cômodos devem ser CONTÍGUOS (sem sobreposição e sem lacunas grandes), totalizando aproximadamente {params['area_construida']} m². Todos dentro dos limites largura_total x comprimento_total.
Responda APENAS com o JSON, sem markdown."""

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
