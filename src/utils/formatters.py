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
            lines.append(f"{meal_emoji} *{meal['meal_type'].capitalize()}:* {int(meal['calories'])} cal")
            food_names = meal.get("food_names", [])
            if food_names:
                lines.append(f"    _{', '.join(food_names)}_")

    return "\n".join(lines)


def format_range_summary(
    label: str,
    range_data: Dict[str, Any],
    goal_calories: int
) -> str:
    """Format a multi-day date-range summary for Slack."""
    totals = range_data["totals"]
    averages = range_data["averages"]
    daily = range_data["daily"]

    lines = [f":calendar: *{label}*  ({range_data['num_days']} day{'s' if range_data['num_days'] != 1 else ''})", ""]
    lines.append(f"*Total:* {_fmt(totals['calories'])} cal | P: {_fmt(totals['protein'])}g  C: {_fmt(totals['carbs'])}g  F: {_fmt(totals['fat'])}g")
    lines.append(f"*Daily avg:* {_fmt(averages['calories'])} cal | P: {_fmt(averages['protein'])}g  C: {_fmt(averages['carbs'])}g  F: {_fmt(averages['fat'])}g")

    if goal_calories:
        pct = int((averages["calories"] / goal_calories) * 100) if goal_calories > 0 else 0
        lines.append(f"_Avg {pct}% of your {goal_calories} cal goal_")

    lines.append("")
    lines.append("*Per-day breakdown:*")
    for day_str, vals in daily.items():
        try:
            day_label = datetime.strptime(day_str, "%Y-%m-%d").strftime("%a, %b %d")
        except ValueError:
            day_label = day_str
        lines.append(f"  *{day_label}:* {_fmt(vals['calories'])} cal")
        foods = vals.get("foods", [])
        if foods:
            lines.append(f"    _{', '.join(foods)}_")

    if not daily:
        lines.append("  _No food logged in this period._")

    return "\n".join(lines)


def create_progress_bar(current: float, goal: float, length: int = 10) -> str:
    if goal == 0:
        filled = 0
    else:
        filled = int((current / goal) * length)
        filled = min(filled, length)

    bar = ":large_green_square:" * filled + ":white_large_square:" * (length - filled)
    return bar


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
