from fastapi import APIRouter, Depends, HTTPException, Request, Path
from sqlalchemy.orm import Session
from typing import List
from fastapi.responses import StreamingResponse
from ..database import get_db, Base, engine
from .. import models, schemas
import json
import sqlite3
import time
import os
import openai

# ✅ Ensure tables exist
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ---------------------- DB + Utility Helpers ----------------------

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
    return json.loads(row["nodes"])


def _to_schema(wf: models.Workflow) -> schemas.WorkflowOut:
    return schemas.WorkflowOut(
        id=wf.id,
        name=wf.name,
        nodes=json.loads(wf.nodes or "[]"),
        edges=json.loads(wf.edges or "[]"),
    )

# ---------------------- CRUD Endpoints ----------------------

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

# ---------------------- Reload Workflow (for UI) ----------------------

@router.get("/get_workflow/{workflow_id}")
def get_full_workflow(workflow_id: int = Path(...)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nodes, edges FROM workflows WHERE id=?", (workflow_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return {"nodes": [], "edges": []}

    nodes = json.loads(row[0])
    edges = json.loads(row[1])
    print(f"[DEBUG] Reloaded Workflow {workflow_id}: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges}

# ---------------------- AI-Driven Conversation ----------------------

openai.api_key = os.getenv("OPENAI_API_KEY", "sk-your-key-here")

@router.post("/cursor_prompt/{workflow_id}")
async def cursor_prompt(workflow_id: int, request: Request):
    data = await request.json()
    user_message = data.get("message", "").strip().lower()
    print(f"[USER INPUT] {user_message}")

    nodes = get_workflow_nodes(workflow_id)
    print(f"[WORKFLOW NODES] {len(nodes)} loaded")

    reply = "Sorry, I didn't understand that."

    # 1️⃣ Check if user input matches any node trigger
    for node in nodes:
        triggers = node.get("data", {}).get("trigger", [])
        if any(trigger.lower() in user_message for trigger in triggers):
            reply = node.get("data", {}).get("prompt", reply)
            print(f"[MATCH] Node: {node['id']} | Reply: {reply}")
            break

    # 2️⃣ If no trigger matched → classify sentiment using OpenAI
    if reply == "Sorry, I didn't understand that.":
        try:
            print("[AI] Running sentiment classification...")
            sentiment_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Classify this message sentiment as positive, negative, or neutral."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=5,
                temperature=0
            )
            sentiment = sentiment_response.choices[0].message["content"].lower().strip()
            print(f"[SENTIMENT] {sentiment}")

            next_node = None
            if sentiment == "positive":
                next_node = next((n for n in nodes if n["data"].get("label") == "Positive Flow"), None)
            elif sentiment == "negative":
                next_node = next((n for n in nodes if n["data"].get("label") == "Negative Flow"), None)

            if next_node:
                reply = next_node["data"].get("prompt", reply)
        except Exception as e:
            print(f"[ERROR] Sentiment analysis failed: {e}")

    # 3️⃣ Stream the reply word by word for a typing effect
    def iter_response():
        for word in reply.split():
            yield word + " "
            time.sleep(0.2)

    return StreamingResponse(iter_response(), media_type="text/plain")

@router.post("/insert_workflow", response_model=schemas.WorkflowOut)
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

