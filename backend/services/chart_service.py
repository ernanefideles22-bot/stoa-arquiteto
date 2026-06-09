"""
Gerador de gráficos e mapas — STOA Civil
Produz imagens base64 para o frontend e para o PDF.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.patches import FancyArrowPatch
from io import BytesIO
import base64
import math


DARK_BG   = "#0f1117"
PANEL_BG  = "#1a1d27"
TEXT_CLR  = "#e0e0e0"
GRID_CLR  = "#2a2d3a"
ACCENT    = "#4fc3f7"


def fig_to_b64(fig) -> str:
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def gerar_mapa_topografico(elevation_grid: dict, topo_metrics: dict,
                             area_ha: float) -> str:
    """Gera mapa de curvas de nível + declividade lado a lado."""
    Z = np.array(elevation_grid["elevations"])
    n = elevation_grid["n"]
    res = elevation_grid["resolution_m"]

    x = np.arange(n) * res / 1000  # km
    y = np.arange(n) * res / 1000
    X, Y = np.meshgrid(x, y)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle(f"Análise Topográfica — {area_ha:.0f} ha", color=TEXT_CLR,
                 fontsize=14, fontweight="bold", y=1.01)

    # ── Curvas de nível ──
    ax1 = axes[0]
    ax1.set_facecolor(PANEL_BG)
    levels = np.linspace(Z.min(), Z.max(), 16)
    cf = ax1.contourf(X, Y, Z, levels=levels, cmap="terrain", alpha=0.9)
    cs = ax1.contour(X, Y, Z, levels=levels[::2], colors="white",
                     linewidths=0.7, alpha=0.6)
    ax1.clabel(cs, inline=True, fontsize=7, fmt="%.0fm", colors="white")
    cb = plt.colorbar(cf, ax=ax1, shrink=0.85, pad=0.02)
    cb.set_label("Elevação (m)", color=TEXT_CLR, fontsize=9)
    cb.ax.yaxis.set_tick_params(color=TEXT_CLR)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color=TEXT_CLR)

    _style_axis(ax1, "Topografia — Curvas de Nível", "Distância L-O (km)", "Distância N-S (km)")
    _rosa_ventos(ax1, 0.92, 0.92)

    # ── Declividade ──
    ax2 = axes[1]
    ax2.set_facecolor(PANEL_BG)
    dzdx = np.gradient(Z, axis=1) / res
    dzdy = np.gradient(Z, axis=0) / res
    slope = np.sqrt(dzdx**2 + dzdy**2) * 100

    bounds = [0, 5, 15, 30, 45, 200]
    colors_slope = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"]
    cmap = mcolors.ListedColormap(colors_slope)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)
    sm = ax2.contourf(X, Y, slope, levels=bounds, cmap=cmap, norm=norm, alpha=0.9)

    patches = [
        mpatches.Patch(color=colors_slope[0], label="Plano 0–5%"),
        mpatches.Patch(color=colors_slope[1], label="Suave 5–15%"),
        mpatches.Patch(color=colors_slope[2], label="Moderado 15–30%"),
        mpatches.Patch(color=colors_slope[3], label="Íngreme 30–45%"),
        mpatches.Patch(color=colors_slope[4], label="Muito Íngreme >45%"),
    ]
    ax2.legend(handles=patches, loc="lower right", fontsize=8,
               facecolor=PANEL_BG, labelcolor=TEXT_CLR, framealpha=0.9,
               edgecolor=GRID_CLR)

    _style_axis(ax2, "Mapa de Declividade", "Distância L-O (km)", "")

    # Métricas
    info = (f"Δh={topo_metrics['desnivel']}m | "
            f"D.média={topo_metrics['decl_media']}% | "
            f"Útil={topo_metrics['area_util_m2']/10000:.1f}ha")
    fig.text(0.5, -0.02, info, ha="center", color=ACCENT, fontsize=10)

    plt.tight_layout(pad=1.5)
    return fig_to_b64(fig)


def gerar_grafico_zonas(zonas: list) -> str:
    """Gráfico de pizza das zonas de declividade."""
    fig, ax = plt.subplots(figsize=(7, 5))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    labels  = [z["tipo"] for z in zonas if z["percentual"] > 0]
    values  = [z["percentual"] for z in zonas if z["percentual"] > 0]
    colors  = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"][:len(labels)]

    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=140,
        textprops={"color": TEXT_CLR, "fontsize": 9},
        wedgeprops={"edgecolor": DARK_BG, "linewidth": 2},
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(9)

    ax.set_title("Distribuição de Declividade", color=TEXT_CLR,
                 fontsize=12, pad=15, fontweight="bold")
    plt.tight_layout()
    return fig_to_b64(fig)


def gerar_grafico_financeiro(financial: dict) -> str:
    """Gráfico de barras de custos e fluxo de caixa."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor(DARK_BG)

    # ── Composição de custos ──
    ax1 = axes[0]
    ax1.set_facecolor(PANEL_BG)
    custos = financial.get("custos", {})
    items = {
        "Terreno":       custos.get("terreno", 0),
        "Infraestrutura":custos.get("infraestrutura_loteamento", 0),
        "Construção":    custos.get("construcao", 0),
        "Projetos":      custos.get("projetos_aprovacoes", 0),
        "Marketing":     custos.get("marketing_vendas", 0),
        "Financeiro":    custos.get("financeiro_juros", 0),
    }
    items = {k: v for k, v in items.items() if v > 0}
    bars = ax1.barh(list(items.keys()), [v/1e6 for v in items.values()],
                    color=ACCENT, alpha=0.85, edgecolor=DARK_BG)
    ax1.bar_label(bars, fmt="R$ %.1fM", color=TEXT_CLR, fontsize=8, padding=3)
    _style_axis(ax1, "Composição de Custos", "Milhões (R$)", "")
    ax1.set_xlim(0, max(items.values()) / 1e6 * 1.3)

    # ── Fluxo de caixa ──
    ax2 = axes[1]
    ax2.set_facecolor(PANEL_BG)
    fluxo = financial.get("fluxo_caixa_anual", [])
    if fluxo:
        anos = [f["ano"] for f in fluxo]
        invest = [-f.get("investimento", 0)/1e6 for f in fluxo]
        receita = [f.get("receita", 0)/1e6 for f in fluxo]
        saldo = [f.get("saldo_acumulado", 0)/1e6 for f in fluxo]

        w = 0.35
        x = np.arange(len(anos))
        ax2.bar(x - w/2, invest,  w, label="Investimento", color="#e74c3c", alpha=0.8)
        ax2.bar(x + w/2, receita, w, label="Receita",      color="#2ecc71", alpha=0.8)
        ax2.plot(x, saldo, "o-", color=ACCENT, linewidth=2, label="Saldo Acum.", zorder=5)
        ax2.axhline(0, color=GRID_CLR, linewidth=1)
        ax2.set_xticks(x)
        ax2.set_xticklabels([f"Ano {a}" for a in anos], color=TEXT_CLR, fontsize=8)
        ax2.legend(facecolor=PANEL_BG, labelcolor=TEXT_CLR, fontsize=8,
                   edgecolor=GRID_CLR)
        _style_axis(ax2, "Fluxo de Caixa", "Milhões (R$)", "")

    plt.tight_layout(pad=2)
    return fig_to_b64(fig)


def _style_axis(ax, title, xlabel, ylabel):
    ax.set_title(title, color=TEXT_CLR, fontsize=11, fontweight="bold", pad=8)
    ax.set_xlabel(xlabel, color=TEXT_CLR, fontsize=9)
    ax.set_ylabel(ylabel, color=TEXT_CLR, fontsize=9)
    ax.tick_params(colors=TEXT_CLR, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(GRID_CLR)
    ax.yaxis.grid(True, color=GRID_CLR, linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)


def _rosa_ventos(ax, xn, yn):
    trans = ax.transAxes
    ax.annotate("N", xy=(xn, yn + 0.05), xycoords=trans,
                ha="center", va="center", fontsize=9,
                color="white", fontweight="bold")
    ax.annotate("", xy=(xn, yn + 0.03), xytext=(xn, yn - 0.03),
                xycoords=trans, textcoords=trans,
                arrowprops=dict(arrowstyle="-|>", color="white", lw=1.5))
