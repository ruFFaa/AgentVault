import os
import sys # Import sys
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl
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

    # --- Database Settings ---
    # Example: postgresql+asyncpg://user:password@host:port/dbname
    # Loaded from DATABASE_URL environment variable or .env file
    DATABASE_URL: str

    # --- Security Settings ---
    # Secret key for signing tokens, etc. MUST be kept secret.
    # Generate a strong key, e.g., using: openssl rand -hex 32
    # Loaded from API_KEY_SECRET environment variable or .env file
    API_KEY_SECRET: str

    # --- CORS Settings ---
    # List of allowed origins. Use ["*"] for development, but restrict in production.
    ALLOWED_ORIGINS: List[Union[AnyHttpUrl, str]] = ["*"] # Default to allow all for dev

    # --- Logging Settings ---
    LOG_LEVEL: str = "INFO"

    # --- Pydantic Settings Configuration ---
    # Tells pydantic-settings where to load the .env file from
    model_config = SettingsConfigDict(
        # --- MODIFIED: Use the explicit path ---
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.is_file() else None,
        # --- END MODIFIED ---
        env_file_encoding='utf-8',      # Specify encoding
        case_sensitive=True,            # Environment variable names are case-sensitive
        extra='ignore',                 # Ignore extra fields not defined in the model
        validate_default=False,         # Don't validate default values (helpful for URL validation in testing)
    )

# Function to help detect testing environments
def is_testing() -> bool:
    """Check if we're running in a test environment"""
    # Using pytest's environment variable is more reliable than checking sys.argv
    return 'PYTEST_CURRENT_TEST' in os.environ

# Instantiate settings. This will load values upon import.
try:
    settings = Settings()
    # --- Add logging *after* successful instantiation ---
    logger_config.info("Settings loaded successfully.")
    # Optionally log *which* env file was actually used by pydantic-settings
    # Note: This relies on internal details and might change in future pydantic-settings versions
    try:
        loaded_env_files = settings.model_config.get('env_file')
        logger_config.info(f"Pydantic settings loaded env_file: {loaded_env_files}")
    except Exception:
        pass # Ignore if internal structure changes
    # --- End logging ---

except Exception as e:
    logger_config.error(f"Failed to instantiate Settings: {e}", exc_info=True) # Log the error here
    if is_testing():
        # Provide default test values if running tests *and* loading failed
        logger_config.warning("Loading settings failed, falling back to test defaults.")
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db",
            API_KEY_SECRET="test_secret_key_for_testing_only_fallback_1234567890abcdef"
        )
        logger_config.warning("Using test settings for DATABASE_URL and API_KEY_SECRET")
    else:
        # Re-raise the exception in production environments if loading fails
        logger_config.critical("CRITICAL: Failed to load application settings from environment or .env file.")
        raise e

# --- Configure Logging ---
# Basic logging configuration based on settings
log_level_int = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
# Ensure the root logger is configured
logging.basicConfig(level=log_level_int, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.info(f"Logging configured with level: {settings.LOG_LEVEL}")
# You might want a more sophisticated logging setup using logging.config later
