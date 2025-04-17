import pytest
# --- MODIFIED: Import respx ---
import respx
# --- END MODIFIED ---
import json
import uuid
import datetime
import asyncio
# --- ADDED: Import re ---
import re
# --- END ADDED ---
# --- ADDED: Import httpx ---
import httpx
# --- END ADDED ---
# --- MODIFIED: Added AsyncMock ---
from unittest.mock import patch, MagicMock, ANY, call, AsyncMock
# --- END MODIFIED ---
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
    AgentVaultError, A2AError, A2AConnectionError, A2AAuthenticationError,
    A2ARemoteAgentError, A2ATimeoutError, A2AMessageError
)
# --- ADDED: Import testing utils ---
from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
# --- MODIFIED: Import setup_mock_a2a_routes ---
from agentvault_testing_utils.mock_server import (
    create_jsonrpc_error_response,
    create_jsonrpc_success_response,
    setup_mock_a2a_routes, # Added import back
    DEFAULT_OAUTH_TOKEN_RESPONSE, # Import default token response
    # generate_sse_stream, # No longer needed directly in test
    JSONRPC_APP_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INTERNAL_ERROR,
    # --- ADDED: Import default task creator ---
    create_default_mock_task
    # --- END ADDED ---
)
# --- END MODIFIED ---
# --- END ADDED ---

import logging

# --- Fixtures ---
# Use fixtures defined in conftest.py implicitly

@pytest.fixture
def mock_key_manager(mocker) -> MagicMock:
    """Provides a mock KeyManager instance."""
    mock_km = MagicMock(spec=KeyManager)
    mock_km.get_key.return_value = "test-key-123" # Default API Key for tests
    mock_km.get_oauth_client_id.return_value = "oauth-client-id-123" # Default OAuth ID
    mock_km.get_oauth_client_secret.return_value = "oauth-client-secret-xyz" # Default OAuth Secret
    return mock_km

@pytest.fixture
def sample_message() -> Message:
    """Provides a sample Message object."""
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


# --- Helper Async Generator Functions ---
async def mock_receive_empty() -> AsyncGenerator[Any, None]:
    if False: yield
    return

async def mock_receive_events(*events) -> AsyncGenerator[Any, None]:
    """Async generator that yields mock events with a delay."""
    test_logger = logging.getLogger("test_mock_receive_events")
    test_logger.info(f"Mock generator starting. Will yield {len(events)} events.")
    for i, event in enumerate(events):
        media_type_to_log = "N/A"
        # --- MODIFIED: Check _AGENTVAULT_AVAILABLE ---
        if _AGENTVAULT_AVAILABLE and isinstance(event, TaskArtifactUpdateEvent):
        # --- END MODIFIED ---
             if hasattr(event, 'artifact') and hasattr(event.artifact, 'media_type'):
                 media_type_to_log = event.artifact.media_type
        test_logger.info(f"Mock generator yielding event {i+1}: type={type(event).__name__}, media_type='{media_type_to_log}'")
        yield event
        await asyncio.sleep(0.01)
    test_logger.info("Mock generator finished yielding events.")

# --- Test Init and Context Manager ---
@pytest.mark.asyncio
async def test_client_init_and_close():
    """Test client initialization and explicit close."""
    client = AgentVaultClient()
    assert isinstance(client._http_client, httpx.AsyncClient)
    assert client._should_close_client is True
    assert not client._http_client.is_closed
    await client.close()
    assert client._http_client.is_closed

@pytest.mark.asyncio
async def test_client_init_with_external_client():
    """Test client initialization with an external httpx client."""
    async with httpx.AsyncClient() as external_client:
        client = AgentVaultClient(http_client=external_client)
        assert client._http_client is external_client
        assert client._should_close_client is False
        await client.close() # Should not close the external client
        assert not external_client.is_closed
    assert external_client.is_closed # Closed by its own context manager

@pytest.mark.asyncio
async def test_client_async_context_manager():
    """Test client usage as an async context manager."""
    async with AgentVaultClient() as client:
        assert isinstance(client._http_client, httpx.AsyncClient)
        assert not client._http_client.is_closed
    assert client._http_client.is_closed # Should be closed on exit

# --- Test _get_auth_headers ---
@pytest.mark.asyncio
async def test_get_auth_headers_none(mock_key_manager, agent_card_no_auth):
    """Test getting headers when agent uses 'none' auth."""
    async with AgentVaultClient() as client:
        headers = await client._get_auth_headers(agent_card_no_auth, mock_key_manager)
    assert headers == {}
    mock_key_manager.get_key.assert_not_called()
    mock_key_manager.get_oauth_client_id.assert_not_called()

@pytest.mark.asyncio
async def test_get_auth_headers_apikey_success(mock_key_manager, agent_card_apikey):
    """Test getting headers when agent uses 'apiKey' and key is found."""
    mock_key_manager.get_key.return_value = "found-api-key"
    async with AgentVaultClient() as client:
        headers = await client._get_auth_headers(agent_card_apikey, mock_key_manager)
    assert headers == {"X-Api-Key": "found-api-key"}
    mock_key_manager.get_key.assert_called_once_with("test-service-apikey")

@pytest.mark.asyncio
async def test_get_auth_headers_apikey_missing(mock_key_manager, agent_card_apikey):
    """Test error when agent uses 'apiKey' and key is missing."""
    mock_key_manager.get_key.return_value = None
    with pytest.raises(A2AAuthenticationError, match="Missing API key"):
        async with AgentVaultClient() as client:
            await client._get_auth_headers(agent_card_apikey, mock_key_manager)
    mock_key_manager.get_key.assert_called_once_with("test-service-apikey")

@pytest.mark.asyncio
# --- MODIFIED: Use respx context manager ---
async def test_get_auth_headers_oauth2_success(mock_key_manager, agent_card_oauth2, mock_a2a_server: MockServerInfo, mocker): # Removed respx_mock fixture
# --- END MODIFIED ---
    """Test getting headers when agent uses 'oauth2' and token fetch succeeds."""
    mock_key_manager.get_oauth_client_id.return_value = "test-client-id-123"
    mock_key_manager.get_oauth_client_secret.return_value = "test-client-secret-xyz"
    # --- MODIFIED: Use respx context manager and setup routes inside ---
    # --- FIX: Access first element of auth_schemes list ---
    token_url = str(agent_card_oauth2.auth_schemes[0].token_url)
    # --- END FIX ---
    async with respx.mock(using="httpx") as respx_mock_context:
        # Setup the token route *within* the context
        token_route = respx_mock_context.post(token_url).mock(
            return_value=httpx.Response(200, json=DEFAULT_OAUTH_TOKEN_RESPONSE)
        )
        # Instantiate and use the client *within* the context
        async with AgentVaultClient() as client:
            headers = await client._get_auth_headers(agent_card_oauth2, mock_key_manager)
    # --- END MODIFIED ---

    assert headers == {"Authorization": f"Bearer {DEFAULT_OAUTH_TOKEN_RESPONSE['access_token']}"}
    mock_key_manager.get_oauth_client_id.assert_called_once_with("test-service-oauth")
    mock_key_manager.get_oauth_client_secret.assert_called_once_with("test-service-oauth")
    # Check token endpoint was called via respx
    assert token_route.called

@pytest.mark.asyncio
async def test_get_auth_headers_oauth2_missing_creds(mock_key_manager, agent_card_oauth2):
    """Test error when agent uses 'oauth2' and client creds are missing."""
    mock_key_manager.get_oauth_client_id.return_value = "test-client-id-123"
    mock_key_manager.get_oauth_client_secret.return_value = None # Secret missing
    with pytest.raises(A2AAuthenticationError, match="Missing OAuth Client ID or Client Secret"):
        async with AgentVaultClient() as client:
            await client._get_auth_headers(agent_card_oauth2, mock_key_manager)
    mock_key_manager.get_oauth_client_id.assert_called_once_with("test-service-oauth")
    mock_key_manager.get_oauth_client_secret.assert_called_once_with("test-service-oauth")

@pytest.mark.asyncio
# --- MODIFIED: Use respx context manager ---
async def test_get_auth_headers_oauth2_token_endpoint_error(mock_key_manager, agent_card_oauth2, mock_a2a_server: MockServerInfo, mocker): # Removed respx_mock fixture
# --- END MODIFIED ---
    """Test error when agent uses 'oauth2' and token endpoint returns error."""
    mock_key_manager.get_oauth_client_id.return_value = "test-client-id-123"
    mock_key_manager.get_oauth_client_secret.return_value = "test-client-secret-xyz"
    # --- MODIFIED: Use respx context manager and setup routes inside ---
    # --- FIX: Access first element of auth_schemes list ---
    token_url = str(agent_card_oauth2.auth_schemes[0].token_url)
    # --- END FIX ---
    async with respx.mock(using="httpx") as respx_mock_context:
        # Mock the token endpoint to return 401
        token_route = respx_mock_context.post(token_url).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))

        with pytest.raises(A2AAuthenticationError, match="Invalid credentials or request"):
            async with AgentVaultClient() as client:
                await client._get_auth_headers(agent_card_oauth2, mock_key_manager)
    # --- END MODIFIED ---
    assert token_route.called # Verify token endpoint was called

# --- Test initiate_task ---
@pytest.mark.asyncio
@pytest.mark.respx(using="httpx")
async def test_initiate_task_success(mock_key_manager, agent_card_no_auth, sample_message, mock_a2a_server: MockServerInfo, respx_mock):
    """Test successful task initiation."""
    task_id = "new-mock-task-1"
    a2a_url = str(agent_card_no_auth.url)
    a2a_route = respx_mock.post(a2a_url).mock(
        return_value=httpx.Response(200, json=create_jsonrpc_success_response("req-init-uuid", {"id": task_id}))
    )
    async with AgentVaultClient() as client:
        returned_id = await client.initiate_task(agent_card_no_auth, sample_message, mock_key_manager)
    assert returned_id == task_id
    assert a2a_route.called

# --- Test send_message ---
@pytest.mark.asyncio
@pytest.mark.respx(using="httpx")
async def test_send_message_success(mock_key_manager, agent_card_no_auth, sample_message, mock_a2a_server: MockServerInfo, respx_mock):
    """Test successfully sending a message to an existing task."""
    task_id = "existing-task-send"
    a2a_url = str(agent_card_no_auth.url)
    a2a_route = respx_mock.post(a2a_url).mock(
        return_value=httpx.Response(200, json=create_jsonrpc_success_response("req-send-uuid", {"id": task_id}))
    )
    async with AgentVaultClient() as client:
        result = await client.send_message(agent_card_no_auth, task_id, sample_message, mock_key_manager)
    assert result is True
    assert a2a_route.called

# --- Test get_task_status ---
@pytest.mark.asyncio
@pytest.mark.respx(using="httpx")
async def test_get_task_status_success(mock_key_manager, agent_card_no_auth, mock_a2a_server: MockServerInfo, respx_mock):
    """Test successfully getting task status."""
    task_id = "existing-task-get"
    mock_task_data = create_default_mock_task(task_id, state=TaskState.WORKING)
    a2a_url = str(agent_card_no_auth.url)
    a2a_route = respx_mock.post(a2a_url).mock(
        return_value=httpx.Response(200, json=create_jsonrpc_success_response("req-get-uuid", mock_task_data))
    )
    async with AgentVaultClient() as client:
        task_result = await client.get_task_status(agent_card_no_auth, task_id, mock_key_manager)
    assert isinstance(task_result, Task)
    assert task_result.id == task_id
    assert task_result.state == TaskState.WORKING
    assert a2a_route.called

# --- Test terminate_task ---
@pytest.mark.asyncio
@pytest.mark.respx(using="httpx")
async def test_terminate_task_success(mock_key_manager, agent_card_no_auth, mock_a2a_server: MockServerInfo, respx_mock):
    """Test successfully terminating a task."""
    task_id = "existing-task-term"
    a2a_url = str(agent_card_no_auth.url)
    a2a_route = respx_mock.post(a2a_url).mock(
        return_value=httpx.Response(200, json=create_jsonrpc_success_response("req-cancel-uuid", {"success": True}))
    )
    async with AgentVaultClient() as client:
        result = await client.terminate_task(agent_card_no_auth, task_id, mock_key_manager)
    assert result is True
    assert a2a_route.called

# --- Test receive_messages ---
@pytest.mark.asyncio
@pytest.mark.respx(using="httpx")
async def test_receive_messages_success(
    mock_a2a_server: MockServerInfo,
    agent_card_apikey: AgentCard,
    mock_key_manager,
    respx_mock # Add fixture
):
    """Test successful SSE stream processing."""
    task_id = "existing-task-sse"
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING} # Ensure task exists

    # Configure events to be streamed via the fixture's store
    now = datetime.datetime.now(datetime.timezone.utc)
    event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
    event2 = TaskMessageEvent(taskId=task_id, message=Message(role="assistant", parts=[TextPart(content="SSE Message")]), timestamp=now)
    mock_a2a_server.sse_event_store[task_id] = [event1, event2] # Store events

    # Fixture handles route setup

    received_events = []
    logging.info("Starting test_receive_messages_success loop...")
    try:
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_apikey, task_id, mock_key_manager):
                logging.info(f"Test received event: {type(event)} - {event}")
                received_events.append(event)
    except Exception as e:
        logging.exception("Error during receive_messages in test_receive_messages_success")
        pytest.fail(f"receive_messages raised unexpected exception: {e}")

    logging.info(f"Finished test_receive_messages_success loop. Received {len(received_events)} events.")

    assert len(received_events) == 2, f"Expected 2 events, but received {len(received_events)}"
    # --- FIX: Correct assertion for list elements ---
    assert isinstance(received_events[0], TaskStatusUpdateEvent)
    assert received_events[0].state == TaskState.WORKING
    assert isinstance(received_events[1], TaskMessageEvent)
    assert isinstance(received_events[1].message.parts[0], TextPart) # Check part type
    assert received_events[1].message.parts[0].content == "SSE Message"
    # --- END FIX ---
    assert respx_mock.calls.call_count == 1


@pytest.mark.asyncio
@pytest.mark.respx(using="httpx")
async def test_receive_messages_stream_error(
    mock_a2a_server: MockServerInfo,
    agent_card_apikey: AgentCard,
    mock_key_manager,
    mocker,
    respx_mock
):
    """Test handling of error during SSE stream processing."""
    task_id = "existing-task-sse-err"
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING}
    mock_a2a_server.sse_event_store[task_id] = []

    error_message = "Simulated connection error during stream."
    error_to_raise = A2AConnectionError(error_message)

    # --- MODIFIED: Patch with an async generator function that raises ---
    async def mock_generator_that_raises(*args, **kwargs):
        # This generator immediately raises the exception when iterated
        raise error_to_raise
        if False: # Make it a generator type
             yield # pragma: no cover

    # --- MODIFIED: Patch the helper method directly ---
    mock_process_lines = mocker.patch(
        "agentvault.client.AgentVaultClient._process_sse_stream_lines",
        new=mock_generator_that_raises # Patch with the new async generator
    )
    # --- END MODIFIED ---

    # Fixture handles route setup

    received_events = []
    # --- MODIFIED: Correct assertion using pytest.raises and checking exception type/message ---
    # --- FIX: Expect A2AConnectionError directly now, as the cause should be preserved ---
    with pytest.raises(A2AConnectionError) as excinfo: # Expect the original error
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_apikey, task_id, mock_key_manager):
                received_events.append(event) # Should not be reached

    # Assert the exception is the expected type
    assert isinstance(excinfo.value, A2AConnectionError)
    # Assert the error message is correct
    assert error_message in str(excinfo.value)
    # --- END FIX ---

    assert len(received_events) == 0
    # --- MODIFIED: Remove assertion on mock_process_lines ---
    # mock_process_lines.assert_awaited_once() # Cannot assert await on the generator function itself
    # --- END MODIFIED ---
    assert respx_mock.calls.call_count == 1
