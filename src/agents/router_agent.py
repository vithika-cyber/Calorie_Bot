"""
Router Agent - Determines user intent and routes to appropriate agent
"""

import re
import logging
from typing import Dict, List, Any, Optional
from ..services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

# Question patterns that indicate a QUERY about past food, not logging new food.
# These are checked before log_food to avoid "what did I eat" matching "ate ".
QUERY_PHRASES = [
    "what did i eat", "what i ate", "what did i have", "what have i eaten",
    "tell me what i ate", "show me what i ate", "can you tell me what",
    "how much did i eat", "how many calories did i",
]

# Order matters: query intents checked first, then log_food, then others
KEYWORD_INTENTS = {
    "query_today": ["today", "so far", "how many calories", "daily", "progress", "summary"],
    "query_history": ["yesterday", "last week", "this week", "history", "past",
                      "jan ", "feb ", "mar ", "apr ", "may ", "jun ",
                      "jul ", "aug ", "sep ", "oct ", "nov ", "dec ",
                      "january", "february", "march", "april", "june",
                      "july", "august", "september", "october", "november", "december"],
    "help": ["help", "how do", "what can", "instructions", "how to use"],
    "greeting": ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"],
    "log_food": ["i had", "i ate", "ate ", "had ", "eaten", "just had",
                 "for breakfast", "for lunch", "for dinner", "for snack"],
}


class RouterAgent:
    """Agent that determines user intent from messages"""

    def __init__(self):
        self.ai_service = get_ai_service()

    def route(self, message: str, user_context: Optional[Dict[str, Any]] = None,
              history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Route user message to appropriate handler based on intent."""
        if user_context and not user_context.get("is_onboarded"):
            if self._match_by_keywords(message, {"greeting": KEYWORD_INTENTS["greeting"]}):
                return {"intent": "onboarding_needed", "confidence": "high", "data": {"step": "welcome"}}
            return {"intent": "onboarding_needed", "confidence": "high", "data": {"step": "start"}}

        keyword_intent = self._match_by_keywords(message, KEYWORD_INTENTS)
        if keyword_intent:
            logger.info(f"Keyword-matched intent: {keyword_intent} (skipped Gemini)")
            return {"intent": keyword_intent, "confidence": "high", "data": {}}

        intent_result = self.ai_service.detect_intent(message, history=history)
        intent = intent_result.get("intent", "other")
        confidence = intent_result.get("confidence", "low")
        entities = intent_result.get("entities", {})
        logger.info(f"Gemini-detected intent: {intent} (confidence: {confidence})")

        return {"intent": intent, "confidence": confidence, "data": entities}

    def _match_by_keywords(self, message: str, intent_map: Dict[str, list]) -> Optional[str]:
        """Try to match message to an intent using keyword lists. Returns None if no match."""
        msg = message.lower().strip()

        if any(qp in msg for qp in QUERY_PHRASES):
            for intent in ("query_today", "query_history"):
                if intent in intent_map:
                    return intent
            return "query_history"

        for intent, keywords in intent_map.items():
            for kw in keywords:
                # Short keywords (<=3 chars like "hi") must be whole words
                # to avoid matching inside other words (e.g. "chicken")
                if len(kw) <= 3:
                    if re.search(r'\b' + re.escape(kw) + r'\b', msg):
                        return intent
                else:
                    if kw in msg:
                        return intent
        return None


_router_agent: Optional[RouterAgent] = None


def get_router_agent() -> RouterAgent:
    """Get or create router agent singleton."""
    global _router_agent
    if _router_agent is None:
        _router_agent = RouterAgent()
    return _router_agent
