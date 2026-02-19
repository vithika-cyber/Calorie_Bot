"""
Router Agent - Determines user intent and routes to appropriate agent
"""

import logging
from typing import Dict, Any, Optional
from ..services.openai_service import get_openai_service

logger = logging.getLogger(__name__)


class RouterAgent:
    """Agent that determines user intent from messages"""
    
    def __init__(self):
        """Initialize router agent"""
        self.openai_service = get_openai_service()
    
    def route(self, message: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route user message to appropriate handler
        
        Args:
            message: User's message
            user_context: Optional user context (onboarded status, etc.)
            
        Returns:
            Dictionary with routing decision:
            {
                "intent": "log_food" | "query_history" | "query_today" | "update_food" | "greeting" | "onboarding_needed" | "help" | "other",
                "confidence": "high" | "medium" | "low",
                "data": {...} # Intent-specific data
            }
        """
        # Check if user needs onboarding
        if user_context and not user_context.get("is_onboarded"):
            # Check if this is initial greeting/start
            if self._is_greeting(message):
                return {
                    "intent": "onboarding_needed",
                    "confidence": "high",
                    "data": {"step": "welcome"}
                }
            # If user tries to log food without onboarding, redirect
            return {
                "intent": "onboarding_needed",
                "confidence": "high",
                "data": {"step": "start"}
            }
        
        # Detect intent using OpenAI
        intent_result = self.openai_service.detect_intent(message)
        
        intent = intent_result.get("intent", "other")
        confidence = intent_result.get("confidence", "low")
        entities = intent_result.get("entities", {})
        
        logger.info(f"Routed message to: {intent} (confidence: {confidence})")
        
        return {
            "intent": intent,
            "confidence": confidence,
            "data": entities
        }
    
    def _is_greeting(self, message: str) -> bool:
        """Check if message is a greeting"""
        greetings = [
            "hi", "hello", "hey", "greetings", "good morning",
            "good afternoon", "good evening", "start", "begin"
        ]
        message_lower = message.lower().strip()
        return any(greeting in message_lower for greeting in greetings)


# Singleton instance
_router_agent: Optional[RouterAgent] = None


def get_router_agent() -> RouterAgent:
    """
    Get or create router agent instance
    
    Returns:
        Router agent singleton
    """
    global _router_agent
    if _router_agent is None:
        _router_agent = RouterAgent()
    return _router_agent


if __name__ == "__main__":
    # Test router agent
    agent = get_router_agent()
    
    test_messages = [
        "I had pizza for lunch",
        "What did I eat today?",
        "Hello!",
        "How many calories have I had?",
        "Actually that was 3 eggs not 2",
        "Delete my last meal",
    ]
    
    print("Testing Router Agent:\n")
    for msg in test_messages:
        result = agent.route(msg, {"is_onboarded": True})
        print(f"'{msg}'")
        print(f"  → Intent: {result['intent']} (confidence: {result['confidence']})")
        print()
