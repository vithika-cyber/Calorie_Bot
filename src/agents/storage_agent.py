"""
Storage Agent - Handles all database operations
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from sqlalchemy import and_

from ..database.database import get_db_session
from ..database.models import User, FoodLog, MealType

logger = logging.getLogger(__name__)


class StorageAgent:
    """Agent that handles database operations"""
    
    def __init__(self):
        """Initialize storage agent"""
        pass
    
    # User Operations
    
    def get_or_create_user(self, slack_user_id: str, slack_team_id: str) -> Dict[str, Any]:
        """Get existing user or create new one."""
        with get_db_session() as db:
            user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
            
            if not user:
                user = User(
                    slack_user_id=slack_user_id,
                    slack_team_id=slack_team_id
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created new user: {slack_user_id}")
            
            # Convert to dict while session is active
            user_dict = {
                "id": user.id,
                "slack_user_id": user.slack_user_id,
                "slack_team_id": user.slack_team_id,
                "age": user.age,
                "gender": user.gender,
                "current_weight": user.current_weight,
                "target_weight": user.target_weight,
                "height": user.height,
                "activity_level": user.activity_level.value if user.activity_level else None,
                "daily_calorie_goal": user.daily_calorie_goal,
                "preferences": user.preferences,
                "onboarded_at": user.onboarded_at,
                "is_onboarded": user.onboarded_at is not None,
                "created_at": user.created_at,
                "is_active": user.is_active
            }
            
            return user_dict
    
    def update_user(self, slack_user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user information and return updated dict."""
        with get_db_session() as db:
            user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
            
            if not user:
                raise ValueError(f"User not found: {slack_user_id}")
            
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            db.commit()
            db.refresh(user)
            logger.info(f"Updated user {slack_user_id}: {list(updates.keys())}")
            
            # Convert to dict while session is active
            user_dict = {
                "id": user.id,
                "slack_user_id": user.slack_user_id,
                "slack_team_id": user.slack_team_id,
                "age": user.age,
                "gender": user.gender,
                "current_weight": user.current_weight,
                "target_weight": user.target_weight,
                "height": user.height,
                "activity_level": user.activity_level.value if user.activity_level else None,
                "daily_calorie_goal": user.daily_calorie_goal,
                "preferences": user.preferences,
                "onboarded_at": user.onboarded_at,
                "is_onboarded": user.onboarded_at is not None,
                "created_at": user.created_at,
                "is_active": user.is_active
            }
            
            return user_dict
    
    def mark_user_onboarded(self, slack_user_id: str) -> Dict[str, Any]:
        """Mark user as having completed onboarding"""
        return self.update_user(slack_user_id, {"onboarded_at": datetime.now()})
    
    # Food Log Operations
    
    def create_food_log(
        self,
        slack_user_id: str,
        raw_text: str,
        items: List[Dict[str, Any]],
        meal_type: str,
        totals: Dict[str, float]
    ) -> Dict[str, Any]:
        """Create a new food log entry."""
        with get_db_session() as db:
            user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
            
            if not user:
                raise ValueError(f"User not found: {slack_user_id}")
            
            # Convert meal_type string to enum
            try:
                meal_enum = MealType[meal_type.upper()]
            except KeyError:
                meal_enum = MealType.OTHER
            
            food_log = FoodLog(
                user_id=user.id,
                raw_text=raw_text,
                items=items,
                meal_type=meal_enum,
                total_calories=totals.get("calories", 0),
                total_protein=totals.get("protein", 0),
                total_carbs=totals.get("carbs", 0),
                total_fat=totals.get("fat", 0),
                logged_at=datetime.now()
            )
            
            db.add(food_log)
            db.commit()
            db.refresh(food_log)
            
            logger.info(f"Created food log for {slack_user_id}: {totals['calories']} cal")
            
            # Convert to dict while session is active
            food_log_dict = {
                "id": food_log.id,
                "user_id": food_log.user_id,
                "logged_at": food_log.logged_at,
                "meal_type": food_log.meal_type.value,
                "raw_text": food_log.raw_text,
                "items": food_log.items,
                "total_calories": food_log.total_calories,
                "total_protein": food_log.total_protein,
                "total_carbs": food_log.total_carbs,
                "total_fat": food_log.total_fat,
                "confidence_score": food_log.confidence_score,
                "created_at": food_log.created_at
            }
            
            return food_log_dict
    
    def get_food_logs_by_date(
        self,
        slack_user_id: str,
        target_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get all food logs for a specific date (default: today)."""
        if target_date is None:
            target_date = date.today()
        
        with get_db_session() as db:
            user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
            
            if not user:
                return []
            
            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())
            
            logs = db.query(FoodLog).filter(
                and_(
                    FoodLog.user_id == user.id,
                    FoodLog.logged_at >= start_of_day,
                    FoodLog.logged_at <= end_of_day
                )
            ).order_by(FoodLog.logged_at).all()
            
            # Convert to dicts while session is active
            return [
                {
                    "id": log.id,
                    "meal_type": log.meal_type.value if log.meal_type else "other",
                    "raw_text": log.raw_text,
                    "total_calories": log.total_calories or 0,
                    "total_protein": log.total_protein or 0,
                    "total_carbs": log.total_carbs or 0,
                    "total_fat": log.total_fat or 0,
                    "logged_at": log.logged_at
                }
                for log in logs
            ]
    
    def get_daily_totals(
        self,
        slack_user_id: str,
        target_date: Optional[date] = None
    ) -> Dict[str, float]:
        """Get total nutrition for a specific date (default: today)."""
        logs = self.get_food_logs_by_date(slack_user_id, target_date)
        
        totals = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0
        }
        
        for log in logs:
            totals["calories"] += log["total_calories"]
            totals["protein"] += log["total_protein"]
            totals["carbs"] += log["total_carbs"]
            totals["fat"] += log["total_fat"]
        
        # Round to 1 decimal
        for key in totals:
            totals[key] = round(totals[key], 1)
        
        return totals
    
    def delete_food_log(self, log_id: int, slack_user_id: str) -> bool:
        """Delete a food log entry. Returns True if deleted."""
        with get_db_session() as db:
            user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
            
            if not user:
                return False
            
            log = db.query(FoodLog).filter(
                and_(
                    FoodLog.id == log_id,
                    FoodLog.user_id == user.id
                )
            ).first()
            
            if not log:
                return False
            
            db.delete(log)
            db.commit()
            logger.info(f"Deleted food log {log_id} for user {slack_user_id}")
            
            return True
    


# Singleton instance
_storage_agent: Optional[StorageAgent] = None


def get_storage_agent() -> StorageAgent:
    """Get or create storage agent singleton."""
    global _storage_agent
    if _storage_agent is None:
        _storage_agent = StorageAgent()
    return _storage_agent
