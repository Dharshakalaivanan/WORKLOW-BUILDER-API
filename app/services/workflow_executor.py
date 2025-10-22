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


class VapiWorkflowExecutor:
	def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], global_prompt: str = ""):
		self.nodes = {n.get("id"): n for n in nodes}
		self.edges = edges
		self.global_prompt = global_prompt
		self.current_node_id: Optional[str] = None
		self.execution_history: List[Dict[str, Any]] = []
		self.extracted_variables: Dict[str, Any] = {}

	def _find_start_node(self) -> Optional[str]:
		"""Find the starting node in the workflow"""
		for node in self.nodes.values():
			# Check both at root level and in data
			node_data = node.get("data", node)
			if node_data.get("isStart") or node.get("isStart"):
				return node.get("id")
		# Fallback to first conversation node
		for node in self.nodes.values():
			node_data = node.get("data", node)
			if node_data.get("type") == "conversation" or node.get("type") == "vapi":
				return node.get("id")
		return next(iter(self.nodes)) if self.nodes else None

	def get_current_node(self) -> Optional[Dict[str, Any]]:
		"""Get the current node being executed"""
		if self.current_node_id:
			return self.nodes.get(self.current_node_id)
		return None

	def start_execution(self) -> Dict[str, Any]:
		"""Start workflow execution from the beginning"""
		self.current_node_id = self._find_start_node()
		self.execution_history = []
		self.extracted_variables = {}

		if self.current_node_id:
			node = self.nodes[self.current_node_id]
			return {
				"action": "start",
				"node": node,
				"message": f"Starting workflow execution at node: {node.get('name', self.current_node_id)}"
			}
		return {"action": "error", "message": "No starting node found"}

	def execute_current_node(self, user_input: str = "") -> Dict[str, Any]:
		"""Execute the current node and return the result"""
		if not self.current_node_id:
			return self.start_execution()

		current_node = self.nodes[self.current_node_id]
		node_type = current_node.get("type")

		result = {
			"node_id": self.current_node_id,
			"node_type": node_type,
			"action": "continue",
			"message": "",
			"data": {},
			"extracted_variables": {}
		}

		if node_type == "conversation":
			# Handle conversation node
			first_message = current_node.get("messagePlan", {}).get("firstMessage", "")
			prompt = current_node.get("prompt", "")
			
			result["message"] = f"Conversation: {current_node.get('name', 'Unknown')}"
			result["data"]["first_message"] = first_message
			result["data"]["prompt"] = prompt
			result["data"]["user_input"] = user_input
			
			# Extract variables if configured
			variable_plan = current_node.get("variableExtractionPlan", {})
			if variable_plan.get("output"):
				extracted = self._extract_variables(user_input, variable_plan["output"])
				result["extracted_variables"] = extracted
				self.extracted_variables.update(extracted)

		elif node_type == "tool":
			# Handle tool node
			tool_config = current_node.get("tool", {})
			tool_type = tool_config.get("type")
			
			if tool_type == "transferCall":
				destinations = tool_config.get("destinations", [])
				result["message"] = f"Transferring call to: {', '.join(destinations)}"
				result["data"]["destinations"] = destinations
				result["action"] = "transfer"
				
			elif tool_type == "endCall":
				messages = tool_config.get("messages", [])
				end_message = messages[0].get("content", "Thank you for calling. Goodbye!") if messages else "Thank you for calling. Goodbye!"
				result["message"] = f"Ending call: {end_message}"
				result["data"]["end_message"] = end_message
				result["action"] = "end"
				
			elif tool_type == "apiRequest":
				result["message"] = f"Making API request: {current_node.get('prompt', 'No endpoint specified')}"
				result["data"]["endpoint"] = current_node.get("prompt", "")
				result["action"] = "api_request"

		elif node_type == "condition":
			# Handle condition node
			condition_prompt = current_node.get("prompt", "")
			result["message"] = f"Evaluating condition: {condition_prompt}"
			result["data"]["condition"] = condition_prompt
			result["data"]["user_input"] = user_input

		elif node_type == "api":
			# Handle API node
			endpoint = current_node.get("prompt", "")
			result["message"] = f"API Request to: {endpoint}"
			result["data"]["endpoint"] = endpoint
			result["action"] = "api_request"

		# Record execution
		self.execution_history.append({
			"node_id": self.current_node_id,
			"timestamp": asyncio.get_event_loop().time(),
			"result": result
		})

		return result

	def _extract_variables(self, user_input: str, variable_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""Extract variables from user input based on the variable extraction plan"""
		extracted = {}
		
		for variable in variable_plan:
			var_name = variable.get("title", "")
			var_type = variable.get("type", "string")
			enum_values = variable.get("enum", [])
			
			if enum_values:
				# Check if user input matches any enum value
				user_lower = user_input.lower()
				for enum_val in enum_values:
					if enum_val.lower() in user_lower:
						extracted[var_name] = enum_val
						break
			else:
				# For non-enum variables, we'll need AI to extract them
				# For now, just store the raw input
				extracted[var_name] = user_input
		
		return extracted

	def move_to_next_node(self, condition_result: str = None) -> Optional[str]:
		"""Move to the next node based on edge conditions"""
		if not self.current_node_id:
			return None

		# Find outgoing edges from current node (support both from/to and source/target)
		outgoing_edges = [
			e for e in self.edges 
			if e.get("from") == self.current_node_id or e.get("source") == self.current_node_id
		]
		
		if not outgoing_edges:
			self.current_node_id = None
			return None

		# For now, take the first edge (in a real implementation, you'd evaluate conditions)
		next_edge = outgoing_edges[0]
		next_node_id = next_edge.get("to") or next_edge.get("target")
		
		if next_node_id in self.nodes:
			self.current_node_id = next_node_id
			return next_node_id
		
		self.current_node_id = None
		return None

	def get_execution_status(self) -> Dict[str, Any]:
		"""Get current execution status"""
		return {
			"current_node_id": self.current_node_id,
			"total_nodes": len(self.nodes),
			"execution_history_length": len(self.execution_history),
			"is_complete": self.current_node_id is None,
			"extracted_variables": self.extracted_variables,
			"global_prompt": self.global_prompt
		}

	def reset_execution(self):
		"""Reset execution to start"""
		self.current_node_id = None
		self.execution_history = []
		self.extracted_variables = {}
