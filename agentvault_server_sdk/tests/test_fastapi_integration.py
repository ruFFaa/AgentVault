import pytest
import uuid
import datetime
import json
import asyncio
import logging # Added import
# --- ADDED: Import ABC ---
from abc import ABC
# --- END ADDED ---
from unittest.mock import patch, MagicMock, ANY, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse, JSONResponse # Added JSONResponse


# Import SDK components
from agentvault_server_sdk.agent import BaseA2AAgent
# --- MODIFIED: Import decorator ---
from agentvault_server_sdk.fastapi_integration import create_a2a_router, SSEResponse, a2a_method
# --- END MODIFIED ---
from agentvault_server_sdk.fastapi_integration import JSONRPC_INVALID_PARAMS, JSONRPC_METHOD_NOT_FOUND, JSONRPC_PARSE_ERROR, JSONRPC_INVALID_REQUEST, JSONRPC_APP_ERROR, JSONRPC_INTERNAL_ERROR
# --- ADDED: Import state classes ---
from agentvault_server_sdk.state import BaseTaskStore, InMemoryTaskStore, TaskContext
# --- END ADDED ---


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
        # --- ADDED: State for custom echo ---
        self.custom_echo_should_raise: Optional[Exception] = None
        # --- END ADDED ---

    def configure_error(self, error: Optional[Exception]):
        self.should_raise = error
        self.subscribe_should_raise = None # Reset subscribe error
        self.custom_echo_should_raise = None # Reset custom error

    def configure_subscribe_error(self, error: Optional[Exception]):
        self.subscribe_should_raise = error
        self.should_raise = None # Reset general error
        self.custom_echo_should_raise = None # Reset custom error

    # --- ADDED: Configure custom echo error ---
    def configure_custom_echo_error(self, error: Optional[Exception]):
        self.custom_echo_should_raise = error
        self.should_raise = None
        self.subscribe_should_raise = None
    # --- END ADDED ---

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
                # Simulate adding message if Task model is available
                if _MODELS_AVAILABLE and isinstance(self.tasks[task_id], Task):
                    self.tasks[task_id].messages.append(message) # type: ignore
            return task_id
        else:
            new_id = f"task-{uuid.uuid4()}"
            self.last_task_id_handled = new_id
            now = datetime.datetime.now(datetime.timezone.utc)
            # Use mock Task if models not available
            task_obj = Task(
                id=new_id, state=TaskState.SUBMITTED, createdAt=now, updatedAt=now,
                messages=[message], artifacts=[]
            ) if _MODELS_AVAILABLE else {"id": new_id, "state": "SUBMITTED"}
            self.tasks[new_id] = task_obj # type: ignore
            return new_id

    async def handle_task_get(self, task_id: str) -> Task:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        task = self.tasks.get(task_id)
        if task is None:
            raise A2AError(f"Mock Task not found: {task_id}")
        return task # type: ignore

    async def handle_task_cancel(self, task_id: str) -> bool:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        if task_id not in self.tasks:
             raise A2AError(f"Mock Task not found for cancellation: {task_id}")
        if _MODELS_AVAILABLE and isinstance(self.tasks[task_id], Task):
            self.tasks[task_id].state = TaskState.CANCELED # type: ignore
        else:
             self.tasks[task_id]["state"] = "CANCELED" # type: ignore
        return self.cancel_result

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        if self.subscribe_should_raise: raise self.subscribe_should_raise # Use specific error for subscribe
        self.last_task_id_handled = task_id
        if task_id not in self.tasks:
             raise A2AError(f"Mock Task not found for subscription: {task_id}")

        for event in self.sse_events_to_yield:
            yield event
            await asyncio.sleep(0.01)

    # --- ADDED: Decorated Method ---
    @a2a_method("custom/echo")
    async def custom_echo(self, message: str) -> str:
        """A simple echo method for testing decorators."""
        logging.info(f"Executing custom_echo with message: '{message}'")
        if self.custom_echo_should_raise:
            raise self.custom_echo_should_raise
        return message
    # --- END ADDED ---


# --- Pytest Fixture ---

@pytest.fixture
def test_app() -> Tuple[MockAgent, TestClient]:
    """Creates a FastAPI app with the A2A router for testing."""
    mock_agent = MockAgent()
    # --- MODIFIED: Pass task store ---
    task_store = InMemoryTaskStore() # Create instance for the test app
    a2a_router = create_a2a_router(agent=mock_agent, prefix="/a2a", task_store=task_store)
    # --- END MODIFIED ---
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

# --- ADDED: Tests for Decorated Method ---

def test_decorated_method_success(test_app: Tuple[MockAgent, TestClient]):
    """Test calling a method defined with the @a2a_method decorator."""
    mock_agent, client = test_app
    response = make_rpc_request(client, "custom/echo", params={"message": "hello world"}, req_id="echo-1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert "result" in resp_data
    assert resp_data["result"] == "hello world"
    assert resp_data["id"] == "echo-1"

def test_decorated_method_invalid_params_missing(test_app: Tuple[MockAgent, TestClient]):
    """Test calling decorated method with missing required parameter."""
    mock_agent, client = test_app
    response = make_rpc_request(client, "custom/echo", params={}, req_id="echo-err-1") # Missing 'message'
    assert response.status_code == status.HTTP_200_OK # JSON-RPC errors are 200 OK
    resp_data = response.json()
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Field required" in resp_data["error"]["message"]
    assert "message" in resp_data["error"]["message"]
    assert resp_data["id"] == "echo-err-1"

def test_decorated_method_invalid_params_type(test_app: Tuple[MockAgent, TestClient]):
    """Test calling decorated method with incorrect parameter type."""
    mock_agent, client = test_app
    response = make_rpc_request(client, "custom/echo", params={"message": 123}, req_id="echo-err-2") # 'message' should be str
    assert response.status_code == status.HTTP_200_OK # JSON-RPC errors are 200 OK
    resp_data = response.json()
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Input should be a valid string" in resp_data["error"]["message"]
    assert "message" in resp_data["error"]["message"]
    assert resp_data["id"] == "echo-err-2"

def test_decorated_method_agent_error(test_app: Tuple[MockAgent, TestClient]):
    """Test decorated method raising an A2AError."""
    mock_agent, client = test_app
    error_message = "Agent echo failed"
    mock_agent.configure_custom_echo_error(A2AError(error_message))

    response = make_rpc_request(client, "custom/echo", params={"message": "test"}, req_id="echo-err-3")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC app errors are 200 OK
    resp_data = response.json()
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_APP_ERROR
    assert f"Agent processing error: {error_message}" in resp_data["error"]["message"]
    assert resp_data["id"] == "echo-err-3"

def test_decorated_method_internal_error(test_app: Tuple[MockAgent, TestClient]):
    """Test decorated method raising an unexpected Exception."""
    mock_agent, client = test_app
    error_message = "Unexpected echo failure"
    mock_agent.configure_custom_echo_error(ValueError(error_message)) # Use a generic exception

    response = make_rpc_request(client, "custom/echo", params={"message": "test"}, req_id="echo-err-4")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR # Internal errors return 500
    resp_data = response.json()
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INTERNAL_ERROR
    assert "Internal agent error: ValueError" in resp_data["error"]["message"]
    assert resp_data["id"] == "echo-err-4"

# --- END ADDED ---
