from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import json
from ..database import get_db
from ..models import Workflow
from ..services.ai_client import AIClient
from ..services.workflow_executor import WorkflowExecutor, VapiWorkflowExecutor
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
    
    executor = None
    is_vapi_workflow = False

    while True:
        try:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("text", "")
            print("User message:", user_message)

            # Initialize executor if not already done
            if not executor:
                workflow_data = get_workflow_data(workflow_id)
                nodes = workflow_data.get("nodes", [])
                edges = workflow_data.get("edges", [])
                global_prompt = workflow_data.get("global_prompt", "")
                
                print("Workflow nodes:", nodes)
                print("Workflow edges:", edges)
                
                if nodes:
                    # Detect if this is a Vapi-style workflow
                    is_vapi_workflow = any(node.get('type') == 'vapi' or node.get('data', {}).get('type') in ['conversation', 'tool', 'condition', 'api'] for node in nodes)
                    
                    if is_vapi_workflow:
                        executor = VapiWorkflowExecutor(nodes=nodes, edges=edges, global_prompt=global_prompt)
                        # Start the workflow
                        start_result = executor.start_execution()
                        
                        # Send the first message from the start node
                        start_node = executor.get_current_node()
                        if start_node:
                            node_data = start_node.get('data', start_node)
                            first_message = node_data.get('messagePlan', {}).get('firstMessage', '')
                            
                            if first_message:
                                await websocket.send_json({
                                    "type": "assistant_message",
                                    "content": first_message
                                })
                        
                        await websocket.send_json({
                            "type": "workflow_loaded",
                            "message": f"Vapi workflow loaded with {len(nodes)} nodes",
                            "workflow_type": "vapi"
                        })
                    else:
                        executor = WorkflowExecutor(nodes=nodes, edges=edges)
                        await websocket.send_json({
                            "type": "workflow_loaded", 
                            "message": f"Legacy workflow loaded with {len(nodes)} nodes",
                            "workflow_type": "legacy"
                        })
                continue  # Skip processing on first connection

            # Generate response based on workflow type
            if executor and is_vapi_workflow:
                # Get current node data
                current_node = executor.get_current_node()
                if not current_node:
                    await websocket.send_json({
                        "type": "assistant_message",
                        "content": "I'm sorry, I couldn't process that. Let's start over."
                    })
                    continue
                
                node_data = current_node.get('data', current_node)
                node_type = node_data.get('type')
                
                print(f"Processing node: {node_data.get('name')} (type: {node_type})")
                
                if node_type == "conversation":
                    prompt = node_data.get('prompt', '')
                    
                    # Build AI prompt with context
                    ai_prompt = f"""{executor.global_prompt}

{prompt}

User said: {user_message}

Respond naturally based on the prompt above. Keep it conversational and helpful."""
                    
                    reply = await ai_client.generate(ai_prompt, context={"workflowLoaded": True})
                    
                    # Send assistant response
                    await websocket.send_json({
                        "type": "assistant_message",
                        "content": reply
                    })
                    
                    # Check if we should move to next node based on edges
                    outgoing_edges = [e for e in edges if e.get("source") == current_node.get('id')]
                    
                    if outgoing_edges:
                        # Evaluate which edge to take based on user response and edge conditions
                        best_edge = await evaluate_edge_condition(user_message, reply, outgoing_edges, ai_client)
                        
                        if best_edge:
                            # Move to next node
                            next_node_id = best_edge.get('target')
                            if next_node_id in executor.nodes:
                                executor.current_node_id = next_node_id
                                print(f"Moving to node: {next_node_id}")
                                
                                # Execute the next node immediately if it has a first message
                                next_node = executor.get_current_node()
                                next_data = next_node.get('data', next_node)
                                next_first_message = next_data.get('messagePlan', {}).get('firstMessage', '')
                                
                                if next_first_message:
                                    await websocket.send_json({
                                        "type": "assistant_message",
                                        "content": next_first_message
                                    })
                    
                elif node_type == "tool":
                    tool_config = node_data.get('tool', {})
                    tool_type = tool_config.get('type')
                    
                    if tool_type == "endCall":
                        messages = tool_config.get('messages', [])
                        end_message = messages[0].get('content', 'Thank you for calling. Goodbye!') if messages else 'Thank you for calling. Goodbye!'
                        
                        await websocket.send_json({
                            "type": "assistant_message",
                            "content": end_message
                        })
                        
                        await websocket.send_json({
                            "type": "call_ended",
                            "reason": "workflow_complete"
                        })
                        break
                    
            else:
                # Legacy workflow execution
                reply = "Sorry, I didn't understand that."
                
                workflow_data = get_workflow_data(workflow_id)
                nodes = workflow_data.get("nodes", [])
                
                for node in nodes:
                    triggers = node.get("data", {}).get("trigger", [])
                    base_prompt = node.get("data", {}).get("prompt", "")
                    if any(trigger.lower() in user_message.lower() for trigger in triggers):
                        prompt = f"""
                        Node prompt: {base_prompt}
                        User said: {user_message}
                        Respond appropriately with context-aware, professional, and relational reply.
                        """
                        reply = await ai_client.generate(prompt, context={"workflowLoaded": True})
                        break

                print("Replying with:", reply)
                await websocket.send_json({"type": "assistant_message", "content": reply})

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

async def evaluate_edge_condition(user_message: str, assistant_reply: str, edges: list, ai_client: AIClient) -> dict:
    """
    Evaluate which edge to follow based on user input and edge conditions.
    Uses AI to determine if the condition matches.
    """
    if len(edges) == 1:
        return edges[0]
    
    # Use AI to evaluate which condition matches best
    edge_descriptions = []
    for i, edge in enumerate(edges):
        label = edge.get('label', '')
        edge_descriptions.append(f"{i}. {label}")
    
    ai_prompt = f"""Given this conversation:
User: {user_message}
Assistant: {assistant_reply}

Which of these conditions best matches the user's intent?
{chr(10).join(edge_descriptions)}

Respond with ONLY the number (0, 1, 2, etc.) of the best matching condition."""
    
    try:
        result = await ai_client.generate(ai_prompt, context={})
        choice = int(result.strip())
        if 0 <= choice < len(edges):
            return edges[choice]
    except:
        pass
    
    # Default to first edge if AI evaluation fails
    return edges[0]

def get_workflow_data(workflow_id: int) -> dict:
    """
    Fetch complete workflow data including nodes and edges.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT nodes, edges, name FROM workflows WHERE id=?", (workflow_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"nodes": [], "edges": [], "name": ""}
    
    try:
        nodes = json.loads(row["nodes"]) if row["nodes"] else []
        edges = json.loads(row["edges"]) if row["edges"] else []
        return {
            "nodes": nodes,
            "edges": edges,
            "name": row["name"],
            "global_prompt": ""
        }
    except json.JSONDecodeError:
        return {"nodes": [], "edges": [], "name": ""}

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