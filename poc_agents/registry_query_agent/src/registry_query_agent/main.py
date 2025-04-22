import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any # Added Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status # Added Depends, status
from fastapi.responses import JSONResponse
# --- ADDED: Import APIKeyHeader if needed ---

# --- END ADDED ---
import uvicorn
from pydantic import ValidationError as PydanticValidationError

# SDK Imports
from agentvault_server_sdk import create_a2a_router
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError, ConfigurationError # Added ConfigurationError
from agentvault_server_sdk.state import InMemoryTaskStore, BaseTaskStore
from agentvault_server_sdk.fastapi_integration import (
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
)

# Import agent logic
from .agent import RegistryQueryAgent # <<< UPDATED IMPORT

# Load .env file (if exists) - important for local running
# from dotenv import load_dotenv # Uncomment if you use a .env file locally
# load_dotenv() # Uncomment if you use a .env file locally

# Configure logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App Setup ---
app = FastAPI(
    title="Registry Query Agent", # <<< UPDATED TITLE
    description="Accepts a search term and queries the AgentVault Registry API.", # <<< UPDATED DESCRIPTION
    version="0.1.0" # Agent specific version
)

# --- Agent and Router Setup ---
# Use a persistent store (Redis, DB) in production!
task_store: BaseTaskStore = InMemoryTaskStore()
agent_instance = RegistryQueryAgent(task_store_ref=task_store) # <<< UPDATED INSTANTIATION

# --- Optional Authentication Dependency ---

# No authentication dependency needed for this example
# a2a_router_dependencies = []
# logger.info("No authentication configured for the /a2a endpoint.")

# --- End Optional Authentication Dependency ---


a2a_router = create_a2a_router(
    agent=agent_instance,
    task_store=task_store,
    prefix="/a2a", # Standard A2A endpoint prefix
    tags=["A2A"]
    # dependencies removed as they are not supported
)
app.include_router(a2a_router)

# --- Exception Handlers (Required for SDK Router) ---
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValueError, validation_exception_handler)
app.add_exception_handler(TypeError, validation_exception_handler)
app.add_exception_handler(PydanticValidationError, validation_exception_handler)
app.add_exception_handler(ConfigurationError, agent_server_error_handler) # Handle config errors
app.add_exception_handler(AgentServerError, agent_server_error_handler)
app.add_exception_handler(Exception, generic_exception_handler) # Catch-all

# --- Root Endpoint ---
@app.get("/", tags=["Status"])
async def read_root():
    return {"message": f"Registry Query Agent running"} # <<< UPDATED MESSAGE

# --- Serve Agent Card ---
# Assumes agent-card.json is in the root of the generated project
CARD_PATH = Path(__file__).parent.parent.parent / "agent-card.json" # Adjusted path

@app.get("/agent-card.json", tags=["Agent Card"], response_model=Dict[str, Any])
async def get_agent_card_json():
    """Serves the agent-card.json file."""
    if not CARD_PATH.is_file():
        logger.error(f"Agent card file not found at expected location: {CARD_PATH}")
        raise HTTPException(status_code=500, detail="Agent card configuration file not found on server.")
    try:
        with open(CARD_PATH, 'r', encoding='utf-8') as f:
            card_data = json.load(f)
        return card_data
    except Exception as e:
        logger.exception("Failed to load or parse agent-card.json")
        raise HTTPException(status_code=500, detail=f"Failed to load agent card: {e}")

logger.info(f"'Registry Query Agent' application initialized.") # <<< UPDATED NAME

# --- Uvicorn Runner (for direct execution using `python src/registry_query_agent/main.py`) ---
if __name__ == "__main__":
    # Determine package name dynamically if needed, or use the known name
    package_name = Path(__file__).parent.name
    port = int(os.environ.get("PORT", 8001)) # Default port for this agent
    logger.info(f"Starting Uvicorn server on host 0.0.0.0, port {port}")
    # Ensure reload is False when running directly, rely on external tools like Docker for production
    uvicorn.run(f"{package_name}.main:app", host="0.0.0.0", port=port, reload=False) # Use package name
