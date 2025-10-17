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
			nodes = json.loads(wf.nodes)
			edges = json.loads(wf.edges)
			executor = WorkflowExecutor(nodes=nodes, edges=edges)
			await ws.send_json({
				"type": "workflow_loaded",
				"message": f"Workflow '{wf.name}' loaded with {len(nodes)} nodes and {len(edges)} edges"
			})
	
	try:
		while True:
			data = await ws.receive_text()
			message = json.loads(data) if data.startswith("{") else {"text": data}
			
			user_prompt = message.get("text", "")
			workflow_data = message.get("workflow", {})
			
			# Build context for AI
			context = {
				"workflowLoaded": executor is not None,
				"workflowData": workflow_data,
				"executorStatus": executor.get_execution_status() if executor else None
			}
			
			# Generate AI response
			response = await ai.generate(user_prompt, context)
			
			# If executor exists and user wants to execute workflow
			if executor and ("execute" in user_prompt.lower() or "run" in user_prompt.lower()):
				execution_result = executor.execute_current_node(user_prompt)
				response += f"\n\nWorkflow Execution:\n{execution_result['message']}"
				
				# Move to next node
				next_node_id = executor.move_to_next_node()
				if next_node_id:
					response += f"\n\nMoving to next node: {next_node_id}"
				else:
					response += "\n\nWorkflow execution completed."
			
			await ws.send_json({
				"type": "response",
				"reply": response,
				"executor_status": executor.get_execution_status() if executor else None
			})
			
	except WebSocketDisconnect:
		return
	except Exception as e:
		await ws.send_json({
			"type": "error",
			"message": f"Error: {str(e)}"
		})


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
