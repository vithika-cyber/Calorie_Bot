"""
Orchestrator - Coordinates all agents using LangGraph
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, TypedDict, Tuple
from langgraph.graph import StateGraph, END

from .router_agent import get_router_agent
from .food_parser import get_food_parser_agent
from .nutrition_lookup import get_nutrition_agent
from .storage_agent import get_storage_agent
from ..utils.formatters import format_food_log_message, format_daily_summary, format_range_summary
from ..utils.calculations import calculate_tdee, calculate_calorie_goal
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """State that flows through the agent graph"""
    user_id: str
    team_id: str
    message: str
    intent: Optional[str]
    user_context: Optional[Dict[str, Any]]
    history: Optional[list]
    parsed_foods: Optional[list]
    enriched_foods: Optional[list]
    totals: Optional[Dict[str, float]]
    response: Optional[str]
    error: Optional[str]


class CalorieBotOrchestrator:
    """Orchestrates the calorie bot using LangGraph"""
    
    def __init__(self):
        """Initialize orchestrator with all agents"""
        self.router = get_router_agent()
        self.food_parser = get_food_parser_agent()
        self.nutrition = get_nutrition_agent()
        self.storage = get_storage_agent()
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ConversationState)
        
        # Add nodes (agent functions)
        workflow.add_node("get_user_context", self._get_user_context)
        workflow.add_node("route_intent", self._route_intent)
        workflow.add_node("handle_onboarding", self._handle_onboarding)
        workflow.add_node("parse_food", self._parse_food)
        workflow.add_node("lookup_nutrition", self._lookup_nutrition)
        workflow.add_node("store_food_log", self._store_food_log)
        workflow.add_node("handle_query", self._handle_query)
        workflow.add_node("handle_greeting", self._handle_greeting)
        workflow.add_node("handle_help", self._handle_help)
        workflow.add_node("handle_error", self._handle_error)
        
        # Define edges (flow between nodes)
        workflow.set_entry_point("get_user_context")
        workflow.add_edge("get_user_context", "route_intent")
        
        # Conditional routing based on intent
        workflow.add_conditional_edges(
            "route_intent",
            self._route_by_intent,
            {
                "onboarding_needed": "handle_onboarding",
                "log_food": "parse_food",
                "query_today": "handle_query",
                "query_history": "handle_query",
                "greeting": "handle_greeting",
                "help": "handle_help",
                "error": "handle_error",
                "other": "handle_error",  # Route unknown intents to error handler
                END: END
            }
        )
        
        # Food logging flow
        workflow.add_edge("parse_food", "lookup_nutrition")
        workflow.add_edge("lookup_nutrition", "store_food_log")
        workflow.add_edge("store_food_log", END)
        
        # Other flows
        workflow.add_edge("handle_query", END)
        workflow.add_edge("handle_greeting", END)
        workflow.add_edge("handle_help", END)
        workflow.add_edge("handle_onboarding", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    def process_message(
        self,
        user_id: str,
        team_id: str,
        message: str
    ) -> Dict[str, Any]:
        """Process a user message through the agent graph."""
        if not self.rate_limiter.is_allowed(user_id):
            wait = int(self.rate_limiter.time_until_allowed(user_id)) + 1
            return {
                "response": f":hourglass: You're sending messages too fast. Try again in {wait} seconds.",
                "intent": "rate_limited",
                "error": None
            }

        try:
            initial_state = ConversationState(
                user_id=user_id,
                team_id=team_id,
                message=message,
                intent=None,
                user_context=None,
                history=None,
                parsed_foods=None,
                enriched_foods=None,
                totals=None,
                response=None,
                error=None
            )

            final_state = self.graph.invoke(initial_state)

            bot_response = final_state.get("response", "I'm not sure how to help with that.")

            try:
                self.storage.save_message(user_id, "user", message)
                self.storage.save_message(user_id, "bot", bot_response)
            except Exception as save_err:
                logger.warning(f"Could not save conversation history: {save_err}")

            return {
                "response": bot_response,
                "intent": final_state.get("intent"),
                "error": final_state.get("error")
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "response": "Sorry, I encountered an error processing your message. Please try again.",
                "intent": "error",
                "error": str(e)
            }
    
    # Agent Node Functions
    
    def _get_user_context(self, state: ConversationState) -> ConversationState:
        """Get user context and conversation history from database."""
        try:
            user_dict = self.storage.get_or_create_user(state["user_id"], state["team_id"])

            state["user_context"] = {
                "is_onboarded": user_dict["is_onboarded"],
                "daily_calorie_goal": user_dict["daily_calorie_goal"] if user_dict["daily_calorie_goal"] else 2000,
                "current_weight": user_dict["current_weight"],
                "target_weight": user_dict["target_weight"],
                "preferences": user_dict["preferences"] if user_dict["preferences"] else {}
            }

            state["history"] = self.storage.get_recent_messages(state["user_id"], limit=5)
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            state["user_context"] = {
                "is_onboarded": False,
                "daily_calorie_goal": 2000,
                "current_weight": None,
                "target_weight": None,
                "preferences": {}
            }
            state["history"] = []
            state["error"] = str(e)

        return state
    
    def _route_intent(self, state: ConversationState) -> ConversationState:
        """Route message to appropriate handler"""
        try:
            routing = self.router.route(state["message"], state["user_context"], history=state.get("history"))
            state["intent"] = routing["intent"]
            logger.info(f"Routed to intent: {routing['intent']}")
        except Exception as e:
            logger.error(f"Error routing intent: {e}")
            state["intent"] = "error"
            state["error"] = str(e)
        
        return state
    
    def _route_by_intent(self, state: ConversationState) -> str:
        """Determine next node based on intent"""
        intent = state.get("intent", "error")
        
        intent_map = {
            "onboarding_needed": "onboarding_needed",
            "log_food": "log_food",
            "query_today": "query_today",
            "query_history": "query_history",
            "greeting": "greeting",
            "help": "help",
            "error": "error",
            "other": "error"  # Route "other" to error handler
        }
        
        return intent_map.get(intent, "error")  # Default to error handler instead of END
    
    def _parse_food(self, state: ConversationState) -> ConversationState:
        """Parse food from message"""
        try:
            parsed = self.food_parser.parse(state["message"], state["user_context"], history=state.get("history"))
            state["parsed_foods"] = parsed["foods"]
            
            if not parsed["foods"]:
                state["response"] = "I couldn't identify any food items in your message. Could you try describing what you ate?"
                state["intent"] = END
        except Exception as e:
            logger.error(f"Error parsing food: {e}")
            state["error"] = str(e)
            state["intent"] = "error"
        
        return state
    
    def _lookup_nutrition(self, state: ConversationState) -> ConversationState:
        """Look up nutrition data"""
        try:
            if state["parsed_foods"]:
                enriched = self.nutrition.lookup_nutrition(state["parsed_foods"])
                state["enriched_foods"] = enriched
                state["totals"] = self.nutrition.calculate_totals(enriched)
        except Exception as e:
            logger.error(f"Error looking up nutrition: {e}")
            state["error"] = str(e)
        
        return state
    
    def _store_food_log(self, state: ConversationState) -> ConversationState:
        """Store food log in database"""
        try:
            if not state["enriched_foods"] or not state["totals"]:
                return state

            unknown_items = [f for f in state["enriched_foods"] if f.get("confidence") == "unknown"]
            known_items = [f for f in state["enriched_foods"] if f.get("confidence") != "unknown"]

            if not known_items and unknown_items:
                names = ", ".join(f.get("name", "unknown") for f in unknown_items)
                state["response"] = (
                    f":thinking_face: I couldn't find nutritional info for _{names}_.\n\n"
                    "Could you help me out? You can:\n"
                    f"  1. Try a more common name (e.g. instead of a brand name, describe the food type)\n"
                    f"  2. Tell me the calories directly, like: _\"{unknown_items[0].get('name', 'food')} is about 250 calories\"_\n"
                    f"  3. Break it down into ingredients I might know"
                )
                return state

            meal_type = state["enriched_foods"][0].get("meal_type", "other")

            self.storage.create_food_log(
                slack_user_id=state["user_id"],
                raw_text=state["message"],
                items=state["enriched_foods"],
                meal_type=meal_type,
                totals=state["totals"]
            )

            daily_totals = self.storage.get_daily_totals(state["user_id"])
            goal = state["user_context"].get("daily_calorie_goal", 2000)

            response = format_food_log_message(
                meal_type=meal_type,
                items=state["enriched_foods"],
                total_calories=state["totals"]["calories"],
                total_macros=state["totals"]
            )

            response += f"\n\n:bar_chart: *Daily Progress:* {int(daily_totals['calories'])}/{goal} cal ({int(daily_totals['calories']/goal*100)}%)"

            if unknown_items:
                names = ", ".join(f.get("name", "unknown") for f in unknown_items)
                response += (
                    f"\n\n:warning: I couldn't find _{names}_ in my database, so those were logged as 0 cal. "
                    f"You can tell me the calories like: _\"{unknown_items[0].get('name', 'food')} is about 250 calories\"_"
                )

            ai_items = [f for f in known_items if f.get("source") == "ai_estimated"]
            if ai_items:
                names = ", ".join(f.get("name", "unknown") for f in ai_items)
                response += f"\n\n:information_source: _{names}_ nutrition was estimated by AI (not from USDA database). Actual values may vary."

            state["response"] = response
        except Exception as e:
            logger.error(f"Error storing food log: {e}")
            state["error"] = str(e)
            state["response"] = "I logged your food, but there was an error generating the summary."

        return state
    
    def _parse_date_reference(self, message: str) -> Tuple[date, date, str]:
        """Extract a date range from natural language. Returns (start, end, label)."""
        import re
        from dateutil import parser as dateutil_parser

        msg = message.lower()
        today = date.today()

        if "yesterday" in msg:
            d = today - timedelta(days=1)
            return (d, d, "Yesterday")
        if "last week" in msg:
            return (today - timedelta(days=7), today - timedelta(days=1), "Last 7 Days")
        if "this week" in msg:
            monday = today - timedelta(days=today.weekday())
            return (monday, today, "This Week")
        if "last 3 days" in msg or "past 3 days" in msg:
            return (today - timedelta(days=3), today, "Last 3 Days")

        # Try to parse a specific date (e.g. "13th Feb 2026", "Feb 13", "2026-02-13")
        try:
            parsed = dateutil_parser.parse(message, fuzzy=True, default=datetime.now()).date()
            label = parsed.strftime("%b %d, %Y")
            return (parsed, parsed, label)
        except (ValueError, OverflowError):
            pass

        return (today, today, "Today")

    def _handle_query(self, state: ConversationState) -> ConversationState:
        """Handle query requests (today or historical date ranges)."""
        try:
            goal = state["user_context"].get("daily_calorie_goal", 2000)
            start, end, label = self._parse_date_reference(state["message"])

            is_single_day = (start == end)

            if is_single_day:
                daily_totals = self.storage.get_daily_totals(state["user_id"], start)
                logs = self.storage.get_food_logs_by_date(state["user_id"], start)
                meals = []
                for log in logs:
                    food_names = [item.get("name", "") for item in log.get("items", []) if item.get("name")]
                    meals.append({
                        "meal_type": log["meal_type"],
                        "calories": log["total_calories"],
                        "food_names": food_names,
                    })

                state["response"] = format_daily_summary(
                    date=label,
                    total_calories=daily_totals["calories"],
                    goal_calories=goal,
                    meals=meals,
                    macros=daily_totals
                )
            else:
                range_data = self.storage.get_range_totals(state["user_id"], start, end)
                state["response"] = format_range_summary(label, range_data, goal)

        except Exception as e:
            logger.error(f"Error handling query: {e}")
            state["response"] = "Sorry, I had trouble retrieving that information."

        return state
    
    def _handle_greeting(self, state: ConversationState) -> ConversationState:
        """Handle greeting messages"""
        if state["user_context"]["is_onboarded"]:
            state["response"] = ":wave: Hey there! Ready to log your meals? Just tell me what you ate!"
        else:
            state["response"] = ":wave: Hi! I'm CalorieBot, and I'm here to help you track your nutrition. Let's get you set up!"
        return state
    
    def _handle_help(self, state: ConversationState) -> ConversationState:
        """Handle help requests"""
        state["response"] = """*How to use CalorieBot:*

*Logging food:*
Just tell me what you ate! Examples:
  "I had 2 eggs and toast for breakfast"
  "Ate a chicken salad for lunch"
  "Had a banana as a snack"

*Checking progress:*
  "What did I eat today?"
  "How many calories so far?"
  "Show me yesterday"
  "What about last week?"

*Tips:*
  Be specific about quantities when possible
  I understand natural language - just chat normally!
  I'll ask for clarification if I'm unsure

Need anything else?"""
        return state
    
    def _handle_onboarding(self, state: ConversationState) -> ConversationState:
        """Handle onboarding flow - check if user already provided data or show welcome"""
        from ..services.ai_service import AIService
        from ..utils.calculations import calculate_tdee, calculate_calorie_goal
        import re
        
        # Try to extract onboarding data from the message
        ai_service = AIService()
        
        try:
            # Ask AI to extract onboarding information
            extraction_prompt = f"""Extract the following information from this message if present:
Message: "{state['message']}"

Return JSON with these fields (use null if not found):
- age (number)
- gender ("male" or "female")
- weight_kg (number, convert from lbs if needed: lbs * 0.453592)
- height_cm (number, convert from inches if needed: inches * 2.54)
- activity_level ("sedentary", "lightly_active", "moderately_active", or "very_active")
- goal ("lose_weight", "maintain_weight", or "gain_weight")

Examples:
"I'm 30 years old, male, 75kg, 175cm, moderately active, and want to lose weight"
→ {{"age": 30, "gender": "male", "weight_kg": 75, "height_cm": 175, "activity_level": "moderately_active", "goal": "lose_weight"}}

"25 female 140 lbs 5'6\" sedentary maintain"
→ {{"age": 25, "gender": "female", "weight_kg": 63.5, "height_cm": 167.64, "activity_level": "sedentary", "goal": "maintain_weight"}}"""
            
            result = ai_service.chat_model.invoke(extraction_prompt)
            import json
            content = result.content.strip()
            # Clean markdown if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            # Check if we have all required fields
            required_fields = ["age", "gender", "weight_kg", "height_cm", "activity_level", "goal"]
            has_all_data = all(data.get(field) is not None for field in required_fields)
            
            if has_all_data:
                # Process the onboarding data
                logger.info(f"Processing onboarding data: {data}")
                
                # Calculate TDEE and calorie goal
                tdee = calculate_tdee(
                    weight_kg=data["weight_kg"],
                    height_cm=data["height_cm"],
                    age=data["age"],
                    gender=data["gender"],
                    activity_level=data["activity_level"]
                )
                
                calorie_goal = calculate_calorie_goal(tdee, data["goal"])
                
                # Update user in database
                self.storage.update_user(state["user_id"], {
                    "age": data["age"],
                    "gender": data["gender"],
                    "current_weight": data["weight_kg"],
                    "height": data["height_cm"],
                    "activity_level": data["activity_level"],
                    "daily_calorie_goal": calorie_goal,
                    "target_weight": data["weight_kg"] - 5 if data["goal"] == "lose_weight" else data["weight_kg"] + 5 if data["goal"] == "gain_weight" else data["weight_kg"]
                })
                
                # Mark as onboarded
                self.storage.mark_user_onboarded(state["user_id"])
                
                # Create success response
                state["response"] = f""":white_check_mark: *You're all set!*

Here's your personalized plan:
  *Daily Calorie Goal:* {calorie_goal:,} cal
  *TDEE (Maintenance):* {tdee:,} cal
  *Goal:* {data['goal'].replace('_', ' ').title()}

You can now start logging your meals! Just tell me what you eat, like:
  "I had 2 eggs and toast for breakfast"
  "Ate a chicken salad"
  "Had an apple as a snack"

Let's get started! :dart:"""
                return state
                
        except Exception as e:
            logger.error(f"Error processing onboarding data: {e}")
            # Fall through to show welcome message
        
        # Show welcome message if data extraction failed
        state["response"] = """:wave: *Welcome to CalorieBot!*

Before we start tracking, I need a few details to calculate your personalized calorie goal.

Please tell me:
1. Your age
2. Your gender (male/female)
3. Your current weight (in kg or lbs)
4. Your height (in cm or inches)
5. Your activity level (sedentary / lightly active / moderately active / very active)
6. Your goal (lose weight / maintain weight / gain weight)

You can say something like: _"I'm 30 years old, male, 75kg, 175cm, moderately active, and want to lose weight"_

(Or we can do this step by step if you prefer!)"""
        return state
    
    def _handle_error(self, state: ConversationState) -> ConversationState:
        """Handle errors"""
        state["response"] = "I'm not sure how to help with that. Try saying something like 'I had an apple' or 'show me today's meals'."
        return state


# Singleton instance
_orchestrator: Optional[CalorieBotOrchestrator] = None


def get_orchestrator() -> CalorieBotOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CalorieBotOrchestrator()
    return _orchestrator
