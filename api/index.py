"""
Entry point para Vercel Serverless Functions.
Importa o app FastAPI e o expoe como handler ASGI.
"""
import sys
import os
import logging

# Adiciona a raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from backend.models.database import create_tables
from backend.main import app

# Cria tabelas na primeira execucao (idempotente, tolerante a falhas)
# Em serverless a conexao pode falhar no cold start — isso nao bloqueia o handler
try:
    create_tables()
except Exception as _e:
    logging.warning("api/index.py create_tables falhou: %s", _e)

# Vercel usa o objeto 'app' diretamente via ASGI
handler = app
