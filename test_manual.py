"""
Manual Testing Script - Test individual components without running full bot
"""

import sys
import os

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

from src.config import get_settings, validate_settings
from src.database.database import init_db, check_db_connection
from src.agents.orchestrator import get_orchestrator


def test_configuration():
    """Test that configuration is valid"""
    print("\n" + "="*50)
    print("Testing Configuration")
    print("="*50)
    
    is_valid, errors = validate_settings()
    
    if is_valid:
        print("✅ Configuration is valid!")
        settings = get_settings()
        print(f"   Environment: {settings.environment}")
        print(f"   OpenAI Model: {settings.openai_model}")
        print(f"   Database: {settings.database_url}")
        return True
    else:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"   - {error}")
        print("\nPlease check your .env file")
        return False


def test_database():
    """Test database connection"""
    print("\n" + "="*50)
    print("Testing Database")
    print("="*50)
    
    try:
        print("Initializing database...")
        init_db()
        
        if check_db_connection():
            print("✅ Database connection successful!")
            return True
        else:
            print("❌ Database connection failed")
            return False
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def test_food_parsing():
    """Test food parsing with sample messages"""
    print("\n" + "="*50)
    print("Testing Food Parsing")
    print("="*50)
    
    from src.agents.food_parser import get_food_parser_agent
    
    test_messages = [
        "I had 2 eggs and toast for breakfast",
        "Ate a banana",
        "Lunch was chicken breast with rice",
    ]
    
    agent = get_food_parser_agent()
    
    for msg in test_messages:
        print(f"\n📝 Message: '{msg}'")
        try:
            result = agent.parse(msg)
            print(f"   ✅ Parsed {len(result['foods'])} food items")
            for food in result['foods']:
                print(f"      - {food['quantity']} {food.get('unit', '')} {food['name']}")
            print(f"   Confidence: {result['confidence']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return True


def test_nutrition_lookup():
    """Test USDA nutrition lookup"""
    print("\n" + "="*50)
    print("Testing Nutrition Lookup")
    print("="*50)
    
    from src.agents.nutrition_lookup import get_nutrition_agent
    
    test_foods = [
        {"name": "apple", "quantity": 1, "unit": "medium"},
        {"name": "eggs", "quantity": 2, "unit": "large"},
    ]
    
    agent = get_nutrition_agent()
    
    print("\n🔍 Looking up nutrition data...")
    try:
        enriched = agent.lookup_nutrition(test_foods)
        
        for food in enriched:
            print(f"\n   {food['name']}:")
            print(f"      Calories: {food['calories']}")
            print(f"      Protein: {food['protein']}g")
            print(f"      Carbs: {food['carbs']}g")
            print(f"      Fat: {food['fat']}g")
            print(f"      Source: {food['source']}")
        
        totals = agent.calculate_totals(enriched)
        print(f"\n   ✅ Total: {totals['calories']} calories")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_orchestrator():
    """Test full orchestrator workflow"""
    print("\n" + "="*50)
    print("Testing Orchestrator")
    print("="*50)
    
    test_user = "TEST_USER_MANUAL"
    test_team = "TEST_TEAM_MANUAL"
    
    test_messages = [
        ("Hi!", "greeting"),
        ("I had 2 eggs for breakfast", "food logging"),
        ("What did I eat today?", "query"),
    ]
    
    orchestrator = get_orchestrator()
    
    for msg, description in test_messages:
        print(f"\n📨 Testing: {description}")
        print(f"   Message: '{msg}'")
        
        try:
            result = orchestrator.process_message(test_user, test_team, msg)
            print(f"   Intent: {result['intent']}")
            print(f"   Response preview: {result['response'][:100]}...")
            print("   ✅ Success")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 CalorieBot Manual Testing Suite")
    print("="*60)
    
    tests = [
        ("Configuration", test_configuration),
        ("Database", test_database),
        ("Food Parsing", test_food_parsing),
        ("Nutrition Lookup", test_nutrition_lookup),
        ("Orchestrator", test_orchestrator),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your bot is ready to run!")
        print("\nNext step: python src/main.py")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
