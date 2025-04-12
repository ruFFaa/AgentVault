import pytest
import httpx
import respx
import json
import uuid
import datetime
import asyncio
from unittest.mock import MagicMock, ANY, patch

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
def mock_key_manager(mocker) -> MagicMock:
    mock_km = MagicMock(spec=KeyManager)
    mock_km.get_key.return_value = TEST_API_KEY
    return mock_km

@pytest.fixture
def sample_message() -> Message:
    return Message(role="user", parts=[TextPart(content="Hello Agent")])

@pytest.fixture
def sample_task_data() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"id": TEST_TASK_ID, "state": "RUNNING", "createdAt": now.isoformat(), "updatedAt": now.isoformat(), "messages": [{"role": "user", "parts": [{"type": "text", "content": "Hello"}]}, {"role": "assistant", "parts": [{"type": "text", "content": "Hi"}]}], "artifacts": [], "metadata": {}}

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
    # --- CORRECTED LINE BREAK ---
    async with AgentVaultClient(http_client=external_http_client) as client:
        assert client._http_client is external_http_client
        assert client._should_close_client is False
    assert not external_http_client.is_closed
    await external_http_client.aclose()

# --- Test _get_auth_headers ---
def test_get_auth_headers_apikey_success(agent_card_fixture, mock_key_manager):
    client = AgentVaultClient()
    headers = client._get_auth_headers(agent_card_fixture, mock_key_manager)
    assert headers == {"X-Api-Key": TEST_API_KEY}
    mock_key_manager.get_key.assert_called_once_with(TEST_SERVICE_ID)

def test_get_auth_headers_none_success(agent_card_no_auth_fixture, mock_key_manager):
    client = AgentVaultClient()
    headers = client._get_auth_headers(agent_card_no_auth_fixture, mock_key_manager)
    assert headers == {}
    mock_key_manager.get_key.assert_not_called()

def test_get_auth_headers_key_missing(agent_card_fixture, mock_key_manager):
    mock_key_manager.get_key.return_value = None
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match=f"Missing API key for service '{TEST_SERVICE_ID}'"):
        client._get_auth_headers(agent_card_fixture, mock_key_manager)

def test_get_auth_headers_no_supported_scheme(agent_card_dict_fixture, mock_key_manager):
    unsupported_data = agent_card_dict_fixture.copy()
    unsupported_data["authSchemes"] = [{"scheme": "oauth2"}]
    unsupported_card = AgentCard.model_validate(unsupported_data)
    client = AgentVaultClient()
    assert [s.scheme for s in unsupported_card.auth_schemes] == ["oauth2"]
    with pytest.raises(A2AAuthenticationError, match="No compatible authentication scheme found"):
        client._get_auth_headers(unsupported_card, mock_key_manager)

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
    request = route.calls[0].request
    assert request.headers["x-api-key"] == TEST_API_KEY
    payload = json.loads(request.content)
    assert payload["method"] == "tasks/send"
    assert "id" not in payload["params"]

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_with_mcp(agent_card_fixture, mock_key_manager, sample_message):
    mcp_data = {"user_preference": "verbose"}
    mock_response = {"jsonrpc": "2.0", "result": {"id": "task-mcp"}, "id": "req-init-mcp"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, mcp_context=mcp_data)
    assert route.called
    payload = json.loads(route.calls[0].request.content)
    assert payload["params"]["message"]["metadata"]["mcp_context"] == mcp_data

@pytest.mark.asyncio
async def test_initiate_task_auth_error(agent_card_fixture, mock_key_manager, sample_message):
    mock_key_manager.get_key.return_value = None
    async with AgentVaultClient() as client:
        with pytest.raises(A2AAuthenticationError):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_remote_error(agent_card_fixture, mock_key_manager, sample_message):
    error_response = {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Agent failed", "data": {"details": "..."}}, "id": "req-init-error"}
    respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=error_response))
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError) as excinfo:
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager)
    assert "Agent failed" in str(excinfo.value)
    assert excinfo.value.status_code == -32000
    assert excinfo.value.response_body == {"details": "..."}

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
        with pytest.raises(A2AMessageError, match="Failed to validate task initiation result"):
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
    assert route.called
    request = route.calls[0].request
    assert request.headers["x-api-key"] == TEST_API_KEY
    payload = json.loads(request.content)
    assert payload["method"] == "tasks/send"
    assert payload["params"]["id"] == TEST_TASK_ID

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
        success = await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)
    assert success is False

# --- Test get_task_status ---
@pytest.mark.asyncio
@respx.mock
async def test_get_task_status_success(agent_card_fixture, mock_key_manager, sample_task_data):
    mock_response = {"jsonrpc": "2.0", "result": sample_task_data, "id": "req-get-static"}
    route = respx.post(AGENT_URL).mock(return_value=httpx.Response(200, json=mock_response))
    async with AgentVaultClient() as client:
        task = await client.get_task_status(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
    assert isinstance(task, Task)
    assert task.id == TEST_TASK_ID
    assert task.state == TaskState.RUNNING
    assert route.called
    request = route.calls[0].request
    payload = json.loads(request.content)
    assert payload["method"] == "tasks/get"
    assert payload["params"]["id"] == TEST_TASK_ID

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
    assert route.called
    request = route.calls[0].request
    payload = json.loads(request.content)
    assert payload["method"] == "tasks/cancel"
    assert payload["params"]["id"] == TEST_TASK_ID

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
        success = await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
    assert success is False

# --- Test receive_messages ---
async def mock_sse_stream(*lines: str):
    for line in lines: yield line.encode('utf-8'); await asyncio.sleep(0)

@pytest.mark.asyncio
@respx.mock
async def test_receive_messages_success(agent_card_fixture, mock_key_manager, mocker):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sse_lines = [f"event: task_status\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'state': 'RUNNING', 'timestamp': now_iso})}\n\n", f"data: {json.dumps({'taskId': TEST_TASK_ID, 'message': {'role': 'assistant', 'parts': [{'type': 'text', 'content': 'Working...'}]}, 'timestamp': now_iso})}\n\n", f"event: task_artifact\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'artifact': {'id': 'art-1', 'type': 'log', 'content': 'Step 1 done'}, 'timestamp': now_iso})}\n\n", ": comment\n", f"event: task_status\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'state': 'COMPLETED', 'timestamp': now_iso})}\n\n"]
    mock_stream = mock_sse_stream(*sse_lines)
    mock_make_request = mocker.patch.object(AgentVaultClient, "_make_request", return_value=mock_stream)
    received_events = []
    async with AgentVaultClient() as client:
        async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
            received_events.append(event)
    assert len(received_events) == 4
    assert isinstance(received_events[0], TaskStatusUpdateEvent)
    assert received_events[0].state == TaskState.RUNNING
    assert isinstance(received_events[1], TaskMessageEvent)
    assert received_events[1].message.role == "assistant"
    assert isinstance(received_events[2], TaskArtifactUpdateEvent)
    assert received_events[2].artifact.id == "art-1"
    assert isinstance(received_events[3], TaskStatusUpdateEvent)
    assert received_events[3].state == TaskState.COMPLETED
    mock_make_request.assert_called_once()
    call_kwargs = mock_make_request.call_args[1]
    assert call_kwargs.get("stream") is True
    assert call_kwargs.get("json_payload", {}).get("method") == "tasks/sendSubscribe"

@pytest.mark.asyncio
async def test_receive_messages_invalid_json(agent_card_fixture, mock_key_manager, mocker, caplog):
    sse_lines = ["event: task_status\ndata: {invalid json\n\n", f"event: task_message\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'message': {'role': 'assistant', 'parts': [{'type': 'text', 'content': 'OK'}]}, 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()})}\n\n"]
    mock_stream = mock_sse_stream(*sse_lines)
    mocker.patch.object(AgentVaultClient, "_make_request", return_value=mock_stream)
    received_events = []
    with caplog.at_level(logging.ERROR):
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                received_events.append(event)
    assert len(received_events) == 1
    assert isinstance(received_events[0], TaskMessageEvent)
    assert "Failed to decode JSON data for SSE event type 'task_status'" in caplog.text

@pytest.mark.asyncio
async def test_receive_messages_validation_error(agent_card_fixture, mock_key_manager, mocker, caplog):
    sse_lines = [f"event: task_status\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'state': 'INVALID_STATE'})}\n\n", f"event: task_message\ndata: {json.dumps({'taskId': TEST_TASK_ID, 'message': {'role': 'assistant', 'parts': [{'type': 'text', 'content': 'OK'}]}, 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()})}\n\n"]
    mock_stream = mock_sse_stream(*sse_lines)
    mocker.patch.object(AgentVaultClient, "_make_request", return_value=mock_stream)
    received_events = []
    with caplog.at_level(logging.ERROR):
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                received_events.append(event)
    assert len(received_events) == 1
    assert isinstance(received_events[0], TaskMessageEvent)
    assert "Failed to validate SSE event type 'task_status'" in caplog.text

@pytest.mark.asyncio
async def test_receive_messages_unknown_event(agent_card_fixture, mock_key_manager, mocker, caplog):
    sse_lines = ["event: unknown_event_type\ndata: {}\n\n"]
    mock_stream = mock_sse_stream(*sse_lines)
    mocker.patch.object(AgentVaultClient, "_make_request", return_value=mock_stream)
    received_events = []
    with caplog.at_level(logging.WARNING):
        async with AgentVaultClient() as client:
            async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                received_events.append(event)
    assert len(received_events) == 0
    assert "Received unknown SSE event type: 'unknown_event_type'" in caplog.text

@pytest.mark.asyncio
async def test_receive_messages_stream_error(agent_card_fixture, mock_key_manager, mocker):
    async def error_stream():
        yield b"event: task_status\ndata: {}\n\n"
        raise ConnectionAbortedError("Stream broken")
    mocker.patch.object(AgentVaultClient, "_make_request", return_value=error_stream())
    with pytest.raises(A2AConnectionError, match="Error reading from SSE stream"):
         async with AgentVaultClient() as client:
             async for event in client.receive_messages(agent_card_fixture, TEST_TASK_ID, mock_key_manager):
                 pass # pragma: no cover

#
