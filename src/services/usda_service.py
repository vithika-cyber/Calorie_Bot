"""
USDA Service - Wrapper for USDA FoodData Central API
"""

import logging
from typing import Dict, List, Optional, Any
import httpx
from datetime import datetime, timedelta

from ..config import get_settings

logger = logging.getLogger(__name__)


class USDAService:
    """Service for interacting with USDA FoodData Central API"""
    
    def __init__(self):
        """Initialize USDA service"""
        settings = get_settings()
        self.base_url = settings.usda_base_url
        self.api_key = settings.usda_api_key
        
        # Simple in-memory cache for frequent lookups
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(hours=24)  # Cache for 24 hours
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for: {key}")
                return data
            else:
                del self._cache[key]
        return None
    
    def _add_to_cache(self, key: str, data: Any) -> None:
        """Add data to cache"""
        self._cache[key] = (data, datetime.now())
    
    def search_foods(self, query: str, page_size: int = 10) -> List[Dict[str, Any]]:
        """
        Search for foods in USDA database
        
        Args:
            query: Food name to search for
            page_size: Number of results to return
            
        Returns:
            List of food items with nutrition data
            
        Example result:
            [
                {
                    "fdc_id": 12345,
                    "description": "Egg, whole, raw, fresh",
                    "data_type": "Survey (FNDDS)",
                    "calories": 143,
                    "protein": 12.6,
                    "carbs": 0.7,
                    "fat": 9.5,
                    "serving_size": 100,
                    "serving_unit": "g"
                }
            ]
        """
        # Check cache
        cache_key = f"search:{query}:{page_size}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        # Build URL
        url = f"{self.base_url}/foods/search"
        params = {
            "query": query,
            "pageSize": page_size,
            "dataType": ["Survey (FNDDS)", "Foundation", "SR Legacy"],  # Most comprehensive types
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse and format results
            results = []
            for food in data.get("foods", []):
                try:
                    parsed = self._parse_food_item(food)
                    if parsed:
                        results.append(parsed)
                except Exception as e:
                    logger.warning(f"Error parsing food item: {e}")
                    continue
            
            # Cache results
            self._add_to_cache(cache_key, results)
            
            logger.info(f"Found {len(results)} foods for query: {query}")
            return results
            
        except httpx.HTTPStatusError as e:
            logger.error(f"USDA API HTTP error: {e.response.status_code}")
            return []
        except httpx.TimeoutException:
            logger.error("USDA API timeout")
            return []
        except Exception as e:
            logger.error(f"Error calling USDA API: {e}")
            return []
    
    def get_food_by_id(self, fdc_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed food information by FDC ID
        
        Args:
            fdc_id: USDA FoodData Central ID
            
        Returns:
            Detailed food information
        """
        # Check cache
        cache_key = f"food:{fdc_id}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        url = f"{self.base_url}/food/{fdc_id}"
        params = {}
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            parsed = self._parse_food_item(data)
            
            # Cache result
            if parsed:
                self._add_to_cache(cache_key, parsed)
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error getting food by ID {fdc_id}: {e}")
            return None
    
    def _parse_food_item(self, food_data: Dict) -> Optional[Dict[str, Any]]:
        """
        Parse USDA food item into our standard format
        
        Args:
            food_data: Raw food data from USDA API
            
        Returns:
            Parsed food data
        """
        try:
            # Extract basic info
            result = {
                "fdc_id": food_data.get("fdcId"),
                "description": food_data.get("description", "Unknown"),
                "data_type": food_data.get("dataType", ""),
                "serving_size": 100,  # Default to 100g
                "serving_unit": "g",
            }
            
            # Extract nutrients
            nutrients = {}
            for nutrient in food_data.get("foodNutrients", []):
                nutrient_name = nutrient.get("nutrientName", "").lower()
                nutrient_unit = nutrient.get("unitName", "").lower()
                nutrient_value = nutrient.get("value", 0)
                nutrient_id = nutrient.get("nutrientId", 0)
                
                # Match by nutrient ID (most reliable) or by name
                if nutrient_id == 1008 or (nutrient_name == "energy" and nutrient_unit == "kcal"):
                    nutrients["calories"] = round(nutrient_value, 2)
                elif nutrient_id == 1003 or (nutrient_name == "protein"):
                    nutrients["protein"] = round(nutrient_value, 2)
                elif nutrient_id == 1005 or "carbohydrate" in nutrient_name:
                    nutrients["carbs"] = round(nutrient_value, 2)
                elif nutrient_id == 1004 or "total lipid" in nutrient_name:
                    nutrients["fat"] = round(nutrient_value, 2)
                elif nutrient_id == 1079 or "fiber" in nutrient_name:
                    nutrients["fiber"] = round(nutrient_value, 2)
                elif nutrient_id == 2000 or "sugars" in nutrient_name:
                    nutrients["sugar"] = round(nutrient_value, 2)
            
            result.update(nutrients)
            
            # Ensure we have at least calories
            if "calories" not in result:
                logger.warning(f"No calorie data for: {result['description']}")
                return None
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing food item: {e}")
            return None
    
    def calculate_nutrition_for_serving(
        self,
        food_data: Dict[str, Any],
        quantity: float,
        unit: str
    ) -> Dict[str, float]:
        """
        Calculate nutrition for a specific serving size
        
        Args:
            food_data: Food data from USDA
            quantity: Quantity eaten
            unit: Unit of measurement
            
        Returns:
            Nutrition data scaled to the serving
        """
        # Weight-based units (exact)
        weight_units = {
            "g": 1, "gram": 1, "grams": 1,
            "kg": 1000, "kilogram": 1000,
            "oz": 28.35, "ounce": 28.35, "ounces": 28.35,
            "lb": 453.592, "pound": 453.592, "pounds": 453.592,
        }

        # Volume/portion units (approximate grams)
        portion_units = {
            "cup": 240, "cups": 240,
            "tbsp": 15, "tablespoon": 15, "tablespoons": 15,
            "tsp": 5, "teaspoon": 5, "teaspoons": 5,
            "bowl": 300, "bowls": 300,
            "plate": 300, "plates": 300,
            "glass": 240,
        }

        # Size descriptors (grams per item)
        size_units = {
            "small": 80, "medium": 130, "large": 180,
            "standard": 100, "regular": 130,
        }

        # Countable item units (grams per piece)
        piece_units = {
            "piece": 30, "pieces": 30,
            "slice": 30, "slices": 30,
            "chip": 5, "chips": 5,
            "nacho": 7, "nachos": 7,
            "cracker": 5, "crackers": 5,
            "cookie": 30, "cookies": 30,
            "strip": 20, "strips": 20,
            "nugget": 18, "nuggets": 18,
            "wing": 30, "wings": 30,
            "bite": 15, "bites": 15,
            "scoop": 70, "scoops": 70,
            "handful": 30,
            "bar": 50, "bars": 50,
            "patty": 85, "patties": 85,
            "fillet": 170, "fillets": 170,
            "breast": 170, "breasts": 170,
            "thigh": 115, "thighs": 115,
            "drumstick": 75, "drumsticks": 75,
            "egg": 50, "eggs": 50,
            "wrap": 60, "wraps": 60,
            "tortilla": 50, "tortillas": 50,
            "roll": 50, "rolls": 50,
        }

        # "Serving" means 1 USDA standard portion (100g)
        serving_units = {
            "serving": 100, "servings": 100,
            "portion": 100, "portions": 100,
        }

        unit_lower = unit.lower().strip()

        all_units = {}
        all_units.update(weight_units)
        all_units.update(portion_units)
        all_units.update(size_units)
        all_units.update(piece_units)
        all_units.update(serving_units)

        if unit_lower in all_units:
            grams = quantity * all_units[unit_lower]
        else:
            # Unknown unit - if quantity is small (1-2), treat as servings (100g each)
            # If quantity is larger, treat as individual pieces (~30g each)
            if quantity <= 2:
                grams = quantity * 100
            else:
                grams = quantity * 30
                logger.info(f"Unknown unit '{unit}' with qty {quantity}, using 30g/piece estimate")
        
        # Calculate multiplier (USDA data is per 100g)
        multiplier = grams / 100.0
        
        # Scale nutrients
        result = {
            "calories": round((food_data.get("calories", 0) * multiplier), 2),
            "protein": round((food_data.get("protein", 0) * multiplier), 2),
            "carbs": round((food_data.get("carbs", 0) * multiplier), 2),
            "fat": round((food_data.get("fat", 0) * multiplier), 2),
            "fiber": round((food_data.get("fiber", 0) * multiplier), 2),
            "sugar": round((food_data.get("sugar", 0) * multiplier), 2),
            "quantity": quantity,
            "unit": unit,
            "grams": round(grams, 2),
        }
        
        return result
    
    def clear_cache(self) -> None:
        """Clear the nutrition cache"""
        self._cache.clear()
        logger.info("USDA cache cleared")


# Singleton instance
_usda_service: Optional[USDAService] = None


def get_usda_service() -> USDAService:
    """
    Get or create USDA service instance
    
    Returns:
        USDA service singleton
    """
    global _usda_service
    if _usda_service is None:
        _usda_service = USDAService()
    return _usda_service


if __name__ == "__main__":
    # Test USDA service
    service = get_usda_service()
    
    # Test food search
    print("Searching for 'eggs'...")
    results = service.search_foods("eggs", page_size=5)
    
    if results:
        print(f"\nFound {len(results)} results:")
        for i, food in enumerate(results[:3], 1):
            print(f"\n{i}. {food['description']}")
            print(f"   Calories: {food.get('calories', 'N/A')} per 100g")
            print(f"   Protein: {food.get('protein', 'N/A')}g")
            print(f"   Carbs: {food.get('carbs', 'N/A')}g")
            print(f"   Fat: {food.get('fat', 'N/A')}g")
        
        # Test serving calculation
        print("\n\nCalculating nutrition for 2 large eggs...")
        nutrition = service.calculate_nutrition_for_serving(
            results[0],
            quantity=2,
            unit="large"
        )
        print(f"Total calories: {nutrition['calories']}")
        print(f"Total protein: {nutrition['protein']}g")
    else:
        print("No results found")
