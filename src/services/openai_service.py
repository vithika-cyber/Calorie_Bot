"""
AI Service - Wrapper for Google Gemini API interactions
"""

import json
import logging
from typing import Dict, List, Optional, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import get_settings

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with Google Gemini API"""
    
    def __init__(self):
        """Initialize Gemini service with API key"""
        settings = get_settings()
        self.api_key = settings.google_api_key
        self.model = settings.gemini_model
        
        # Initialize LangChain ChatGoogleGenerativeAI
        self.chat_model = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=0.3,  # Lower temperature for more consistent parsing
            convert_system_message_to_human=True,  # Gemini doesn't support system messages
            response_mime_type="application/json"  # Force JSON responses
        )
    
    def parse_food_message(self, message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a natural language food message into structured data
        
        Args:
            message: User's message about food they ate
            context: Optional context (time of day, previous meals, etc.)
            
        Returns:
            Dictionary with parsed food items and metadata
            
        Example:
            Input: "Had 2 scrambled eggs and whole wheat toast"
            Output: {
                "foods": [
                    {"name": "scrambled eggs", "quantity": 2, "unit": "large", "meal_type": "breakfast"},
                    {"name": "whole wheat toast", "quantity": 1, "unit": "slice", "meal_type": "breakfast"}
                ],
                "confidence": "high",
                "meal_type": "breakfast",
                "clarifications_needed": []
            }
        """
        system_prompt = """You are a nutrition assistant that extracts food items from natural language.

Extract all food items mentioned with their quantities and units. Be smart about inferring:
- Standard serving sizes (e.g., "an apple" = 1 medium apple)
- Common portions (e.g., "toast" = 1 slice)
- Meal type from context (breakfast/lunch/dinner/snack)

Return a JSON object with this structure:
{
    "foods": [
        {
            "name": "food name (lowercase, descriptive)",
            "quantity": numeric quantity,
            "unit": "serving unit (e.g., large, medium, small, slice, cup, grams)",
            "meal_type": "breakfast/lunch/dinner/snack",
            "notes": "any preparation method or additional details"
        }
    ],
    "confidence": "high/medium/low",
    "meal_type": "overall meal type if determinable",
    "clarifications_needed": ["list of questions if ambiguous"]
}

IMPORTANT unit guidelines:
- Use standard units: "serving", "small", "medium", "large", "cup", "piece", "slice", "g", "oz"
- For fruits/vegetables: "small", "medium", or "large" (e.g., 1 medium apple)
- For countable items: "piece" or specific names (e.g., 2 pieces)
- For meals/dishes: "serving" (e.g., 1 serving nachos, 1 serving pasta)
- For drinks: "cup" or "glass"
- NEVER use the food name as the unit (wrong: unit="nacho", correct: unit="serving" or "piece")

Examples:
- "I had an apple" → quantity: 1, unit: "medium"
- "2 eggs" → quantity: 2, unit: "large"
- "a handful of almonds" → quantity: 1, unit: "handful"
- "chicken breast" → quantity: 1, unit: "medium"
- "10 nachos" → quantity: 10, unit: "piece"
- "a protein bar" → quantity: 1, unit: "bar"
- "some nachos" → quantity: 1, unit: "serving"

Be concise but accurate. If unsure about quantity, default to 1 serving."""

        user_prompt = f"Parse this food message: {message}"
        if context:
            user_prompt += f"\n\nContext: {context}"
        
        try:
            # Add explicit JSON instruction to prompt
            user_prompt_with_json = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON, no other text."
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt_with_json)
            ]
            
            response = self.chat_model.invoke(messages)
            
            # Clean response content (remove markdown code blocks if present)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON response
            result = json.loads(content)
            logger.info(f"Parsed food message: {len(result.get('foods', []))} items")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            logger.error(f"Response content: {response.content[:200]}")
            return {
                "foods": [],
                "confidence": "low",
                "meal_type": "other",
                "clarifications_needed": ["Could not understand the food description. Please try again."],
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {
                "foods": [],
                "confidence": "low",
                "meal_type": "other",
                "clarifications_needed": ["An error occurred. Please try again."],
                "error": str(e)
            }
    
    def detect_intent(self, message: str) -> Dict[str, Any]:
        """
        Detect user's intent from their message
        
        Args:
            message: User's message
            
        Returns:
            Dictionary with intent and confidence
            
        Possible intents:
        - log_food: User wants to log food they ate
        - query_history: User wants to see their history
        - query_today: User wants today's summary
        - query_goal: User wants goal information
        - update_food: User wants to modify a previous entry
        - delete_food: User wants to delete an entry
        - general_question: General nutrition question
        - greeting: Just saying hi
        - other: Unclear intent
        """
        system_prompt = """You are an intent classifier for a calorie tracking bot.

Classify the user's message into one of these intents:
- log_food: Logging food they ate (e.g., "I had pizza", "Ate an apple")
- query_history: Asking about past meals (e.g., "What did I eat yesterday?")
- query_today: Asking about today's progress (e.g., "How many calories today?")
- query_goal: Asking about their goal (e.g., "What's my goal?")
- update_food: Wants to correct previous entry (e.g., "Actually that was 3 eggs")
- delete_food: Wants to remove entry (e.g., "Delete my last meal")
- general_question: General nutrition question (e.g., "How many calories in an apple?")
- greeting: Greeting or casual chat (e.g., "Hi", "Hello")
- help: Asking for help (e.g., "How does this work?")
- other: Unclear or doesn't fit above

Return JSON:
{
    "intent": "intent_name",
    "confidence": "high/medium/low",
    "entities": {"key": "value"} // any extracted entities
}"""

        try:
            user_prompt = f"Classify this message: {message}\n\nIMPORTANT: Respond ONLY with valid JSON, no other text."
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            
            # Clean response content
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            
            # Validate result is a dict (sometimes AI returns a list)
            if not isinstance(result, dict):
                logger.warning(f"AI returned non-dict result: {type(result)}")
                return {
                    "intent": "other",
                    "confidence": "low",
                    "entities": {}
                }
            
            logger.info(f"Detected intent: {result.get('intent')} (confidence: {result.get('confidence')})")
            return result
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            return {
                "intent": "other",
                "confidence": "low",
                "entities": {},
                "error": str(e)
            }
    
    def generate_response(self, context: str, data: Dict[str, Any]) -> str:
        """
        Generate a natural language response based on context and data
        
        Args:
            context: What the bot is responding to
            data: Data to include in response
            
        Returns:
            Natural language response string
        """
        system_prompt = """You are a friendly, supportive nutrition coach assistant.
Generate a warm, encouraging response based on the context and data provided.
Keep responses concise (2-3 sentences max) unless more detail is needed.
Be supportive and non-judgmental. Celebrate progress, encourage consistency."""

        user_prompt = f"Context: {context}\nData: {json.dumps(data)}\n\nGenerate an appropriate response."
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm having trouble generating a response right now. Please try again."


# Singleton instance
_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    """
    Get or create OpenAI service instance
    
    Returns:
        OpenAI service singleton
    """
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service


if __name__ == "__main__":
    # Test OpenAI service
    service = get_openai_service()
    
    # Test food parsing
    test_message = "I had 2 scrambled eggs and whole wheat toast for breakfast"
    result = service.parse_food_message(test_message)
    print("Food parsing result:")
    print(json.dumps(result, indent=2))
    
    # Test intent detection
    test_messages = [
        "I ate pizza",
        "What did I eat today?",
        "Hello!",
        "How many calories in an apple?"
    ]
    
    print("\nIntent detection:")
    for msg in test_messages:
        intent = service.detect_intent(msg)
        print(f"'{msg}' → {intent['intent']}")
