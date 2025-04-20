"""
Tests for the FastAPI integration helpers in the Server SDK.
"""
import pytest
# --- MODIFIED: Added uuid, datetime ---
import uuid
import datetime
import json
import asyncio
import logging # Added import
from abc import ABC
from unittest.mock import patch, MagicMock, ANY, AsyncMock, call
# --- MODIFIED: Added Tuple ---
from typing import Optional, Dict, Any, Union, AsyncGenerator, List, Callable, TypeVar, Tuple # Added Tuple
# --- END MODIFIED ---


# --- MODIFIED: Import FastAPI directly ---
from fastapi import FastAPI, status, Request, Response, HTTPException
# --- END MODIFIED ---
from fastapi.testclient import TestClient
# --- MODIFIED: Import StreamingResponse directly, removed SSEResponse ---
from fastapi.responses import StreamingResponse, JSONResponse
# --- END MODIFIED ---
import pydantic # Import pydantic for ValidationError
# --- ADDED: Import pydantic_core ---
from pydantic_core import ValidationError
# --- END ADDED ---


# Import SDK components
from agentvault_server_sdk.agent import BaseA2AAgent
# --- MODIFIED: Removed SSEResponse import ---
from agentvault_server_sdk.fastapi_integration import (
    create_a2a_router, a2a_method,
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
)
# --- END MODIFIED ---
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
from agentvault_server_sdk.fastapi_integration import JSONRPC_INVALID_PARAMS, JSONRPC_METHOD_NOT_FOUND, JSONRPC_PARSE_ERROR, JSONRPC_INVALID_REQUEST, JSONRPC_APP_ERROR, JSONRPC_INTERNAL_ERROR, JSONRPC_TASK_NOT_FOUND
from agentvault_server_sdk.state import BaseTaskStore, InMemoryTaskStore, TaskContext


# Import necessary models from the core library
try:
    from agentvault.models import (
        Message, Task, TaskState, A2AEvent,
        TaskSendParams, TaskSendResult, TaskGetParams, GetTaskResult,
        TaskCancelParams, TaskCancelResult,
        TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent, Artifact, TextPart
    )
    from agentvault.exceptions import A2AError, A2ARemoteAgentError, A2AMessageError
    _AGENTVAULT_IMPORTED = True
except ImportError:
    pytest.skip("agentvault core library not available, skipping integration tests", allow_module_level=True)
    # Define placeholders if needed for type hints below, though skip should prevent execution
    class Message: pass # type: ignore
    class Task: pass # type: ignore
    class TaskState: pass # type: ignore
    class A2AEvent: pass # type: ignore
    class TaskSendParams: pass # type: ignore
    class TaskSendResult: pass # type: ignore
    class TaskGetParams: pass # type: ignore
    class GetTaskResult: pass # type: ignore
    class TaskCancelParams: pass # type: ignore
    class TaskCancelResult: pass # type: ignore
    class A2AError(Exception): pass # type: ignore
    class A2ARemoteAgentError(A2AError): pass # type: ignore
    class A2AMessageError(A2AError): pass # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    class Artifact: pass # type: ignore
    class TextPart: pass # type: ignore


logger = logging.getLogger(__name__)

# --- Mock Agent Implementation (from test_agents.py in testing_utils for consistency) ---
class MockAgentForRouter(BaseA2AAgent):
    """A mock agent specifically for testing the FastAPI router integration."""
    def __init__(self, task_store: BaseTaskStore):
        super().__init__()
        self.task_store = task_store # Use the provided store
        self.should_raise: Optional[Exception] = None
        self.last_received_message: Optional[Message] = None
        self.last_task_id_handled: Optional[str] = None
        self.cancel_result = True
        self.sse_events_to_yield: List[A2AEvent] = []
        self.subscribe_should_raise: Optional[Exception] = None
        self.custom_echo_should_raise: Optional[Exception] = None
        self.custom_bad_return_value: Any = None

    # --- Methods to configure mock behavior ---
    def configure_error(self, error: Optional[Exception]): self.should_raise = error; self.subscribe_should_raise = None; self.custom_echo_should_raise = None
    def configure_subscribe_error(self, error: Optional[Exception]): self.subscribe_should_raise = error; self.should_raise = None; self.custom_echo_should_raise = None
    def configure_custom_echo_error(self, error: Optional[Exception]): self.custom_echo_should_raise = error; self.should_raise = None; self.subscribe_should_raise = None
    def configure_custom_bad_return(self, value: Any): self.custom_bad_return_value = value
    def configure_cancel_result(self, result: bool): self.cancel_result = result
    def configure_sse_events(self, events: List[A2AEvent]): self.sse_events_to_yield = events

    # --- Implement BaseA2AAgent methods ---
    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        if self.should_raise: raise self.should_raise
        self.last_received_message = message
        if task_id:
            self.last_task_id_handled = task_id
            ctx = await self.task_store.get_task(task_id)
            if ctx is None: raise TaskNotFoundError(task_id=task_id)
            # Simulate some update
            await self.task_store.update_task_state(task_id, ctx.current_state)
            return task_id
        else:
            new_id = f"task-{uuid.uuid4().hex[:4]}"
            self.last_task_id_handled = new_id
            await self.task_store.create_task(new_id)
            return new_id

    async def handle_task_get(self, task_id: str) -> Task:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        ctx = await self.task_store.get_task(task_id)
        if ctx is None: raise TaskNotFoundError(task_id=task_id)
        # Return a mock Task object based on context
        return Task(
            id=ctx.task_id, state=ctx.current_state, # type: ignore
            createdAt=ctx.created_at, updatedAt=ctx.updated_at,
            messages=[], artifacts=[]
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        ctx = await self.task_store.get_task(task_id)
        if ctx is None: raise TaskNotFoundError(task_id=task_id)
        await self.task_store.update_task_state(task_id, TaskState.CANCELED)
        return self.cancel_result

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        if self.subscribe_should_raise: raise self.subscribe_should_raise
        self.last_task_id_handled = task_id
        ctx = await self.task_store.get_task(task_id)
        if ctx is None: raise TaskNotFoundError(task_id=task_id)

        # Simulate yielding pre-configured events
        for event in self.sse_events_to_yield:
            yield event
            await asyncio.sleep(0.01)
        # Keep stream open conceptually unless task becomes terminal
        # (In a real agent, this would listen to the store's queue)
        if False: yield # pragma: no cover

    # --- Decorated methods ---
    @a2a_method("custom/echo")
    async def custom_echo(self, message: str, extra_param: Optional[int] = None) -> str:
        if self.custom_echo_should_raise: raise self.custom_echo_should_raise
        return f"Echo: {message}" + (f" | Extra: {extra_param}" if extra_param is not None else "")

    @a2a_method("custom/bad_return")
    async def custom_bad_return(self, value: int) -> str: # Expects str return
        if self.custom_bad_return_value is not None: return self.custom_bad_return_value
        return 12345 # Return invalid type


# --- Pytest Fixture ---
@pytest.fixture
def test_app_with_agent() -> Tuple[MockAgentForRouter, TestClient, InMemoryTaskStore]:
    """Creates a FastAPI app with the A2A router and a mock agent for testing."""
    task_store = InMemoryTaskStore()
    mock_agent = MockAgentForRouter(task_store)
    a2a_router = create_a2a_router(agent=mock_agent, prefix="/a2a", task_store=task_store)

    app = FastAPI()
    app.include_router(a2a_router)

    # Register all handlers on the test app
    app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    app.add_exception_handler(ValueError, validation_exception_handler)
    app.add_exception_handler(TypeError, validation_exception_handler)
    # --- MODIFIED: Use correct ValidationError ---
    app.add_exception_handler(ValidationError, validation_exception_handler)
    # --- END MODIFIED ---
    app.add_exception_handler(AgentServerError, agent_server_error_handler)
    app.add_exception_handler(RuntimeError, generic_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler) # Generic handler LAST

    client = TestClient(app)
    return mock_agent, client, task_store

# --- Helper ---
def make_rpc_request(
    client: TestClient,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    req_id: Union[str, int] = 1,
    # --- ADDED: Allow sending raw content ---
    raw_content: Optional[Union[str, bytes]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    # --- END ADDED ---
) -> Any:
    """Helper to make JSON-RPC POST requests."""
    # --- MODIFIED: Handle raw_content ---
    if raw_content is not None:
        headers = {"Content-Type": "application/json"} # Still set header
        response = client.post("/a2a/", content=raw_content, headers=headers)
    elif json_payload is not None:
         response = client.post("/a2a/", json=json_payload)
    # --- END MODIFIED ---
    else:
        payload = {"jsonrpc": "2.0", "method": method, "id": req_id}
        if params is not None:
            payload["params"] = params
        response = client.post("/a2a/", json=payload)
    return response

# --- Test Cases ---

def test_router_creation(test_app_with_agent):
    """Test that the router is created and added."""
    mock_agent, client, store = test_app_with_agent
    # Check if a known route exists
    response = client.post("/a2a/", json={"jsonrpc": "2.0", "method": "nonexistent", "id": 1})
    assert response.status_code == status.HTTP_200_OK # Should return JSON-RPC error
    assert response.json()["error"]["code"] == JSONRPC_METHOD_NOT_FOUND

# --- Tests for Standard Method Routing ---

def test_route_tasks_send_new(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    params = {"message": {"role": "user", "parts": [{"type": "text", "content": "init"}]}}
    response = make_rpc_request(client, "tasks/send", params=params, req_id="ts1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["id"] == "ts1"
    assert "result" in resp_data and "id" in resp_data["result"]
    new_task_id = resp_data["result"]["id"]
    assert new_task_id in store._tasks # Check store

def test_route_tasks_send_existing(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    task_id = "existing-task-send"
    store._tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    params = {"id": task_id, "message": {"role": "user", "parts": [{"type": "text", "content": "follow up"}]}}
    response = make_rpc_request(client, "tasks/send", params=params, req_id="ts2")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["id"] == "ts2"
    assert resp_data["result"]["id"] == task_id # Should return existing ID

def test_route_tasks_get_success(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    task_id = "existing-task-get"
    store._tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    response = make_rpc_request(client, "tasks/get", params={"id": task_id}, req_id="tg1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["id"] == "tg1"
    assert resp_data["result"]["id"] == task_id
    assert resp_data["result"]["state"] == TaskState.WORKING

def test_route_tasks_get_not_found(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    response = make_rpc_request(client, "tasks/get", params={"id": "not-a-task"}, req_id="tg2")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "tg2"
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND

def test_route_tasks_cancel_success(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    task_id = "existing-task-cancel"
    store._tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    response = make_rpc_request(client, "tasks/cancel", params={"id": task_id}, req_id="tc1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["id"] == "tc1"
    assert resp_data["result"]["success"] is True
    assert store._tasks[task_id].current_state == TaskState.CANCELED

def test_route_tasks_cancel_not_found(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    response = make_rpc_request(client, "tasks/cancel", params={"id": "not-a-task"}, req_id="tc2")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "tc2"
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND

def test_route_tasks_send_invalid_params(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    # Missing 'message' parameter
    response = make_rpc_request(client, "tasks/send", params={}, req_id="ts-bad1")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "ts-bad1"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "message" in resp_data["error"]["message"] # Check detail

# --- Tests for Decorated Method Routing ---
def test_route_decorated_method_success(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    response = make_rpc_request(client, "custom/echo", params={"message": "hello"}, req_id="deco1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["id"] == "deco1"
    assert resp_data["result"] == "Echo: hello"

def test_route_decorated_method_invalid_params(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    # 'message' should be string, sending int
    response = make_rpc_request(client, "custom/echo", params={"message": 123}, req_id="deco2")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "deco2"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "message" in resp_data["error"]["message"]
    assert "Input should be a valid string" in resp_data["error"]["message"]

# --- Test SSE Endpoint ---
@pytest.mark.asyncio
async def test_route_tasks_sendSubscribe_success(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    task_id = "sse-task-route"
    await store.create_task(task_id) # Ensure task exists

    # Configure mock agent to yield specific events
    now = datetime.datetime.now(datetime.timezone.utc)
    event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
    mock_agent.configure_sse_events([event1])

    # Make the request using the TestClient's stream context
    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id="sub1")

    # Check initial response headers
    assert response.status_code == status.HTTP_200_OK
    # --- MODIFIED: Use startswith ---
    assert response.headers["content-type"].startswith("text/event-stream")
    # --- END MODIFIED ---

    # Consume the stream content
    content = response.content.decode('utf-8')
    lines = content.strip().split('\n\n')

    assert len(lines) >= 1 # Expect at least the one event
    assert "event: task_status" in lines[0]
    # --- MODIFIED: Parse JSON and assert dict content ---
    assert lines[0].startswith("event: task_status\ndata: ")
    data_str = lines[0].split("data: ", 1)[1]
    event_data = json.loads(data_str)
    assert event_data.get("taskId") == task_id
    assert event_data.get("state") == TaskState.WORKING
    # --- END MODIFIED ---

@pytest.mark.asyncio
async def test_route_tasks_sendSubscribe_task_not_found(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    task_id = "sse-task-not-found"
    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id="sub-err1")

    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "sub-err1"
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND

@pytest.mark.asyncio
async def test_route_tasks_sendSubscribe_generator_error(test_app_with_agent):
    mock_agent, client, store = test_app_with_agent
    task_id = "sse-task-gen-err"
    await store.create_task(task_id)
    error_message = "Generator failed!"
    mock_agent.configure_subscribe_error(RuntimeError(error_message))

    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id="sub-err2")

    # Check initial response headers
    assert response.status_code == status.HTTP_200_OK
    # --- MODIFIED: Use startswith ---
    assert response.headers["content-type"].startswith("text/event-stream")
    # --- END MODIFIED ---

    # Consume the stream - should yield the error event
    content = response.content.decode('utf-8')
    lines = content.strip().split('\n\n')

    assert len(lines) == 1
    assert "event: error" in lines[0]
    # --- MODIFIED: Parse JSON and assert error content ---
    assert lines[0].startswith("event: error\ndata: ")
    data_str = lines[0].split("data: ", 1)[1]
    error_data = json.loads(data_str)
    assert error_data.get("error") == "stream_error"
    assert f"RuntimeError: {error_message}" in error_data.get("message", "")
    # --- END MODIFIED ---

# --- ADDED: Tests for Invalid JSON-RPC Requests ---

def test_invalid_json_request(test_app_with_agent):
    """Test sending invalid JSON."""
    _, client, _ = test_app_with_agent
    response = make_rpc_request(client, method="", raw_content=b"{invalid json")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] is None # No ID could be parsed
    assert resp_data["error"]["code"] == JSONRPC_PARSE_ERROR

def test_non_dict_request(test_app_with_agent):
    """Test sending a JSON array instead of an object."""
    _, client, _ = test_app_with_agent
    response = make_rpc_request(client, method="", json_payload=[1, 2, 3])
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] is None # No ID could be parsed
    assert resp_data["error"]["code"] == JSONRPC_INVALID_REQUEST
    assert "Payload must be a JSON object" in resp_data["error"]["message"]

def test_missing_method_request(test_app_with_agent):
    """Test sending a request missing the 'method' field."""
    _, client, _ = test_app_with_agent
    payload = {"jsonrpc": "2.0", "id": "m-err"}
    response = make_rpc_request(client, method="", json_payload=payload)
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "m-err"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_REQUEST
    assert "'method' is required" in resp_data["error"]["message"]

def test_invalid_jsonrpc_version(test_app_with_agent):
    """Test sending a request with the wrong 'jsonrpc' version."""
    _, client, _ = test_app_with_agent
    payload = {"jsonrpc": "1.0", "method": "test", "id": "v-err"}
    response = make_rpc_request(client, method="", json_payload=payload)
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "v-err"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_REQUEST
    assert "'jsonrpc' must be '2.0'" in resp_data["error"]["message"]

# --- ADDED: Tests for tasks/sendSubscribe Parameter Validation ---

def test_route_tasks_sendSubscribe_missing_params(test_app_with_agent):
    """Test tasks/sendSubscribe with missing 'params' field."""
    mock_agent, client, store = test_app_with_agent
    response = make_rpc_request(client, "tasks/sendSubscribe", params=None, req_id="sub-bad1")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "sub-bad1"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Params must be a dictionary" in resp_data["error"]["message"]

def test_route_tasks_sendSubscribe_missing_id_in_params(test_app_with_agent):
    """Test tasks/sendSubscribe with 'params' missing the 'id' key."""
    mock_agent, client, store = test_app_with_agent
    response = make_rpc_request(client, "tasks/sendSubscribe", params={"other": "value"}, req_id="sub-bad2")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "sub-bad2"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "'id' parameter is required" in resp_data["error"]["message"]

def test_route_tasks_sendSubscribe_invalid_id_type(test_app_with_agent):
    """Test tasks/sendSubscribe with 'id' parameter of wrong type."""
    mock_agent, client, store = test_app_with_agent
    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": 12345}, req_id="sub-bad3")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "sub-bad3"
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "'id' parameter is required" in resp_data["error"]["message"] # Error message might be generic

# --- ADDED: Tests for Decorated Method Error Handling ---

def test_route_decorated_method_agent_error(test_app_with_agent):
    """Test decorated method raising AgentServerError returns JSONRPC_APP_ERROR."""
    mock_agent, client, store = test_app_with_agent
    error_msg = "Agent failed processing echo"
    mock_agent.configure_custom_echo_error(AgentServerError(error_msg))

    response = make_rpc_request(client, "custom/echo", params={"message": "test"}, req_id="deco-err1")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["id"] == "deco-err1"
    assert resp_data["error"]["code"] == JSONRPC_APP_ERROR
    assert f"Agent error: {error_msg}" in resp_data["error"]["message"]

def test_route_decorated_method_bad_return_type(test_app_with_agent):
    """Test decorated method returning wrong type results in JSONRPC_INTERNAL_ERROR."""
    mock_agent, client, store = test_app_with_agent
    # Configure the mock agent's method to return an int instead of a str
    mock_agent.configure_custom_bad_return(12345) # Method expects str

    response = make_rpc_request(client, "custom/bad_return", params={"value": 1}, req_id="deco-err2")
    # This error happens *after* the handler runs, during response validation/serialization
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR # Internal server error
    resp_data = response.json()
    assert resp_data["id"] == "deco-err2"
    assert resp_data["error"]["code"] == JSONRPC_INTERNAL_ERROR
    assert "Invalid return type" in resp_data["error"]["message"]

# --- END ADDED ---
