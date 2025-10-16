from typing import Dict, Any, List


class WorkflowExecutor:
	def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
		self.nodes = {n.get("id"): n for n in nodes}
		self.edges = edges

	def _find_start(self) -> str | None:
		for node in self.nodes.values():
			if node.get("type") == "start":
				return node.get("id")
		return next(iter(self.nodes)) if self.nodes else None

	def next_node(self, current_id: str | None) -> str | None:
		if current_id is None:
			return self._find_start()
		for e in self.edges:
			if e.get("source") == current_id:
				return e.get("target")
		return None
