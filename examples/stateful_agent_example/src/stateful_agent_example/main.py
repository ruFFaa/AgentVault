import logging
import os
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import ValidationError as PydanticValidationError

# SDK Imports
from agentvault_server_sdk import create_a2a_router
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
from agentvault_server_sdk.state import InMemoryTaskStore, BaseTaskStore
from agentvault_server_sdk.fastapi_integration import (
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
)

# Import agent logic
from .agent import StatefulChatAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App Setup ---
app = FastAPI(
    title="AgentVault Stateful Agent Example",
    description="Demonstrates an A2A agent that maintains state across interactions.",
    version="0.1.0"
)

# --- Agent and Router Setup ---
# Using InMemoryTaskStore for simplicity. Replace with a persistent store for production.
task_store: BaseTaskStore = InMemoryTaskStore()
agent_instance = StatefulChatAgent(task_store_ref=task_store)

a2a_router = create_a2a_router(
    agent=agent_instance,
    task_store=task_store,
    prefix="/a2a",
    tags=["A2A"]
)
app.include_router(a2a_router)

# --- Exception Handlers (Required for SDK Router) ---
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValueError, validation_exception_handler)
app.add_exception_handler(TypeError, validation_exception_handler)
app.add_exception_handler(PydanticValidationError, validation_exception_handler)
app.add_exception_handler(AgentServerError, agent_server_error_handler)
app.add_exception_handler(Exception, generic_exception_handler) # Catch-all

# --- Root and Agent Card Endpoints ---
@app.get("/", tags=["Status"])
async def read_root():
    return {"message": "AgentVault Stateful Agent Example Running"}

@app.get("/agent-card.json", tags=["Agent Card"], response_model=dict)
async def get_agent_card_json():
    """Serves the agent-card.json file."""
    card_path = Path(__file__).parent.parent / "agent-card.json"
    if not card_path.is_file():
        raise HTTPException(status_code=500, detail="agent-card.json not found on server.")
    try:
        with open(card_path, 'r', encoding='utf-8') as f:
            card_data = json.load(f)
        return card_data
    except Exception as e:
        logger.exception("Failed to load or parse agent-card.json")
        raise HTTPException(status_code=500, detail=f"Failed to load agent card: {e}")

logger.info("Stateful Agent Example application initialized.")

# --- Uvicorn Runner ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8003))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0, port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
