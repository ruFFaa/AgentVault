import pytest
import uuid
import datetime
import json
import asyncio
import logging # Added import
from abc import ABC
from unittest.mock import patch, MagicMock, ANY, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List, Callable

# --- MODIFIED: Import FastAPI directly ---
from fastapi import FastAPI, status, Request, Response, HTTPException
# --- END MODIFIED ---
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse, JSONResponse
import pydantic # Import pydantic for ValidationError
# --- ADDED: Import pydantic_core ---
from pydantic_core import ValidationError
# --- END ADDED ---


# Import SDK components
from agentvault_server_sdk.agent import BaseA2AAgent
from agentvault_server_sdk.fastapi_integration import (
    create_a2a_router, SSEResponse, a2a_method,
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
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
        self.custom_bad_return_value: Any = None # For testing return validation


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

    def configure_custom_bad_return(self, value: Any):
        self.custom_bad_return_value = value

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
    async def custom_echo(self, message: str, extra_param: Optional[int] = None) -> str:
        """A simple echo method for testing decorators."""
        logging.info(f"Executing custom_echo with message: '{message}', extra: {extra_param}")
        if self.custom_echo_should_raise:
            raise self.custom_echo_should_raise
        return f"Echo: {message}" + (f" | Extra: {extra_param}" if extra_param is not None else "")

    @a2a_method("custom/bad_return")
    async def custom_bad_return(self, value: int) -> str: # Expects str return
        """Method designed to return an invalid type for testing."""
        logging.info(f"Executing custom_bad_return with value: {value}")
        # Return an int instead of the annotated str
        return self.custom_bad_return_value if self.custom_bad_return_value is not None else 12345


# --- Pytest Fixture ---

@pytest.fixture
def test_app() -> Tuple[MockAgent, TestClient]:
    """Creates a FastAPI app with the A2A router and exception handlers for testing."""
    mock_agent = MockAgent()
    task_store = InMemoryTaskStore()
    # Link the agent's task dict to the store for consistency in tests
    # In a real scenario, the agent would likely use the injected store directly
    task_store._tasks = mock_agent.tasks
    a2a_router = create_a2a_router(agent=mock_agent, prefix="/a2a", task_store=task_store)

    # Create the main app instance for testing
    app = FastAPI()
    app.include_router(a2a_router)

    # Register all handlers on the test app
    app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    app.add_exception_handler(ValueError, validation_exception_handler)
    app.add_exception_handler(TypeError, validation_exception_handler)
    # --- MODIFIED: Use correct ValidationError import ---
    app.add_exception_handler(ValidationError, validation_exception_handler)
    # --- END MODIFIED ---
    app.add_exception_handler(AgentServerError, agent_server_error_handler)
    app.add_exception_handler(RuntimeError, generic_exception_handler)
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

# Tests for Decorator Directly
def test_a2a_method_decorator_success():
    """Test applying decorator to async function attaches attribute."""
    method_name = "test/method"
    @a2a_method(method_name)
    async def my_async_handler(param1: str): pass

    assert hasattr(my_async_handler, "_a2a_method_name")
    assert getattr(my_async_handler, "_a2a_method_name") == method_name

def test_a2a_method_decorator_sync_fail():
    """Test applying decorator to sync function raises TypeError."""
    with pytest.raises(TypeError, match="must be an async function"):
        @a2a_method("test/sync_fail")
        def my_sync_handler(param1: str): pass

def test_a2a_method_decorator_empty_name_fail():
    """Test decorator raises ValueError for empty method name."""
    with pytest.raises(ValueError, match="requires a non-empty string"):
        a2a_method("")

def test_a2a_method_decorator_non_string_name_fail():
    """Test decorator raises ValueError for non-string method name."""
    with pytest.raises(ValueError, match="requires a non-empty string"):
        a2a_method(123) # type: ignore


# Tests for Decorated Method Routing
def test_decorated_method_routing_success(test_app: Tuple[MockAgent, TestClient]):
    """Test a request to a decorated method is routed correctly."""
    mock_agent, client = test_app
    req_id = "echo-req-1"
    params = {"message": "Hello Decorator!"}
    response = make_rpc_request(client, "custom/echo", params=params, req_id=req_id)

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data.get("id") == req_id
    assert resp_data.get("result") == "Echo: Hello Decorator!"

def test_decorated_method_routing_param_validation_fail(test_app: Tuple[MockAgent, TestClient]):
    """Test parameter validation failure for a decorated method."""
    mock_agent, client = test_app
    req_id = "echo-req-bad-param"
    # Send 'message' as an integer instead of string
    params = {"message": 12345}
    response = make_rpc_request(client, "custom/echo", params=params, req_id=req_id)

    assert response.status_code == status.HTTP_200_OK # JSON-RPC errors return 200
    resp_data = response.json()
    assert resp_data.get("id") == req_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Invalid parameters" in resp_data["error"]["message"]
    # Check Pydantic's error detail if possible
    assert "Input should be a valid string" in resp_data["error"]["message"]

def test_decorated_method_routing_return_validation_fail(test_app: Tuple[MockAgent, TestClient]):
    """Test return value validation failure for a decorated method."""
    mock_agent, client = test_app
    req_id = "bad-return-req"
    params = {"value": 10} # Correct input param type

    # Configure the mock agent to return an int instead of str
    mock_agent.configure_custom_bad_return(999)

    response = make_rpc_request(client, "custom/bad_return", params=params, req_id=req_id)

    # Return type validation errors currently result in 500 Internal Server Error
    # because it happens *after* the main request handling logic but before serialization.
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    resp_data = response.json()
    assert resp_data.get("id") == req_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INTERNAL_ERROR
    assert "Invalid return type" in resp_data["error"]["message"] # Check for specific message

def test_decorated_method_routing_not_found(test_app: Tuple[MockAgent, TestClient]):
    """Test calling a method name that is not decorated or standard."""
    mock_agent, client = test_app
    req_id = "not-found-req"
    response = make_rpc_request(client, "non/existent_method", params={}, req_id=req_id)

    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data.get("id") == req_id
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_METHOD_NOT_FOUND
    assert resp_data["error"]["message"] == "Method not found"

# --- MODIFIED: Refactored test to create app/client inside ---
def test_decorated_method_overrides_standard_if_named_same():
    """Test that a decorated method overrides a standard handle_ method if named identically."""
    # 1. Create a new agent instance specifically for this test
    agent_with_override = MockAgent()

    # 2. Define and attach the overriding decorated method *before* creating the router
    @a2a_method("tasks/get")
    async def custom_tasks_get(self, task_id: str) -> Dict: # Return dict instead of Task
        return {"id": task_id, "status": "overridden by decorator"}

    # Use MethodType to bind 'self' correctly if needed, or just setattr
    # setattr(agent_with_override, 'custom_tasks_get_handler', custom_tasks_get.__get__(agent_with_override, MockAgent))
    # Simpler: just assign the async function directly if it doesn't rely on 'self' state beyond what's passed in
    agent_with_override.custom_tasks_get_handler = custom_tasks_get.__get__(agent_with_override, MockAgent)


    # 3. Create the router using this specific agent instance
    task_store = InMemoryTaskStore()
    task_store._tasks = agent_with_override.tasks # Link store if needed
    a2a_router = create_a2a_router(agent=agent_with_override, prefix="/a2a", task_store=task_store)

    # 4. Create a new FastAPI app instance
    test_override_app = FastAPI()

    # 5. Add exception handlers (copy from fixture setup)
    test_override_app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    test_override_app.add_exception_handler(ValueError, validation_exception_handler)
    test_override_app.add_exception_handler(TypeError, validation_exception_handler)
    test_override_app.add_exception_handler(ValidationError, validation_exception_handler)
    test_override_app.add_exception_handler(AgentServerError, agent_server_error_handler)
    test_override_app.add_exception_handler(RuntimeError, generic_exception_handler)
    test_override_app.add_exception_handler(Exception, generic_exception_handler)

    # 6. Include the router
    test_override_app.include_router(a2a_router)

    # 7. Create a TestClient for this specific app
    client = TestClient(test_override_app)

    # 8. Run the test logic
    task_id = "task-override-test"
    agent_with_override.tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    req_id = "override-req"
    response = make_rpc_request(client, "tasks/get", params={"id": task_id}, req_id=req_id) # Use the new client

    # 9. Assertions
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data.get("id") == req_id
    assert "result" in resp_data
    # Check that the decorator's response was returned
    assert resp_data["result"] == {"id": task_id, "status": "overridden by decorator"}

# --- END MODIFIED ---


# Test agent raising specific AgentServerError
def test_agent_server_error(test_app: Tuple[MockAgent, TestClient]):
    mock_agent, client = test_app
    error_message = "Agent failed during processing"
    mock_agent.configure_error(AgentServerError(error_message))
    task_id = "task-agent-fail"
    req_id = "agent-err-1" # Define req_id
    mock_agent.tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)

    response = make_rpc_request(client, "tasks/get", params={"id": task_id}, req_id=req_id)
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_APP_ERROR
    assert f"Agent error: {error_message}" in resp_data["error"]["message"]
    assert resp_data["id"] == req_id # ID should be preserved

# Test agent raising TaskNotFoundError
def test_agent_task_not_found_error(test_app: Tuple[MockAgent, TestClient]):
    mock_agent, client = test_app
    task_id = "task-not-found-agent"
    req_id = "agent-err-2" # Define req_id
    mock_agent.configure_error(TaskNotFoundError(task_id=task_id))

    response = make_rpc_request(client, "tasks/get", params={"id": task_id}, req_id=req_id)
    assert response.status_code == status.HTTP_200_OK # JSON-RPC error
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_TASK_NOT_FOUND
    assert f"Task not found: {task_id}" in resp_data["error"]["message"]
    assert resp_data["id"] == req_id # ID should be preserved


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
    assert resp_data["id"] == req_id # ID should be preserved


# --- Test SSE Endpoint ---

@pytest.mark.asyncio
async def test_subscribe_success_yields_events(test_app: Tuple[MockAgent, TestClient]):
    """Test successful subscription yields configured SSE events."""
    mock_agent, client = test_app
    task_id = "sse-task-1"
    mock_agent.tasks[task_id] = TaskContext(task_id=task_id, current_state=TaskState.WORKING)
    now = datetime.datetime.now(datetime.timezone.utc)
    event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
    event2 = TaskMessageEvent(taskId=task_id, message=Message(role="assistant", parts=[TextPart(content="Update")]), timestamp=now)
    mock_agent.configure_sse_events([event1, event2])

    response = make_rpc_request(client, "tasks/sendSubscribe", params={"id": task_id}, req_id="sse-1")

    # Check initial response is streaming
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")

    # Consume the stream (using TestClient's streaming support)
    content = response.content.decode('utf-8')
    lines = content.strip().split('\n\n') # Split by empty lines between events

    assert len(lines) >= 2 # Expect at least the two events

    # Parse JSON and check alias
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
