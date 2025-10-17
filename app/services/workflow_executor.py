from typing import Dict, Any, List, Optional
import json
import asyncio


class WorkflowExecutor:
	def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
		self.nodes = {n.get("id"): n for n in nodes}
		self.edges = edges
		self.current_node_id: Optional[str] = None
		self.execution_history: List[Dict[str, Any]] = []

	def _find_start(self) -> Optional[str]:
		"""Find the starting node in the workflow"""
		for node in self.nodes.values():
			if node.get("data", {}).get("type") == "Conversation":
				return node.get("id")
		return next(iter(self.nodes)) if self.nodes else None

	def get_current_node(self) -> Optional[Dict[str, Any]]:
		"""Get the current node being executed"""
		if self.current_node_id:
			return self.nodes.get(self.current_node_id)
		return None

	def start_execution(self) -> Dict[str, Any]:
		"""Start workflow execution from the beginning"""
		self.current_node_id = self._find_start()
		self.execution_history = []
		
		if self.current_node_id:
			node = self.nodes[self.current_node_id]
			return {
				"action": "start",
				"node": node,
				"message": f"Starting workflow execution at node: {node.get('data', {}).get('label', self.current_node_id)}"
			}
		return {"action": "error", "message": "No starting node found"}

	def execute_current_node(self, user_input: str = "") -> Dict[str, Any]:
		"""Execute the current node and return the result"""
		if not self.current_node_id:
			return self.start_execution()

		current_node = self.nodes[self.current_node_id]
		node_data = current_node.get("data", {})
		node_type = node_data.get("type")

		result = {
			"node_id": self.current_node_id,
			"node_type": node_type,
			"action": "continue",
			"message": "",
			"data": {}
		}

		if node_type == "Conversation":
			prompt = node_data.get("prompt", "")
			result["message"] = f"Conversation node: {prompt}"
			result["data"]["prompt"] = prompt
			result["data"]["user_input"] = user_input

		elif node_type == "Call":
			phone_number = node_data.get("phoneNumber", "")
			call_script = node_data.get("callScript", "")
			result["message"] = f"Making call to {phone_number}"
			result["data"]["phone_number"] = phone_number
			result["data"]["script"] = call_script

		elif node_type == "Transfer Call":
			transfer_number = node_data.get("transferNumber", "")
			transfer_message = node_data.get("transferMessage", "")
			result["message"] = f"Transferring call to {transfer_number}"
			result["data"]["transfer_number"] = transfer_number
			result["data"]["transfer_message"] = transfer_message

		elif node_type == "API Request":
			method = node_data.get("method", "GET")
			url = node_data.get("url", "")
			result["message"] = f"Making {method} request to {url}"
			result["data"]["method"] = method
			result["data"]["url"] = url

		elif node_type == "End Call":
			result["message"] = "Ending call"
			result["action"] = "end"

		# Record execution
		self.execution_history.append({
			"node_id": self.current_node_id,
			"timestamp": asyncio.get_event_loop().time(),
			"result": result
		})

		return result

	def move_to_next_node(self) -> Optional[str]:
		"""Move to the next node in the workflow"""
		if not self.current_node_id:
			return None

		# Find next node based on edges
		for edge in self.edges:
			if edge.get("source") == self.current_node_id:
				next_node_id = edge.get("target")
				if next_node_id in self.nodes:
					self.current_node_id = next_node_id
					return next_node_id

		# No next node found
		self.current_node_id = None
		return None

	def get_execution_status(self) -> Dict[str, Any]:
		"""Get current execution status"""
		return {
			"current_node_id": self.current_node_id,
			"total_nodes": len(self.nodes),
			"execution_history_length": len(self.execution_history),
			"is_complete": self.current_node_id is None
		}

	def reset_execution(self):
		"""Reset execution to start"""
		self.current_node_id = None
		self.execution_history = []
