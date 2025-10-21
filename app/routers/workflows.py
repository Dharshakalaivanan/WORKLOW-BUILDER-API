from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db, Base, engine
from .. import models, schemas
import json
import sqlite3
from fastapi import FastAPI, Request, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import sqlite3
import time
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


DB_FILE = "workflows.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_workflow_nodes(workflow_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nodes FROM workflows WHERE id=?", (workflow_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row["nodes"]:
        return []
    return json.loads(row["nodes"])  # nodes stored as JSON string

# POST endpoint with workflow_id in path
@router.post("/cursor_prompt/{workflow_id}")
async def cursor_prompt(workflow_id: int, request: Request):
    data = await request.json()
    user_message = data.get("message", "").lower()
    print(f"User message: {user_message}")

    nodes = get_workflow_nodes(workflow_id)
    print(f"Workflow nodes: {nodes}")

    # Default reply
    reply = "Sorry, I didn't understand that."

    # Match the first node where trigger matches user message
    for node in nodes:
        triggers = node.get("data", {}).get("trigger", [])
        print(f"Checking node {node['id']} with triggers: {triggers}")
        if any(trigger.lower() in user_message for trigger in triggers):
            reply = node.get("data", {}).get("prompt", reply)
            print(f"Matched node: {node['id']} | Reply: {reply}")
            break

    # Stream reply word by word for typing effect
    def iter_response():
        for word in reply.split():
            yield word + " "
            time.sleep(0.2)  # simulate typing

    return StreamingResponse(iter_response(), media_type="text/plain")


# @router.get("/get_workflow/{workflow_id}")
# def get_workflow(workflow_id: int = Path(...)):
#     nodes = get_workflow_nodes(workflow_id)
# 	print(nodes,"nodes")
#     return {"nodes": nodes}   

@router.get("/get_workflow/{workflow_id}")
def get_workflow_edges(workflow_id: int = Path(...)):
    nodes = get_workflow_edges(workflow_id)
    print(nodes,"nodes")
    return {"nodes": nodes}    