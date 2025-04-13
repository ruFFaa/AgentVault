import pytest
import httpx
import respx
import json
import uuid
import datetime
import asyncio
import time
# --- MODIFIED: Import Union and Tuple ---
from unittest.mock import MagicMock, call, patch, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple # Added Tuple
# --- END MODIFIED ---

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
TEST_OAUTH_ACCESS_TOKEN_2 = "test-access-token-789-new"


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

# --- MODIFIED: Enhanced Mock A2A Router Function ---
def mock_a2a_router(
    request: httpx.Request,
    *,
    task_data_fixture: dict,
    custom_responses: Optional[Dict[str, Union[httpx.Response, Dict[str, Any]]]] = None,
    expected_auth_header: Optional[Tuple[str, str]] = None,
    simulate_error: Optional[Exception] = None,
    simulate_status_code: Optional[int] = None
) -> httpx.Response:
    """
    A side_effect function for respx to simulate JSON-RPC routing based on method.
    Allows overriding responses, checking auth, and simulating errors.
    """
    custom_responses = custom_responses or {}
    req_id_fallback = "unknown" # Default request ID if payload parsing fails

    # 1. Simulate immediate network/request errors
    if simulate_error:
        raise simulate_error

    # 2. Simulate specific HTTP status code errors
    if simulate_status_code:
        # Try to get request ID if possible for error response
        try: req_id_fallback = json.loads(request.content).get("id", "unknown")
        except: pass
        error_body = {"code": -32000, "message": f"Simulated HTTP {simulate_status_code} Error"}
        return httpx.Response(simulate_status_code, json={"jsonrpc": "2.0", "error": error_body, "id": req_id_fallback})

    # 3. Check Authentication Header
    if expected_auth_header:
        header_name, expected_value = expected_auth_header
        actual_value = request.headers.get(header_name.lower()) # Headers are case-insensitive
        if actual_value != expected_value:
            try: req_id_fallback = json.loads(request.content).get("id", "unknown")
            except: pass
            error = {"code": -32000, "message": "Unauthorized", "data": f"Expected header '{header_name}' not found or invalid"}
            return httpx.Response(401, json={"jsonrpc": "2.0", "error": error, "id": req_id_fallback})

    # 4. Proceed with JSON-RPC routing if no simulations/auth checks failed
    try:
        payload = json.loads(request.content)
        method = payload.get("method")
        params = payload.get("params", {})
        req_id = payload.get("id", "unknown")

        # Check for custom response override for this method
        if method in custom_responses:
            custom_resp = custom_responses[method]
            if isinstance(custom_resp, httpx.Response):
                return custom_resp
            elif isinstance(custom_resp, dict): # Assume it's an error dict
                return httpx.Response(200, json={"jsonrpc": "2.0", "error": custom_resp, "id": req_id})
            else: # Fallback for unexpected custom response type
                error = {"code": -32000, "message": f"Invalid custom_response type for method {method}"}
                return httpx.Response(500, json={"jsonrpc": "2.0", "error": error, "id": req_id})

        # Default routing logic
        if method == "tasks/send":
            task_id = params.get("id") or f"task-{uuid.uuid4()}" # Generate ID if initiating
            result = {"id": task_id}
            return httpx.Response(200, json={"jsonrpc": "2.0", "result": result, "id": req_id})

        elif method == "tasks/get":
            task_id = params.get("id")
            if task_id == TEST_TASK_ID: # Use the ID from the fixture
                return httpx.Response(200, json={"jsonrpc": "2.0", "result": task_data_fixture, "id": req_id})
            else:
                error = {"code": -32002, "message": "Task not found"}
                return httpx.Response(200, json={"jsonrpc": "2.0", "error": error, "id": req_id})

        elif method == "tasks/cancel":
            result = {"success": True}
            return httpx.Response(200, json={"jsonrpc": "2.0", "result": result, "id": req_id})

        elif method == "tasks/sendSubscribe":
             return httpx.Response(200, json={"jsonrpc": "2.0", "result": {"subscribed": True}, "id": req_id})

        else:
            # Unknown method
            error = {"code": -32601, "message": "Method not found"}
            return httpx.Response(200, json={"jsonrpc": "2.0", "error": error, "id": req_id}) # Return 200 OK with JSON-RPC error

    except json.JSONDecodeError:
        return httpx.Response(400, text="Invalid JSON payload")
    except Exception as e:
        # Catch-all for unexpected errors in the mock router
        error = {"code": -32000, "message": f"Mock server error: {e}"}
        req_id_fallback = payload.get("id", "unknown") if 'payload' in locals() else 'unknown'
        return httpx.Response(500, json={"jsonrpc": "2.0", "error": error, "id": req_id_fallback})

# --- END MODIFIED ---


# --- Test Init and Context Manager ---
# (Keep existing tests)
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
# (Keep existing tests - they don't use the A2A router)
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
# (Keep existing tests)
@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_success(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    token_route = respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={
            "access_token": TEST_OAUTH_ACCESS_TOKEN, "token_type": "Bearer", "expires_in": 3600
        })
    )
    client = AgentVaultClient()
    headers = await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)
    assert headers == {"Authorization": f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"}
    mock_key_manager.get_oauth_client_id.assert_called_once_with(TEST_OAUTH_SERVICE_ID)
    mock_key_manager.get_oauth_client_secret.assert_called_once_with(TEST_OAUTH_SERVICE_ID)
    assert token_route.called

@pytest.mark.asyncio
async def test_get_auth_headers_oauth2_missing_creds(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = None
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match=f"Missing OAuth Client ID or Client Secret for service '{TEST_OAUTH_SERVICE_ID}'"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_401(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = "wrong_secret"
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Invalid credentials or request.*HTTP 401"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_500(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(500, text="Server Error"))
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Token endpoint .* returned server error.*HTTP 500"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_connect_error(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Could not connect to token endpoint"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_timeout(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(side_effect=httpx.TimeoutException("Timeout"))
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Timeout connecting to token endpoint"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_invalid_json(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(200, text="{not json"))
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Invalid JSON response from token endpoint"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_token_endpoint_missing_token(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json={"token_type": "Bearer"}))
    client = AgentVaultClient()
    with pytest.raises(A2AAuthenticationError, match="Invalid token response.*missing 'access_token'"):
        await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)

# --- Tests for OAuth Token Caching ---
# (Keep existing tests)
@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_cache_hit(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    token_route = respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "should_not_use_this", "token_type": "Bearer"})
    )
    client = AgentVaultClient()
    valid_expiry = time.time() + 1000
    client._token_cache[TEST_OAUTH_SERVICE_ID] = (TEST_OAUTH_ACCESS_TOKEN, valid_expiry)
    headers = await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)
    assert headers == {"Authorization": f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"}
    assert not token_route.called
    mock_key_manager.get_oauth_client_id.assert_not_called()
    mock_key_manager.get_oauth_client_secret.assert_not_called()

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_cache_expired(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    token_route = respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={
            "access_token": TEST_OAUTH_ACCESS_TOKEN_2, "token_type": "Bearer", "expires_in": 3600
        })
    )
    client = AgentVaultClient()
    expired_expiry = time.time() - 1000
    client._token_cache[TEST_OAUTH_SERVICE_ID] = ("expired_token", expired_expiry)
    headers = await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)
    assert headers == {"Authorization": f"Bearer {TEST_OAUTH_ACCESS_TOKEN_2}"}
    assert token_route.called
    mock_key_manager.get_oauth_client_id.assert_called_once_with(TEST_OAUTH_SERVICE_ID)
    mock_key_manager.get_oauth_client_secret.assert_called_once_with(TEST_OAUTH_SERVICE_ID)
    assert client._token_cache[TEST_OAUTH_SERVICE_ID][0] == TEST_OAUTH_ACCESS_TOKEN_2
    assert client._token_cache[TEST_OAUTH_SERVICE_ID][1] > time.time()

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_cache_no_expiry(agent_card_oauth2_fixture, mock_key_manager):
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    token_route = respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={
            "access_token": TEST_OAUTH_ACCESS_TOKEN, "token_type": "Bearer"
        })
    )
    client = AgentVaultClient()
    headers1 = await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)
    assert headers1 == {"Authorization": f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"}
    assert token_route.call_count == 1
    assert client._token_cache[TEST_OAUTH_SERVICE_ID] == (TEST_OAUTH_ACCESS_TOKEN, None)
    headers2 = await client._get_auth_headers(agent_card_oauth2_fixture, mock_key_manager)
    assert headers2 == {"Authorization": f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"}
    assert token_route.call_count == 1

@pytest.mark.asyncio
@respx.mock
async def test_get_auth_headers_oauth2_cache_different_services(agent_card_oauth2_fixture, mock_key_manager):
    service_id_1 = "service_one"
    service_id_2 = "service_two"
    token_1 = "token_for_1"
    token_2 = "token_for_2"
    card1_data = agent_card_oauth2_fixture.model_dump(by_alias=True)
    card1_data["authSchemes"][0]["service_identifier"] = service_id_1
    card1 = AgentCard.model_validate(card1_data)
    card2_data = agent_card_oauth2_fixture.model_dump(by_alias=True)
    card2_data["authSchemes"][0]["service_identifier"] = service_id_2
    card2 = AgentCard.model_validate(card2_data)
    def mock_get_id(sid):
        if sid == service_id_1: return f"id_for_{service_id_1}"
        if sid == service_id_2: return f"id_for_{service_id_2}"
        return None
    def mock_get_secret(sid):
        if sid == service_id_1: return f"secret_for_{service_id_1}"
        if sid == service_id_2: return f"secret_for_{service_id_2}"
        return None
    mock_key_manager.get_oauth_client_id.side_effect = mock_get_id
    mock_key_manager.get_oauth_client_secret.side_effect = mock_get_secret
    def token_response(request):
        content = request.content.decode()
        payload = dict(item.split("=") for item in content.split("&"))
        if payload.get("client_id") == f"id_for_{service_id_1}":
            return httpx.Response(200, json={"access_token": token_1, "token_type": "Bearer"})
        elif payload.get("client_id") == f"id_for_{service_id_2}":
            return httpx.Response(200, json={"access_token": token_2, "token_type": "Bearer"})
        else:
            return httpx.Response(401, json={"error": "mock_invalid_client"})
    token_route = respx.post(TEST_OAUTH_TOKEN_URL).mock(side_effect=token_response)
    client = AgentVaultClient()
    headers1 = await client._get_auth_headers(card1, mock_key_manager)
    assert headers1 == {"Authorization": f"Bearer {token_1}"}
    assert token_route.call_count == 1
    assert client._token_cache[service_id_1] == (token_1, None)
    assert service_id_2 not in client._token_cache
    headers2 = await client._get_auth_headers(card2, mock_key_manager)
    assert headers2 == {"Authorization": f"Bearer {token_2}"}
    assert token_route.call_count == 2
    assert client._token_cache[service_id_2] == (token_2, None)
    headers3 = await client._get_auth_headers(card1, mock_key_manager)
    assert headers3 == {"Authorization": f"Bearer {token_1}"}
    assert token_route.call_count == 2


# --- Test initiate_task ---
@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_success(agent_card_fixture, mock_key_manager, sample_message, sample_task_data):
    # --- MODIFIED: Use router with expected auth ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        task_id = await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)
    assert isinstance(task_id, str)
    assert route.called
    request = route.calls[0].request; assert request.headers["x-api-key"] == TEST_API_KEY
    payload = json.loads(request.content); assert payload["method"] == "tasks/send"; assert "id" not in payload["params"]

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_with_mcp(agent_card_fixture, mock_key_manager, sample_message, sample_task_data):
    mcp_data_structured = {"items": {"user_prefs": {"content": {"user_preference": "verbose"}}}}
    # --- MODIFIED: Use router ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, mcp_context=mcp_data_structured, webhook_url=None)
    assert route.called; payload = json.loads(route.calls[0].request.content)
    assert payload["params"]["message"]["metadata"]["mcp_context"] == mcp_data_structured

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_with_webhook_url(agent_card_fixture, mock_key_manager, sample_message, sample_task_data):
    """Test that webhookUrl is included in the request params when provided."""
    webhook_url = "https://my.callback.example.com/notify"
    # --- MODIFIED: Use router ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---

    async with AgentVaultClient() as client:
        task_id = await client.initiate_task(
            agent_card_fixture, sample_message, mock_key_manager, webhook_url=webhook_url
        )

    assert isinstance(task_id, str)
    assert route.called
    request = route.calls[0].request
    payload = json.loads(request.content)
    assert payload["method"] == "tasks/send"
    assert payload["params"]["webhookUrl"] == webhook_url
    assert payload["params"]["message"]["role"] == "user" # Ensure message is still there

@pytest.mark.asyncio
async def test_initiate_task_auth_error(agent_card_fixture, mock_key_manager, sample_message):
    # This test checks logic *before* the request, so no respx needed
    mock_key_manager.get_key.return_value = None
    async with AgentVaultClient() as client:
        with pytest.raises(A2AAuthenticationError):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)

@pytest.mark.asyncio
@respx.mock # Keep respx mock for token endpoint
async def test_initiate_task_oauth_success(agent_card_oauth2_fixture, mock_key_manager, sample_message, sample_task_data):
    """Test initiate_task succeeds using OAuth2."""
    mock_key_manager.get_oauth_client_id.return_value = TEST_OAUTH_CLIENT_ID
    mock_key_manager.get_oauth_client_secret.return_value = TEST_OAUTH_CLIENT_SECRET
    respx.post(TEST_OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": TEST_OAUTH_ACCESS_TOKEN, "token_type": "Bearer"})
    )
    agent_url_str = str(agent_card_oauth2_fixture.url)
    # --- MODIFIED: Use router with expected auth ---
    expected_auth = ("authorization", f"Bearer {TEST_OAUTH_ACCESS_TOKEN}")
    route_a2a = respx.post(agent_url_str).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        task_id = await client.initiate_task(agent_card_oauth2_fixture, sample_message, mock_key_manager, webhook_url=None)
    assert isinstance(task_id, str)
    assert route_a2a.called
    a2a_request = route_a2a.calls[0].request
    assert a2a_request.headers["authorization"] == f"Bearer {TEST_OAUTH_ACCESS_TOKEN}"


@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_remote_error(agent_card_fixture, mock_key_manager, sample_message):
    error_code = -32000
    error_message = "Agent failed"
    error_data = {"details": "..."}
    custom_error_response = {"code": error_code, "message": error_message, "data": error_data}
    # --- MODIFIED: Use router with custom error ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/send": custom_error_response}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError) as excinfo:
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)
    assert error_message in str(excinfo.value)
    assert excinfo.value.status_code == error_code
    assert excinfo.value.response_body == error_data

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_invalid_response_json(agent_card_fixture, mock_key_manager, sample_message):
    # --- MODIFIED: Use router with custom response ---
    invalid_resp = httpx.Response(200, text="{not json")
    expected_auth = ("x-api-key", TEST_API_KEY)
    respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/send": invalid_resp}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2AMessageError, match="Failed to decode JSON response"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_invalid_response_structure(agent_card_fixture, mock_key_manager, sample_message):
    # --- MODIFIED: Use router with custom response ---
    invalid_resp = httpx.Response(200, json={"jsonrpc": "2.0", "id": "req-init-struct-err"}) # No result or error
    expected_auth = ("x-api-key", TEST_API_KEY)
    respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/send": invalid_resp}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2AMessageError, match="Invalid JSON-RPC response.*Missing 'result' or 'error' key"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_invalid_result_structure(agent_card_fixture, mock_key_manager, sample_message):
    # --- MODIFIED: Use router with custom response ---
    invalid_resp = httpx.Response(200, json={"jsonrpc": "2.0", "result": {"wrong_field": "abc"}, "id": "req-init-struct-err"})
    expected_auth = ("x-api-key", TEST_API_KEY)
    respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/send": invalid_resp}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2AMessageError, match="Failed to validate task initiation result structure"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)


@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_connection_error(agent_card_fixture, mock_key_manager, sample_message):
    # --- MODIFIED: Use router to simulate error ---
    sim_error = httpx.ConnectError("Failed to connect")
    respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, simulate_error=sim_error))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2AConnectionError, match="Connection failed"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)

@pytest.mark.asyncio
@respx.mock
async def test_initiate_task_timeout_error(agent_card_fixture, mock_key_manager, sample_message):
    # --- MODIFIED: Use router to simulate error ---
    sim_error = httpx.TimeoutException("Request timed out")
    respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, simulate_error=sim_error))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2ATimeoutError, match="Request timed out"):
            await client.initiate_task(agent_card_fixture, sample_message, mock_key_manager, webhook_url=None)

# --- Test send_message ---
@pytest.mark.asyncio
@respx.mock
async def test_send_message_success(agent_card_fixture, mock_key_manager, sample_message, sample_task_data):
    # --- MODIFIED: Use router with expected auth ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        success = await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)
    assert success is True
    assert route.called; request = route.calls[0].request; assert request.headers["x-api-key"] == TEST_API_KEY
    payload = json.loads(request.content); assert payload["method"] == "tasks/send"; assert payload["params"]["id"] == TEST_TASK_ID

@pytest.mark.asyncio
@respx.mock
async def test_send_message_remote_error(agent_card_fixture, mock_key_manager, sample_message):
    # --- MODIFIED: Use router configured to return error ---
    error_response = {"code": -32001, "message": "Task invalid"}
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/send": error_response}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError, match="Task invalid"):
            await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)

# --- MODIFIED: Remove mocker patch, error happens before request ---
@pytest.mark.asyncio
async def test_send_message_unexpected_error(agent_card_fixture, mock_key_manager, sample_message, mocker):
    # Mocking _get_auth_headers to raise an unexpected error
    mocker.patch.object(AgentVaultClient, "_get_auth_headers", side_effect=ValueError("Something broke"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AError, match="An unexpected error occurred sending message: Something broke"):
            await client.send_message(agent_card_fixture, TEST_TASK_ID, sample_message, mock_key_manager)
# --- END MODIFIED ---

# --- Test get_task_status ---
@pytest.mark.asyncio
@respx.mock
async def test_get_task_status_success(agent_card_fixture, mock_key_manager, sample_task_data):
    # --- MODIFIED: Use router with expected auth ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        task = await client.get_task_status(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
    assert isinstance(task, Task); assert task.id == TEST_TASK_ID; assert task.state == TaskState.WORKING
    assert route.called; request = route.calls[0].request; payload = json.loads(request.content)
    assert payload["method"] == "tasks/get"; assert payload["params"]["id"] == TEST_TASK_ID

@pytest.mark.asyncio
@respx.mock
async def test_get_task_status_remote_error(agent_card_fixture, mock_key_manager):
    # --- MODIFIED: Use router configured to return error ---
    error_response = {"code": -32002, "message": "Task not found"}
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/get": error_response}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError, match="Task not found"):
            await client.get_task_status(agent_card_fixture, "invalid-task-id", mock_key_manager)

# --- Test terminate_task ---
@pytest.mark.asyncio
@respx.mock
async def test_terminate_task_success(agent_card_fixture, mock_key_manager, sample_task_data):
    # --- MODIFIED: Use router with expected auth ---
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture=sample_task_data, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        success = await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
    assert success is True
    assert route.called; request = route.calls[0].request; payload = json.loads(request.content)
    assert payload["method"] == "tasks/cancel"; assert payload["params"]["id"] == TEST_TASK_ID

@pytest.mark.asyncio
@respx.mock
async def test_terminate_task_remote_error(agent_card_fixture, mock_key_manager):
    # --- MODIFIED: Use router configured to return error ---
    error_response = {"code": -32003, "message": "Cannot cancel"}
    expected_auth = ("x-api-key", TEST_API_KEY)
    route = respx.post(AGENT_URL).mock(side_effect=lambda req: mock_a2a_router(req, task_data_fixture={}, custom_responses={"tasks/cancel": error_response}, expected_auth_header=expected_auth))
    # --- END MODIFIED ---
    async with AgentVaultClient() as client:
        with pytest.raises(A2ARemoteAgentError, match="Cannot cancel"):
            await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)

# --- MODIFIED: Remove mocker patch, error happens before request ---
@pytest.mark.asyncio
async def test_terminate_task_unexpected_error(agent_card_fixture, mock_key_manager, mocker):
    # Mocking _get_auth_headers to raise an unexpected error
    mocker.patch.object(AgentVaultClient, "_get_auth_headers", side_effect=TypeError("Something else broke"))
    async with AgentVaultClient() as client:
        with pytest.raises(A2AError, match="An unexpected error occurred terminating task:"):
             await client.terminate_task(agent_card_fixture, TEST_TASK_ID, mock_key_manager)
# --- END MODIFIED ---

# --- Test receive_messages ---
# (Keep existing SSE tests as they mock _make_request at a higher level)
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
        # Handle non-stream POST for subscribe
        if kwargs.get("method") == "POST" and kwargs.get("json", {}).get("method") == "tasks/sendSubscribe":
             return {"subscribed": True} # Return simple success dict
        raise ValueError("Mock _make_request only configured for stream=True or subscribe POST in this test")
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
    async def mock_make_request_side_effect(*args, **kwargs):
        if kwargs.get("stream") is True: return mock_stream_gen
        if kwargs.get("method") == "POST" and kwargs.get("json", {}).get("method") == "tasks/sendSubscribe": return {"subscribed": True}
        raise ValueError("Mock _make_request misconfigured")
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
    async def mock_make_request_side_effect(*args, **kwargs):
        if kwargs.get("stream") is True: return mock_stream_gen
        if kwargs.get("method") == "POST" and kwargs.get("json", {}).get("method") == "tasks/sendSubscribe": return {"subscribed": True}
        raise ValueError("Mock _make_request misconfigured")
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
    async def mock_make_request_side_effect(*args, **kwargs):
        if kwargs.get("stream") is True: return mock_stream_gen
        if kwargs.get("method") == "POST" and kwargs.get("json", {}).get("method") == "tasks/sendSubscribe": return {"subscribed": True}
        raise ValueError("Mock _make_request misconfigured")
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
