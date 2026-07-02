"""
Motor de parcelamento sensivel a topografia.

Gera a GEOMETRIA de um projeto de loteamento a partir do grid de elevacao
real (SRTM 30m, 20x20) coletado na etapa de Analise:

- vias longitudinais acompanham as curvas de nivel (menor rampa);
- vias transversais a cada ~150 m (quadra urbana razoavel);
- celulas com declividade > LIMITE_DECLIVIDADE viram verde/preservacao;
- quadras com duas fileiras de lotes costas-com-costas, lotes numerados
  com area, cota e declividade individuais;
- quadro de areas fecha com a area total do terreno.

Deterministico: mesmo terreno + mesmos parametros => mesmo projeto.
A IA decide o PROGRAMA (nº de lotes, faixa de area); a geometria e calculada.

Coordenadas: plano local em metros, origem no canto SW do terreno
(quadrado de lado L = sqrt(area)), x leste, y norte. O grid de elevacao
cobre 2.8x o lado do terreno (ver geo_service.get_elevation_grid) com o
terreno no miolo central.
"""
import math

LIMITE_DECLIVIDADE = 30.0   # % — acima disso nao se edifica (vira verde)
PROFUNDIDADE_LOTE = 30.0    # m
LARGURA_VIA = 12.0          # m
LARGURA_MIN_LOTE = 10.0     # m de frente
QUADRA_MAX = 150.0          # m entre vias transversais


class _Elevacao:
    """Amostragem bilinear do grid de elevacao no plano local do terreno."""

    def __init__(self, elevation_grid: dict, L: float):
        self.Z = elevation_grid["elevations"]
        self.n = int(elevation_grid.get("n") or len(self.Z))
        self.span = 2.0 * L * 1.4
        self.off = (self.span - L) / 2.0
        self.L = L

    def cota(self, x: float, y: float) -> float:
        gx = (self.off + min(max(x, 0.0), self.L)) / self.span * (self.n - 1)
        gy = (self.off + min(max(y, 0.0), self.L)) / self.span * (self.n - 1)
        i0, j0 = int(gy), int(gx)
        i1, j1 = min(i0 + 1, self.n - 1), min(j0 + 1, self.n - 1)
        fy, fx = gy - i0, gx - j0
        z00, z01 = self.Z[i0][j0], self.Z[i0][j1]
        z10, z11 = self.Z[i1][j0], self.Z[i1][j1]
        return (z00 * (1 - fx) + z01 * fx) * (1 - fy) + (z10 * (1 - fx) + z11 * fx) * fy

    def declividade_pct(self, x: float, y: float, h: float = 15.0) -> float:
        dzdx = (self.cota(x + h, y) - self.cota(x - h, y)) / (2 * h)
        dzdy = (self.cota(x, y + h) - self.cota(x, y - h)) / (2 * h)
        return math.hypot(dzdx, dzdy) * 100.0

    def gradiente_medio(self) -> tuple:
        sx = sy = 0.0
        k = 8
        for i in range(1, k):
            for j in range(1, k):
                x, y = self.L * j / k, self.L * i / k
                sx += abs(self.cota(x + 10, y) - self.cota(x - 10, y)) / 20
                sy += abs(self.cota(x, y + 10) - self.cota(x, y - 10)) / 20
        m = (k - 1) ** 2
        return sx / m, sy / m


def _segmentos(total: float, tam_max: float, separador: float):
    """Divide `total` em segmentos <= tam_max intercalados por `separador`."""
    segs, pos = [], 0.0
    while pos < total - 1e-6:
        seg = min(tam_max, total - pos)
        # evita segmento final minusculo (< 1 lote): funde no anterior
        if total - (pos + seg + separador) < LARGURA_MIN_LOTE and total - pos - seg > 1e-6:
            seg = total - pos
        segs.append((pos, seg))
        pos += seg + separador
    return segs


def gerar_parcelamento(area_m2: float, elevation_grid: dict,
                       num_lotes_alvo: int = 40,
                       area_min_lote: float = 300.0,
                       area_max_lote: float = 1000.0) -> dict:
    L = math.sqrt(max(area_m2, 1000.0))
    ele = _Elevacao(elevation_grid, L)

    # Orientacao: terreno cai mais ao longo de x => curvas de nivel em y =>
    # vias longitudinais verticais. Caso contrario, horizontais.
    gx, gy = ele.gradiente_medio()
    vias_verticais = gx >= gy

    def T(x, y, w, h):
        return (x, y, w, h) if vias_verticais else (y, x, h, w)

    # ── Vias longitudinais + faixas de quadra (eixo "x" local) ────────────
    vias_long, faixas = [], []
    vias_long.append((0.0, 0.0, LARGURA_VIA, L))          # acesso na borda
    x = LARGURA_VIA
    while x + PROFUNDIDADE_LOTE <= L + 1e-6:
        qw = min(2 * PROFUNDIDADE_LOTE, L - x)
        faixas.append((x, qw))
        x += qw
        if x + LARGURA_VIA + PROFUNDIDADE_LOTE <= L + 1e-6:
            vias_long.append((x, 0.0, LARGURA_VIA, L))
            x += LARGURA_VIA
        else:
            break

    # ── Vias transversais (eixo "y" local) ───────────────────────────────
    segs_y = _segmentos(L, QUADRA_MAX, LARGURA_VIA)
    vias_trans = []
    for (y0, seg) in segs_y[:-1]:
        vias_trans.append((0.0, y0 + seg, L, LARGURA_VIA))

    # ── Lotes ─────────────────────────────────────────────────────────────
    area_media = max(area_min_lote, min(area_max_lote,
                     (area_min_lote + area_max_lote) / 2))
    frente = max(LARGURA_MIN_LOTE, area_media / PROFUNDIDADE_LOTE)

    lotes, verdes = [], []
    num = 0
    for qx, qw in faixas:
        n_fileiras = 2 if qw >= 2 * PROFUNDIDADE_LOTE - 1e-6 else 1
        prof = qw / n_fileiras
        for f in range(n_fileiras):
            fx = qx + f * prof
            for (y0, seg) in segs_y:
                y = y0
                fim = y0 + seg
                while y + LARGURA_MIN_LOTE <= fim + 1e-6:
                    w_lote = frente if (y + 2 * frente <= fim) else (fim - y)
                    cx, cy = fx + prof / 2, y + w_lote / 2
                    if not vias_verticais:
                        cx, cy = cy, cx
                    decl = ele.declividade_pct(cx, cy)
                    r = T(fx, y, prof, w_lote)
                    item = {"x": round(r[0], 2), "y": round(r[1], 2),
                            "w": round(r[2], 2), "h": round(r[3], 2),
                            "area": round(prof * w_lote, 1),
                            "cota": round(ele.cota(cx, cy), 1),
                            "declividade": round(decl, 1)}
                    if decl > LIMITE_DECLIVIDADE:
                        verdes.append(item)
                    else:
                        num += 1
                        item["num"] = num
                        lotes.append(item)
                    y += w_lote

    # ── Quadro de areas ───────────────────────────────────────────────────
    a_lotes = sum(l["area"] for l in lotes)
    a_verde = sum(v["area"] for v in verdes)
    a_long = sum(w * h for (_, _, w, h) in vias_long)
    a_trans = sum(w * h for (_, _, w, h) in vias_trans)
    # intersecoes (via longitudinal x transversal) contadas 2x
    a_inter = len(vias_long) * len(vias_trans) * LARGURA_VIA * LARGURA_VIA
    a_vias = a_long + a_trans - a_inter
    a_total = L * L
    stats = {
        "area_total_m2": round(a_total, 1),
        "area_lotes_m2": round(a_lotes, 1),
        "area_vias_m2": round(a_vias, 1),
        "area_verde_m2": round(a_verde, 1),
        "sobra_m2": round(a_total - a_lotes - a_vias - a_verde, 1),
        "num_lotes": len(lotes),
        "num_lotes_alvo": num_lotes_alvo,
        "aproveitamento_pct": round(a_lotes / a_total * 100, 1),
        "area_media_lote_m2": round(a_lotes / len(lotes), 1) if lotes else 0,
    }

    vias = [T(*v) for v in vias_long] + [T(*v) for v in vias_trans]
    return {
        "L": round(L, 2),
        "vias_verticais": vias_verticais,
        "vias": [{"x": round(a, 2), "y": round(b, 2), "w": round(c, 2), "h": round(d, 2)}
                 for (a, b, c, d) in vias],
        "lotes": lotes,
        "verdes": verdes,
        "stats": stats,
    }
