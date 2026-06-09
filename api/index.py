"""
Entry point para Vercel Serverless Functions.
Importa o app FastAPI e o expõe como handler ASGI.
"""
import sys
import os

# Adiciona a raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from backend.models.database import create_tables
from backend.main import app

# Cria tabelas na primeira execução (idempotente)
create_tables()

# Vercel usa o objeto `app` diretamente via ASGI
handler = app
