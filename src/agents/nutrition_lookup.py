"""
Nutrition Lookup Agent - Looks up nutrition data for food items
"""

import json
import logging
from typing import Dict, List, Any, Optional
from ..services.usda_service import get_usda_service

logger = logging.getLogger(__name__)


class NutritionAgent:
    """Agent that looks up nutrition data for foods"""
    
    def __init__(self):
        """Initialize nutrition agent"""
        self.usda_service = get_usda_service()
    
    def lookup_nutrition(
        self,
        parsed_foods: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Look up nutrition data for parsed food items."""
        enriched_foods = []
        
        for food in parsed_foods:
            try:
                enriched = self._lookup_single_food(food)
                enriched_foods.append(enriched)
            except Exception as e:
                logger.error(f"Error looking up nutrition for {food.get('name')}: {e}")
                # Add food with estimated/default nutrition
                enriched_foods.append(self._create_fallback_food(food))
        
        return enriched_foods
    
    def _lookup_single_food(self, food: Dict[str, Any]) -> Dict[str, Any]:
        """Look up nutrition for a single food item via USDA."""
        food_name = food.get("name", "")
        quantity = food.get("quantity", 1)
        unit = food.get("unit", "serving")
        
        # Search USDA database
        search_results = self.usda_service.search_foods(food_name, page_size=5)
        
        if not search_results:
            logger.warning(f"No USDA results found for: {food_name}")
            return self._create_fallback_food(food)
        
        # Take the best match (first result)
        best_match = search_results[0]
        
        # Calculate nutrition for the specified serving
        nutrition = self.usda_service.calculate_nutrition_for_serving(
            best_match,
            quantity,
            unit
        )
        
        # Merge with original food data
        enriched = food.copy()
        enriched.update({
            "calories": nutrition["calories"],
            "protein": nutrition["protein"],
            "carbs": nutrition["carbs"],
            "fat": nutrition["fat"],
            "fiber": nutrition.get("fiber", 0),
            "sugar": nutrition.get("sugar", 0),
            "usda_match": best_match["description"],
            "fdc_id": best_match["fdc_id"],
            "source": "usda",
            "confidence": self._calculate_match_confidence(food_name, best_match["description"])
        })
        
        logger.info(
            f"Found nutrition for {food_name}: {nutrition['calories']} cal "
            f"(matched: {best_match['description']})"
        )
        
        return enriched
    
    def _create_fallback_food(self, food: Dict[str, Any]) -> Dict[str, Any]:
        """
        When USDA lookup fails, use AI to estimate nutrition.
        If AI also fails, mark as unknown.
        """
        food_name = food.get("name", "").lower()
        quantity = food.get("quantity", 1)
        unit = food.get("unit", "serving")

        ai_estimate = self._ai_estimate_nutrition(food_name, quantity, unit)
        if ai_estimate:
            enriched = food.copy()
            enriched.update({
                "calories": round(ai_estimate["calories"], 2),
                "protein": round(ai_estimate["protein"], 2),
                "carbs": round(ai_estimate["carbs"], 2),
                "fat": round(ai_estimate["fat"], 2),
                "source": "ai_estimated",
                "confidence": "medium",
                "note": "Nutrition estimated by AI (not from USDA database)"
            })
            logger.info(f"AI estimated nutrition for: {food_name} -> {ai_estimate['calories']} cal")
            return enriched

        enriched = food.copy()
        enriched.update({
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "source": "estimated",
            "confidence": "unknown",
            "note": f"Could not find nutrition data for '{food.get('name', food_name)}'"
        })
        logger.warning(f"Could not estimate nutrition for: {food_name}")
        return enriched

    def _ai_estimate_nutrition(self, food_name: str, quantity: float, unit: str) -> Optional[Dict[str, float]]:
        """Use AI to estimate nutrition when USDA lookup fails."""
        try:
            from ..services.ai_service import get_ai_service
            ai_service = get_ai_service()

            prompt = f"""Estimate the nutritional content for: {quantity} {unit} of {food_name}

Return ONLY a JSON object with these fields (numbers only, no text):
{{
    "calories": <total calories as number>,
    "protein": <grams of protein>,
    "carbs": <grams of carbs>,
    "fat": <grams of fat>
}}

Use your knowledge of typical nutritional values. Be as accurate as possible.
If you truly have no idea what this food is, return: {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "unknown": true}}"""

            result = ai_service.chat_model.invoke(prompt)
            content = result.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)

            if data.get("unknown"):
                return None

            if data.get("calories", 0) > 0:
                return {
                    "calories": float(data["calories"]),
                    "protein": float(data.get("protein", 0)),
                    "carbs": float(data.get("carbs", 0)),
                    "fat": float(data.get("fat", 0))
                }
            return None

        except Exception as e:
            logger.error(f"AI nutrition estimation failed for {food_name}: {e}")
            return None
    
    def _calculate_match_confidence(self, query: str, matched_description: str) -> str:
        """Calculate confidence score for USDA match (high/medium/low)."""
        query_lower = query.lower()
        matched_lower = matched_description.lower()
        
        # Exact match
        if query_lower in matched_lower or matched_lower in query_lower:
            return "high"
        
        # Partial word match
        query_words = set(query_lower.split())
        matched_words = set(matched_lower.split())
        overlap = len(query_words & matched_words)
        
        if overlap >= len(query_words):
            return "high"
        elif overlap >= len(query_words) * 0.5:
            return "medium"
        else:
            return "low"
    
    def calculate_totals(self, enriched_foods: List[Dict[str, Any]]) -> Dict[str, float]:
        """Sum up nutrition totals from all food items."""
        totals = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "fiber": 0,
            "sugar": 0
        }
        
        for food in enriched_foods:
            totals["calories"] += food.get("calories", 0)
            totals["protein"] += food.get("protein", 0)
            totals["carbs"] += food.get("carbs", 0)
            totals["fat"] += food.get("fat", 0)
            totals["fiber"] += food.get("fiber", 0)
            totals["sugar"] += food.get("sugar", 0)
        
        for key in totals:
            totals[key] = round(totals[key], 2)
        
        return totals


# Singleton instance
_nutrition_agent: Optional[NutritionAgent] = None


def get_nutrition_agent() -> NutritionAgent:
    """Get or create nutrition agent singleton."""
    global _nutrition_agent
    if _nutrition_agent is None:
        _nutrition_agent = NutritionAgent()
    return _nutrition_agent
