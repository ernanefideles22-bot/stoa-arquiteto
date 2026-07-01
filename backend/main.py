"""
STOA Civil — Plataforma de Desenvolvimento Imobiliário Assistido por IA
"""
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from .models.database import create_tables
from .routers import projects, terrain, implantation, financial, report

# Criar tabelas na inicialização (tolerante a falhas de conexão em serverless)
try:
    create_tables()
except Exception as _e:
    logging.warning("create_tables falhou no startup: %s", _e)

app = FastAPI(
    title="STOA Civil",
    description="Plataforma de Desenvolvimento Imobiliário Assistido por IA",
    version="1.0.0",
)

# CORS_ORIGINS: lista separada por virgula (ex: "https://stoacivil.com.br,https://app.stoacivil.com.br").
# Sem essa variavel definida, mantem o comportamento atual (libera geral) para nao quebrar
# nada em producao sem dominio fixo ainda -- mas o ideal e restringir assim que houver um
# dominio definitivo, em vez de manter allow_origins=["*"] indefinidamente.
_cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] if _cors_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(projects.router)
app.include_router(terrain.router)
app.include_router(implantation.router)
app.include_router(financial.router)
app.include_router(report.router)

# Servir frontend
# Fonte unica de verdade: public/ (mesmo arquivo servido em producao pela Vercel,
# conforme vercel.json). Ate 2026-07 existia um segundo frontend em frontend/index.html
# (Leaflet/MapLibre) que tinha ficado para tras da versao com Cesium 3D publicada em
# producao -- foi removido para eliminar a divergencia entre ambiente local e producao.
FRONTEND_DIR = Path(__file__).parent.parent / "public"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "STOA Civil API rodando", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
