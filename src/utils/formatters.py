"""
Formatters Module - Message formatting for Slack (uses Slack mrkdwn, not markdown)
"""

from datetime import datetime
from typing import Dict, List, Any, Optional


def _fmt(val, decimals=2):
    """Round a numeric value to given decimal places."""
    if val is None:
        return 0
    return round(float(val), decimals)


def format_food_log_message(
    meal_type: str,
    items: List[Dict[str, Any]],
    total_calories: float,
    total_macros: Dict[str, float],
    logged_time: Optional[datetime] = None
) -> str:
    if logged_time is None:
        logged_time = datetime.now()

    time_str = logged_time.strftime("%I:%M %p")

    lines = [f":white_check_mark: *Logged {meal_type.capitalize()}* ({time_str})", ""]

    for item in items:
        emoji = _get_food_emoji(item["name"])
        quantity_str = f"{item['quantity']} {item['unit']}" if item.get('unit') else str(item['quantity'])
        cal = _fmt(item.get('calories', 0))

        line = f"{emoji} {quantity_str} {item['name']}: *{cal} cal*"

        macros = []
        if item.get("protein"):
            macros.append(f"P: {_fmt(item['protein'])}g")
        if item.get("carbs"):
            macros.append(f"C: {_fmt(item['carbs'])}g")
        if item.get("fat"):
            macros.append(f"F: {_fmt(item['fat'])}g")

        if macros:
            line += f" | {' '.join(macros)}"

        if item.get("source") == "estimated" and item.get("confidence") == "unknown":
            line += "  _(estimate - item not in database)_"

        lines.append(line)

    lines.append("")
    lines.append(f"*Meal total: {_fmt(total_calories)} calories*")

    if total_macros:
        macro_parts = []
        if total_macros.get("protein"):
            macro_parts.append(f"Protein: {_fmt(total_macros['protein'])}g")
        if total_macros.get("carbs"):
            macro_parts.append(f"Carbs: {_fmt(total_macros['carbs'])}g")
        if total_macros.get("fat"):
            macro_parts.append(f"Fat: {_fmt(total_macros['fat'])}g")

        if macro_parts:
            lines.append(f"_{' | '.join(macro_parts)}_")

    return "\n".join(lines)


def format_daily_summary(
    date: str,
    total_calories: float,
    goal_calories: int,
    meals: List[Dict[str, Any]],
    macros: Dict[str, float]
) -> str:
    lines = [f":bar_chart: *Daily Summary - {date}*", ""]

    percentage = int((total_calories / goal_calories) * 100) if goal_calories > 0 else 0
    remaining = goal_calories - total_calories

    if abs(remaining) < 50:
        status = ":dart: Perfect! You hit your goal!"
    elif remaining > 0:
        status = f":chart_with_upwards_trend: {int(remaining)} calories remaining"
    else:
        status = f":chart_with_downwards_trend: {int(abs(remaining))} calories over"

    lines.append(f"*{int(total_calories)}/{goal_calories} calories* ({percentage}%)")
    lines.append(status)
    lines.append("")

    bar = create_progress_bar(total_calories, goal_calories)
    lines.append(bar)
    lines.append("")

    if macros:
        lines.append("*Macros:*")
        lines.append(f"  Protein: {_fmt(macros.get('protein', 0))}g")
        lines.append(f"  Carbs: {_fmt(macros.get('carbs', 0))}g")
        lines.append(f"  Fat: {_fmt(macros.get('fat', 0))}g")
        lines.append("")

    if meals:
        lines.append("*Meals logged:*")
        for meal in meals:
            meal_emoji = _get_meal_emoji(meal['meal_type'])
            lines.append(f"{meal_emoji} {meal['meal_type'].capitalize()}: {int(meal['calories'])} cal")

    return "\n".join(lines)


def format_meal_entry(
    meal_type: str,
    calories: float,
    time: datetime,
    items_count: int
) -> str:
    emoji = _get_meal_emoji(meal_type)
    time_str = time.strftime("%I:%M %p")
    items_str = "item" if items_count == 1 else "items"
    return f"{emoji} {meal_type.capitalize()} ({time_str}): {int(calories)} cal - {items_count} {items_str}"


def format_goal_progress(
    current_weight: float,
    target_weight: float,
    starting_weight: float,
    unit: str = "kg"
) -> str:
    weight_lost = starting_weight - current_weight
    remaining = abs(current_weight - target_weight)

    total_to_lose = abs(starting_weight - target_weight)
    if total_to_lose > 0:
        percentage = int((abs(weight_lost) / total_to_lose) * 100)
    else:
        percentage = 100

    lines = [
        ":dart: *Goal Progress*",
        "",
        f"Starting: {_fmt(starting_weight)} {unit}",
        f"Current: {_fmt(current_weight)} {unit}",
        f"Target: {_fmt(target_weight)} {unit}",
        "",
        f"Progress: {_fmt(abs(weight_lost))} {unit} lost ({percentage}%)",
        f"Remaining: {_fmt(remaining)} {unit}",
        "",
        create_progress_bar(abs(weight_lost), total_to_lose)
    ]

    return "\n".join(lines)


def create_progress_bar(current: float, goal: float, length: int = 10) -> str:
    if goal == 0:
        filled = 0
    else:
        filled = int((current / goal) * length)
        filled = min(filled, length)

    bar = ":large_green_square:" * filled + ":white_large_square:" * (length - filled)
    return bar


def format_nutrition_facts(food_data: Dict[str, Any]) -> str:
    lines = [
        f"*{food_data.get('name', 'Unknown')}*",
        f"_Per {food_data.get('serving_size', 100)}{food_data.get('serving_unit', 'g')}_",
        "",
        f"  Calories: {_fmt(food_data.get('calories', 0))}",
        f"  Protein: {_fmt(food_data.get('protein', 0))}g",
        f"  Carbohydrates: {_fmt(food_data.get('carbs', 0))}g",
        f"  Fat: {_fmt(food_data.get('fat', 0))}g",
    ]

    if food_data.get('fiber'):
        lines.append(f"  Fiber: {_fmt(food_data['fiber'])}g")

    if food_data.get('sugar'):
        lines.append(f"  Sugar: {_fmt(food_data['sugar'])}g")

    return "\n".join(lines)


def format_onboarding_welcome() -> str:
    return """:wave: *Welcome to CalorieBot!*

I'm here to help you track your nutrition in the most natural way possible. Just tell me what you eat, and I'll handle the rest!

Let's get you set up with a quick profile. This helps me calculate your personalized calorie goal.

Ready to start?"""


def format_macro_comparison(actual: Dict[str, float], target: Dict[str, float]) -> str:
    lines = ["*Macro Targets:*", ""]

    for macro_name in ['protein', 'carbs', 'fat']:
        actual_val = _fmt(actual.get(macro_name, 0))
        target_val = _fmt(target.get(macro_name, 0))

        if target_val > 0:
            percentage = int((actual_val / target_val) * 100)
            status = ":white_check_mark:" if 90 <= percentage <= 110 else ":bar_chart:"
        else:
            percentage = 0
            status = ":bar_chart:"

        lines.append(f"{status} {macro_name.capitalize()}: {actual_val}g / {target_val}g ({percentage}%)")

    return "\n".join(lines)


def _get_food_emoji(food_name: str) -> str:
    food_lower = food_name.lower()

    emoji_map = {
        "egg": ":egg:",
        "toast": ":bread:",
        "bread": ":bread:",
        "apple": ":apple:",
        "banana": ":banana:",
        "orange": ":tangerine:",
        "salad": ":green_salad:",
        "chicken": ":poultry_leg:",
        "rice": ":rice:",
        "pasta": ":spaghetti:",
        "pizza": ":pizza:",
        "burger": ":hamburger:",
        "sandwich": ":sandwich:",
        "coffee": ":coffee:",
        "tea": ":tea:",
        "milk": ":glass_of_milk:",
        "cheese": ":cheese_wedge:",
        "fish": ":fish:",
        "meat": ":cut_of_meat:",
        "steak": ":cut_of_meat:",
        "potato": ":potato:",
        "avocado": ":avocado:",
        "soup": ":stew:",
        "cake": ":cake:",
        "cookie": ":cookie:",
        "chocolate": ":chocolate_bar:",
    }

    for keyword, emoji in emoji_map.items():
        if keyword in food_lower:
            return emoji

    return ":fork_and_knife:"


def _get_meal_emoji(meal_type: str) -> str:
    meal_emojis = {
        "breakfast": ":sunrise:",
        "lunch": ":sunny:",
        "dinner": ":crescent_moon:",
        "snack": ":popcorn:",
        "other": ":fork_and_knife:"
    }
    return meal_emojis.get(meal_type.lower(), ":fork_and_knife:")
