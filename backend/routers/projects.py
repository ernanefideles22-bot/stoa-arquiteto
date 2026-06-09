from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..models.database import get_db, Project

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


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    return [_serialize(p) for p in projects]


@router.post("")
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    p = Project(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Projeto não encontrado")
    return _serialize_full(p)


@router.put("/{project_id}")
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Projeto não encontrado")
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
        raise HTTPException(404, "Projeto não encontrado")
    db.delete(p)
    db.commit()
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
    d["has_architecture"] = p.architecture is not None
    d["has_financial"]    = p.financial is not None
    d["implantations_count"] = len(p.implantations)
    return d
