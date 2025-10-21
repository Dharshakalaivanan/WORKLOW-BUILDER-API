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

			response_text = response.choices[0].message.content
			
			# If this is a workflow conversation, enhance the response
			if context and context.get("workflowLoaded"):
				response_text = self._enhance_workflow_response(response_text, context)
			
			return response_text
		except Exception as e:
			return f"I apologize, but I encountered an error: {str(e)}. Please try again."

	def _enhance_workflow_response(self, response: str, context: Dict[str, Any]) -> str:
		"""Enhance responses for workflow conversations"""
		# Add workflow context to make responses more relevant
		if "workflow" in response.lower() or "call" in response.lower():
			return response
		
		# For general responses, make them more call-focused
		return f"In this phone call workflow: {response}"

	def _build_system_message(self, context: Dict[str, Any] | None) -> str:
		base_message = """You are an AI assistant for a phone call automation system.

CRITICAL RULES:
- NEVER say "I didn't understand" or "Sorry, I didn't understand"
- NEVER repeat words or phrases
- ALWAYS provide helpful, specific responses
- Be conversational and engaging
- If you don't understand something, ask clarifying questions in a helpful way

Your role is to:
- Help users with phone call workflows
- Provide intelligent responses to user queries
- Be conversational and helpful
- Follow the assistant behavior instructions when provided

When users speak to you:
- Listen carefully and respond appropriately
- Ask follow-up questions to better understand their needs
- Provide helpful information and guidance
- Be encouraging and supportive"""

		if context and context.get("workflowLoaded"):
			base_message += "\n\nYou currently have access to a workflow that can be executed. You can reference the workflow structure when providing assistance."
			
			# Add assistant behavior from workflow if available
			workflow_data = context.get("workflowData", {})
			if workflow_data:
				nodes = workflow_data.get("nodes", [])
				conversation_node = next((node for node in nodes if node.get("data", {}).get("type") == "Conversation"), None)
				if conversation_node:
					assistant_behavior = conversation_node.get("data", {}).get("prompt", "")
					if assistant_behavior:
						base_message += f"\n\nAssistant Behavior Instructions:\n{assistant_behavior}"

		return base_message
