"""
Configuration Module - Manages environment variables and application settings
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Google Gemini Configuration
    google_api_key: str = Field(..., description="Google API key for Gemini")
    gemini_model: str = Field(default="gemini-1.5-flash", description="Gemini model to use")
    
    # USDA Configuration
    usda_api_key: Optional[str] = Field(default=None, description="USDA FoodData Central API key (optional)")
    usda_base_url: str = Field(
        default="https://api.nal.usda.gov/fdc/v1",
        description="USDA API base URL"
    )
    
    # Slack Configuration
    slack_bot_token: str = Field(..., description="Slack Bot User OAuth Token")
    slack_app_token: str = Field(..., description="Slack App-Level Token for Socket Mode")
    slack_signing_secret: str = Field(..., description="Slack Signing Secret")
    
    # Database Configuration
    database_url: str = Field(
        default="sqlite:///calories.db",
        description="Database connection URL"
    )
    
    # Application Configuration
    environment: str = Field(default="development", description="Environment (development/production)")
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Debug mode")
    timezone: str = Field(default="UTC", description="Application timezone")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() == "production"


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create settings instance
    
    Returns:
        Settings instance with all configuration
    """
    global settings
    if settings is None:
        settings = Settings()
    return settings


def validate_settings() -> tuple[bool, list[str]]:
    """
    Validate that all required settings are present
    
    Returns:
        Tuple of (is_valid, list of missing/invalid settings)
    """
    errors = []
    
    try:
        config = get_settings()
        
        # Check Google API Key
        if not config.google_api_key:
            errors.append("GOOGLE_API_KEY is missing")
        
        # Check Slack
        if not config.slack_bot_token or not config.slack_bot_token.startswith("xoxb-"):
            errors.append("SLACK_BOT_TOKEN is missing or invalid")
        
        if not config.slack_app_token or not config.slack_app_token.startswith("xapp-"):
            errors.append("SLACK_APP_TOKEN is missing or invalid")
        
        if not config.slack_signing_secret:
            errors.append("SLACK_SIGNING_SECRET is missing")
        
    except Exception as e:
        errors.append(f"Configuration error: {str(e)}")
    
    return len(errors) == 0, errors


if __name__ == "__main__":
    # Test configuration
    is_valid, errors = validate_settings()
    if is_valid:
        print("✅ Configuration is valid!")
        config = get_settings()
        print(f"Environment: {config.environment}")
        print(f"Gemini Model: {config.gemini_model}")
        print(f"Database: {config.database_url}")
    else:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
