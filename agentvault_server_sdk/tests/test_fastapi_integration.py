import pytest
import uuid
import datetime
import json
import asyncio
import logging # Added import
from abc import ABC
from unittest.mock import patch, MagicMock, ANY, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List

from fastapi import FastAPI, status, Request, Response
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse, JSONResponse
import pydantic # Import pydantic for ValidationError

# Import SDK components
from agentvault_server_sdk.agent import BaseA2AAgent
from agentvault_server_sdk.fastapi_integration import (
    create_a2a_router, SSEResponse, a2a_method,
    # --- MODIFIED: Import renamed handlers ---
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
    # --- END MODIFIED ---
)
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
from agentvault_server_sdk.fastapi_integration import JSONRPC_INVALID_PARAMS, JSONRPC_METHOD_NOT_FOUND, JSONRPC_PARSE_ERROR, JSONRPC_INVALID_REQUEST, JSONRPC_APP_ERROR, JSONRPC_INTERNAL_ERROR, JSONRPC_TASK_NOT_FOUND
from agentvault_server_sdk.state import BaseTaskStore, InMemoryTaskStore, TaskContext


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
class MockAgent(BaseA2AAgent):
    """A mock agent for testing the FastAPI router integration."""
    def __init__(self):
        super().__init__()
        self.tasks: Dict[str, TaskContext] = {} # Store TaskContext now
        self.should_raise: Optional[Exception] = None
        self.last_received_message: Optional[Message] = None
        self.last_task_id_handled: Optional[str] = None
        self.cancel_result = True # Default cancel success
        self.sse_events_to_yield: List[A2AEvent] = []
        self.subscribe_should_raise: Optional[Exception] = None # Specific error for subscribe handler
        self.custom_echo_should_raise: Optional[Exception] = None

    def configure_error(self, error: Optional[Exception]):
        self.should_raise = error
        self.subscribe_should_raise = None
        self.custom_echo_should_raise = None

    def configure_subscribe_error(self, error: Optional[Exception]):
        self.subscribe_should_raise = error
        self.should_raise = None
        self.custom_echo_should_raise = None

    def configure_custom_echo_error(self, error: Optional[Exception]):
        self.custom_echo_should_raise = error
        self.should_raise = None
        self.subscribe_should_raise = None

    def configure_cancel_result(self, result: bool):
        self.cancel_result = result

    def configure_sse_events(self, events: List[A2AEvent]):
        self.sse_events_to_yield = events

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        if self.should_raise: raise self.should_raise
        self.last_received_message = message
        if task_id:
            self.last_task_id_handled = task_id
            if task_id not in self.tasks:
                 raise TaskNotFoundError(task_id=task_id) # Should exist if ID provided
            return task_id
        else:
            new_id = f"task-{uuid.uuid4()}"
            self.last_task_id_handled = new_id
            new_task_context = TaskContext(task_id=new_id, current_state=TaskState.SUBMITTED)
            self.tasks[new_id] = new_task_context
            return new_id

    async def handle_task_get(self, task_id: str) -> Task: # Return type is still Task model
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        task_context = self.tasks.get(task_id)
        if task_context is None:
            raise TaskNotFoundError(task_id=task_id)
        # This is a simplified representation for testing
        now = datetime.datetime.now(datetime.timezone.utc)
        return Task(
            id=task_context.task_id,
            state=task_context.current_state, # type: ignore
            createdAt=task_context.created_at,
            updatedAt=task_context.updated_at,
            messages=[], # Keep simple for now
            artifacts=[]
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        task_context = self.tasks.get(task_id)
        if task_context is None:
             raise TaskNotFoundError(task_id=task_id)
        task_context.update_state(TaskState.CANCELED)
        return self.cancel_result

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        # Note: Task existence check is now done *before* calling this in the router
        if self.subscribe_should_raise: raise self.subscribe_should_raise
        self.last_task_id_handled = task_id
        # if task_id not in self.tasks: # Check removed, handled by router
        #      raise TaskNotFoundError(task_id=task_id)

        for event in self.sse_events_to_yield:
            yield event
            await asyncio.sleep(0.01)

    @a2a_method("custom/echo")
    async def custom_echo(self, message: str) -> str:
        """A simple echo method for testing decorators."""
        logging.info(f"Executing custom_echo with message: '{message}'")
        if self.custom_echo_should_raise:
            raise self.custom_echo_should_raise
        return message


# --- Pytest Fixture ---

@pytest.fixture
def test_app() -> Tuple[MockAgent, TestClient]:
    """Creates a FastAPI app with the A2A router and exception handlers for testing."""
    mock_agent = MockAgent()
    task_store = InMemoryTaskStore()
    task_store._tasks = mock_agent.tasks
    a2a_router = create_a2a_router(agent=mock_agent, prefix="/a2a", task_store=task_store)

    # Create the main app instance for testing
    app = FastAPI()
    app.include_router(a2a_router)

    # --- Register all handlers on the test app ---
    app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    app.add_exception_handler(ValueError, validation_exception_handler)
    app.add_exception_handler(TypeError, validation_exception_handler)
    app.add_exception_handler(pydantic.ValidationError, validation_exception_handler)
    app.add_exception_handler(AgentServerError, agent_server_error_handler)
    # --- ADDED: Explicit RuntimeError handler ---
    app.add_exception_handler(RuntimeError, generic_exception_handler)
    # --- END ADDED ---
    app.add_exception_handler(Exception, generic_exception_handler) # Generic handler LAST

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
# ... (other tests remain the same) ...

# Test agent raising unexpected Python error
def test_agent_unexpected_error(test_app: Tuple[MockAgent, TestClient]):
    mock_agent, client = test_app
    mock_agent.configure_error(RuntimeError("Something broke unexpectedly"))
    task_id = "task-unexpected-fail"
    req_id = "agent-err-3" # Define req_id
    mock_agent.tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)

    response = make_rpc_request(client, "tasks/get", params={"id": task_id}, req_id=req_id)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR # Caught by generic handler
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INTERNAL_ERROR
    assert "Internal server error: RuntimeError" in resp_data["error"]["message"]
    # --- Assert ID matches original request ID (generic handler preserves it) ---
    assert resp_data["id"] == req_id
    # --- END Assert ---

# ... (other tests remain the same) ...

# --- Test SSE Endpoint ---

@pytest.mark.asyncio
async def test_subscribe_success_yields_events(test_app: Tuple[MockAgent, TestClient]):
    """Test successful subscription yields configured SSE events."""
    mock_agent, client = test_app
    task_id = "sse-task-1"
    mock_agent.tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    now = datetime.datetime.now(datetime.timezone.utc)
    event1 = TaskStatusUpdateEvent(task_id=task_id, state=TaskState.WORKING, timestamp=now)
    event2 = TaskMessageEvent(task_id=task_id, message=Message(role="assistant", parts=[TextPart(content="Update")]), timestamp=now)
    mock_agent.configure_sse_events([event1, event2])

    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id="sse-1")

    # Check initial response is streaming
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")

    # Consume the stream (using TestClient's streaming support)
    content = response.content.decode('utf-8')
    lines = content.strip().split('\n\n') # Split by empty lines between events

    assert len(lines) >= 2 # Expect at least the two events

    # --- Parse JSON and check alias ---
    event1_data_str = lines[0].split("data: ", 1)[1]
    event1_data = json.loads(event1_data_str)
    assert "event: task_status" in lines[0]
    assert event1_data.get("taskId") == task_id # Check alias in parsed data
    assert event1_data.get("state") == "WORKING"

    event2_data_str = lines[1].split("data: ", 1)[1]
    event2_data = json.loads(event2_data_str)
    assert "event: task_message" in lines[1]
    assert event2_data.get("taskId") == task_id # Check alias in parsed data
    assert event2_data.get("message", {}).get("role") == "assistant"
    assert event2_data.get("message", {}).get("parts", [{}])[0].get("content") == "Update"

@pytest.mark.asyncio
async def test_subscribe_task_not_found(test_app: Tuple[MockAgent, TestClient]):
    """Test subscribe request for a non-existent task."""
    mock_agent, client = test_app
    task_id = "sse-not-found"
    req_id = "sse-err-1" # Define req_id
    # Do not add task_id to mock_agent.tasks

    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id=req_id)

    # The TaskNotFoundError should be caught *before* streaming now
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json() # Should be valid JSON now
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
    assert f"Task not found: {task_id}" in resp_data["error"]["message"]
    assert resp_data["id"] == req_id # ID should be preserved

@pytest.mark.asyncio
async def test_subscribe_generator_error(test_app: Tuple[MockAgent, TestClient]):
    """Test when the agent's subscribe handler itself raises an error."""
    mock_agent, client = test_app
    task_id = "sse-gen-err"
    mock_agent.tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    error_message = "Error during event generation"
    mock_agent.configure_subscribe_error(RuntimeError(error_message))

    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id="sse-err-2")

    # Check initial response indicates streaming
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")

    # Consume the stream - it should yield a single error event
    content = response.content.decode('utf-8')
    lines = content.strip().split('\n\n')

    assert len(lines) == 1
    assert "event: error" in lines[0]
    assert '"error": "stream_error"' in lines[0]
    assert f'"message": "Error generating events: RuntimeError: {error_message}"' in lines[0]
