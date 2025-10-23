from typing import Dict, Any
import openai
import os
import logging

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self):
        self.client = openai.OpenAI(
            # api_key=os.getenv(
            #     "API", ""
            # )
        )

    async def generate(self, prompt: str, context: Dict[str, Any] | None = None) -> str:
        """
        Generate a contextual response for a user prompt using OpenAI chat model.
        """
        try:
            system_message = self._build_system_message(context)
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

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error in AIClient.generate: {e}")
            return f"⚠️ AI Error: {str(e)}"

    async def classify_sentiment(self, message: str) -> str:
        """
        Classify sentiment as 'positive', 'negative', or 'neutral'.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Classify this message sentiment as positive, negative, or neutral."},
                    {"role": "user", "content": message}
                ],
                max_tokens=10,
                temperature=0
            )
            result = response.choices[0].message.content.strip().lower()
            logger.info(f"Sentiment classified as: {result}")
            return result
        except Exception as e:
            logger.error(f"Sentiment classification failed: {e}")
            return "neutral"

    def _build_system_message(self, context: Dict[str, Any] | None) -> str:
        base_message = """You are an AI assistant integrated with a workflow builder system. 
You help users create, manage, and execute automated workflows for phone calls, conversations, and API integrations.

Capabilities:
- Design conversation flows
- Handle call scripting and transfers
- Integrate with APIs
- Explain workflow logic
- Detect conversation tone (positive, negative, neutral)

Always respond professionally and concisely."""

        if context and context.get("workflowLoaded"):
            base_message += "\nYou have access to workflow details. Use them to tailor your responses."

        return base_message
