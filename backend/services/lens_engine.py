"""
STOA Lens — analise de imagens via Claude Vision.

Quatro modos, um pipeline: a imagem (base64) vai para o Claude com um prompt
especifico do modo e volta JSON estruturado. Quando faz sentido, o resultado
inclui `campos_cadastro` — valores prontos para preencher o formulario de
terreno no frontend (o usuario revisa antes de salvar; nada e gravado
automaticamente).
"""
import json
import os
import anthropic

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "Voce e um especialista em engenharia civil, arquitetura, urbanismo, "
    "documentacao imobiliaria e cartografia no Brasil. Analisa imagens com rigor "
    "tecnico e NUNCA inventa dados que nao estao visiveis na imagem: quando algo "
    "nao e legivel ou nao da para inferir com confianca, devolve null e explica em "
    "'limitacoes'. Responde SEMPRE em JSON valido, sem markdown, sem texto fora do JSON."
)

_PROMPTS = {
    "terreno": """Analise esta FOTO DE TERRENO para estudo de viabilidade imobiliaria.
Devolva JSON com exatamente estas chaves:
{
 "descricao": "descricao objetiva do que se ve (3-5 frases)",
 "vegetacao": "nenhuma|rasteira|arbustiva|arborea|mata",
 "topografia_aparente": "plano|ondulado|acidentado|montanhoso",
 "acesso": "via pavimentada|via de terra|sem acesso definido",
 "construcoes_vizinhas": "o que se ve no entorno",
 "riscos_visiveis": ["lista de riscos: erosao, alagamento, APP, rede eletrica, etc"],
 "potencial": "avaliacao franca do potencial construtivo visivel",
 "limitacoes": "o que NAO da para avaliar por foto (fundacao, solo, zoneamento...)",
 "campos_cadastro": {"vegetation": "...", "topography_general": "...", "access": "...", "zoning_notes": "resumo dos riscos e observacoes"}
}
Os valores de campos_cadastro devem usar exatamente os enums acima.""",

    "documento": """Extraia os dados desta imagem de DOCUMENTO IMOBILIARIO (matricula, escritura, IPTU, contrato etc).
Devolva JSON com exatamente estas chaves:
{
 "tipo_documento": "matricula|escritura|iptu|contrato|outro",
 "endereco": null ou "endereco completo legivel",
 "cidade": null ou "...",
 "estado": null ou "UF",
 "area_m2": null ou numero,
 "matricula_numero": null ou "...",
 "cartorio": null ou "...",
 "proprietario": null ou "...",
 "confrontacoes": null ou "resumo das divisas",
 "onus_gravames": ["hipoteca, penhora, usufruto... se visiveis"],
 "texto_relevante": "transcricao dos trechos-chave legiveis",
 "limitacoes": "partes ilegiveis ou cortadas",
 "campos_cadastro": {"address": null, "city": null, "state": null, "area_ha": null, "zoning_notes": "matricula, cartorio, onus e observacoes"}
}
area_ha = area_m2/10000. So preencha o que estiver LEGIVEL no documento.""",

    "planta": """Interprete esta imagem de PLANTA BAIXA ou CROQUI (pode ser desenho a mao).
Devolva JSON com exatamente estas chaves:
{
 "tipo": "planta tecnica|croqui|desenho a mao|outro",
 "pavimentos_visiveis": numero ou null,
 "ambientes": [{"nome": "...", "dimensoes": "ex: 3,00 x 4,00 m ou null", "area_m2": numero ou null}],
 "area_total_estimada_m2": numero ou null,
 "escala_visivel": null ou "ex: 1:50",
 "observacoes_tecnicas": ["pontos relevantes: estrutura, hidraulica, circulacao..."],
 "inconsistencias": ["cotas que nao fecham, ambientes sem dimensao, etc"],
 "limitacoes": "o que nao da para extrair desta imagem"
}
So calcule areas quando as cotas estiverem legiveis; nao chute dimensoes.""",

    "mapa": """Analise este PRINT DE MAPA/SATELITE (Google Maps, Earth ou similar) com um terreno de interesse.
Devolva JSON com exatamente estas chaves:
{
 "local_identificado": null ou "o que da para identificar por rotulos visiveis",
 "cidade": null ou "...",
 "estado": null ou "UF",
 "coordenadas_visiveis": null ou {"lat": numero, "lon": numero},
 "terreno_demarcado": true/false (ha poligono/marcador visivel?),
 "entorno": "vias, bairros, corpos d'agua, vegetacao visiveis",
 "caracteristicas_relevantes": ["proximidade de rodovia, APP, adensamento..."],
 "limitacoes": "IMPORTANTE: seja explicito que coordenadas so podem ser extraidas se estiverem ESCRITAS na imagem (URL, rotulo, marcador com lat/lon). Nao estime coordenadas visualmente.",
 "campos_cadastro": {"city": null, "state": null, "lat": null, "lon": null, "zoning_notes": "observacoes do entorno"}
}
lat/lon SOMENTE se houver numeros visiveis na imagem; caso contrario null.""",
}

MODES = set(_PROMPTS.keys())


async def analisar_imagem(image_b64: str, media_type: str, mode: str, contexto: str = "") -> dict:
    """Envia a imagem ao Claude com o prompt do modo e devolve o JSON da analise."""
    prompt = _PROMPTS[mode]
    if contexto:
        prompt += f"\n\nContexto adicional fornecido pelo usuario: {contexto[:500]}"

    resp = await client.messages.create(
        model=MODEL,
        max_tokens=3000,
        temperature=0.2,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
