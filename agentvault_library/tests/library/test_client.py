import pytest
import httpx
import respx # Re-add respx import
import json
import uuid
import datetime
import asyncio
# --- ADDED: Import re ---
import re
# --- END ADDED ---
from unittest.mock import MagicMock, call, patch, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple, List, AsyncGenerator


# Import client, models, exceptions, and KeyManager
from agentvault.client import AgentVaultClient, A2AEvent, CACHE_EXPIRY_BUFFER_SECONDS
from agentvault.key_manager import KeyManager
from agentvault.models import (
    AgentCard, AgentProvider, AgentCapabilities, AgentAuthentication, Message, TextPart,
    Task, TaskState, TaskSendResult, TaskCancelResult,
    TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent, Artifact
)
from agentvault.exceptions import (
    A2AError, A2AConnectionError, A2AAuthenticationError, A2ARemoteAgentError,
    A2ATimeoutError, A2AMessageError
)
# --- ADDED: Import testing utils ---
from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
from agentvault_testing_utils.mock_server import (
    create_jsonrpc_error_response,
    create_jsonrpc_success_response,
    # generate_sse_stream, # No longer needed directly in test
    JSONRPC_APP_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INTERNAL_ERROR,
    # --- ADDED: Import default task creator ---
    create_default_mock_task
    # --- END ADDED ---
)
# --- END ADDED ---

import logging

# --- Fixtures ---
# (Fixtures remain the same)
@pytest.fixture
def mock_key_manager(mocker) -> MagicMock:
    mock_km = MagicMock(spec=KeyManager)
    mock_km.get_key.return_value = "test-key-123" # Default API Key for tests
    mock_km.get_oauth_client_id.return_value = "oauth-client-id-123" # Default OAuth ID
    mock_km.get_oauth_client_secret.return_value = "oauth-client-secret-xyz" # Default OAuth Secret
    return mock_km

@pytest.fixture
def sample_message() -> Message:
    return Message(role="user", parts=[TextPart(content="Hello Agent")])

@pytest.fixture
def agent_card_apikey(mock_a2a_server: MockServerInfo) -> AgentCard:
    """Provides an AgentCard instance supporting only apiKey."""
    return AgentCard(
        schemaVersion="1.0", humanReadableId="test-org/apikey-agent", agentVersion="1.0.0",
        name="API Key Test Agent", description="Agent for testing api key auth.",
        url=f"{mock_a2a_server.base_url}/a2a", # Use URL from fixture
        provider=AgentProvider(name="Test Suite Inc."), capabilities=AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[AgentAuthentication(scheme="apiKey", service_identifier="test-service-apikey")]
    )

@pytest.fixture
def agent_card_no_auth(mock_a2a_server: MockServerInfo) -> AgentCard:
     """Provides an AgentCard instance supporting only none auth."""
     return AgentCard(
        schemaVersion="1.0", humanReadableId="test-org/no-auth-agent", agentVersion="1.0.0",
        name="No Auth Test Agent", description="Agent for testing no auth.",
        url=f"{mock_a2a_server.base_url}/a2a", # Use URL from fixture
        provider=AgentProvider(name="Test Suite Inc."), capabilities=AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[AgentAuthentication(scheme="none")]
    )

@pytest.fixture
def agent_card_oauth2(mock_a2a_server: MockServerInfo) -> AgentCard:
    """Provides an AgentCard instance supporting only OAuth2."""
    return AgentCard(
        schemaVersion="1.0", humanReadableId="test-org/oauth2-agent", agentVersion="1.0.0",
        name="OAuth2 Test Agent", description="Agent for testing oauth2 auth.",
        url=f"{mock_a2a_server.base_url}/a2a", # Use URL from fixture
        provider=AgentProvider(name="Test Suite Inc."), capabilities=AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[AgentAuthentication(
            scheme="oauth2",
            tokenUrl=f"{mock_a2a_server.base_url}/token", # Use token URL from fixture
            scopes=["tasks:read"],
            service_identifier="test-service-oauth"
        )]
    )


# --- Test Init and Context Manager ---
# (Keep existing tests)
# ...

# --- Test _get_auth_headers ---
# (Keep existing tests)
# ...

# --- Test initiate_task ---
# (Keep existing tests)
# ...

# --- Test send_message ---
# (Keep existing tests)
# ...

# --- Test get_task_status ---
@pytest.mark.asyncio
async def test_get_task_status_success(
    mock_a2a_server: MockServerInfo,
    agent_card_apikey: AgentCard,
    mock_key_manager
):
    task_id = "existing-task-2"
    # --- MODIFIED: Put the full default task dict in the store ---
    mock_a2a_server.task_store[task_id] = create_default_mock_task(task_id)
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        task = await client.get_task_status(agent_card_apikey, task_id, mock_key_manager)
    assert isinstance(task, Task)
    assert task.id == task_id
    # Assert against default mock data state (which is COMPLETED)
    assert task.state == TaskState.COMPLETED
    assert isinstance(task.messages, list)
    assert isinstance(task.artifacts, list)
    # --- MODIFIED: Use correct attribute name ---
    assert isinstance(task.created_at, datetime.datetime)
    assert isinstance(task.updated_at, datetime.datetime)
    # --- END MODIFIED ---


# --- Test terminate_task ---
# (Keep existing test)
# ...

# --- Test receive_messages ---
@pytest.mark.asyncio
async def test_receive_messages_success(
    mock_a2a_server: MockServerInfo,
    # respx_mock: respx.mock, # No longer needed directly here
    agent_card_apikey: AgentCard,
    mock_key_manager
):
    task_id = "existing-task-sse"
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING} # Ensure task exists

    # Configure events to be streamed via the fixture's store
    now = datetime.datetime.now(datetime.timezone.utc)
    event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
    event2 = TaskMessageEvent(taskId=task_id, message=Message(role="assistant", parts=[TextPart(content="SSE Message")]), timestamp=now)
    mock_a2a_server.sse_event_store[task_id] = [event1, event2] # Store events

    # The mock_a2a_server fixture now handles setting up the respx route
    # to return a streaming response using generate_sse_stream internally.

    received_events = []
    logging.info("Starting test_receive_messages_success loop...") # Log before loop
    async with AgentVaultClient() as client:
        async for event in client.receive_messages(agent_card_apikey, task_id, mock_key_manager):
            # --- ADDED: Logging ---
            logging.info(f"Test received event: {type(event)} - {event}")
            # --- END ADDED ---
            received_events.append(event)
    logging.info(f"Finished test_receive_messages_success loop. Received {len(received_events)} events.") # Log after loop

    # --- MODIFIED: Assert correct number of events ---
    assert len(received_events) == 2, f"Expected 2 events, but received {len(received_events)}"
    # --- END MODIFIED ---
    assert isinstance(received_events[0], TaskStatusUpdateEvent)
    assert received_events[0].state == TaskState.WORKING
    assert isinstance(received_events[1], TaskMessageEvent)
    assert received_events[1].message.parts[0].content == "SSE Message" # type: ignore

@pytest.mark.asyncio
async def test_receive_messages_stream_error(
    mock_a2a_server: MockServerInfo,
    # respx_mock: respx.mock, # No longer needed
    agent_card_apikey: AgentCard,
    mock_key_manager,
    mocker # Use mocker to patch internal method
):
    task_id = "existing-task-sse-err"
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING}
    mock_a2a_server.sse_event_store[task_id] = [] # No events needed

    error_message = "Simulated connection error during stream."
    error_to_raise = A2AConnectionError(error_message)

    # --- MODIFIED: Mock _process_sse_stream_lines to return a generator that raises ---
    async def error_raising_generator(*args, **kwargs):
        # This generator will raise the error when iterated upon
        raise error_to_raise
        if False: yield {} # Make it a generator type hint-wise

    # Patch the processing function to RETURN the error generator
    mock_process_lines = mocker.patch(
        "agentvault.client.AgentVaultClient._process_sse_stream_lines",
        return_value=error_raising_generator() # Return the generator instance
    )
    # --- END MODIFIED ---

    received_events = []
    # --- MODIFIED: Expect A2AConnectionError directly and match its message ---
    # The receive_messages function should now re-raise the specific error
    with pytest.raises(A2AConnectionError, match=re.escape(error_message)):
    # --- END MODIFIED ---
        async with AgentVaultClient() as client:
            # The error now happens when the async for loop tries to iterate
            # the generator returned by the mocked _process_sse_stream_lines
            async for event in client.receive_messages(agent_card_apikey, task_id, mock_key_manager):
                received_events.append(event) # Should not be reached

    assert len(received_events) == 0
    # --- MODIFIED: Assert the correct mock was called ---
    mock_process_lines.assert_called_once() # Check the new mock
    # --- END MODIFIED ---
