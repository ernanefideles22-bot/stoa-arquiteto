from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import traceback
import os

from ..models.database import (get_db, engine, Project, Terrain, Topography,
                               Implantation, Financial, Report)
from ..services.errors import error_detail

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    client: Optional[str] = None
    typology: Optional[str] = None
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client: Optional[str] = None
    typology: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.get("/debug-db")
def debug_db():
    """
    Endpoint de diagnostico de conexao com o DB (Vercel/Supabase).
    Desligado por padrao — so responde se ENABLE_DEBUG_ENDPOINTS=true no ambiente,
    pra nao vazar detalhes de infraestrutura em producao.
    """
    if os.getenv("ENABLE_DEBUG_ENDPOINTS", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    db_url = os.getenv("DATABASE_URL", "NOT SET")
    # Mascara a senha para log seguro
    masked = db_url[:20] + "..." if len(db_url) > 20 else db_url
    try:
        with engine.connect() as conn:
            result = conn.execute(__import__("sqlalchemy").text("SELECT 1 as ok"))
            row = result.fetchone()
            return {"status": "ok", "result": row[0], "url_prefix": masked}
    except Exception as e:
        return {"status": "error", "error": str(e), "url_prefix": masked, "traceback": traceback.format_exc()[-500:]}


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    try:
        projects = db.query(Project).order_by(Project.updated_at.desc()).all()
        return [_serialize(p) for p in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_detail(e, "projects"))


@router.post("")
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    try:
        p = Project(**data.model_dump())
        db.add(p)
        db.commit()
        db.refresh(p)
        return _serialize(p)
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_detail(e, "projects"))


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Projeto nao encontrado")
    return _serialize_full(p)


@router.put("/{project_id}")
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Projeto nao encontrado")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Projeto nao encontrado")
    try:
        # As FKs no banco de producao nao tem ON DELETE CASCADE, entao deletar
        # o projeto direto estoura IntegrityError (e o 500 que impedia qualquer
        # exclusao de projeto com dados). Remove os filhos explicitamente antes.
        for model in (Report, Financial, Implantation, Topography, Terrain):
            db.query(model).filter(model.project_id == project_id).delete(
                synchronize_session=False)
        db.delete(p)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_detail(e, "delete_project"))
    return {"ok": True}


def _serialize(p: Project) -> dict:
    return {
        "id": p.id, "name": p.name, "client": p.client,
        "typology": p.typology, "status": p.status,
        "description": p.description,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_full(p: Project) -> dict:
    d = _serialize(p)
    d["has_terrain"]      = p.terrain is not None
    d["has_topography"]   = p.topography is not None
    d["has_implantation"] = len(p.implantations) > 0
    d["has_financial"]    = p.financial is not None
    d["has_implantation_selected"] = any(i.is_selected for i in p.implantations)
    d["implantations_count"] = len(p.implantations)
    return d
