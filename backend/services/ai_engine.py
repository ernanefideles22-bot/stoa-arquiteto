"""
Motor de IA — STOA Civil
Orquestra analises usando Claude (Anthropic). Cada funcao recebe dados reais e retorna analise estruturada.
"""
import json
import os
import anthropic

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

SYSTEM = (
    "Voce e um especialista em engenharia civil, arquitetura, urbanismo e desenvolvimento imobiliario no Brasil. "
    "Responde sempre em JSON estruturado, sem markdown, sem texto fora do JSON."
)

async def _ask(prompt: str, temperature: float = 0.3, max_tokens: int = 2048) -> dict:
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)

# ─── ANÁLISE DE TERRENO ─────────────────────────────────────────────────────

async def analisar_terreno(terrain: dict, topo: dict) -> dict:
    """Analise completa do terreno com dados reais de elevacao SRTM 30m."""

    area_ha  = terrain.get("area_ha", 0)
    area_m2  = terrain.get("area_m2", 0)
    area_util = topo.get("area_util_m2", 0)
    pct_util  = round(area_util / max(area_m2, 1) * 100)

    zonas_txt = "\n".join(
        "  - %s: %.1f%% (%d m2)" % (z["tipo"], z["percentual"], z["area_m2"])
        for z in topo.get("zonas", [])
    )

    prompt = (
        "Analise este terreno para desenvolvimento imobiliario no Brasil.\n"
        "Os dados de elevacao sao REAIS, obtidos do SRTM 30m via OpenTopoData.\n"
        "Seja especifico — referencie os valores numericos reais fornecidos. Nao use frases genericas.\n\n"
        "LOCALIZACAO: %s, %s/%s\n"
        "AREA: %.1f hectares (%d m2)\n"
        "TIPOLOGIA PRETENDIDA: %s\n\n"
        "TOPOGRAFIA REAL (grade 20x20, SRTM 30m):\n"
        "- Altitude: %.1fm a %.1fm (desnivel total: %.1fm)\n"
        "- Declividade media: %.1f%% | P90: %.1f%% | Maxima: %.1f%%\n"
        "- Orientacao do declive (aspecto): %s (%.1f graus)\n"
        "- Area util (decl < 30%%): %d m2 (%d%% do terreno)\n"
        "- Area restrita (decl > 30%%): %d m2\n\n"
        "DISTRIBUICAO POR ZONA:\n%s\n\n"
        "CARACTERISTICAS:\n"
        "- Vegetacao: %s\n"
        "- Acesso: %s\n"
        "- Infraestrutura: %s\n"
        "- Zoneamento: %s\n\n"
        "Retorne JSON exato com estas chaves:\n"
        "{\n"
        '  "resumo": "analise tecnica 3-4 frases com dados numericos reais",\n'
        '  "pontuacao_geral": <0-10>,\n'
        '  "pontos_fortes": ["ativo real do terreno com dados numericos"],\n'
        '  "restricoes": ["desafio tecnico/legal especifico ao terreno"],\n'
        '  "recomendacoes": ["acao prioritaria especifica"],\n'
        '  "tipo_fundacao_recomendado": "tipo adequado para desnivel e declividade reais",\n'
        '  "movimentacao_terra": "estimativa de corte/aterro em m3 baseada nos dados reais",\n'
        '  "aptidao": {"residencial_unifamiliar":0,"condominio_loteamento":0,"comercial":0,"pousada_hotel":0,"industrial":0},\n'
        '  "potencial_construtivo": "estimativa de m2 construivel baseada na area util real",\n'
        '  "riscos_criticos": ["risco especifico ao terreno"]\n'
        "}"
    ) % (
        terrain.get("address", "nao informado"),
        terrain.get("city", ""),
        terrain.get("state", ""),
        area_ha,
        area_m2,
        terrain.get("typology_intent") or "nao definida",
        topo["alt_min"], topo["alt_max"], topo["desnivel"],
        topo["decl_media"],
        topo.get("decl_p90", topo["decl_max"]),
        topo["decl_max"],
        topo["orientacao_predominante"],
        topo.get("aspect_deg", 0.0),
        area_util, pct_util,
        topo["area_restrita_m2"],
        zonas_txt,
        terrain.get("vegetacao", "nao informado"),
        terrain.get("acesso", "nao informado"),
        ", ".join(terrain.get("infraestrutura", [])) or "nao informado",
        terrain.get("zoneamento") or "nao informado",
    )

    return await _ask(prompt)

# ─── ALTERNATIVAS DE IMPLANTAÇÃO ────────────────────────────────────────────

async def gerar_alternativas_implantacao(terrain: dict, topo: dict,
                                          typology: str, programa: dict) -> dict:
    prompt = (
        "Crie 3 alternativas de implantacao para um projeto de %s neste terreno:\n\n"
        "TERRENO: %.1f ha | %s\n"
        "TOPOGRAFIA: desnivel %.1fm | decl. media %.1f%% | orientacao %s\n"
        "AREA UTIL: %d m2 (%d%% do total)\n\n"
        "PROGRAMA DESEJADO:\n%s\n\n"
        "Crie exatamente 3 alternativas com nomes descritivos (ex: Economica, Equilibrada, Premium).\n"
        "Retorne JSON:\n"
        '{"alternativas":[{"nome":"","conceito":"","programa":{"num_lotes":0,"area_media_lote_m2":0,'
        '"area_construida_total_m2":0,"area_verde_m2":0,"area_vias_m2":0,"area_equipamentos_m2":0,'
        '"coef_aproveitamento":0.0},"scores":{"tecnico":0,"economico":0,"ambiental":0,"viabilidade":0},'
        '"vantagens":[],"desvantagens":[],"custo_estimado_infraestrutura":"","vgv_estimado":"",'
        '"prazo_obra_meses":0}],"recomendacao":""}'
    ) % (
        typology,
        terrain.get("area_ha", 0),
        terrain.get("address", ""),
        topo["desnivel"], topo["decl_media"], topo["orientacao_predominante"],
        topo["area_util_m2"],
        round(topo["area_util_m2"] / max(terrain.get("area_m2", 1), 1) * 100),
        json.dumps(programa, ensure_ascii=False, indent=2),
    )
    return await _ask(prompt, temperature=0.5)

# ─── CONCEITO ARQUITETÔNICO ─────────────────────────────────────────────────

async def gerar_conceito_arquitetonico(terrain: dict, implantation: dict,
                                        programa: dict) -> dict:
    prompt = (
        "Crie um conceito arquitetonico detalhado para:\n\n"
        "PROJETO: %s em %s\n"
        "TIPOLOGIA: %s\n"
        "AREA UNIDADE TIPO: %s m2\n"
        "ESTILO: %s\n"
        "PAVIMENTOS: %s\n\n"
        "PROGRAMA DE NECESSIDADES:\n%s\n\n"
        "Retorne JSON:\n"
        '{"memorial_descritivo":"","estilo_arquitetonico":"","materiais_principais":[],'
        '"sustentabilidade":[],"diferenciais":[],'
        '"programa_definitivo":[{"comodo":"","area_m2":0,"caracteristicas":""}],'
        '"sistema_estrutural":"","estimativa_custo_m2":"","prazo_execucao":""}'
    ) % (
        implantation.get("nome", ""),
        terrain.get("address", ""),
        terrain.get("typology_intent", ""),
        programa.get("area_unidade", "nao definida"),
        programa.get("estilo", "contemporaneo brasileiro"),
        programa.get("pavimentos", 1),
        json.dumps(programa.get("comodos", []), ensure_ascii=False),
    )
    return await _ask(prompt, temperature=0.4)

# ─── VIABILIDADE FINANCEIRA ─────────────────────────────────────────────────

async def calcular_viabilidade(terrain: dict, implantation: dict,
                                architecture: dict, cenario: str = "base") -> dict:
    prompt = (
        "Faca uma analise de viabilidade financeira completa:\n\n"
        "LOCAL: %s/%s\n"
        "TIPOLOGIA: %s\n"
        "AREA TOTAL: %.1f hectares\n\n"
        "PROGRAMA:\n"
        "- Lotes/unidades: %d\n"
        "- Area media por lote: %d m2\n"
        "- Area construida total: %d m2\n"
        "- Area de vias: %d m2\n\n"
        "CENARIO: %s (indices do mercado imobiliario brasileiro atual)\n\n"
        "Retorne JSON:\n"
        '{"custos":{"terreno":0,"infraestrutura_loteamento":0,"construcao":0,"projetos_aprovacoes":0,'
        '"marketing_vendas":0,"financeiro_juros":0,"contingencia_percent":0,"total":0},'
        '"receitas":{"vgv_total":0,"preco_medio_por_lote":0,"preco_m2_venda":0,"velocidade_venda_meses":0},'
        '"resultado":{"lucro_bruto":0,"margem_bruta_percent":0,"roi_percent":0,"payback_meses":0,"tir_anual_percent":0},'
        '"custo_por_lote":0,"custo_por_m2_construido":0,'
        '"cronograma_financeiro":[{"fase":"","duracao_meses":0,"custo":0,"percentual":0}],'
        '"fluxo_caixa_anual":[{"ano":0,"investimento":0,"receita":0,"saldo_acumulado":0}],'
        '"cenarios":{"otimista":{"vgv":0,"lucro":0,"margem":0},"base":{"vgv":0,"lucro":0,"margem":0},'
        '"pessimista":{"vgv":0,"lucro":0,"margem":0}},'
        '"recomendacoes_financeiras":[],"alertas":[]}'
    ) % (
        terrain.get("city", ""),
        terrain.get("state", ""),
        terrain.get("typology_intent", ""),
        terrain.get("area_ha", 0),
        implantation.get("num_lotes", 0),
        implantation.get("area_media_lote_m2", 0),
        implantation.get("area_construida_total_m2", 0),
        implantation.get("area_vias_m2", 0),
        cenario,
    )
    return await _ask(prompt, temperature=0.2, max_tokens=4096)

# ─── RELATÓRIO EXECUTIVO ────────────────────────────────────────────────────

async def gerar_resumo_executivo(project_data: dict) -> str:
    prompt = (
        "Escreva um Resumo Executivo tecnico e profissional para este estudo de desenvolvimento imobiliario:\n\n"
        "%s\n\n"
        "O texto deve ter 3-4 paragrafos, linguagem tecnica acessivel, "
        "destacar potencial, viabilidade e proximos passos, "
        "seguindo padroes de relatorios tecnicos brasileiros.\n\n"
        'Retorne JSON: {"resumo_executivo": "texto completo"}'
    ) % json.dumps(project_data, ensure_ascii=False, indent=2)
    result = await _ask(prompt, temperature=0.3)
    return result.get("resumo_executivo", "")
