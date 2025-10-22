from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import json
from ..database import get_db
from ..models import Workflow
from ..services.ai_client import AIClient
from ..services.workflow_executor import WorkflowExecutor
import asyncio
import sqlite3
import json


router = APIRouter(tags=["assistant"])


ai_client = AIClient()

@router.websocket("/ws/assistant")
async def assistant_ws(websocket: WebSocket):
    await websocket.accept()
    workflow_id = int(websocket.query_params.get("workflow_id", 0))
    print("Connected to workflow_id:", workflow_id)

    while True:
        try:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("text", "").lower()
            print("User message:", user_message)

            nodes = get_workflow_nodes(workflow_id)
            print("Workflow nodes:", nodes)

            reply = "Sorry, I didn't understand that."

            for node in nodes:
                triggers = node.get("data", {}).get("trigger", [])
                base_prompt = node.get("data", {}).get("prompt", "")
                if any(trigger.lower() in user_message for trigger in triggers):
                    # Generate OpenAI reply using node prompt
                    prompt = f"""
                    Node prompt: {base_prompt}
                    User said: {user_message}
                    Respond appropriately with context-aware, professional, and relational reply.
                    """
                    reply = await ai_client.generate(prompt, context={"workflowLoaded": True})
                    break

            print("Replying with:", reply)
            await websocket.send_json({"reply": reply})

        except Exception as e:
            print("WebSocket error:", e)
            break



@router.post("/assistant/execute-workflow/{workflow_id}")
async def execute_workflow(workflow_id: int, db: Session = Depends(get_db)):

	"""Execute a workflow programmatically"""
	wf = db.query(Workflow).get(workflow_id)
	if not wf:
		return {"error": "Workflow not found"}
	
	nodes = json.loads(wf.nodes)
	edges = json.loads(wf.edges)
	executor = WorkflowExecutor(nodes=nodes, edges=edges)
	
	# Start execution
	result = executor.start_execution()
	execution_log = [result]
	
	# Execute all nodes
	while executor.current_node_id:
		node_result = executor.execute_current_node()
		execution_log.append(node_result)
		executor.move_to_next_node()
	
	return {
		"workflow_id": workflow_id,
		"execution_log": execution_log,
		"status": "completed"
	}

@router.websocket("/cursor_prompt")
async def cursor_prompt(websocket: WebSocket):
    await websocket.accept()
    while True:
        msg = await websocket.receive_text()
        # Simulate cursor typing (streamed response)
        for word in ["Typing", "your", "response", "now..."]:
            await websocket.send_text(word)
            await asyncio.sleep(0.5)
        await websocket.send_text(f"Echo: {msg}")


DB_FILE = "workflows.db"

def get_connection():
    """Return a SQLite connection with row factory as dictionary."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_workflow_nodes(workflow_id: int):
    """
    Fetch workflow nodes for a given workflow ID.
    
    Returns:
        List[Dict]: List of nodes with their data and triggers.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT nodes FROM workflows WHERE id=?", (workflow_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row["nodes"]:
        return []
    
    try:
        nodes = json.loads(row["nodes"])
        # Ensure each node has 'data' key
        for node in nodes:
            if "data" not in node:
                node["data"] = {}
        return nodes
    except json.JSONDecodeError:
        return []