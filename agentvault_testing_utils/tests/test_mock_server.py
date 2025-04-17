import pytest
import httpx
import uuid
import datetime
import json
# --- ADDED: Import respx ---
import respx
# --- END ADDED ---
# --- ADDED: Import status ---
from http import HTTPStatus
# --- END ADDED ---
# --- ADDED: Import logging ---
import logging
# --- END ADDED ---
from typing import List, Any, Dict # Added Dict, Any

# Import fixture and helpers
from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
from agentvault_testing_utils.mock_server import (
    create_jsonrpc_success_response, create_jsonrpc_error_response,
    JSONRPC_TASK_NOT_FOUND, JSONRPC_METHOD_NOT_FOUND,
    # --- ADDED: Import setup function ---
    setup_mock_a2a_routes, create_default_mock_task, DEFAULT_OAUTH_TOKEN_RESPONSE
    # --- END ADDED ---
)

# Import core types for creating test data
try:
    from agentvault.models import TaskState, TaskStatusUpdateEvent, A2AEvent # Added A2AEvent
    _MODELS_AVAILABLE = True
except ImportError:
    class TaskState: # type: ignore
        SUBMITTED = "SUBMITTED"; WORKING = "WORKING"; COMPLETED = "COMPLETED"; CANCELED = "CANCELED" # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    A2AEvent = Any # type: ignore
    _MODELS_AVAILABLE = False

# --- ADDED: Logger ---
logger = logging.getLogger(__name__)
# --- END ADDED ---

# Use the mock_a2a_server fixture implicitly for other tests

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use both fixtures ---
@pytest.mark.respx(using="httpx")
async def test_mock_tasks_send_adds_to_store(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/send adds task ID to the store."""
    test_id = "req-send-1"
    params = {"message": {"role": "user", "parts": [{"type": "text", "content": "test"}]}}
    payload = {"jsonrpc": "2.0", "method": "tasks/send", "params": params, "id": test_id}
    a2a_url = f"{mock_a2a_server.base_url}/a2a"

    # --- MODIFIED: Setup routes inside test using fixture data ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        response = await client.post(a2a_url, json=payload)
    # --- END MODIFIED ---

    assert response.status_code == HTTPStatus.OK # Use constant
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    # --- MODIFIED: Correct assertion ---
    assert "result" in resp_data and "id" in resp_data["result"]
    # --- END MODIFIED ---
    task_id = resp_data["result"].get("id")
    assert isinstance(task_id, str)
    # --- MODIFIED: Check store again ---
    assert task_id in mock_a2a_server.task_store
    assert mock_a2a_server.task_store[task_id]["state"] == (TaskState.SUBMITTED if _MODELS_AVAILABLE else "SUBMITTED")
    # --- END MODIFIED ---
    assert respx_mock.calls.call_count == 1
    assert str(respx_mock.calls[0].request.url) == a2a_url # Compare string URLs


@pytest.mark.asyncio
# --- MODIFIED: Add respx marker, use respx_mock fixture arg ---
@pytest.mark.respx(using="httpx")
async def test_mock_tasks_get_reads_from_store(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/get reads state from the store."""
    task_id = "task-state-test-1"
    test_state = TaskState.WORKING if _MODELS_AVAILABLE else "WORKING"
    # Manually set state in the store
    mock_a2a_server.task_store[task_id] = {"state": test_state}

    test_id = "req-get-1"
    payload = {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": task_id}, "id": test_id}

    # --- MODIFIED: Setup routes inside test using fixture data ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)
    # --- END MODIFIED ---

    assert response.status_code == HTTPStatus.OK
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "result" in resp_data
    assert resp_data["result"]["id"] == task_id
    assert resp_data["result"]["state"] == test_state # Check state matches store
    # --- MODIFIED: Correct assertion ---
    assert respx_mock.calls.call_count == 1 # Verify respx handled it
    # --- END MODIFIED ---

@pytest.mark.asyncio
# --- MODIFIED: Add respx marker, use respx_mock fixture arg ---
@pytest.mark.respx(using="httpx")
async def test_mock_tasks_get_not_found(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/get returns error if task not in store."""
    task_id = "task-not-in-store"
    test_id = "req-get-err"
    payload = {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": task_id}, "id": test_id}

    # --- MODIFIED: Setup routes inside test ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)
    # --- END MODIFIED ---

    assert response.status_code == HTTPStatus.OK
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
    assert "Task not found" in resp_data["error"]["message"]
    # --- MODIFIED: Correct assertion ---
    assert respx_mock.calls.call_count == 1 # Verify respx handled it
    # --- END MODIFIED ---

@pytest.mark.asyncio
# --- MODIFIED: Add respx marker, use respx_mock fixture arg ---
@pytest.mark.respx(using="httpx")
async def test_mock_tasks_cancel_updates_store(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/cancel updates state in the store."""
    task_id = "task-to-cancel"
    # Add task to store
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING if _MODELS_AVAILABLE else "WORKING"}

    test_id = "req-cancel-1"
    payload = {"jsonrpc": "2.0", "method": "tasks/cancel", "params": {"id": task_id}, "id": test_id}

    # --- MODIFIED: Setup routes inside test ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)
    # --- END MODIFIED ---

    assert response.status_code == HTTPStatus.OK
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    # --- MODIFIED: Correct assertion ---
    assert resp_data.get("result") == {"success": True}
    # --- END MODIFIED ---

    # Check state in store was updated
    assert mock_a2a_server.task_store[task_id]["state"] == (TaskState.CANCELED if _MODELS_AVAILABLE else "CANCELED")
    # --- MODIFIED: Correct assertion ---
    assert respx_mock.calls.call_count == 1 # Verify respx handled it
    # --- END MODIFIED ---

@pytest.mark.asyncio
# --- MODIFIED: Add respx marker, use respx_mock fixture arg ---
@pytest.mark.respx(using="httpx")
async def test_mock_tasks_cancel_not_found(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/cancel returns error if task not in store."""
    task_id = "task-cancel-not-found"
    test_id = "req-cancel-err"
    payload = {"jsonrpc": "2.0", "method": "tasks/cancel", "params": {"id": task_id}, "id": test_id}

    # --- MODIFIED: Setup routes inside test ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)
    # --- END MODIFIED ---

    assert response.status_code == HTTPStatus.OK
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "error" in resp_data
    # --- MODIFIED: Correct assertion ---
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
    # --- END MODIFIED ---
    assert respx_mock.calls.call_count == 1 # Verify respx handled it

@pytest.mark.asyncio
# --- MODIFIED: Add respx marker, use respx_mock fixture arg ---
@pytest.mark.respx(using="httpx")
async def test_mock_subscribe_yields_configured_events(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/sendSubscribe yields events from sse_event_store."""
    task_id = "task-sse-test"
    # Add task to store so it's found
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING if _MODELS_AVAILABLE else "WORKING"}
    # Configure events
    now = datetime.datetime.now(datetime.timezone.utc)
    # --- MODIFIED: Create a valid TaskStatusUpdateEvent if models available ---
    if _MODELS_AVAILABLE:
        event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
        # Create expected data *without* timestamp for comparison
        expected_event_data = {"taskId": task_id, "state": TaskState.WORKING.value}
    else:
        # Fallback dict representation
        event1 = {"taskId": task_id, "state": "WORKING", "timestamp": now.isoformat()}
        expected_event_data = {"taskId": task_id, "state": "WORKING"}
    # --- END MODIFIED ---
    mock_a2a_server.sse_event_store[task_id] = [event1] # Configure one event

    test_id = "req-sub-1"
    payload = {"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": {"id": task_id}, "id": test_id}

    # --- MODIFIED: Setup routes using fixture data ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", f"{mock_a2a_server.base_url}/a2a", json=payload) as response:
            # Check initial response headers
            assert response.status_code == HTTPStatus.OK # Use status code constant
            # --- MODIFIED: Use startswith ---
            assert response.headers["content-type"].startswith("text/event-stream")
            # --- END MODIFIED ---
            # Consume the stream content
            content = await response.aread()
    # --- END MODIFIED ---

    # Check the received content
    content_str = content.decode('utf-8').strip() # Strip trailing newlines
    # --- MODIFIED: Parse SSE and compare essential fields ---
    received_event_type = None
    received_data_str = None
    for line in content_str.splitlines():
        if line.startswith("event:"):
            received_event_type = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            received_data_str = line.split(":", 1)[1].strip()

    assert received_event_type == "task_status"
    assert received_data_str is not None
    try:
        received_data_dict = json.loads(received_data_str)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to decode SSE data as JSON: {received_data_str!r}")

    # --- ADDED: Logging for comparison ---
    logger.info(f"Comparing SSE data:\nExpected (essential): {expected_event_data}\nReceived: {received_data_dict}")
    # --- END ADDED ---

    # Compare only the essential fields, ignoring timestamp
    assert received_data_dict.get("taskId") == expected_event_data.get("taskId"), f"Expected taskId {expected_event_data.get('taskId')}, got {received_data_dict.get('taskId')}"
    assert received_data_dict.get("state") == expected_event_data.get("state"), f"Expected state {expected_event_data.get('state')}, got {received_data_dict.get('state')}"
    # --- END MODIFIED ---
    assert respx_mock.calls.call_count == 1 # Verify respx handled it

@pytest.mark.asyncio
# --- MODIFIED: Add respx marker, use respx_mock fixture arg ---
@pytest.mark.respx(using="httpx")
async def test_mock_subscribe_task_not_found(mock_a2a_server: MockServerInfo, respx_mock):
# --- END MODIFIED ---
    """Verify tasks/sendSubscribe returns error if task not in store."""
    task_id = "task-sub-not-found"
    test_id = "req-sub-err"
    payload = {"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": {"id": task_id}, "id": test_id}

    # --- MODIFIED: Setup routes inside test ---
    # Fixture handles setup
    # --- END MODIFIED ---

    # --- MODIFIED: Removed async with respx.mock ---
    async with httpx.AsyncClient() as client:
        # Subscription request itself should fail with JSON-RPC error, not stream
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)
    # --- END MODIFIED ---

    assert response.status_code == HTTPStatus.OK
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "error" in resp_data
    # --- MODIFIED: Correct assertion ---
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
    # --- END MODIFIED ---
    assert respx_mock.calls.call_count == 1 # Verify respx handled it
