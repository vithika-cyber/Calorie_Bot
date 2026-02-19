"""
Slack Service - Wrapper for Slack API interactions
"""

import logging
from typing import Optional, List, Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import get_settings

logger = logging.getLogger(__name__)


class SlackService:
    """Service for interacting with Slack API"""
    
    def __init__(self):
        """Initialize Slack service with bot token"""
        settings = get_settings()
        self.bot_token = settings.slack_bot_token
        self.client = WebClient(token=self.bot_token)
    
    def send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None
    ) -> Optional[str]:
        """
        Send a message to a Slack channel or user
        
        Args:
            channel: Channel ID or user ID
            text: Message text (fallback for notifications)
            blocks: Optional rich formatting blocks
            thread_ts: Optional thread timestamp to reply in thread
            
        Returns:
            Message timestamp if successful, None otherwise
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts
            )
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Error sending message: {e.response['error']}")
            return None
    
    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> bool:
        """
        Update an existing message
        
        Args:
            channel: Channel ID
            ts: Message timestamp to update
            text: New message text
            blocks: Optional new blocks
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks
            )
            return True
        except SlackApiError as e:
            logger.error(f"Error updating message: {e.response['error']}")
            return False
    
    def delete_message(self, channel: str, ts: str) -> bool:
        """
        Delete a message
        
        Args:
            channel: Channel ID
            ts: Message timestamp to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.chat_delete(channel=channel, ts=ts)
            return True
        except SlackApiError as e:
            logger.error(f"Error deleting message: {e.response['error']}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information
        
        Args:
            user_id: Slack user ID
            
        Returns:
            User info dictionary or None
        """
        try:
            response = self.client.users_info(user=user_id)
            return response["user"]
        except SlackApiError as e:
            logger.error(f"Error getting user info: {e.response['error']}")
            return None
    
    def send_dm(
        self,
        user_id: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> Optional[str]:
        """
        Send a direct message to a user
        
        Args:
            user_id: Slack user ID
            text: Message text
            blocks: Optional rich formatting blocks
            
        Returns:
            Message timestamp if successful, None otherwise
        """
        # Open DM channel
        try:
            response = self.client.conversations_open(users=[user_id])
            channel_id = response["channel"]["id"]
            return self.send_message(channel_id, text, blocks)
        except SlackApiError as e:
            logger.error(f"Error sending DM: {e.response['error']}")
            return None
    
    def add_reaction(self, channel: str, ts: str, emoji: str) -> bool:
        """
        Add an emoji reaction to a message
        
        Args:
            channel: Channel ID
            ts: Message timestamp
            emoji: Emoji name (without colons)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.reactions_add(
                channel=channel,
                timestamp=ts,
                name=emoji
            )
            return True
        except SlackApiError as e:
            logger.error(f"Error adding reaction: {e.response['error']}")
            return False


# Singleton instance
_slack_service: Optional[SlackService] = None


def get_slack_service() -> SlackService:
    """
    Get or create Slack service instance
    
    Returns:
        Slack service singleton
    """
    global _slack_service
    if _slack_service is None:
        _slack_service = SlackService()
    return _slack_service


# Helper functions for creating Slack Block Kit messages

def create_food_log_blocks(
    meal_type: str,
    items: List[Dict[str, Any]],
    total_calories: float,
    daily_progress: Optional[Dict[str, float]] = None
) -> List[Dict]:
    """
    Create rich Slack blocks for food log confirmation
    
    Args:
        meal_type: Type of meal (breakfast/lunch/dinner/snack)
        items: List of food items
        total_calories: Total calories for the meal
        daily_progress: Optional daily progress data
        
    Returns:
        List of Slack blocks
    """
    blocks = []
    
    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"✅ Logged {meal_type.capitalize()}",
            "emoji": True
        }
    })
    
    # Food items
    items_text = ""
    for item in items:
        emoji = _get_food_emoji(item["name"])
        items_text += f"{emoji} {item['quantity']} {item['unit']} {item['name']}: "
        items_text += f"*{item['calories']} cal*"
        
        # Add macros if available
        macros = []
        if item.get("protein"):
            macros.append(f"P: {item['protein']}g")
        if item.get("carbs"):
            macros.append(f"C: {item['carbs']}g")
        if item.get("fat"):
            macros.append(f"F: {item['fat']}g")
        
        if macros:
            items_text += f" | {' '.join(macros)}"
        
        items_text += "\n"
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": items_text.strip()
        }
    })
    
    # Meal total
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Meal total: {total_calories} calories*"
        }
    })
    
    # Daily progress if available
    if daily_progress:
        current = daily_progress["current"]
        goal = daily_progress["goal"]
        percentage = int((current / goal) * 100) if goal > 0 else 0
        
        # Progress bar
        filled = int(percentage / 10)
        bar = "🟩" * filled + "⬜" * (10 - filled)
        
        blocks.append({
            "type": "divider"
        })
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📊 *Daily Progress*\n{bar}\n{current}/{goal} cal ({percentage}%)"
            }
        })
    
    return blocks


def create_daily_summary_blocks(
    date: str,
    meals: List[Dict[str, Any]],
    total_calories: float,
    goal_calories: int,
    macros: Dict[str, float]
) -> List[Dict]:
    """
    Create rich Slack blocks for daily summary
    
    Args:
        date: Date string
        meals: List of meals
        total_calories: Total calories for the day
        goal_calories: Daily goal
        macros: Macro breakdown
        
    Returns:
        List of Slack blocks
    """
    blocks = []
    
    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"📊 Daily Summary - {date}",
            "emoji": True
        }
    })
    
    # Overall stats
    percentage = int((total_calories / goal_calories) * 100) if goal_calories > 0 else 0
    status_emoji = "✅" if abs(total_calories - goal_calories) < 100 else "⚠️"
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{status_emoji} *{total_calories}/{goal_calories} calories* ({percentage}%)\n\n"
                   f"*Macros:* P: {macros.get('protein', 0)}g | C: {macros.get('carbs', 0)}g | F: {macros.get('fat', 0)}g"
        }
    })
    
    # Meals breakdown
    if meals:
        blocks.append({
            "type": "divider"
        })
        
        meals_text = "*Meals logged:*\n"
        for meal in meals:
            meals_text += f"\n• {meal['meal_type'].capitalize()}: {meal['calories']} cal"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": meals_text
            }
        })
    
    return blocks


def _get_food_emoji(food_name: str) -> str:
    """Get appropriate emoji for food item"""
    food_lower = food_name.lower()
    
    emoji_map = {
        "egg": "🥚",
        "toast": "🍞",
        "bread": "🍞",
        "apple": "🍎",
        "banana": "🍌",
        "orange": "🍊",
        "salad": "🥗",
        "chicken": "🍗",
        "rice": "🍚",
        "pasta": "🍝",
        "pizza": "🍕",
        "burger": "🍔",
        "coffee": "☕",
        "milk": "🥛",
        "cheese": "🧀",
        "fish": "🐟",
        "meat": "🥩",
        "vegetable": "🥦",
        "fruit": "🍓",
        "avocado": "🥑",
    }
    
    for keyword, emoji in emoji_map.items():
        if keyword in food_lower:
            return emoji
    
    return "🍽️"  # Default food emoji


if __name__ == "__main__":
    # Test Slack service
    service = get_slack_service()
    
    # Test creating blocks
    test_items = [
        {
            "name": "scrambled eggs",
            "quantity": 2,
            "unit": "large",
            "calories": 140,
            "protein": 12,
            "carbs": 1,
            "fat": 10
        },
        {
            "name": "whole wheat toast",
            "quantity": 1,
            "unit": "slice",
            "calories": 80,
            "protein": 4,
            "carbs": 13,
            "fat": 1
        }
    ]
    
    blocks = create_food_log_blocks(
        meal_type="breakfast",
        items=test_items,
        total_calories=220,
        daily_progress={"current": 220, "goal": 2000}
    )
    
    print("Food log blocks created successfully!")
    print(f"Number of blocks: {len(blocks)}")
