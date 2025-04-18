import os
import sys # Import sys
# --- MODIFIED: Added List, Union, Optional, EmailStr ---
from typing import List, Union, Optional
from pydantic import AnyHttpUrl, EmailStr # Added EmailStr
# --- END MODIFIED ---
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
from pathlib import Path # Import Path

# Determine the root directory of the registry component to find the .env file
# config.py is in src/agentvault_registry/
# We want the .env file in the parent directory (agentvault_registry/)
CONFIG_DIR = Path(__file__).resolve().parent
REGISTRY_ROOT_DIR = CONFIG_DIR.parent.parent # Go up two levels (src/ -> agentvault_registry/)
ENV_FILE_PATH = REGISTRY_ROOT_DIR / ".env"

# --- Add Logging to check if the .env file is found ---
logger_config = logging.getLogger(__name__ + ".config_loading") # Use a distinct logger name
logger_config.info(f"Attempting to load .env file from explicit path: {ENV_FILE_PATH}")
if ENV_FILE_PATH.is_file():
    logger_config.info(f".env file found at: {ENV_FILE_PATH}")
else:
    logger_config.warning(f".env file NOT found at the expected path: {ENV_FILE_PATH}. CWD: {os.getcwd()}")
# --- End Logging ---


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables and .env file.
    """
    # --- Core Settings ---
    PROJECT_NAME: str = "AgentVault Registry API"
    API_V1_STR: str = "/api/v1" # Base path for API endpoints
    BASE_URL: AnyHttpUrl = "http://localhost:8000" # Default for local dev, override in production .env


    # --- Database Settings ---
    DATABASE_URL: str

    # --- Security Settings ---
    API_KEY_SECRET: str # Used for JWT signing now
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # Default JWT expiry
    # --- MODIFIED: Added Verification Token Expiry ---
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24 # Default: 24 hours
    # --- END MODIFIED ---


    # --- CORS Settings ---
    ALLOWED_ORIGINS: List[Union[AnyHttpUrl, str]] = ["*"]

    # --- Logging Settings ---
    LOG_LEVEL: str = "INFO"

    # --- ADDED: Email Settings ---
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[EmailStr] = None
    MAIL_PORT: int = 587
    MAIL_SERVER: Optional[str] = None
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_FROM_NAME: Optional[str] = "AgentVault Registry"
    # --- END ADDED ---


    # --- Pydantic Settings Configuration ---
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.is_file() else None,
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
        validate_default=False,
    )

# Function to help detect testing environments
def is_testing() -> bool:
    """Check if we're running in a test environment"""
    return 'PYTEST_CURRENT_TEST' in os.environ

# Instantiate settings. This will load values upon import.
try:
    settings = Settings()
    logger_config.info("Settings loaded successfully.")
    try:
        loaded_env_files = settings.model_config.get('env_file')
        logger_config.info(f"Pydantic settings loaded env_file: {loaded_env_files}")
    except Exception:
        pass
    # --- MODIFIED: Check email settings ---
    if not settings.MAIL_SERVER or not settings.MAIL_USERNAME or not settings.MAIL_FROM:
        logger_config.warning("Email settings (MAIL_SERVER, MAIL_USERNAME, MAIL_FROM) are not fully configured. Email sending will likely fail.")
    # --- END MODIFIED ---


except Exception as e:
    logger_config.error(f"Failed to instantiate Settings: {e}", exc_info=True)
    if is_testing():
        logger_config.warning("Loading settings failed, falling back to test defaults.")
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db",
            API_KEY_SECRET="test_secret_key_for_testing_only_fallback_1234567890abcdef",
            # --- MODIFIED: Added default for testing ---
            EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=1,
            # --- END MODIFIED ---
            # --- ADDED: Placeholder email settings for tests ---
            MAIL_SERVER="smtp.example.com",
            MAIL_USERNAME="test@example.com",
            MAIL_FROM="test@example.com",
            # --- END ADDED ---
            BASE_URL="http://testserver"
        )
        logger_config.warning("Using test settings for DATABASE_URL, API_KEY_SECRET, BASE_URL and placeholder EMAIL settings.")
    else:
        logger_config.critical("CRITICAL: Failed to load application settings from environment or .env file.")
        raise e

# --- Configure Logging ---
log_level_int = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=log_level_int, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.info(f"Logging configured with level: {settings.LOG_LEVEL}")
