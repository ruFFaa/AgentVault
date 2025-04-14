import os
import sys
import pytest
import pytest_asyncio
import asyncio
import uuid
import datetime
from typing import AsyncGenerator, Dict, Any, Generator, List # Added List
from unittest.mock import MagicMock, AsyncMock

# Set test environment variables BEFORE importing any app modules
os.environ["DATABASE_URL"] = "postgresql+asyncpg://fake:fake@localhost:5432/test_db"
os.environ["API_KEY_SECRET"] = "test_secret_key_for_testing_only"

import httpx
from fastapi.testclient import TestClient # Import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status, HTTPException, FastAPI

# Now import the FastAPI app and dependencies
from agentvault_registry.main import app # Import the app instance
from agentvault_registry.database import get_db
# --- MODIFIED: Import security module ---
from agentvault_registry import models, security # Import security here
# --- END MODIFIED ---
from agentvault_registry.security import get_current_developer, get_current_developer_optional # Import optional dep


# --- Fixtures for Core Test Utilities ---

@pytest.fixture(scope="session")
def event_loop():
    """Create and return a session-scoped event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def sync_test_client() -> Generator[TestClient, None, None]:
    """Provides a synchronous FastAPI TestClient."""
    client = TestClient(app=app, base_url="http://testserver")
    yield client


@pytest_asyncio.fixture(scope="function")
async def mock_db_session() -> AsyncGenerator[MagicMock, None]:
    """Provides a mock SQLAlchemy AsyncSession with configured result structure."""
    session_mock = MagicMock(spec=AsyncSession)
    session_mock.commit = AsyncMock()
    session_mock.refresh = AsyncMock()
    # --- MODIFIED: Configure mock result chain for async iteration ---
    mock_result = AsyncMock() # Mock for the Result object returned by execute

    # Default async generator for scalars() - yields nothing
    async def default_mock_scalar_generator():
        if False: yield None # Make it a generator

    # Configure result.scalars to return an instance of the generator
    mock_result.scalars.return_value = default_mock_scalar_generator()

    # Configure session.execute(...) to return the result mock
    session_mock.execute.return_value = mock_result
    # --- END MODIFIED ---
    session_mock.get = AsyncMock(return_value=None) # Default for get
    session_mock.add = MagicMock()
    session_mock.rollback = AsyncMock()
    session_mock.close = AsyncMock()

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: session_mock
    yield session_mock
    if original_override: app.dependency_overrides[get_db] = original_override
    else: del app.dependency_overrides[get_db]


# --- Fixtures for Mock Data ---
@pytest.fixture
def mock_developer() -> models.Developer:
    """Provides a mock Developer object."""
    return models.Developer(
        id=1, name="Test Developer", api_key_hash=security.hash_api_key("fake-key"), is_verified=False, # Hash the key
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc)
    )

@pytest.fixture
def mock_other_developer() -> models.Developer:
    """Provides a different mock Developer object for ownership tests."""
    return models.Developer(
        id=99, name="Other Developer", api_key_hash="hashed_key_xyz", is_verified=True, # Make this one verified
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc)
    )

@pytest.fixture
def valid_agent_card_data_dict() -> Dict[str, Any]:
    """Provides a valid dictionary representing Agent Card data."""
    return {
        "schemaVersion": "1.0", "humanReadableId": "test-org/test-api-agent", "agentVersion": "1.2.0",
        "name": "API Test Agent", "description": "An agent created via API test.",
        "url": "https://test-agent.example.com/a2a",
        "provider": {"name": "Test Fixtures Inc."}, "capabilities": {"a2aVersion": "1.0"},
        "authSchemes": [{"scheme": "apiKey", "service_identifier": "test-api-key"}]
    }

@pytest.fixture
def mock_agent_card_db_object(mock_developer: models.Developer, valid_agent_card_data_dict: Dict[str, Any]) -> models.AgentCard:
    """Provides a mock AgentCard database object."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return models.AgentCard(
        id=uuid.uuid4(), developer_id=mock_developer.id, card_data=valid_agent_card_data_dict,
        name=valid_agent_card_data_dict["name"], description=valid_agent_card_data_dict.get("description"),
        is_active=True, created_at=now, updated_at=now, developer=mock_developer
    )

# --- Fixture for Overriding Authentication ---
@pytest_asyncio.fixture
async def override_get_current_developer(mock_developer: models.Developer):
    """Fixture to override the authentication dependency to return a mock developer."""
    original_override = app.dependency_overrides.get(get_current_developer)
    async def mock_auth():
        return mock_developer
    app.dependency_overrides[get_current_developer] = mock_auth
    yield
    if original_override: app.dependency_overrides[get_current_developer] = original_override
    else: del app.dependency_overrides[get_current_developer]

# --- ADDED: Fixture to override OPTIONAL auth ---
@pytest_asyncio.fixture
async def override_get_current_developer_optional(mock_developer: models.Developer):
    """Fixture to override the OPTIONAL authentication dependency to return a mock developer."""
    original_override = app.dependency_overrides.get(get_current_developer_optional)
    async def mock_auth_opt():
        return mock_developer
    app.dependency_overrides[get_current_developer_optional] = mock_auth_opt
    yield
    if original_override: app.dependency_overrides[get_current_developer_optional] = original_override
    else: del app.dependency_overrides[get_current_developer_optional]
# --- END ADDED ---


@pytest_asyncio.fixture
async def override_get_current_developer_optional_none():
    """Fixture to override the optional auth dependency to return None."""
    original_override = app.dependency_overrides.get(security.get_current_developer_optional)
    async def mock_auth_none():
        return None
    app.dependency_overrides[security.get_current_developer_optional] = mock_auth_none
    yield
    if original_override: app.dependency_overrides[security.get_current_developer_optional] = original_override
    else: del app.dependency_overrides[security.get_current_developer_optional]


@pytest_asyncio.fixture
async def override_get_current_developer_forbidden():
    """Fixture to override the authentication dependency to raise 403."""
    async def _mock_forbidden(): raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    original_override = app.dependency_overrides.get(get_current_developer)
    app.dependency_overrides[get_current_developer] = _mock_forbidden
    yield
    if original_override: app.dependency_overrides[get_current_developer] = original_override
    else: del app.dependency_overrides[get_current_developer]

@pytest_asyncio.fixture
async def override_get_current_developer_unauthorized():
    """Fixture to override the authentication dependency to raise 401."""
    async def _mock_unauthorized(): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    original_override = app.dependency_overrides.get(get_current_developer)
    app.dependency_overrides[get_current_developer] = _mock_unauthorized
    yield
    if original_override: app.dependency_overrides[get_current_developer] = original_override
    else: del app.dependency_overrides[get_current_developer]
