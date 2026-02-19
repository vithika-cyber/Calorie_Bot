"""
Food Parser Agent - Extracts structured food data from natural language
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from ..services.openai_service import get_openai_service

logger = logging.getLogger(__name__)


class FoodParserAgent:
    """Agent that parses natural language food descriptions"""
    
    def __init__(self):
        """Initialize food parser agent"""
        self.openai_service = get_openai_service()
    
    def parse(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse food message into structured data
        
        Args:
            message: User's food description
            context: Optional context (time of day, user preferences, etc.)
            
        Returns:
            Dictionary with parsed food data:
            {
                "foods": [
                    {
                        "name": "food name",
                        "quantity": float,
                        "unit": "unit",
                        "meal_type": "breakfast|lunch|dinner|snack",
                        "notes": "optional notes"
                    }
                ],
                "meal_type": "overall meal type",
                "confidence": "high|medium|low",
                "clarifications_needed": ["questions if ambiguous"],
                "timestamp": datetime
            }
        """
        # Build context string
        context_str = self._build_context_string(context)
        
        # Parse using OpenAI
        result = self.openai_service.parse_food_message(message, context_str)
        
        # Add timestamp
        result["timestamp"] = datetime.now()
        result["original_message"] = message
        
        # Log parsing results
        foods_count = len(result.get("foods", []))
        confidence = result.get("confidence", "unknown")
        logger.info(f"Parsed {foods_count} food items with {confidence} confidence")
        
        # Check if clarifications are needed
        if result.get("clarifications_needed"):
            logger.info(f"Clarifications needed: {result['clarifications_needed']}")
        
        return result
    
    def _build_context_string(self, context: Optional[Dict[str, Any]]) -> Optional[str]:
        """Build context string from context dict"""
        if not context:
            return None
        
        parts = []
        
        # Time of day
        now = datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            parts.append("Time: morning (likely breakfast)")
        elif 12 <= hour < 17:
            parts.append("Time: afternoon (likely lunch)")
        elif 17 <= hour < 22:
            parts.append("Time: evening (likely dinner)")
        else:
            parts.append("Time: late night (likely snack)")
        
        # User preferences
        if context.get("preferred_units"):
            parts.append(f"User prefers: {context['preferred_units']}")
        
        # Recent meals
        if context.get("recent_meals"):
            parts.append(f"Recent meals: {context['recent_meals']}")
        
        return " | ".join(parts) if parts else None
    
    def validate_parsed_foods(self, parsed_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate that parsed foods are reasonable
        
        Args:
            parsed_data: Parsed food data
            
        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        
        foods = parsed_data.get("foods", [])
        
        if not foods:
            issues.append("No food items found in the message")
            return False, issues
        
        for i, food in enumerate(foods):
            # Check required fields
            if not food.get("name"):
                issues.append(f"Food item {i+1}: missing name")
            
            if not food.get("quantity"):
                issues.append(f"Food item {i+1} ({food.get('name', 'unknown')}): missing quantity")
            
            # Check reasonable quantities
            quantity = food.get("quantity", 0)
            if quantity <= 0:
                issues.append(f"Food item {i+1} ({food.get('name', 'unknown')}): quantity must be positive")
            elif quantity > 100:
                # Very high quantity might be a parsing error
                issues.append(f"Food item {i+1} ({food.get('name', 'unknown')}): quantity {quantity} seems very high")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def enhance_food_item(self, food: Dict[str, Any], user_prefs: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Enhance a food item with additional metadata
        
        Args:
            food: Food item dictionary
            user_prefs: User preferences
            
        Returns:
            Enhanced food item
        """
        enhanced = food.copy()
        
        # Normalize food name
        enhanced["name"] = food["name"].lower().strip()
        
        # Add search hints for USDA lookup
        enhanced["search_terms"] = self._generate_search_terms(food["name"])
        
        # Add confidence boost for common foods
        if self._is_common_food(food["name"]):
            enhanced["lookup_confidence"] = "high"
        else:
            enhanced["lookup_confidence"] = "medium"
        
        return enhanced
    
    def _generate_search_terms(self, food_name: str) -> List[str]:
        """Generate search terms for nutrition lookup"""
        # Start with the food name
        terms = [food_name.lower()]
        
        # Add variations
        # Remove common preparation words
        prep_words = ["cooked", "raw", "fresh", "frozen", "canned", "grilled", "baked", "fried", "steamed"]
        clean_name = food_name.lower()
        for word in prep_words:
            clean_name = clean_name.replace(word, "").strip()
        
        if clean_name != food_name.lower():
            terms.append(clean_name)
        
        return terms
    
    def _is_common_food(self, food_name: str) -> bool:
        """Check if food is in common foods list"""
        common_foods = {
            "egg", "eggs", "bread", "toast", "apple", "banana", "orange",
            "chicken", "rice", "pasta", "milk", "cheese", "yogurt",
            "salad", "coffee", "tea", "water", "potato", "beef", "fish"
        }
        
        food_lower = food_name.lower()
        return any(common in food_lower for common in common_foods)


# Singleton instance
_food_parser_agent: Optional[FoodParserAgent] = None


def get_food_parser_agent() -> FoodParserAgent:
    """
    Get or create food parser agent instance
    
    Returns:
        Food parser agent singleton
    """
    global _food_parser_agent
    if _food_parser_agent is None:
        _food_parser_agent = FoodParserAgent()
    return _food_parser_agent


if __name__ == "__main__":
    # Test food parser agent
    agent = get_food_parser_agent()
    
    test_messages = [
        "I had 2 scrambled eggs and toast for breakfast",
        "Ate a banana",
        "Lunch was chicken breast with rice and broccoli",
        "Had a handful of almonds as a snack"
    ]
    
    print("Testing Food Parser Agent:\n")
    for msg in test_messages:
        result = agent.parse(msg)
        print(f"Message: '{msg}'")
        print(f"Parsed foods: {len(result['foods'])}")
        for food in result['foods']:
            print(f"  - {food['quantity']} {food.get('unit', '')} {food['name']} ({food.get('meal_type', 'unknown')})")
        print(f"Confidence: {result['confidence']}")
        if result.get('clarifications_needed'):
            print(f"Clarifications: {result['clarifications_needed']}")
        print()
