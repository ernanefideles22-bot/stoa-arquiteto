"""
Tratamento seguro de erros para respostas HTTP.

Regra: o traceback completo SEMPRE vai para o log do servidor (visivel nos
logs da Vercel), mas NUNCA para o cliente em producao. Antes deste modulo,
varios endpoints devolviam `traceback.format_exc()` no corpo do 500 -- o que
vazava detalhes de infraestrutura (ex.: usuario do banco no erro do pg8000)
para qualquer visitante.

Com ENABLE_DEBUG_ENDPOINTS=true (mesma env var que libera /api/projects/debug-db),
o traceback tambem e incluido na resposta, para facilitar debug em ambiente
de desenvolvimento.
"""
import logging
import os
import traceback

logger = logging.getLogger("stoa")


def _debug_enabled() -> bool:
    return os.getenv("ENABLE_DEBUG_ENDPOINTS", "").lower() == "true"


def error_detail(e: Exception, context: str = "") -> dict:
    """Loga o erro completo e devolve um detalhe seguro para HTTPException(500)."""
    tb = traceback.format_exc()
    logger.error("Erro em %s: %s\n%s", context or "endpoint", e, tb)
    if _debug_enabled():
        return {"error": str(e), "traceback": tb[-1000:]}
    return {"error": "Erro interno no servidor. Tente novamente; se persistir, contate o suporte."}


def debug_or_none(value):
    """Devolve `value` apenas em modo debug (para campos debug_* de respostas)."""
    return value if _debug_enabled() else None
