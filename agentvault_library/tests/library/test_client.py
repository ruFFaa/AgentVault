import pytest
import httpx
import respx
import json
import uuid
import datetime
import asyncio
# --- MODIFIED: Remove ANY import ---
from unittest.mock import MagicMock, call, patch # Removed ANY
# --- END MODIFIED ---


# Import client, models, exceptions, and KeyManager
from agentvault.client import AgentVaultClient, A2AEvent
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
import logging

# --- Fixtures ---
AGENT_URL = "https://fake-agent.example.com/a2a"
TEST_API_KEY = "test-key-123"
TEST_SERVICE_ID = "test-agent-service"
TEST_TASK_ID = "task-abc-123"
# OAuth Fixtures
TEST_OAUTH_SERVICE_ID = "oauth-service"
TEST_OAUTH_CLIENT_ID = "oauth-client-id-123"
TEST_OAUTH_CLIENT_SECRET = "oauth-client-secret-xyz"
TEST_OAUTH_TOKEN_URL = "https://auth.example.com/token"
TEST_OAUTH_ACCESS_TOKEN = "test-access-token-456"


@pytest.fixture
def agent_card_dict_fixture() -> dict:
    """ Provides dictionary data for a valid AgentCard. """
    return {
        "schemaVersion": "1.0",
        "humanReadableId": "test-org/test-client-agent",
        "agentVersion": "1.1.0",
        "name": "Client Test Agent",
        "description": "Agent for testing the client.",
        "url": AGENT_URL,
        "provider": {"name": "Test Suite Inc."},
        "capabilities": {"a2aVersion": "1.0"},
        "authSchemes": [{"scheme": "apiKey", "service_identifier": TEST_SERVICE_ID}]
    }

@pytest.fixture
def agent_card_fixture(agent_card_dict_fixture) -> AgentCard:
    """Provides a valid AgentCard instance from dictionary."""
    return AgentCard.model_validate(agent_card_dict_fixture)

@pytest.fixture
def agent_card_no_auth_fixture() -> AgentCard:
    return AgentCard(
        schemaVersion="1.0", humanReadableId="test-org/no-auth-agent", agentVersion="1.0.0",
        name="No Auth Test Agent", description="Agent for testing no auth.", url=AGENT_URL + "/noauth",
        provider=AgentProvider(name="Test Suite Inc."), capabilities=AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[AgentAuthentication(scheme="none")]
    )

@pytest.fixture
def agent_card_oauth2_fixture() -> AgentCard:
    """Provides an AgentCard instance supporting only OAuth2."""
    card_data = {
        "schemaVersion":"1.0", "humanReadableId":"test-org/oauth2-agent", "agentVersion":"1.0.0",
        "name":"OAuth2 Test Agent", "description":"Agent for testing oauth2 auth.", "url":AGENT_URL + "/oauth",
        "provider":{"name": "Test Suite Inc."}, "capabilities":{"a2aVersion":"1.0"},
        "authSchemes":[{"scheme":"oauth2", "tokenUrl":TEST_OAUTH_TOKEN_URL, "scopes":["tasks:read"], "service_identifier": TEST_OAUTH_SERVICE_ID}]
    }
    return AgentCard.model_validate(card_data)


@pytest.fixture
def mock_key_manager(mocker) -> MagicMock:
    mock_km = MagicMock(spec=KeyManager)
    mock_km.get_key.return_value = TEST_API_KEY
    mock_km.get_oauth_client_id.return_value = None
    mock_km.get_oauth_client_secret.return_value = None
    return mock_km

@pytest.fixture
def sample_message() -> Message:
    return Message(role="user", parts=[TextPart(content="Hello Agent")])

@pytest.fixture
def sample_task_data() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    # Use WORKING state as per Task 2.C.1
    return {"id": TEST_TASK_ID, "state": "WORKING", "createdAt": now.isoformat(), "updatedAt": now.isoformat(), "messages": [{"role": "user", "parts": [{"type": "text", "content": "Hello"}]}, {"role": "assistant", "parts": [{"type": "text", "content": "Hi"}]}], "artifacts": [], "metadata": {}}

# --- Test Init and Context Manager ---
@pytest.mark.asyncio
async def test_client_init_internal_client():
    client = AgentVaultClient()
    assert isinstance(client._http_client, httpx.AsyncClient)
    assert client._should_close_client is True
    await client.close()
    assert client._http_client.is_closed

@pytest.mark.asyncio
async def test_client_init_external_client():
    external_http_client = httpx.AsyncClient()
    client = AgentVaultClient(http_client=external_http_client)
    assert client._http_client is external_http_client
    assert client._should_close_client is False
    await client.close()
    assert not external_http_client.is_closed
    await external_http_client.aclose()

@pytest.mark.asyncio
async def test_client_context_manager():
    async with AgentVaultClient() as client:
        assert isinstance(client._http_client, httpx.AsyncClient)
        assert client._should_close_client is True
        internal_client = client._http_client
    assert internal_client.is_closed

@pytest.mark.asyncio
async def test_client_context_manager_external():
    external_http_client = httpx.AsyncClient()
    async with AgentVaultClient(http_client=external_http_client) as client:
        assert client._http_client is external_http_client
        assert client._should_close_client is False
    assert not external_http_client.is_closed
    await external_http_client.aclose()

# --- Test _get_auth_headers ---
@pytest.mark.asyncio
async def test_get_auth_headers_apikey_success(agent_card_fixture, mock_key_manager):
    client = AgentVaultClient()
    headers = await client._get_auth_headers(agent_card_fixture, mock_key_manager)
    assert headers == {"X-Api-Key": TEST_API_KEY}
    mock_key_manager.get_key.assert_called_once_with(TEST_SERVICE_ID)

@pytest.mark.asyncio
async def test_get_auth_headers_none_success(agent_card_no_auth_fixture, mock_key_manager):
    client = AgentVaultClient()
    headers = await client._get_auth_headers(agent_card_no_auth_fixture, mock_key_manager)
    assert headers == {}
    mock_key_manager.get_key.assert_not_called()

@pytest.mark.asyncio
async def test_get_auth_headers_key_missing(agent_card_fixture, mock_key_manager):
    mock_key_manager.get_key.return_value = None
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match=f"Missing API key for service '{TEST_SERVICE_ID}'"):
        await client._get_auth_headers(agent_card_fixture, mock_key_manager)

@pytest.mark.asyncio
async def test_get_auth_headers_no_supported_scheme(agent_card_dict_fixture, mock_key_manager):
    unsupported_data = agent_card_dict_fixture.copy()
    unsupported_data["authSchemes"] = [{"scheme": "bearer"}] # Use bearer as unsupported example
    unsupported_card = AgentCard.model_validate(unsupported_data)
    client = AgentVaultClient()
    assert [s.scheme for s in unsupported_card.auth_schemes] == ["bearer"]
    with pytest.raises(A2AAuthenticationError, match="No compatible authentication scheme found"):
        await client._get_auth_headers(unsupported_card, mock_key_manager)

# --- Tests for OAuth2 Flow in _get_auth_headers ---
@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_success(agent_card_oauth2_fixture, mock_key_manager):
    """Test successful OAuth2 token retrieval."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET

    # Mock the token endpoint
    respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={
            "access_token": TEST_OAUTH_ACCESS_TOKEN,
            "token_type": "Bearer",
            "expires_in": 3600
        })
    )

    client = AgentVaultClient()
    headers = await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

    assert headers == {"Authorization": f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"}
    mock_key_manager.get_oauth_client_id.assert_called_once_with(TEST_OAUTH_SERVICE_ID)
    mock_key_manager.get_oauth_client_secret.assert_called_once_with(TEST_OAUTH_SERVICE_ID)
    # Check token request payload
    token_request = respx.calls[0].request
    assert token_request.headers["content-type"] == "application/x-www-form-urlencoded"
    # httpx encodes form data, need to decode for assertion
    content = token_request.content.decode()
    assert f"client_id={TEST_OAUTH_CLIENT_ID}" in content
    assert f"client_secret={TEST_OAUTH_CLIENT_SECRET}" in content
    assert "grant_type=client_credentials" in content
    assert "scope=tasks%3Aread" in content # Check scopes are included and url-encoded


@pytest.mark.asyncio
async def test_get_auth_headers_oauth2_missing_creds(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when KeyManager doesn't have OAuth creds."""
    mock_key_manager.get_oauth_client_id.return_value = None # Simulate missing ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match=f"Missing OAuth Client ID or Client Secret for service '{TEST_OAUTH_SERVICE_ID}'"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_401(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when token endpoint returns 401."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = "wrong_secret"
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Invalid credentials or request"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_500(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when token endpoint returns 500."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(500, text="Server Error"))

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Token endpoint .* returned server error"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_connect_error(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when token endpoint connection fails."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(side_effect=httpx.ConnectError("Connection refused"))

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Could not connect to token endpoint"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_timeout(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when token endpoint times out."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(side_effect=httpx.TimeoutException("Timeout"))

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Timeout connecting to token endpoint"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_invalid_json(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when token endpoint returns invalid JSON."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(200, text="{not json"))

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Invalid JSON response from token endpoint"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_missing_token(agent_card_oauth2_fixture, mock_key_manager):
    """Test failure when token endpoint response misses access_token."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json={"token_type": "Bearer"}))

    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Invalid token response.*missing 'access_token'"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)


# --- Test initiate_task ---
@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_success(agent_card_fixture, mock_key_manager, sample_message):
    expected_task_id = f"task-{uuid.uuid4()}"
    mock_response = {"jsonrpc": "2.0", "result": {"id": expected_task_id}, "id": "req-init-static"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        task_id = await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)
    assert task_id == expected_task_id
    assert route.called
    request = route.calls[0].request; assert request.headers["x-api-key"] == TEST_API_KEY
    payload = json.loads(request.content); assert payload["method"] == "tasks/send"; assert "id" not in payload["params"]

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_with_mcp(agent_card_fixture, mock_key_manager, sample_message):
    mcp_data_structured = {"items": {"user_prefs": {"content": {"user_preference": "verbose"}}}}
    mock_response = {"jsonrpc": "2.0", "result": {"id": "task-mcp"}, "id": "req-init-mcp"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, mcp_context=mcp_data_structured)
    assert route.called; payload = json.loads(route.calls[0].request.content)
    assert payload["params"]["message"]["metadata"]["mcp_context"] == mcp_data_structured

@pytest.mark.asyncio
async def test_initiate_task_auth_error(agent_card_fixture, mock_key_manager, sample_message):
    mock_key_manager.get_key.return_value = None
    async with AgentVaultClient() as client:
        with pytest.raises(A2AAuthenticationError):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)

@pytest.mark.asyncio
@respx.mock # Keep respx mock for token endpoint
async def test_initiate_task_oauth_success(agent_card_oauth2_fixture, mock_key_manager, sample_message):
    """Test initiate_task succeeds using OAuth2."""
    # Setup KeyManager mock for OAuth
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET

    # Mock Token Endpoint
    respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": TEST_OAUTH_ACCESS_TOKEN, "token_type": "Bearer"})
    )

    # Mock A2A Endpoint
    expected_task_id = f"task-oauth-{uuid.uuid4()}"
    # --- FIX: Use JSON serializable value for ID ---
    mock_a2a_response = {"jsonrpc": "2.0", "result": {"id": expected_task_id}, "id": "mock-req-id"}
    # --- END FIX ---
    agent_url_str = str(agent_card_oauth2_fixture.url)
    route_a2a = respx.post(agent_url_str).mock(return_value=httpx.Response(200, json=mock_a2a_response))

    async with AgentVaultClient() as client:
        task_id = await client.initiate_task(agent_card_oauth2_fixture, sample_message, mock_key_manager)

    assert task_id == expected_task_id
    assert route_a2a.called
    # Check A2A request has Bearer token
    a2a_request = route_a2a.calls[0].request
    assert a2a_request.headers["authorization"] == f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"


@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_remote_error(agent_card_fixture, mock_key_manager, sample_message):
    error_response = {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Agent failed", "data": {"details": "..."}}, "id": "req-init-error"}
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=error_response))
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError) as excinfo:
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)
    assert "Agent failed" in str(excinfo.value); assert excinfo.value.status_code == -32000; assert excinfo.value.response_body == {"details": "..."}

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_invalid_response_json(agent_card_fixture, mock_key_manager, sample_message):
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, text="{not json"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AMessageError, match="Failed to decode JSON response"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_invalid_response_structure(agent_card_fixture, mock_key_manager, sample_message):
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json={"jsonrpc": "2.0", "result": {}, "id": "req-init-struct-err"}))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AMessageError, match="Failed to validate task initiation result structure"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_connection_error(agent_card_fixture, mock_key_manager, sample_message):
    respx.post(AGENT_URL).mock(side_effect=httpx.ConnectError("Failed to connect"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AConnectionError, match="Connection failed"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_timeout_error(agent_card_fixture, mock_key_manager, sample_message):
    respx.post(AGENT_URL).mock(side_effect=httpx.TimeoutException("Request timed out"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2ATimeoutError, match="Request timed out"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)

# --- Test send_message ---
@pytest.mark.asyncio
@respx.mock
async def test_send_message_success(agent_card_fixture, mock_key_manager, sample_message):
    mock_response = {"jsonrpc": "2.0", "result": {"id": TEST_TASK_ID}, "id": "req-send-static"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        success = await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)
    assert success is True
    assert route.called; request = route.calls[0].request; assert request.headers["x-api-key"] == TEST_API_KEY
    payload = json.loads(request.content); assert payload["method"] == "tasks/send"; assert payload["params"]["id"] == TEST_TASK_ID

@pytest.mark.asyncio
@respx.mock
async def test_send_message_remote_error(agent_card_fixture, mock_key_manager, sample_message):
    error_response = {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Task invalid"}, "id": "req-send-err"}
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=error_response))
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError, match="Task invalid"):
            await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)

@pytest.mark.asyncio
async def test_send_message_unexpected_error(agent_card_fixture, mock_key_manager, sample_message, mocker):
    mocker.patch.object(AgentVaultClient, "_make_request", side_effect=ValueError("Something broke"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AError, match="An unexpected error occurred sending message: Something broke"):
            await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)

# --- Test get_task_status ---
@pytest.mark.asyncio
@respx.mock
async def test_get_task_status_success(agent_card_fixture, mock_key_manager, sample_task_data):
    mock_response = {"jsonrpc": "2.0", "result": sample_task_data, "id": "req-get-static"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        task = await client.get_task_status(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
    assert isinstance(task, Task); assert task.id == TEST_TASK_ID; assert task.state == TaskState.WORKING
    assert route.called; request = route.calls[0].request; payload = json.loads(request.content)
    assert payload["method"] == "tasks/get"; assert payload["params"]["id"] == TEST_TASK_ID

@pytest.mark.asyncio
@respx.mock
async def test_get_task_status_remote_error(agent_card_fixture, mock_key_manager):
    error_response = {"jsonrpc": "2.0", "error": {"code": -32002, "message": "Task not found"}, "id": "req-get-err"}
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=error_response))
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError, match="Task not found"):
            await client.get_task_status(agent_card_fixture, "invalid-task-id", mock_key_manager)

# --- Test terminate_task ---
@pytest.mark.asyncio
@respx.mock
async def test_terminate_task_success(agent_card_fixture, mock_key_manager):
    mock_response = {"jsonrpc": "2.0", "result": {"success": True}, "id": "req-cancel-static"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        success = await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
    assert success is True
    assert route.called; request = route.calls[0].request; payload = json.loads(request.content)
    assert payload["method"] == "tasks/cancel"; assert payload["params"]["id"] == TEST_TASK_ID

@pytest.mark.asyncio
@respx.mock
async def test_terminate_task_remote_error(agent_card_fixture, mock_key_manager):
    error_response = {"jsonrpc": "2.0", "error": {"code": -32003, "message": "Cannot cancel"}, "id": "req-cancel-err"}
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=error_response))
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError, match="Cannot cancel"):
            await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)

@pytest.mark.asyncio
async def test_terminate_task_unexpected_error(agent_card_fixture, mock_key_manager, mocker):
    mocker.patch.object(AgentVaultClient, "_make_request", side_effect=TypeError("Something else broke"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AError, match="An unexpected error occurred terminating task:"):
             await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)

# --- Test receive_messages ---
async def mock_sse_stream(*lines: str):
    for line in lines: yield line.encode('utf-8'); await asyncio.sleep(0.01) # Added small delay
    yield b'\n'


@pytest.mark.asyncio
@respx.mock
async def test_receive_messages_success(agent_card_fixture, mock_key_manager, mocker):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sse_lines = [f"event: task_status\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'state': 'WORKING', 'timestamp': now_iso})}\n\n", f"data: {json.dumps({'taskId': TEST_TASK_ID, 'message': {'role': 'assistant', 'parts': [{'type': 'text', 'content': 'Working...'}]}, 'timestamp': now_iso})}\n\n", f"event: task_artifact\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'artifact': {'id': 'art-1', 'type': 'log', 'content': 'Step 1 done'}, 'timestamp': now_iso})}\n\n", ": comment\n", f"event: task_status\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'state': 'COMPLETED', 'timestamp': now_iso})}\n\n"]
    mock_stream_gen = mock_sse_stream(*sse_lines)
    async def mock_make_request_side_effect(*args, **kwargs):
        if kwargs.get("stream") is True: return mock_stream_gen
        raise ValueError("Mock _make_request only configured for stream=True in this test")
    mocker.patch.object(AgentVaultClient, "_make_request", side_effect=mock_make_request_side_effect)
    received_events = []
    async with AgentVaultClient() as client:
        async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
            received_events.append(event)
    assert len(received_events) == 4
    assert isinstance(received_events[0], TaskStatusUpdateEvent); assert received_events[0].state == TaskState.WORKING
    assert isinstance(received_events[1], TaskMessageEvent); assert received_events[1].message.role == "assistant"
    assert isinstance(received_events[2], TaskArtifactUpdateEvent); assert received_events[2].artifact.id == "art-1"
    assert isinstance(received_events[3], TaskStatusUpdateEvent); assert received_events[3].state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_receive_messages_invalid_json(agent_card_fixture, mock_key_manager, mocker, caplog):
    sse_lines = ["event: task_status\ndata: {invalid json\n\n", f"event: task_message\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'message': {'role': 'assistant', 'parts': [{'type': 'text', 'content': 'OK'}]}, 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()})}\n\n"]
    mock_stream_gen = mock_sse_stream(*sse_lines)
    async def mock_make_request_side_effect(*args, **kwargs): return mock_stream_gen
    mocker.patch.object(AgentVaultClient, "_make_request", side_effect=mock_make_request_side_effect)
    received_events = []
    with caplog.at_level(logging.ERROR): # Check logs from _process_sse_stream
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                received_events.append(event)
    assert len(received_events) == 1 # Should yield the valid event
    assert isinstance(received_events[0], TaskMessageEvent)
    assert "Failed to decode JSON data for SSE event type 'task_status'" in caplog.text

@pytest.mark.asyncio
async def test_receive_messages_validation_error(agent_card_fixture, mock_key_manager, mocker, caplog):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sse_lines = [f"event: task_status\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'state': 'INVALID_STATE', 'timestamp': now_iso})}\n\n", f"event: task_message\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'message': {'role': 'assistant', 'parts': [{'type': 'text', 'content': 'OK'}]}, 'timestamp': now_iso})}\n\n"]
    mock_stream_gen = mock_sse_stream(*sse_lines)
    async def mock_make_request_side_effect(*args, **kwargs): return mock_stream_gen
    mocker.patch.object(AgentVaultClient, "_make_request", side_effect=mock_make_request_side_effect)
    received_events = []
    with caplog.at_level(logging.ERROR):
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                received_events.append(event)
    assert len(received_events) == 1 # Should yield the valid event
    assert isinstance(received_events[0], TaskMessageEvent)
    assert "Failed to validate SSE event type 'task_status'" in caplog.text

@pytest.mark.asyncio
async def test_receive_messages_unknown_event(agent_card_fixture, mock_key_manager, mocker, caplog):
    sse_lines = ["event: unknown_event_type\ndata: {}\n\n"]
    mock_stream_gen = mock_sse_stream(*sse_lines)
    async def mock_make_request_side_effect(*args, **kwargs): return mock_stream_gen
    mocker.patch.object(AgentVaultClient, "_make_request", side_effect=mock_make_request_side_effect)
    received_events = []
    with caplog.at_level(logging.WARNING):
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                received_events.append(event)
    assert len(received_events) == 0
    assert "Received unknown SSE event type: 'unknown_event_type'" in caplog.text

@pytest.mark.asyncio
async def test_receive_messages_stream_error(agent_card_fixture, mock_key_manager, mocker):
    async def error_stream(*args, **kwargs): # Mock for _stream_request
        yield b"some initial data"
        raise ConnectionAbortedError("Stream broken") # Simulate non-httpx error during streaming
    mocker.patch.object(AgentVaultClient, "_stream_request", side_effect=error_stream) # Patch the correct helper

    with pytest.raises(A2AConnectionError, match="Unexpected error processing SSE stream: Stream broken"):
         async with AgentVaultClient() as client:
             async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                 pass # pragma: no cover

#
