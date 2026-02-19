"""
Calculations Module - Health and nutrition calculations
"""

from enum import Enum


class ActivityLevel(Enum):
    """Activity level multipliers for TDEE calculation"""
    SEDENTARY = 1.2  # Little to no exercise
    LIGHTLY_ACTIVE = 1.375  # Exercise 1-3 days/week
    MODERATELY_ACTIVE = 1.55  # Exercise 3-5 days/week
    VERY_ACTIVE = 1.725  # Exercise 6-7 days/week
    EXTRA_ACTIVE = 1.9  # Very intense exercise daily


class GoalType(Enum):
    """Goal type calorie adjustments"""
    LOSE_WEIGHT = -500  # 500 cal deficit per day (~1 lb/week)
    MAINTAIN_WEIGHT = 0  # No adjustment
    GAIN_WEIGHT = 500  # 500 cal surplus per day (~1 lb/week)
    BUILD_MUSCLE = 300  # Moderate surplus for muscle building
    GENERAL_HEALTH = 0  # Maintenance


def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str
) -> float:
    """Calculate BMR using Mifflin-St Jeor equation."""
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    
    if gender.lower() in ['male', 'm']:
        bmr += 5
    elif gender.lower() in ['female', 'f']:
        bmr -= 161
    else:
        # Default to female (more conservative estimate)
        bmr -= 161
    
    return round(bmr, 1)


def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str
) -> float:
    """Calculate Total Daily Energy Expenditure (TDEE = BMR x activity multiplier)."""
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    
    # Get activity multiplier
    try:
        activity = ActivityLevel[activity_level.upper()]
        multiplier = activity.value
    except KeyError:
        # Default to sedentary if unknown
        multiplier = ActivityLevel.SEDENTARY.value
    
    tdee = bmr * multiplier
    return round(tdee, 0)


def calculate_calorie_goal(
    tdee: float,
    goal_type: str
) -> int:
    """Calculate daily calorie goal based on TDEE and fitness goal."""
    try:
        goal = GoalType[goal_type.upper()]
        adjustment = goal.value
    except KeyError:
        # Default to maintenance
        adjustment = 0
    
    calorie_goal = tdee + adjustment
    
    # Ensure minimum calories (safety check)
    min_calories = 1200  # Minimum safe calorie intake
    calorie_goal = max(calorie_goal, min_calories)
    
    return int(calorie_goal)


