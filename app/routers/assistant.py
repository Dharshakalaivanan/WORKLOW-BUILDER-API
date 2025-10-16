from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import json
from ..database import get_db
from ..models import Workflow
from ..services.ai_client import AIClient
from ..services.workflow_executor import WorkflowExecutor

router = APIRouter(tags=["assistant"])


@router.websocket("/ws/assistant")
async def assistant_socket(ws: WebSocket, workflow_id: int | None = None, db: Session = Depends(get_db)):
	await ws.accept()
	ai = AIClient()
	executor = None
	if workflow_id:
		wf = db.query(Workflow).get(workflow_id)
		if wf:
			executor = WorkflowExecutor(nodes=json.loads(wf.nodes), edges=json.loads(wf.edges))
	try:
		while True:
			data = await ws.receive_text()
			message = json.loads(data) if data.startswith("{") else {"text": data}
			prompt = message.get("text", "")
			response = await ai.generate(prompt, {"workflowLoaded": executor is not None})
			await ws.send_json({"reply": response})
	except WebSocketDisconnect:
		return
