"""
STOA Civil — Plataforma de Desenvolvimento Imobiliário Assistido por IA
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from .models.database import create_tables
from .routers import projects, terrain, implantation, financial

# Criar tabelas na inicialização
create_tables()

app = FastAPI(
    title="STOA Civil",
    description="Plataforma de Desenvolvimento Imobiliário Assistido por IA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(projects.router)
app.include_router(terrain.router)
app.include_router(implantation.router)
app.include_router(financial.router)

# Servir frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
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
