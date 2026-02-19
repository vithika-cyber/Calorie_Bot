"""
Calculations Module - Health and nutrition calculations
"""

from typing import Dict, Optional
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
    """
    Calculate Basal Metabolic Rate (BMR) using Mifflin-St Jeor equation
    
    This is the most accurate modern formula for BMR calculation.
    
    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        age: Age in years
        gender: 'male' or 'female'
        
    Returns:
        BMR in calories per day
        
    Formula:
        Men: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(y) + 5
        Women: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(y) - 161
    """
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
    """
    Calculate Total Daily Energy Expenditure (TDEE)
    
    TDEE = BMR × Activity Level Multiplier
    
    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        age: Age in years
        gender: 'male' or 'female'
        activity_level: Activity level (sedentary/lightly_active/etc.)
        
    Returns:
        TDEE in calories per day
    """
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
    """
    Calculate daily calorie goal based on TDEE and fitness goal
    
    Args:
        tdee: Total Daily Energy Expenditure
        goal_type: Fitness goal (lose_weight/maintain_weight/gain_weight/etc.)
        
    Returns:
        Daily calorie goal
    """
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


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """
    Calculate Body Mass Index (BMI)
    
    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        
    Returns:
        BMI value
        
    Formula:
        BMI = weight(kg) / (height(m))²
    """
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 1)


def get_bmi_category(bmi: float) -> str:
    """
    Get BMI category description
    
    Args:
        bmi: BMI value
        
    Returns:
        Category description
    """
    if bmi < 18.5:
        return "Underweight"
    elif 18.5 <= bmi < 25:
        return "Normal weight"
    elif 25 <= bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def calculate_macros(
    calorie_goal: int,
    macro_split: Optional[Dict[str, int]] = None
) -> Dict[str, float]:
    """
    Calculate macro nutrient targets in grams
    
    Args:
        calorie_goal: Daily calorie goal
        macro_split: Optional custom split (e.g., {"protein": 30, "carbs": 40, "fat": 30})
                    Values should sum to 100 (percentages)
        
    Returns:
        Dictionary with protein, carbs, and fat in grams
        
    Default split (balanced):
        - Protein: 30% (4 cal/g)
        - Carbs: 40% (4 cal/g)
        - Fat: 30% (9 cal/g)
    """
    if macro_split is None:
        macro_split = {
            "protein": 30,
            "carbs": 40,
            "fat": 30
        }
    
    # Calories per gram
    protein_cal_per_g = 4
    carbs_cal_per_g = 4
    fat_cal_per_g = 9
    
    # Calculate grams
    protein_grams = (calorie_goal * (macro_split["protein"] / 100)) / protein_cal_per_g
    carbs_grams = (calorie_goal * (macro_split["carbs"] / 100)) / carbs_cal_per_g
    fat_grams = (calorie_goal * (macro_split["fat"] / 100)) / fat_cal_per_g
    
    return {
        "protein": round(protein_grams, 1),
        "carbs": round(carbs_grams, 1),
        "fat": round(fat_grams, 1)
    }


def calculate_weight_timeline(
    current_weight: float,
    target_weight: float,
    daily_deficit: int = 500
) -> int:
    """
    Estimate days to reach target weight
    
    Args:
        current_weight: Current weight in kg
        target_weight: Target weight in kg
        daily_deficit: Daily calorie deficit (default 500 = ~1 lb/week)
        
    Returns:
        Estimated days to goal
        
    Note:
        - 3500 calories ≈ 1 lb ≈ 0.45 kg
        - 7700 calories ≈ 1 kg
    """
    weight_difference = abs(current_weight - target_weight)
    
    # Convert to calories needed
    calories_per_kg = 7700
    total_calories_needed = weight_difference * calories_per_kg
    
    # Calculate days
    days = total_calories_needed / abs(daily_deficit)
    
    return int(days)


def pounds_to_kg(pounds: float) -> float:
    """Convert pounds to kilograms"""
    return round(pounds * 0.453592, 2)


def kg_to_pounds(kg: float) -> float:
    """Convert kilograms to pounds"""
    return round(kg * 2.20462, 2)


def inches_to_cm(inches: float) -> float:
    """Convert inches to centimeters"""
    return round(inches * 2.54, 1)


def cm_to_inches(cm: float) -> float:
    """Convert centimeters to inches"""
    return round(cm / 2.54, 1)


if __name__ == "__main__":
    # Example calculations
    print("Health Calculations Demo\n")
    
    # Example person
    weight_kg = 75
    height_cm = 175
    age = 30
    gender = "male"
    activity = "moderately_active"
    goal = "lose_weight"
    
    print(f"Person: {age}yo {gender}, {weight_kg}kg, {height_cm}cm")
    print(f"Activity: {activity}")
    print(f"Goal: {goal}\n")
    
    # BMI
    bmi = calculate_bmi(weight_kg, height_cm)
    category = get_bmi_category(bmi)
    print(f"BMI: {bmi} ({category})")
    
    # BMR
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    print(f"BMR: {bmr} cal/day")
    
    # TDEE
    tdee = calculate_tdee(weight_kg, height_cm, age, gender, activity)
    print(f"TDEE: {tdee} cal/day")
    
    # Calorie Goal
    cal_goal = calculate_calorie_goal(tdee, goal)
    print(f"Calorie Goal: {cal_goal} cal/day")
    
    # Macros
    macros = calculate_macros(cal_goal)
    print(f"\nMacro Targets:")
    print(f"  Protein: {macros['protein']}g")
    print(f"  Carbs: {macros['carbs']}g")
    print(f"  Fat: {macros['fat']}g")
    
    # Timeline
    target_weight = 70
    days = calculate_weight_timeline(weight_kg, target_weight)
    weeks = days / 7
    print(f"\nTime to reach {target_weight}kg: ~{days} days ({weeks:.1f} weeks)")
