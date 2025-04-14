import pytest
import httpx
import uuid
import datetime
import json
from typing import List

# Import fixture and helpers
from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
from agentvault_testing_utils.mock_server import (
    create_jsonrpc_success_response, create_jsonrpc_error_response,
    JSONRPC_TASK_NOT_FOUND, JSONRPC_METHOD_NOT_FOUND
)

# Import core types for creating test data
try:
    from agentvault.models import TaskState, TaskStatusUpdateEvent
    _MODELS_AVAILABLE = True
except ImportError:
    class TaskState: # type: ignore
        SUBMITTED = "SUBMITTED"; WORKING = "WORKING"; COMPLETED = "COMPLETED"; CANCELED = "CANCELED" # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    _MODELS_AVAILABLE = False

# Use the mock_a2a_server fixture implicitly

@pytest.mark.asyncio
async def test_mock_tasks_send_adds_to_store(mock_a2a_server: MockServerInfo):
    """Verify tasks/send adds task ID to the store."""
    test_id = "req-send-1"
    params = {"message": {"role": "user", "parts": [{"type": "text", "content": "test"}]}}
    payload = {"jsonrpc": "2.0", "method": "tasks/send", "params": params, "id": test_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "result" in resp_data
    task_id = resp_data["result"].get("id")
    assert isinstance(task_id, str)

    # Check the store provided by the fixture
    assert task_id in mock_a2a_server.task_store
    assert mock_a2a_server.task_store[task_id]["state"] == (TaskState.SUBMITTED if _MODELS_AVAILABLE else "SUBMITTED")

@pytest.mark.asyncio
async def test_mock_tasks_get_reads_from_store(mock_a2a_server: MockServerInfo):
    """Verify tasks/get reads state from the store."""
    task_id = "task-state-test-1"
    test_state = TaskState.WORKING if _MODELS_AVAILABLE else "WORKING"
    # Manually set state in the store
    mock_a2a_server.task_store[task_id] = {"state": test_state}

    test_id = "req-get-1"
    payload = {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": task_id}, "id": test_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "result" in resp_data
    assert resp_data["result"]["id"] == task_id
    assert resp_data["result"]["state"] == test_state # Check state matches store

@pytest.mark.asyncio
async def test_mock_tasks_get_not_found(mock_a2a_server: MockServerInfo):
    """Verify tasks/get returns error if task not in store."""
    task_id = "task-not-in-store"
    test_id = "req-get-err"
    payload = {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": task_id}, "id": test_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
    assert "Task not found" in resp_data["error"]["message"]

@pytest.mark.asyncio
async def test_mock_tasks_cancel_updates_store(mock_a2a_server: MockServerInfo):
    """Verify tasks/cancel updates state in the store."""
    task_id = "task-to-cancel"
    # Add task to store
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING if _MODELS_AVAILABLE else "WORKING"}

    test_id = "req-cancel-1"
    payload = {"jsonrpc": "2.0", "method": "tasks/cancel", "params": {"id": task_id}, "id": test_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert resp_data.get("result") == {"success": True}

    # Check state in store was updated
    assert mock_a2a_server.task_store[task_id]["state"] == (TaskState.CANCELED if _MODELS_AVAILABLE else "CANCELED")

@pytest.mark.asyncio
async def test_mock_tasks_cancel_not_found(mock_a2a_server: MockServerInfo):
    """Verify tasks/cancel returns error if task not in store."""
    task_id = "task-cancel-not-found"
    test_id = "req-cancel-err"
    payload = {"jsonrpc": "2.0", "method": "tasks/cancel", "params": {"id": task_id}, "id": test_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND

@pytest.mark.asyncio
async def test_mock_subscribe_yields_configured_events(mock_a2a_server: MockServerInfo):
    """Verify tasks/sendSubscribe yields events from sse_event_store."""
    task_id = "task-sse-test"
    # Add task to store so it's found
    mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING if _MODELS_AVAILABLE else "WORKING"}
    # Configure events
    now = datetime.datetime.now(datetime.timezone.utc)
    event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
    mock_a2a_server.sse_event_store[task_id] = [event1] # Configure one event

    test_id = "req-sub-1"
    payload = {"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": {"id": task_id}, "id": test_id}

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", f"{mock_a2a_server.base_url}/a2a", json=payload) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"
            content = await response.aread()

    # Check the received content
    content_str = content.decode('utf-8')
    assert "event: task_status" in content_str
    assert f'"taskId": "{task_id}"' in content_str
    assert '"state": "WORKING"' in content_str

@pytest.mark.asyncio
async def test_mock_subscribe_task_not_found(mock_a2a_server: MockServerInfo):
    """Verify tasks/sendSubscribe returns error if task not in store."""
    task_id = "task-sub-not-found"
    test_id = "req-sub-err"
    payload = {"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": {"id": task_id}, "id": test_id}

    async with httpx.AsyncClient() as client:
        # Subscription request itself should fail with JSON-RPC error, not stream
        response = await client.post(f"{mock_a2a_server.base_url}/a2a", json=payload)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data.get("id") == test_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
