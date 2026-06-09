"""
Motor de IA — STOA Civil
Orquestra análises usando Claude (Anthropic). Cada função recebe dados reais e retorna análise estruturada.
"""
import json
import os
import anthropic

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

SYSTEM = (
    "Você é um especialista em engenharia civil, arquitetura, urbanismo e desenvolvimento imobiliário no Brasil. "
    "Responde sempre em JSON estruturado, sem markdown, sem texto fora do JSON."
)


async def _ask(prompt: str, temperature: float = 0.3, max_tokens: int = 2048) -> dict:
    """Chama o Claude e parseia JSON da resposta."""
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Remove possível bloco markdown ```json ... ```
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ─── ANÁLISE DE TERRENO ─────────────────────────────────────────────────────

async def analisar_terreno(terrain: dict, topo: dict) -> dict:
    """Análise completa do terreno combinando dados geográficos e topográficos."""
    prompt = f"""
Analise este terreno para desenvolvimento imobiliário no Brasil:

LOCALIZAÇÃO: {terrain.get('address', 'não informado')}, {terrain.get('city', '')}/{terrain.get('state', '')}
ÁREA: {terrain.get('area_ha', 0):.1f} hectares ({terrain.get('area_m2', 0):,.0f} m²)
TIPOLOGIA PRETENDIDA: {terrain.get('typology_intent', 'não definida')}

TOPOGRAFIA:
- Altitude: {topo['alt_min']}m a {topo['alt_max']}m (desnível {topo['desnivel']}m)
- Declividade média: {topo['decl_media']}% | máxima: {topo['decl_max']}%
- Orientação predominante da inclinação: {topo['orientacao_predominante']}
- Área útil (decl < 30%): {topo['area_util_m2']:,} m² ({topo['area_util_m2']/terrain.get('area_m2',1)*100:.0f}%)
- Área restrita (decl > 30%): {topo['area_restrita_m2']:,} m²
- Zonas: {json.dumps(topo['zonas'], ensure_ascii=False)}

CARACTERÍSTICAS:
- Vegetação: {terrain.get('vegetacao', 'não informado')}
- Acesso: {terrain.get('acesso', 'não informado')}
- Infraestrutura disponível: {terrain.get('infraestrutura', [])}
- Zoneamento: {terrain.get('zoneamento', 'não informado')}

Retorne JSON com:
{{
  "resumo": "análise técnica em 3-4 frases sobre o potencial do terreno",
  "pontuacao_geral": numero 0-10,
  "pontos_fortes": ["lista dos maiores ativos do terreno"],
  "restricoes": ["desafios técnicos e legais identificados"],
  "recomendacoes": ["ações prioritárias recomendadas"],
  "tipo_fundacao_recomendado": "tipo mais adequado e justificativa",
  "movimentacao_terra": "estimativa de corte/aterro necessário",
  "aptidao": {{
    "residencial_unifamiliar": 0,
    "condominio_loteamento": 0,
    "comercial": 0,
    "pousada_hotel": 0,
    "industrial": 0
  }},
  "potencial_construtivo": "estimativa de m² construível considerando topografia e recuos",
  "riscos_criticos": ["riscos que precisam de atenção imediata"]
}}
"""
    return await _ask(prompt)


# ─── ALTERNATIVAS DE IMPLANTAÇÃO ────────────────────────────────────────────

async def gerar_alternativas_implantacao(terrain: dict, topo: dict,
                                          typology: str, programa: dict) -> dict:
    """Gera 3 alternativas de implantação para o terreno e tipologia."""
    prompt = f"""
Crie 3 alternativas de implantação para um projeto de {typology} neste terreno:

TERRENO: {terrain.get('area_ha', 0):.1f} ha | {terrain.get('address', '')}
TOPOGRAFIA: desnível {topo['desnivel']}m | decl. média {topo['decl_media']}% | orientação {topo['orientacao_predominante']}
ÁREA ÚTIL: {topo['area_util_m2']:,} m² ({topo['area_util_m2']/terrain.get('area_m2',1)*100:.0f}% do total)

PROGRAMA DESEJADO:
{json.dumps(programa, ensure_ascii=False, indent=2)}

Crie exatamente 3 alternativas com nomes descritivos (ex: "Econômica", "Equilibrada", "Premium").
Cada alternativa deve ter estratégia diferente de aproveitamento do terreno.

Retorne JSON:
{{
  "alternativas": [
    {{
      "nome": "nome da alternativa",
      "conceito": "estratégia e filosofia desta alternativa (2-3 frases)",
      "programa": {{
        "num_lotes": 0,
        "area_media_lote_m2": 0,
        "area_construida_total_m2": 0,
        "area_verde_m2": 0,
        "area_vias_m2": 0,
        "area_equipamentos_m2": 0,
        "coef_aproveitamento": 0.0
      }},
      "scores": {{
        "tecnico": 0,
        "economico": 0,
        "ambiental": 0,
        "viabilidade": 0
      }},
      "vantagens": ["lista"],
      "desvantagens": ["lista"],
      "custo_estimado_infraestrutura": "faixa em R$",
      "vgv_estimado": "faixa do Valor Geral de Vendas em R$",
      "prazo_obra_meses": 0
    }}
  ],
  "recomendacao": "qual alternativa recomendar e por que"
}}
"""
    return await _ask(prompt, temperature=0.5)


# ─── CONCEITO ARQUITETÔNICO ─────────────────────────────────────────────────

async def gerar_conceito_arquitetonico(terrain: dict, implantation: dict,
                                        programa: dict) -> dict:
    """Gera conceito arquitetônico detalhado para a implantação selecionada."""
    prompt = f"""
Crie um conceito arquitetônico detalhado para:

PROJETO: {implantation.get('nome', '')} em {terrain.get('address', '')}
TIPOLOGIA: {terrain.get('typology_intent', '')}
ÁREA UNIDADE TIPO: {programa.get('area_unidade', 'não definida')} m²
ESTILO: {programa.get('estilo', 'contemporâneo brasileiro')}
PAVIMENTOS: {programa.get('pavimentos', 1)}

PROGRAMA DE NECESSIDADES:
{json.dumps(programa.get('comodos', []), ensure_ascii=False)}

Retorne JSON:
{{
  "memorial_descritivo": "texto técnico de 4-6 parágrafos descrevendo o projeto",
  "estilo_arquitetonico": "descrição do partido arquitetônico adotado",
  "materiais_principais": ["lista de materiais e acabamentos principais"],
  "sustentabilidade": ["soluções sustentáveis incorporadas"],
  "diferenciais": ["pontos de destaque do projeto"],
  "programa_definitivo": [
    {{"comodo": "nome", "area_m2": 0, "caracteristicas": "descrição"}}
  ],
  "sistema_estrutural": "sistema construtivo recomendado e justificativa",
  "estimativa_custo_m2": "faixa de custo por m² para a região",
  "prazo_execucao": "prazo estimado de construção da unidade tipo"
}}
"""
    return await _ask(prompt, temperature=0.4)


# ─── VIABILIDADE FINANCEIRA ─────────────────────────────────────────────────

async def calcular_viabilidade(terrain: dict, implantation: dict,
                                 architecture: dict, cenario: str = "base") -> dict:
    """Calcula viabilidade financeira completa do empreendimento."""
    prompt = f"""
Faça uma análise de viabilidade financeira completa para este empreendimento:

LOCAL: {terrain.get('city', '')}/{terrain.get('state', '')}
TIPOLOGIA: {terrain.get('typology_intent', '')}
ÁREA TOTAL: {terrain.get('area_ha', 0):.1f} hectares

PROGRAMA (implantação selecionada):
- Lotes/unidades: {implantation.get('num_lotes', 0)}
- Área média por lote: {implantation.get('area_media_lote_m2', 0)} m²
- Área construída total: {implantation.get('area_construida_total_m2', 0)} m²
- Área de vias: {implantation.get('area_vias_m2', 0)} m²

CENÁRIO: {cenario} (considere índices do mercado imobiliário brasileiro atual)

Retorne JSON:
{{
  "custos": {{
    "terreno": 0,
    "infraestrutura_loteamento": 0,
    "construcao": 0,
    "projetos_aprovacoes": 0,
    "marketing_vendas": 0,
    "financeiro_juros": 0,
    "contingencia_percent": 0,
    "total": 0
  }},
  "receitas": {{
    "vgv_total": 0,
    "preco_medio_por_lote": 0,
    "preco_m2_venda": 0,
    "velocidade_venda_meses": 0
  }},
  "resultado": {{
    "lucro_bruto": 0,
    "margem_bruta_percent": 0,
    "roi_percent": 0,
    "payback_meses": 0,
    "tir_anual_percent": 0
  }},
  "custo_por_lote": 0,
  "custo_por_m2_construido": 0,
  "cronograma_financeiro": [
    {{"fase": "nome", "duracao_meses": 0, "custo": 0, "percentual": 0}}
  ],
  "fluxo_caixa_anual": [
    {{"ano": 0, "investimento": 0, "receita": 0, "saldo_acumulado": 0}}
  ],
  "cenarios": {{
    "otimista": {{"vgv": 0, "lucro": 0, "margem": 0}},
    "base": {{"vgv": 0, "lucro": 0, "margem": 0}},
    "pessimista": {{"vgv": 0, "lucro": 0, "margem": 0}}
  }},
  "recomendacoes_financeiras": ["lista"],
  "alertas": ["riscos financeiros identificados"]
}}
"""
    return await _ask(prompt, temperature=0.2, max_tokens=4096)


# ─── RELATÓRIO EXECUTIVO ────────────────────────────────────────────────────

async def gerar_resumo_executivo(project_data: dict) -> str:
    """Gera texto de resumo executivo para o relatório PDF."""
    prompt = f"""
Escreva um Resumo Executivo técnico e profissional para este estudo de desenvolvimento imobiliário:

{json.dumps(project_data, ensure_ascii=False, indent=2)}

O texto deve:
- Ter 3-4 parágrafos
- Linguagem técnica mas acessível
- Destacar potencial, viabilidade e próximos passos
- Seguir padrões de relatórios técnicos brasileiros

Retorne JSON: {{"resumo_executivo": "texto completo"}}
"""
    result = await _ask(prompt, temperature=0.3)
    return result.get("resumo_executivo", "")
