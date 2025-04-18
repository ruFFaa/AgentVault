import logging
import os
import uuid
import datetime
from typing import Annotated, Optional, Dict, Any # <--- Ensure Dict and Any are here
import json # <--- Ensure json is imported
from pathlib import Path # <--- Ensure Path is imported

from fastapi import FastAPI, HTTPException, status, Depends, Form # <--- Ensure HTTPException is here
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse # <--- Ensure JSONResponse is imported
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from dotenv import load_dotenv
import uvicorn
# SDK Imports
from agentvault_server_sdk import create_a2a_router
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
from agentvault_server_sdk.state import InMemoryTaskStore, BaseTaskStore
from agentvault_server_sdk.fastapi_integration import (
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
)

# Import agent logic
from .agent import OAuthProtectedAgent

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration (Load from Environment) ---
MOCK_CLIENT_ID = os.environ.get("MOCK_CLIENT_ID", "DEFAULT_ID_CHANGE_ME")
MOCK_CLIENT_SECRET = os.environ.get("MOCK_CLIENT_SECRET", "DEFAULT_SECRET_CHANGE_ME")
# Simple mock token - in production, use JWT or similar
MOCK_ACCESS_TOKEN = f"mock-token-for-{MOCK_CLIENT_ID}-{uuid.uuid4().hex[:8]}"
SERVER_PORT = int(os.environ.get("PORT", 8002))

if MOCK_CLIENT_ID == "DEFAULT_ID_CHANGE_ME" or MOCK_CLIENT_SECRET == "DEFAULT_SECRET_CHANGE_ME":
    logger.warning("Using default mock client credentials. Please set MOCK_CLIENT_ID and MOCK_CLIENT_SECRET in your .env file.")

# --- FastAPI App Setup ---
app = FastAPI(
    title="AgentVault OAuth2 Agent Example",
    description="Demonstrates an A2A agent protected by OAuth2 Client Credentials.",
    version="0.1.0"
)

# --- Agent and Router Setup ---
task_store: BaseTaskStore = InMemoryTaskStore()
agent_instance = OAuthProtectedAgent(task_store_ref=task_store)

# --- Authentication Dependency ---
# Define the bearer scheme
bearer_scheme = HTTPBearer(description="A Bearer token obtained from the /token endpoint.")

async def verify_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]) -> None:
    """Dependency to verify the mock Bearer token."""
    logger.debug(f"Verifying token: {credentials.scheme} {credentials.credentials[:10]}...")
    if credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication scheme. Use Bearer.",
        )
    if credentials.credentials != MOCK_ACCESS_TOKEN:
        logger.warning("Token verification failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.debug("Token verified successfully.")
    # If valid, just return None (or could return user info if token contained it)

# --- Create A2A Router with Authentication Dependency ---
a2a_router = create_a2a_router(
    agent=agent_instance,
    task_store=task_store,
    prefix="/a2a",
    tags=["A2A (Protected)"],
    dependencies=[Depends(verify_token)] # Apply token verification to all /a2a routes
)
app.include_router(a2a_router)

# --- Custom OAuth2 Token Endpoint ---
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600

@app.post("/token", response_model=TokenResponse, tags=["Authentication"])
async def login_for_access_token(
    grant_type: Annotated[str, Form()],
    client_id: Annotated[str, Form()],
    client_secret: Annotated[str, Form()],
    scope: Annotated[Optional[str], Form()] = None # Optional scope
):
    """OAuth2 Client Credentials Grant endpoint."""
    logger.info(f"Received token request for client_id: {client_id}, grant_type: {grant_type}")
    if grant_type != "client_credentials":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported grant type")

    # Validate mock credentials (replace with real validation in production)
    if client_id == MOCK_CLIENT_ID and client_secret == MOCK_CLIENT_SECRET:
        logger.info(f"Client credentials valid for {client_id}. Issuing mock token.")
        # In a real app, generate a proper token (e.g., JWT)
        return TokenResponse(access_token=MOCK_ACCESS_TOKEN)
    else:
        logger.warning(f"Invalid client credentials provided for client_id: {client_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client credentials")


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
    return {"message": "AgentVault OAuth2 Agent Example Running"}

@app.get("/agent-card.json", tags=["Agent Card"], response_model=Dict[str, Any])
async def get_agent_card_json():
    """Serves the agent-card.json file."""
    card_path = Path(__file__).parent.parent / "agent-card.json" # Adjust path relative to main.py
    if not card_path.is_file():
        raise HTTPException(status_code=500, detail="agent-card.json not found on server.")
    try:
        with open(card_path, 'r', encoding='utf-8') as f:
            card_data = json.load(f)
        return card_data
    except Exception as e:
        logger.exception("Failed to load or parse agent-card.json")
        raise HTTPException(status_code=500, detail=f"Failed to load agent card: {e}")

logger.info(f"OAuth Agent Example application initialized. Expecting Client ID: '{MOCK_CLIENT_ID}'")

# --- Uvicorn Runner ---
if __name__ == "__main__":
    logger.info(f"Starting Uvicorn server on host 0.0.0.0, port {SERVER_PORT}")
    uvicorn.run("src.oauth_agent_example.main:app", host="0.0.0.0", port=SERVER_PORT, reload=True)

