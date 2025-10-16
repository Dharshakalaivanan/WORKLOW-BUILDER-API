from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db, Base, engine
from .. import models, schemas
import json

# Ensure tables exist
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _to_schema(wf: models.Workflow) -> schemas.WorkflowOut:
	return schemas.WorkflowOut(
		id=wf.id,
		name=wf.name,
		nodes=json.loads(wf.nodes or "[]"),
		edges=json.loads(wf.edges or "[]"),
	)


@router.get("/", response_model=List[schemas.WorkflowOut])
def list_workflows(db: Session = Depends(get_db)):
	items = db.query(models.Workflow).order_by(models.Workflow.updated_at.desc()).all()
	return [_to_schema(w) for w in items]


@router.post("/", response_model=schemas.WorkflowOut)
def create_workflow(payload: schemas.WorkflowCreate, db: Session = Depends(get_db)):
	wf = models.Workflow(
		name=payload.name,
		nodes=json.dumps(payload.nodes),
		edges=json.dumps(payload.edges),
	)
	db.add(wf)
	db.commit()
	db.refresh(wf)
	return _to_schema(wf)


@router.get("/{workflow_id}", response_model=schemas.WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
	wf = db.query(models.Workflow).get(workflow_id)
	if not wf:
		raise HTTPException(status_code=404, detail="Workflow not found")
	return _to_schema(wf)


@router.put("/{workflow_id}", response_model=schemas.WorkflowOut)
def update_workflow(workflow_id: int, payload: schemas.WorkflowUpdate, db: Session = Depends(get_db)):
	wf = db.query(models.Workflow).get(workflow_id)
	if not wf:
		raise HTTPException(status_code=404, detail="Workflow not found")
	if payload.name is not None:
		wf.name = payload.name
	if payload.nodes is not None:
		wf.nodes = json.dumps(payload.nodes)
	if payload.edges is not None:
		wf.edges = json.dumps(payload.edges)
	db.commit()
	db.refresh(wf)
	return _to_schema(wf)


@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
	wf = db.query(models.Workflow).get(workflow_id)
	if not wf:
		raise HTTPException(status_code=404, detail="Workflow not found")
	db.delete(wf)
	db.commit()
	return {"ok": True}
