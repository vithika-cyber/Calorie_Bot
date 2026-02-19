"""
Database Models - SQLAlchemy ORM models for users, food logs, and goals
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Text,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship
import enum


Base = declarative_base()


class ActivityLevel(enum.Enum):
    """User activity level for TDEE calculation"""
    SEDENTARY = "sedentary"  # Little to no exercise
    LIGHTLY_ACTIVE = "lightly_active"  # Exercise 1-3 days/week
    MODERATELY_ACTIVE = "moderately_active"  # Exercise 3-5 days/week
    VERY_ACTIVE = "very_active"  # Exercise 6-7 days/week
    EXTRA_ACTIVE = "extra_active"  # Very intense exercise daily


class GoalType(enum.Enum):
    """User fitness goal type"""
    LOSE_WEIGHT = "lose_weight"
    MAINTAIN_WEIGHT = "maintain_weight"
    GAIN_WEIGHT = "gain_weight"
    BUILD_MUSCLE = "build_muscle"
    GENERAL_HEALTH = "general_health"


class GoalStatus(enum.Enum):
    """Goal completion status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MealType(enum.Enum):
    """Type of meal"""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    OTHER = "other"


class User(Base):
    """User model - stores user profile and preferences"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    slack_user_id = Column(String(50), unique=True, nullable=False, index=True)
    slack_team_id = Column(String(50), nullable=False)
    
    # Personal Information
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)  # male, female, other
    current_weight = Column(Float, nullable=True)  # in kg
    target_weight = Column(Float, nullable=True)  # in kg
    height = Column(Float, nullable=True)  # in cm
    
    # Activity and Goals
    activity_level = Column(SQLEnum(ActivityLevel), default=ActivityLevel.SEDENTARY)
    daily_calorie_goal = Column(Integer, nullable=True)
    
    # Preferences
    preferences = Column(JSON, default={})  # JSON for flexible preferences
    # Example preferences: {"units": "metric", "timezone": "UTC", "meal_reminders": true}
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    onboarded_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    food_logs = relationship("FoodLog", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(slack_user_id='{self.slack_user_id}', goal={self.daily_calorie_goal})>"
    
    @property
    def is_onboarded(self) -> bool:
        """Check if user has completed onboarding"""
        return self.onboarded_at is not None
    
    @property
    def bmi(self) -> Optional[float]:
        """Calculate BMI if height and weight are available"""
        if self.height and self.current_weight:
            height_m = self.height / 100  # Convert cm to meters
            return round(self.current_weight / (height_m ** 2), 1)
        return None


class FoodLog(Base):
    """Food Log model - stores individual food entries"""
    
    __tablename__ = "food_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Timing
    logged_at = Column(DateTime, default=datetime.utcnow, index=True)
    meal_type = Column(SQLEnum(MealType), default=MealType.OTHER)
    
    # Original Input
    raw_text = Column(Text, nullable=False)  # Original user message
    
    # Parsed Food Items (JSON array)
    items = Column(JSON, nullable=False)
    # Example: [
    #   {
    #     "name": "scrambled eggs",
    #     "quantity": 2,
    #     "unit": "large",
    #     "calories": 140,
    #     "protein": 12,
    #     "carbs": 1,
    #     "fat": 10,
    #     "source": "usda",
    #     "fdc_id": "12345"
    #   }
    # ]
    
    # Totals
    total_calories = Column(Float, nullable=False)
    total_protein = Column(Float, default=0)  # in grams
    total_carbs = Column(Float, default=0)  # in grams
    total_fat = Column(Float, default=0)  # in grams
    
    # Metadata
    confidence_score = Column(Float, default=1.0)  # How confident is the parsing (0-1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="food_logs")
    
    def __repr__(self):
        return f"<FoodLog(user_id={self.user_id}, meal={self.meal_type.value}, calories={self.total_calories})>"
    
    @property
    def date(self) -> str:
        """Get the date of the log in YYYY-MM-DD format"""
        return self.logged_at.strftime("%Y-%m-%d")
    
    @property
    def time(self) -> str:
        """Get the time of the log in HH:MM format"""
        return self.logged_at.strftime("%H:%M")


class Goal(Base):
    """Goal model - stores user fitness goals"""
    
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Goal Details
    goal_type = Column(SQLEnum(GoalType), nullable=False)
    status = Column(SQLEnum(GoalStatus), default=GoalStatus.ACTIVE, index=True)
    
    # Weight Goals
    starting_weight = Column(Float, nullable=True)  # in kg
    target_weight = Column(Float, nullable=True)  # in kg
    current_weight = Column(Float, nullable=True)  # in kg (updated periodically)
    
    # Timeline
    start_date = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="goals")
    
    def __repr__(self):
        return f"<Goal(user_id={self.user_id}, type={self.goal_type.value}, status={self.status.value})>"
    
    @property
    def progress_percentage(self) -> Optional[float]:
        """Calculate goal progress percentage"""
        if self.starting_weight and self.target_weight and self.current_weight:
            total_change_needed = abs(self.target_weight - self.starting_weight)
            change_achieved = abs(self.current_weight - self.starting_weight)
            if total_change_needed > 0:
                return round((change_achieved / total_change_needed) * 100, 1)
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if goal is completed"""
        return self.status == GoalStatus.COMPLETED
    
    @property
    def is_active(self) -> bool:
        """Check if goal is active"""
        return self.status == GoalStatus.ACTIVE
