import pytest
import uuid
import datetime
import json
import asyncio
import logging # Added import
from unittest.mock import patch, MagicMock, ANY, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse, JSONResponse # Added JSONResponse


# Import SDK components
from agentvault_server_sdk.agent import BaseA2AAgent
from agentvault_server_sdk.fastapi_integration import create_a2a_router, SSEResponse, JSONRPC_INVALID_PARAMS, JSONRPC_METHOD_NOT_FOUND, JSONRPC_PARSE_ERROR, JSONRPC_INVALID_REQUEST, JSONRPC_APP_ERROR, JSONRPC_INTERNAL_ERROR


# Import core library models and exceptions
try:
    from agentvault.models import (
        Message, Task, TaskState, TextPart, A2AEvent, TaskSendResult, GetTaskResult, TaskCancelResult,
        TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent, Artifact
    )
    from agentvault.exceptions import A2AError, A2ARemoteAgentError
    _MODELS_AVAILABLE = True
except ImportError:
    pytest.skip("agentvault core library not available, skipping integration tests", allow_module_level=True)
    # Define placeholders if needed for type hints below, though skip should prevent execution
    class Message: pass # type: ignore
    class Task: pass # type: ignore
    class TaskState: pass # type: ignore
    class A2AEvent: pass # type: ignore
    class TaskSendResult: pass # type: ignore
    class GetTaskResult: pass # type: ignore
    class TaskCancelResult: pass # type: ignore
    class A2AError(Exception): pass # type: ignore
    class A2ARemoteAgentError(A2AError): pass # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    class Artifact: pass # type: ignore


# --- Mock Agent Implementation ---
# (MockAgent class remains the same as previous version)
class MockAgent(BaseA2AAgent):
    """A mock agent for testing the FastAPI router integration."""
    def __init__(self):
        super().__init__()
        self.tasks: Dict[str, Task] = {}
        self.should_raise: Optional[Exception] = None
        self.last_received_message: Optional[Message] = None
        self.last_task_id_handled: Optional[str] = None
        self.cancel_result = True # Default cancel success
        self.sse_events_to_yield: List[A2AEvent] = []
        self.subscribe_should_raise: Optional[Exception] = None # Specific error for subscribe handler

    def configure_error(self, error: Optional[Exception]):
        self.should_raise = error
        self.subscribe_should_raise = None # Reset subscribe error

    def configure_subscribe_error(self, error: Optional[Exception]):
        self.subscribe_should_raise = error
        self.should_raise = None # Reset general error

    def configure_cancel_result(self, result: bool):
        self.cancel_result = result

    def configure_sse_events(self, events: List[A2AEvent]):
        self.sse_events_to_yield = events

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        if self.should_raise: raise self.should_raise
        self.last_received_message = message
        if task_id:
            self.last_task_id_handled = task_id
            if task_id in self.tasks:
                self.tasks[task_id].messages.append(message)
            return task_id
        else:
            new_id = f"task-{uuid.uuid4()}"
            self.last_task_id_handled = new_id
            now = datetime.datetime.now(datetime.timezone.utc)
            self.tasks[new_id] = Task(
                id=new_id, state=TaskState.SUBMITTED, createdAt=now, updatedAt=now,
                messages=[message], artifacts=[]
            )
            return new_id

    async def handle_task_get(self, task_id: str) -> Task:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        task = self.tasks.get(task_id)
        if task is None:
            raise A2AError(f"Mock Task not found: {task_id}")
        return task

    async def handle_task_cancel(self, task_id: str) -> bool:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        if task_id not in self.tasks:
             raise A2AError(f"Mock Task not found for cancellation: {task_id}")
        self.tasks[task_id].state = TaskState.CANCELED
        return self.cancel_result

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        if self.subscribe_should_raise: raise self.subscribe_should_raise # Use specific error for subscribe
        self.last_task_id_handled = task_id
        if task_id not in self.tasks:
             raise A2AError(f"Mock Task not found for subscription: {task_id}")

        for event in self.sse_events_to_yield:
            yield event
            await asyncio.sleep(0.01)


# --- Pytest Fixture ---

@pytest.fixture
def test_app() -> Tuple[MockAgent, TestClient]:
    """Creates a FastAPI app with the A2A router for testing."""
    mock_agent = MockAgent()
    a2a_router = create_a2a_router(agent=mock_agent, prefix="/a2a")
    app = FastAPI()
    app.include_router(a2a_router)
    client = TestClient(app)
    return mock_agent, client

# --- Helper Function ---
def make_rpc_request(
    client: TestClient,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    req_id: Union[str, int] = 1
) -> Any:
    """Helper to make JSON-RPC POST requests."""
    payload = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        payload["params"] = params
    response = client.post("/a2a/", json=payload)
    return response


# --- Test Cases ---
# ... (Keep passing tests for send, get, cancel, invalid requests, method not found) ...

def test_invalid_params_get_missing_id(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/get with params missing the 'id' field."""
    _, client = test_app
    response = make_rpc_request(client, "tasks/get", params={}, req_id="ip-get-1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Field required" in resp_data["error"]["message"]
    assert "id" in resp_data["error"]["message"]
    assert resp_data["id"] == "ip-get-1"

# ... (Keep other passing tests) ...

# --- ADDED: SSE Unit Tests (Testing SSEResponse directly) ---
# (Keep SSE Unit tests as they are)
# ...

# --- ADDED: SSE Integration Tests (Testing the endpoint) ---
# (Keep successful SSE tests: test_tasks_send_subscribe_success, test_tasks_send_subscribe_stream_content)
# ...

def test_tasks_send_subscribe_invalid_params(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/sendSubscribe with invalid parameters."""
    _, client = test_app
    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": 123}, req_id="ip-sub-1") # ID not a string
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "'id' parameter is required and must be a non-empty string" in resp_data["error"]["message"]
    assert resp_data["id"] == "ip-sub-1"

def test_tasks_send_subscribe_agent_a2a_error(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/sendSubscribe when agent handler generator raises A2AError."""
    mock_agent, client = test_app
    task_id = "task-sub-fail"
    error_message = "Subscription failed by agent"
    # Configure agent to raise error *during* generation
    async def error_generator(*args, **kwargs):
        raise A2AError(error_message)
        if False: yield # Make it a generator type
    mock_agent.handle_subscribe_request = error_generator # Override the method directly

    params = {"id": task_id}
    # --- MODIFIED: Expect stream response containing SSE error ---
    with client.stream("POST", "/a2a/", json={"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": params, "id": "sub-err-1"}) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Read the content and check for the SSE error event
        content = response.read().decode('utf-8')
        assert "event: error" in content
        assert "Error generating events: A2AError" in content # Check type
        assert error_message in content # Check message is included
    # --- END MODIFIED ---

def test_tasks_send_subscribe_agent_unexpected_error(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/sendSubscribe when agent handler generator raises generic Exception."""
    mock_agent, client = test_app
    task_id = "task-sub-fail-unexpected"
    error_message = "Something broke badly"
    # Configure agent to raise error *during* generation
    async def error_generator(*args, **kwargs):
        raise RuntimeError(error_message)
        if False: yield # Make it a generator type
    mock_agent.handle_subscribe_request = error_generator # Override the method directly

    params = {"id": task_id}
    # --- MODIFIED: Expect stream response containing SSE error ---
    with client.stream("POST", "/a2a/", json={"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": params, "id": "sub-err-2"}) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Read the content and check for the SSE error event
        content = response.read().decode('utf-8')
        assert "event: error" in content
        assert "Error generating events: RuntimeError" in content # Check type
        assert error_message in content # Check message is included
    # --- END MODIFIED ---
