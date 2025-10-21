from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json
import asyncio
from ..database import get_db
from ..models import Workflow
from ..services.ai_client import AIClient
from ..services.workflow_executor import WorkflowExecutor
import asyncio


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
			
			# Handle Conversation nodes with firstMessage
			if execution_result.get("node_type") == "Conversation":
				first_message = execution_result.get("data", {}).get("first_message", "")
				prompt = execution_result.get("data", {}).get("prompt", "")
				
				if first_message:
					response += f"\n\n🎯 Starting Call:\n\"{first_message}\"\n\n"
				
				if prompt:
					response += f"📋 Assistant Behavior:\n{prompt}\n\n"
				
				response += "✅ Call started. The AI will speak the first message, then listen for user responses and follow the behavior instructions."
			else:
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

@router.post("/cursor_prompt/{workflow_id}")
async def cursor_prompt_stream(workflow_id: int, request: dict, db: Session = Depends(get_db)):
	"""Streaming endpoint for cursor-style prompts"""
	message = request.get("message", "")
	
	ai = AIClient()
	executor = None
	
	wf = db.query(Workflow).get(workflow_id)
	if wf:
		nodes = json.loads(wf.nodes)
		edges = json.loads(wf.edges)
		executor = WorkflowExecutor(nodes=nodes, edges=edges)
	
	async def generate_stream():
		try:
			# Build context for AI
			context = {
				"workflowLoaded": executor is not None,
				"executorStatus": executor.get_execution_status() if executor else None,
				"workflowData": {
					"nodes": nodes,
					"edges": edges
				} if executor else None
			}
			
			# Generate AI response
			response = await ai.generate(message, context)
			
			# Stream the response word by word for typing effect
			words = response.split()
			for i, word in enumerate(words):
				chunk = word + (" " if i < len(words) - 1 else "")
				yield chunk
				await asyncio.sleep(0.05)  # Small delay for typing effect
				
		except Exception as e:
			yield f"Error: {str(e)}"
	
	return StreamingResponse(
		generate_stream(),
		media_type="text/plain",
		headers={"Cache-Control": "no-cache"}
	)