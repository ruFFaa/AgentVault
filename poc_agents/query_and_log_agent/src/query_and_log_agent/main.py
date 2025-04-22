import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import ValidationError as PydanticValidationError

# SDK Imports
from agentvault_server_sdk import create_a2a_router
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError, ConfigurationError
from agentvault_server_sdk.state import InMemoryTaskStore, BaseTaskStore
from agentvault_server_sdk.fastapi_integration import (
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
)

# Import agent logic
from .agent import QueryAndLogAgent

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- FastAPI App Setup ---
app = FastAPI(
    title="Query And Log Agent",
    description="An orchestrator agent that demonstrates agent-to-agent communication by querying one agent and logging results with another.",
    version="0.1.0"
)

# --- Agent and Router Setup ---
# Use a persistent store (Redis, DB) in production!
task_store: BaseTaskStore = InMemoryTaskStore()
agent_instance = QueryAndLogAgent(task_store_ref=task_store)

# No authentication for this example
a2a_router = create_a2a_router(
    agent=agent_instance,
    task_store=task_store,
    prefix="/a2a",  # Standard A2A endpoint prefix
    tags=["A2A"]
)
app.include_router(a2a_router)

# --- Exception Handlers (Required for SDK Router) ---
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValueError, validation_exception_handler)
app.add_exception_handler(TypeError, validation_exception_handler)
app.add_exception_handler(PydanticValidationError, validation_exception_handler)
app.add_exception_handler(ConfigurationError, agent_server_error_handler)
app.add_exception_handler(AgentServerError, agent_server_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# --- Root Endpoint ---
@app.get("/", tags=["Status"])
async def read_root():
    return {"message": "Query And Log Agent running"}

# --- Serve Agent Card ---
# Assumes agent-card.json is in the root of the project
CARD_PATH = Path(__file__).parent.parent.parent / "agent-card.json"

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

logger.info("Query And Log Agent application initialized.")

# --- Uvicorn Runner (for direct execution) ---
if __name__ == "__main__":
    package_name = Path(__file__).parent.name
    port = int(os.environ.get("PORT", 8004))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0, port {port}")
    uvicorn.run(f"{package_name}.main:app", host="0.0.0.0", port=port, reload=False)
