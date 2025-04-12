import os
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl
import logging

# Determine the root directory of the registry component to find the .env file
# Assumes config.py is in src/agentvault_registry/
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# More robust way: Find the pyproject.toml directory if needed, but usually
# running the app from the component root (agentvault_registry/) is expected,
# so .env in that root should be found by default search path.

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
        env_file='.env',                # Load .env file from the current working directory (or parent dirs)
        env_file_encoding='utf-8',      # Specify encoding
        case_sensitive=True,            # Environment variable names are case-sensitive
        extra='ignore'                  # Ignore extra fields not defined in the model
    )

# Instantiate settings. This will load values upon import.
settings = Settings()

# --- Configure Logging ---
# Basic logging configuration based on settings
log_level_int = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=log_level_int, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info(f"Logging configured with level: {settings.LOG_LEVEL}")
# You might want a more sophisticated logging setup using logging.config later
