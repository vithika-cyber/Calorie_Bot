"""
Main Entry Point - Slack Bot with Socket Mode
"""

import logging
import sys
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import get_settings, validate_settings
from .database.database import init_db, check_db_connection
from .agents.orchestrator import get_orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('calorie_bot.log')
    ]
)

logger = logging.getLogger(__name__)


def create_app() -> tuple[App, SocketModeHandler]:
    """Create and configure the Slack app."""
    # Validate configuration
    logger.info("Validating configuration...")
    is_valid, errors = validate_settings()
    if not is_valid:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\nPlease check your .env file and ensure all required variables are set.")
        sys.exit(1)
    
    logger.info("[OK] Configuration valid")
    
    # Get settings
    settings = get_settings()
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        if check_db_connection():
            logger.info("[OK] Database initialized and connected")
        else:
            logger.error("[FAIL] Database connection failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"[FAIL] Database initialization failed: {e}")
        sys.exit(1)
    
    # Initialize Slack app
    logger.info("Initializing Slack app...")
    app = App(token=settings.slack_bot_token)
    
    # Get orchestrator
    orchestrator = get_orchestrator()
    
    # Event handlers
    
    @app.event("app_mention")
    def handle_app_mention(event, say, logger):
        """Handle when bot is mentioned"""
        try:
            user_id = event["user"]
            team_id = event.get("team")
            text = event["text"]
            
            # Remove bot mention from text
            text = text.split('>', 1)[-1].strip() if '>' in text else text
            
            logger.info(f"App mention from {user_id}: {text}")
            
            # Process through orchestrator
            result = orchestrator.process_message(user_id, team_id, text)
            
            # Send response
            say(result["response"], thread_ts=event.get("ts"))
            
        except Exception as e:
            logger.error(f"Error handling app mention: {e}", exc_info=True)
            say("Sorry, I encountered an error. Please try again.")
    
    @app.event("message")
    def handle_message(event, say, logger):
        """Handle direct messages to the bot"""
        try:
            # Ignore bot messages and threaded messages
            if event.get("subtype") or event.get("thread_ts"):
                return
            
            # Only handle DMs (channel type is 'im')
            if event.get("channel_type") != "im":
                return
            
            user_id = event["user"]
            team_id = event.get("team")
            text = event["text"]
            
            logger.info(f"DM from {user_id}: {text}")
            
            # Process through orchestrator
            result = orchestrator.process_message(user_id, team_id, text)
            
            # Send response
            say(result["response"])
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            say("Sorry, I encountered an error. Please try again.")
    
    @app.command("/calorie")
    def handle_calorie_command(ack, command, say, logger):
        """Handle /calorie slash command"""
        try:
            ack()  # Acknowledge command request
            
            user_id = command["user_id"]
            team_id = command["team_id"]
            text = command.get("text", "")
            
            logger.info(f"Command from {user_id}: /calorie {text}")
            
            if not text:
                text = "help"
            
            # Process through orchestrator
            result = orchestrator.process_message(user_id, team_id, text)
            
            # Send response
            say(result["response"])
            
        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            say("Sorry, I encountered an error. Please try again.")
    
    @app.event("app_home_opened")
    def handle_app_home_opened(event, client, logger):
        """Handle when user opens the app home"""
        try:
            user_id = event["user"]
            
            # Publish a simple home view
            client.views_publish(
                user_id=user_id,
                view={
                    "type": "home",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "👋 Welcome to CalorieBot!"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Track your nutrition effortlessly!*\n\nJust send me a message about what you ate, and I'll handle the rest."
                            }
                        },
                        {
                            "type": "divider"
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Quick Start:*\n• 'I had 2 eggs and toast'\n• 'What did I eat today?'\n• 'Show my progress'\n\nReady to get started? Just send me a DM!"
                            }
                        }
                    ]
                }
            )
        except Exception as e:
            logger.error(f"Error handling app home: {e}", exc_info=True)
    
    # Create Socket Mode handler
    logger.info("Setting up Socket Mode...")
    handler = SocketModeHandler(app, settings.slack_app_token)
    
    logger.info("[OK] Slack app initialized")
    
    return app, handler


def main():
    """Main entry point"""
    logger.info("="*50)
    logger.info("CalorieBot Starting...")
    logger.info("="*50)
    
    try:
        # Create app and handler
        app, handler = create_app()
        
        # Start the bot
        logger.info("Bolt app is running!")
        logger.info("CalorieBot is online and ready!")
        logger.info("="*50)
        
        # This will run until interrupted
        handler.start()
        
    except KeyboardInterrupt:
        logger.info("CalorieBot shutting down...")
    except Exception as e:
        logger.error(f"[FAIL] Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
