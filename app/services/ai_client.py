from typing import Dict, Any
import openai
import os
import json


class AIClient:
	def __init__(self):
		self.client = openai.OpenAI(
			api_key=os.getenv("OPENAI_API_KEY", "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")
		)

	async def generate(self, prompt: str, context: Dict[str, Any] | None = None) -> str:
		try:
			# Build system message based on context
			system_message = self._build_system_message(context)
			
			# Create conversation with context
			messages = [
				{"role": "system", "content": system_message},
				{"role": "user", "content": prompt}
			]

			response = self.client.chat.completions.create(
				model="gpt-3.5-turbo",
				messages=messages,
				max_tokens=500,
				temperature=0.7
			)

			return response.choices[0].message.content
		except Exception as e:
			return f"I apologize, but I encountered an error: {str(e)}. Please try again."

	def _build_system_message(self, context: Dict[str, Any] | None) -> str:
		base_message = """You are an AI assistant integrated with a workflow builder system. 
You help users create, manage, and execute automated workflows for phone calls, conversations, and API integrations.

Your capabilities include:
- Helping users design conversation flows
- Assisting with call scripting and transfer logic
- Providing guidance on API integrations
- Explaining workflow concepts and best practices
- Troubleshooting workflow issues

Always be helpful, professional, and provide clear, actionable advice."""

		if context and context.get("workflowLoaded"):
			base_message += "\n\nYou currently have access to a workflow that can be executed. You can reference the workflow structure when providing assistance."
		
		return base_message
