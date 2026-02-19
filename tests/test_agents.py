"""
Unit Tests for Agents
"""

import pytest
from datetime import datetime
from src.agents.router_agent import get_router_agent
from src.agents.food_parser import get_food_parser_agent
from src.agents.nutrition_lookup import get_nutrition_agent
from src.agents.storage_agent import get_storage_agent
from src.database.database import init_db


class TestRouterAgent:
    """Test router agent functionality"""
    
    def test_route_food_logging(self):
        """Test routing food logging messages"""
        agent = get_router_agent()
        result = agent.route("I had pizza for lunch", {"is_onboarded": True})
        assert result["intent"] == "log_food"
    
    def test_route_query(self):
        """Test routing query messages"""
        agent = get_router_agent()
        result = agent.route("What did I eat today?", {"is_onboarded": True})
        assert result["intent"] in ["query_today", "query_history"]
    
    def test_route_greeting(self):
        """Test routing greeting messages"""
        agent = get_router_agent()
        result = agent.route("Hello!", {"is_onboarded": True})
        assert result["intent"] == "greeting"
    
    def test_route_onboarding_needed(self):
        """Test routing when onboarding is needed"""
        agent = get_router_agent()
        result = agent.route("I had an apple", {"is_onboarded": False})
        assert result["intent"] == "onboarding_needed"


class TestFoodParserAgent:
    """Test food parser agent functionality"""
    
    def test_parse_simple_food(self):
        """Test parsing simple food message"""
        agent = get_food_parser_agent()
        result = agent.parse("I had an apple")
        
        assert len(result["foods"]) >= 1
        assert result["confidence"] in ["high", "medium", "low"]
        assert "apple" in result["foods"][0]["name"].lower()
    
    def test_parse_multiple_foods(self):
        """Test parsing multiple food items"""
        agent = get_food_parser_agent()
        result = agent.parse("I had 2 eggs and toast for breakfast")
        
        assert len(result["foods"]) >= 2
        assert result["meal_type"] == "breakfast"
    
    def test_validate_parsed_foods(self):
        """Test validation of parsed foods"""
        agent = get_food_parser_agent()
        
        valid_data = {
            "foods": [
                {"name": "apple", "quantity": 1, "unit": "medium"}
            ]
        }
        is_valid, issues = agent.validate_parsed_foods(valid_data)
        assert is_valid
        assert len(issues) == 0
        
        invalid_data = {
            "foods": [
                {"name": "", "quantity": 0}
            ]
        }
        is_valid, issues = agent.validate_parsed_foods(invalid_data)
        assert not is_valid
        assert len(issues) > 0


class TestNutritionAgent:
    """Test nutrition lookup agent functionality"""
    
    def test_lookup_nutrition(self):
        """Test looking up nutrition data"""
        agent = get_nutrition_agent()
        
        foods = [
            {"name": "apple", "quantity": 1, "unit": "medium"}
        ]
        
        enriched = agent.lookup_nutrition(foods)
        
        assert len(enriched) == 1
        assert "calories" in enriched[0]
        assert enriched[0]["calories"] > 0
    
    def test_calculate_totals(self):
        """Test calculating nutrition totals"""
        agent = get_nutrition_agent()
        
        foods = [
            {"name": "apple", "calories": 95, "protein": 0.5, "carbs": 25, "fat": 0.3},
            {"name": "banana", "calories": 105, "protein": 1.3, "carbs": 27, "fat": 0.4}
        ]
        
        totals = agent.calculate_totals(foods)
        
        assert totals["calories"] == 200
        assert totals["protein"] == 1.8
        assert totals["carbs"] == 52
        assert totals["fat"] == 0.7
    
    def test_fallback_nutrition(self):
        """Test fallback when USDA lookup fails"""
        agent = get_nutrition_agent()
        
        # Use a very obscure food name that likely won't be found
        foods = [
            {"name": "extremely_rare_fictional_food_xyz123", "quantity": 1, "unit": "serving"}
        ]
        
        enriched = agent.lookup_nutrition(foods)
        
        # Should still return data (estimated)
        assert len(enriched) == 1
        assert enriched[0]["source"] == "estimated"


class TestStorageAgent:
    """Test storage agent functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Setup test database before each test"""
        init_db()
        yield
    
    def test_get_or_create_user(self):
        """Test getting or creating a user"""
        agent = get_storage_agent()
        
        user = agent.get_or_create_user("TEST_USER_1", "TEST_TEAM_1")
        assert user is not None
        assert user.slack_user_id == "TEST_USER_1"
        
        # Should return same user on second call
        user2 = agent.get_or_create_user("TEST_USER_1", "TEST_TEAM_1")
        assert user.id == user2.id
    
    def test_update_user(self):
        """Test updating user information"""
        agent = get_storage_agent()
        
        user = agent.get_or_create_user("TEST_USER_2", "TEST_TEAM_1")
        
        updates = {
            "age": 30,
            "current_weight": 75.0,
            "height": 175.0,
            "daily_calorie_goal": 2000
        }
        
        updated_user = agent.update_user("TEST_USER_2", updates)
        
        assert updated_user.age == 30
        assert updated_user.current_weight == 75.0
        assert updated_user.daily_calorie_goal == 2000
    
    def test_create_food_log(self):
        """Test creating a food log"""
        agent = get_storage_agent()
        
        # Create user first
        user = agent.get_or_create_user("TEST_USER_3", "TEST_TEAM_1")
        
        items = [
            {"name": "apple", "quantity": 1, "calories": 95}
        ]
        
        totals = {"calories": 95, "protein": 0.5, "carbs": 25, "fat": 0.3}
        
        log = agent.create_food_log(
            slack_user_id="TEST_USER_3",
            raw_text="I had an apple",
            items=items,
            meal_type="snack",
            totals=totals
        )
        
        assert log is not None
        assert log.total_calories == 95
        assert log.meal_type.value == "snack"
    
    def test_get_daily_totals(self):
        """Test getting daily totals"""
        agent = get_storage_agent()
        
        # Create user and log
        user = agent.get_or_create_user("TEST_USER_4", "TEST_TEAM_1")
        
        items = [
            {"name": "apple", "quantity": 1, "calories": 95}
        ]
        totals = {"calories": 95, "protein": 0.5, "carbs": 25, "fat": 0.3}
        
        agent.create_food_log(
            slack_user_id="TEST_USER_4",
            raw_text="I had an apple",
            items=items,
            meal_type="snack",
            totals=totals
        )
        
        daily_totals = agent.get_daily_totals("TEST_USER_4")
        
        assert daily_totals["calories"] >= 95


def test_full_workflow():
    """Integration test for full food logging workflow"""
    init_db()
    
    # Initialize agents
    router = get_router_agent()
    parser = get_food_parser_agent()
    nutrition = get_nutrition_agent()
    storage = get_storage_agent()
    
    # Create test user
    user = storage.get_or_create_user("TEST_INTEGRATION", "TEST_TEAM")
    storage.mark_user_onboarded("TEST_INTEGRATION")
    
    # Simulate user message
    message = "I had 2 eggs for breakfast"
    
    # 1. Route
    route_result = router.route(message, {"is_onboarded": True})
    assert route_result["intent"] == "log_food"
    
    # 2. Parse
    parsed = parser.parse(message)
    assert len(parsed["foods"]) >= 1
    
    # 3. Lookup nutrition
    enriched = nutrition.lookup_nutrition(parsed["foods"])
    assert len(enriched) >= 1
    assert enriched[0]["calories"] > 0
    
    # 4. Store
    totals = nutrition.calculate_totals(enriched)
    log = storage.create_food_log(
        slack_user_id="TEST_INTEGRATION",
        raw_text=message,
        items=enriched,
        meal_type=parsed["meal_type"],
        totals=totals
    )
    
    assert log is not None
    assert log.total_calories > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
