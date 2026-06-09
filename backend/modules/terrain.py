"""
Módulo de análise de terreno — STOA Civil
Analisa topografia, curvas de nível, orientação solar e gera recomendações via IA.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
import base64
import json
import os
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def gerar_curvas_nivel_automatico(largura: float, comprimento: float,
                                   declividade: float, orientacao: str) -> dict:
    """Gera pontos de curvas de nível sinteticamente a partir dos parâmetros."""
    nx, ny = 40, 40
    x = np.linspace(0, largura, nx)
    y = np.linspace(0, comprimento, ny)
    X, Y = np.meshgrid(x, y)

    # Mapeamento orientação → gradiente
    direcoes = {
        "N":  (0,  1), "S":  (0, -1), "L":  (1, 0),  "O":  (-1, 0),
        "NE": (1,  1), "NO": (-1, 1), "SE": (1, -1), "SO": (-1, -1),
    }
    dx, dy = direcoes.get(orientacao.upper(), (0, 1))

    # Elevação base com declividade + ondulações suaves
    fator = declividade / 100
    Z = 100 + (dx * X + dy * Y) * fator
    Z += np.sin(X / largura * np.pi) * 0.5 + np.cos(Y / comprimento * np.pi) * 0.3

    niveis = np.linspace(Z.min(), Z.max(), 10)
    curvas = []
    for n in niveis:
        curvas.append({"nivel": round(float(n), 2)})

    return {
        "X": X.tolist(), "Y": Y.tolist(), "Z": Z.tolist(),
        "niveis": [round(float(n), 2) for n in niveis],
        "z_min": round(float(Z.min()), 2),
        "z_max": round(float(Z.max()), 2),
        "desnivel_total": round(float(Z.max() - Z.min()), 2),
    }


def gerar_imagem_terreno(dados_terreno: dict, largura: float, comprimento: float,
                          orientacao: str) -> str:
    """Gera imagem do terreno com curvas de nível. Retorna base64."""
    X = np.array(dados_terreno["X"])
    Y = np.array(dados_terreno["Y"])
    Z = np.array(dados_terreno["Z"])

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#1a1a2e")

    # --- Mapa topográfico ---
    ax1 = axes[0]
    ax1.set_facecolor("#1a1a2e")
    cf = ax1.contourf(X, Y, Z, levels=15, cmap="terrain", alpha=0.85)
    cs = ax1.contour(X, Y, Z, levels=10, colors="white", linewidths=0.6, alpha=0.7)
    ax1.clabel(cs, inline=True, fontsize=7, fmt="%.1fm", colors="white")
    plt.colorbar(cf, ax=ax1, label="Elevação (m)", shrink=0.8)

    # Rosa dos ventos simplificada
    _rosa_ventos(ax1, 0.88, 0.88, orientacao)

    ax1.set_title("Topografia e Curvas de Nível", color="white", fontsize=11, pad=10)
    ax1.set_xlabel("Largura (m)", color="#aaa")
    ax1.set_ylabel("Comprimento (m)", color="#aaa")
    ax1.tick_params(colors="#aaa")
    for sp in ax1.spines.values():
        sp.set_color("#444")

    # --- Mapa de declividade ---
    ax2 = axes[1]
    ax2.set_facecolor("#1a1a2e")
    dZdx = np.gradient(Z, axis=1)
    dZdy = np.gradient(Z, axis=0)
    slope_pct = np.sqrt(dZdx**2 + dZdy**2) * 100

    sm = ax2.contourf(X, Y, slope_pct, levels=15, cmap="RdYlGn_r", alpha=0.85)
    plt.colorbar(sm, ax=ax2, label="Declividade (%)", shrink=0.8)

    # Legenda de zonas
    patches = [
        mpatches.Patch(color="#1a9641", label="Plano (0–5%)"),
        mpatches.Patch(color="#a6d96a", label="Suave (5–15%)"),
        mpatches.Patch(color="#fdae61", label="Moderado (15–30%)"),
        mpatches.Patch(color="#d7191c", label="Íngreme (>30%)"),
    ]
    ax2.legend(handles=patches, loc="lower right", fontsize=7,
               facecolor="#2a2a3e", labelcolor="white", framealpha=0.8)

    ax2.set_title("Mapa de Declividade", color="white", fontsize=11, pad=10)
    ax2.set_xlabel("Largura (m)", color="#aaa")
    ax2.tick_params(colors="#aaa")
    for sp in ax2.spines.values():
        sp.set_color("#444")

    plt.tight_layout(pad=2.0)

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _rosa_ventos(ax, x_norm, y_norm, orientacao_frente):
    from matplotlib.transforms import blended_transform_factory
    trans = ax.transAxes
    ax.annotate("N", xy=(x_norm, y_norm + 0.06), xycoords=trans,
                ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    ax.annotate("", xy=(x_norm, y_norm + 0.04), xytext=(x_norm, y_norm - 0.04),
                xycoords=trans, textcoords=trans,
                arrowprops=dict(arrowstyle="->", color="white", lw=1.5))


async def analisar_terreno_ia(params: dict) -> dict:
    """Envia parâmetros do terreno para a IA e retorna análise completa."""
    prompt = f"""Você é um engenheiro civil e urbanista especialista em análise de terrenos para construção.

Dados do terreno:
- Área total: {params['area_total']} m²
- Dimensões: {params['largura']}m x {params['comprimento']}m
- Testada (frente): {params['testada']}m
- Declividade média: {params['declividade']}%
- Orientação solar da frente: {params['orientacao']}
- Tipo de solo: {params['tipo_solo']}
- Desnível total: {params.get('desnivel_total', 'não informado')}m

Analise este terreno e retorne um JSON com exatamente estas chaves:
{{
  "resumo": "parágrafo resumindo as características do terreno",
  "pontuacao": número de 0 a 10 indicando aptidão para construção,
  "restricoes": ["lista de restrições ou desafios"],
  "recomendacoes": ["lista de recomendações técnicas"],
  "area_util_estimada": número em m² (área aproveitável descontando declividade e recuos),
  "tipo_fundacao_recomendado": "tipo de fundação mais adequada",
  "movimentacao_terra": "estimativa de corte/aterro necessário",
  "melhor_posicionamento": "onde posicionar a construção no terreno e por quê",
  "orientacao_ideal_construcao": "qual face da construção deve ficar para o sol da manhã/tarde",
  "riscos": ["riscos geotécnicos ou ambientais identificados"]
}}

Responda APENAS com o JSON, sem markdown."""

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    # Limpar markdown se veio
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
