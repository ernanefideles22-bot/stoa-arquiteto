from sqlalchemy import (create_engine, Column, Integer, String, Float,
                         Text, DateTime, JSON, ForeignKey, Boolean)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stoa_civil.db")

# Configuracao adaptada para SQLite (local) e PostgreSQL (Vercel/Supabase)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL: pool_pre_ping garante reconexao em ambiente serverless
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    client = Column(String)
    typology = Column(String)
    description = Column(Text)
    status = Column(String, default="em_estudo")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    terrain = relationship("Terrain", back_populates="project", uselist=False)
    topography = relationship("Topography", back_populates="project", uselist=False)
    implantations = relationship("Implantation", back_populates="project")
    architecture = relationship("Architecture", back_populates="project", uselist=False)
    urbanism = relationship("Urbanism", back_populates="project", uselist=False)
    financial = relationship("Financial", back_populates="project", uselist=False)
    reports = relationship("Report", back_populates="project")

class Terrain(Base):
    __tablename__ = "terrains"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    geojson = Column(JSON)
    area_ha = Column(Float)
    area_m2 = Column(Float)
    perimetro = Column(Float)
    topografia = Column(String)
    vegetacao = Column(String)
    acesso = Column(String)
    infraestrutura = Column(JSON)
    zoneamento = Column(String)
    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="terrain")

class Topography(Base):
    __tablename__ = "topographies"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    elevation_grid = Column(JSON)
    alt_min = Column(Float)
    alt_max = Column(Float)
    desnivel = Column(Float)
    decl_media = Column(Float)
    decl_max = Column(Float)
    orientacao_predominante = Column(String)
    zonas = Column(JSON)
    area_util_m2 = Column(Float)
    area_restrita_m2 = Column(Float)
    direcao_drenagem = Column(JSON)
    img_topografia = Column(Text)
    img_declividade = Column(Text)
    img_solar = Column(Text)
    analise_ia = Column(Text)
    pontos_fortes = Column(JSON)
    restricoes = Column(JSON)
    recomendacoes = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="topography")

class Implantation(Base):
    __tablename__ = "implantations"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    nome = Column(String)
    descricao = Column(Text)
    score_tecnico = Column(Float)
    score_economico = Column(Float)
    score_ambiental = Column(Float)
    score_total = Column(Float)
    num_lotes = Column(Integer)
    area_media_lote = Column(Float)
    area_construida_total = Column(Float)
    area_verde = Column(Float)
    area_vias = Column(Float)
    area_equipamentos = Column(Float)
    layout_svg = Column(Text)
    layout_3d = Column(JSON)
    lotes = Column(JSON)
    vias = Column(JSON)
    areas_comuns = Column(JSON)
    justificativa = Column(Text)
    vantagens = Column(JSON)
    desvantagens = Column(JSON)
    is_selected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="implantations")

class Architecture(Base):
    __tablename__ = "architectures"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    estilo = Column(String)
    area_unidade = Column(Float)
    pavimentos = Column(Integer)
    programa = Column(JSON)
    planta_svg = Column(Text)
    fachada_svg = Column(Text)
    dados_3d = Column(JSON)
    memorial = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="architecture")

class Urbanism(Base):
    __tablename__ = "urbanisms"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    taxa_ocupacao = Column(Float)
    coef_aproveitamento = Column(Float)
    area_permeavel = Column(Float)
    recuo_frontal = Column(Float)
    recuo_lateral = Column(Float)
    recuo_fundos = Column(Float)
    gabarito_max = Column(Float)
    conformidade = Column(JSON)
    restricoes_legais = Column(JSON)
    analise_ia = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="urbanism")

class Financial(Base):
    __tablename__ = "financials"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    custo_terreno = Column(Float)
    custo_infraestrutura = Column(Float)
    custo_construcao = Column(Float)
    custo_projetos = Column(Float)
    custo_marketing = Column(Float)
    custo_financeiro = Column(Float)
    custo_contingencia = Column(Float)
    custo_total = Column(Float)
    custo_por_lote = Column(Float)
    custo_por_m2 = Column(Float)
    vgv = Column(Float)
    preco_medio_lote = Column(Float)
    preco_m2_venda = Column(Float)
    lucro_bruto = Column(Float)
    margem_bruta = Column(Float)
    roi = Column(Float)
    payback_meses = Column(Integer)
    fluxo_caixa = Column(JSON)
    cronograma_obra = Column(JSON)
    analise_ia = Column(Text)
    cenarios = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="financial")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    tipo = Column(String)
    titulo = Column(String)
    filename = Column(String)
    path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="reports")

def create_tables():
    Base.metadata.create_all(bind=engine)
