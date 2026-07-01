"""
STOA Lens — endpoint de analise de imagem.

O frontend redimensiona a imagem antes de enviar (limite de body da Vercel:
~4,5MB), manda base64 + modo, e recebe o JSON da analise. A aplicacao dos
dados ao cadastro e feita no frontend com revisao humana — este endpoint
nao grava nada no banco.
"""
import base64
import binascii
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services import lens_engine
from ..services.errors import error_detail

router = APIRouter(prefix="/api/lens", tags=["lens"])

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_BYTES = 4 * 1024 * 1024  # margem sob o limite de 4,5MB da Vercel


class LensRequest(BaseModel):
    mode: str
    image_base64: str
    media_type: str = "image/jpeg"
    contexto: Optional[str] = ""


@router.post("/analyze")
async def analyze(data: LensRequest):
    if data.mode not in lens_engine.MODES:
        raise HTTPException(400, f"Modo invalido. Use um de: {sorted(lens_engine.MODES)}")
    if data.media_type not in _ALLOWED_TYPES:
        raise HTTPException(400, "Tipo de imagem nao suportado (use JPEG, PNG ou WebP)")

    # valida base64 e tamanho sem materializar copia extra grande
    try:
        raw_len = len(base64.b64decode(data.image_base64, validate=True))
    except (binascii.Error, ValueError):
        raise HTTPException(400, "image_base64 invalido")
    if raw_len < 1024:
        raise HTTPException(400, "Imagem pequena demais — envie uma foto real")
    if raw_len > _MAX_BYTES:
        raise HTTPException(413, "Imagem acima de 4MB mesmo apos compressao — reduza a resolucao")

    try:
        resultado = await lens_engine.analisar_imagem(
            data.image_base64, data.media_type, data.mode, data.contexto or ""
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_detail(e, "lens_analyze"))

    return {"mode": data.mode, "resultado": resultado}
