from typing import Dict, Any


class AIClient:
	def __init__(self):
		pass

	async def generate(self, prompt: str, context: Dict[str, Any] | None = None) -> str:
		ctx = f" with context {context}" if context else ""
		return f"AI response to: '{prompt}'{ctx}"
