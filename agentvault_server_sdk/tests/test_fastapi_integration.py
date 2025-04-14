import pytest
import uuid
import datetime
import json
import asyncio
# --- MODIFIED: Import AsyncMock, Tuple ---
from unittest.mock import patch, MagicMock, ANY, AsyncMock
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List # Added AsyncGenerator, List
# --- END MODIFIED ---

from fastapi import FastAPI, status
from fastapi.testclient import TestClient # Import sync client
# --- ADDED: Import StreamingResponse for SSEResponse ---
from fastapi.responses import StreamingResponse
# --- END ADDED ---


# Import SDK components
from agentvault_server_sdk.agent import BaseA2AAgent
# --- MODIFIED: Import SSEResponse ---
from agentvault_server_sdk.fastapi_integration import create_a2a_router, SSEResponse, JSONRPC_INVALID_PARAMS, JSONRPC_METHOD_NOT_FOUND, JSONRPC_PARSE_ERROR, JSONRPC_INVALID_REQUEST, JSONRPC_APP_ERROR, JSONRPC_INTERNAL_ERROR
# --- END MODIFIED ---


# Import core library models and exceptions
try:
    from agentvault.models import (
        Message, Task, TaskState, TextPart, A2AEvent, TaskSendResult, GetTaskResult, TaskCancelResult,
        # --- ADDED: Import specific event types for mapping ---
        TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent, Artifact
        # --- END ADDED ---
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
    # --- ADDED: Placeholders for event types ---
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    class Artifact: pass # type: ignore
    # --- END ADDED ---


# --- Mock Agent Implementation ---

class MockAgent(BaseA2AAgent):
    """A mock agent for testing the FastAPI router integration."""
    def __init__(self):
        super().__init__()
        self.tasks: Dict[str, Task] = {}
        self.should_raise: Optional[Exception] = None
        self.last_received_message: Optional[Message] = None
        self.last_task_id_handled: Optional[str] = None
        self.cancel_result = True # Default cancel success
        # --- ADDED: For SSE testing ---
        self.sse_events_to_yield: List[A2AEvent] = []
        # --- END ADDED ---

    def configure_error(self, error: Optional[Exception]):
        self.should_raise = error

    def configure_cancel_result(self, result: bool):
        self.cancel_result = result

    # --- ADDED: Method to configure SSE events ---
    def configure_sse_events(self, events: List[A2AEvent]):
        self.sse_events_to_yield = events
    # --- END ADDED ---

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        if self.should_raise: raise self.should_raise
        self.last_received_message = message
        if task_id:
            self.last_task_id_handled = task_id
            # Simulate adding message to existing task
            if task_id in self.tasks:
                self.tasks[task_id].messages.append(message)
            return task_id
        else:
            new_id = f"task-{uuid.uuid4()}"
            self.last_task_id_handled = new_id
            # Simulate creating a new task
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
            raise A2AError(f"Mock Task not found: {task_id}") # Simulate agent not finding task
        return task

    async def handle_task_cancel(self, task_id: str) -> bool:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        if task_id not in self.tasks:
             raise A2AError(f"Mock Task not found for cancellation: {task_id}")
        # Simulate marking task as canceled
        self.tasks[task_id].state = TaskState.CANCELED
        return self.cancel_result

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        if self.should_raise: raise self.should_raise
        self.last_task_id_handled = task_id
        if task_id not in self.tasks:
             raise A2AError(f"Mock Task not found for subscription: {task_id}")

        # --- MODIFIED: Yield configured events ---
        for event in self.sse_events_to_yield:
            yield event
            await asyncio.sleep(0.01) # Small delay between events
        # --- END MODIFIED ---


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

def test_tasks_send_success(test_app: Tuple[MockAgent, TestClient]):
    """Test successful task initiation via tasks/send."""
    mock_agent, client = test_app
    message = Message(role="user", parts=[TextPart(content="init")])
    params = {"message": message.model_dump(mode='json')}
    response = make_rpc_request(client, "tasks/send", params, req_id="send-1")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data.get("jsonrpc") == "2.0"
    assert resp_data.get("id") == "send-1"
    assert "result" in resp_data
    assert "error" not in resp_data
    result = TaskSendResult.model_validate(resp_data["result"])
    assert isinstance(result.id, str)
    assert result.id.startswith("task-")
    assert mock_agent.last_received_message.role == "user"

def test_tasks_get_success(test_app: Tuple[MockAgent, TestClient]):
    """Test successful task retrieval via tasks/get."""
    mock_agent, client = test_app
    # Pre-populate a task
    task_id = "task-get-test"
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_task = Task(id=task_id, state=TaskState.WORKING, createdAt=now, updatedAt=now, messages=[], artifacts=[])
    mock_agent.tasks[task_id] = mock_task

    params = {"id": task_id}
    response = make_rpc_request(client, "tasks/get", params, req_id="get-1")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data.get("jsonrpc") == "2.0"
    assert resp_data.get("id") == "get-1"
    assert "result" in resp_data
    assert "error" not in resp_data
    # Result should be the Task object itself
    result_task = Task.model_validate(resp_data["result"])
    assert result_task.id == task_id
    assert result_task.state == TaskState.WORKING

def test_tasks_cancel_success(test_app: Tuple[MockAgent, TestClient]):
    """Test successful task cancellation via tasks/cancel."""
    mock_agent, client = test_app
    # Pre-populate a task
    task_id = "task-cancel-test"
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_task = Task(id=task_id, state=TaskState.WORKING, createdAt=now, updatedAt=now, messages=[], artifacts=[])
    mock_agent.tasks[task_id] = mock_task
    mock_agent.configure_cancel_result(True) # Ensure mock returns True

    params = {"id": task_id}
    response = make_rpc_request(client, "tasks/cancel", params, req_id="cancel-1")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data.get("jsonrpc") == "2.0"
    assert resp_data.get("id") == "cancel-1"
    assert "result" in resp_data
    assert "error" not in resp_data
    result = TaskCancelResult.model_validate(resp_data["result"])
    assert result.success is True
    assert mock_agent.tasks[task_id].state == TaskState.CANCELED # Check mock state changed

def test_invalid_json(test_app: Tuple[MockAgent, TestClient]):
    """Test sending invalid JSON."""
    _, client = test_app
    response = client.post("/a2a/", content="{invalid json")
    assert response.status_code == status.HTTP_200_OK # JSON-RPC errors return 200
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_PARSE_ERROR
    assert resp_data["id"] is None # ID couldn't be parsed

def test_invalid_request_not_dict(test_app: Tuple[MockAgent, TestClient]):
    """Test sending a JSON list instead of an object."""
    _, client = test_app
    response = client.post("/a2a/", json=[1, 2, 3])
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_REQUEST
    assert "Payload must be a JSON object" in resp_data["error"]["message"]
    assert resp_data["id"] is None

def test_invalid_request_missing_method(test_app: Tuple[MockAgent, TestClient]):
    """Test request missing the 'method' field."""
    _, client = test_app
    payload = {"jsonrpc": "2.0", "params": {}, "id": "err-1"}
    response = client.post("/a2a/", json=payload)
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_REQUEST
    assert "'method' is required" in resp_data["error"]["message"]
    assert resp_data["id"] == "err-1"

def test_invalid_request_missing_id(test_app: Tuple[MockAgent, TestClient]):
    """Test request missing the 'id' field."""
    _, client = test_app
    payload = {"jsonrpc": "2.0", "method": "tasks/get", "params": {}}
    response = client.post("/a2a/", json=payload)
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_REQUEST
    assert "'id' is missing" in resp_data["error"]["message"]
    assert resp_data["id"] is None

def test_method_not_found(test_app: Tuple[MockAgent, TestClient]):
    """Test calling an unknown method."""
    _, client = test_app
    response = make_rpc_request(client, "unknown/method", params={}, req_id="nf-1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_METHOD_NOT_FOUND
    assert resp_data["id"] == "nf-1"

def test_invalid_params_send_not_dict(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/send with params not being a dictionary."""
    _, client = test_app
    response = make_rpc_request(client, "tasks/send", params=[], req_id="ip-send-1") # Send list
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Input should be a valid dictionary" in resp_data["error"]["message"]
    assert resp_data["id"] == "ip-send-1"

def test_invalid_params_send_missing_message(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/send with params missing the 'message' field."""
    _, client = test_app
    response = make_rpc_request(client, "tasks/send", params={"id": "abc"}, req_id="ip-send-2")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Field required" in resp_data["error"]["message"] # Pydantic validation error
    assert "message" in resp_data["error"]["message"]
    assert resp_data["id"] == "ip-send-2"

def test_invalid_params_get_missing_id(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/get with params missing the 'id' field."""
    _, client = test_app
    response = make_rpc_request(client, "tasks/get", params={}, req_id="ip-get-1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Field required" in resp_data["error"]["message"]
    assert "'id'" in resp_data["error"]["message"]
    assert resp_data["id"] == "ip-get-1"

def test_invalid_params_cancel_wrong_id_type(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/cancel with 'id' field having the wrong type."""
    _, client = test_app
    response = make_rpc_request(client, "tasks/cancel", params={"id": 123}, req_id="ip-cancel-1")
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["error"]["code"] == JSONRPC_INVALID_PARAMS
    assert "Input should be a valid string" in resp_data["error"]["message"]
    assert resp_data["id"] == "ip-cancel-1"

def test_agent_handler_a2a_error(test_app: Tuple[MockAgent, TestClient]):
    """Test when the agent handler raises a specific A2AError."""
    mock_agent, client = test_app
    error_message = "Task failed internally"
    mock_agent.configure_error(A2AError(error_message))

    message = Message(role="user", parts=[TextPart(content="cause error")])
    params = {"message": message.model_dump(mode='json')}
    response = make_rpc_request(client, "tasks/send", params, req_id="agent-err-1")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert "result" not in resp_data
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_APP_ERROR
    assert error_message in resp_data["error"]["message"]
    assert resp_data["id"] == "agent-err-1"

def test_agent_handler_unexpected_error(test_app: Tuple[MockAgent, TestClient]):
    """Test when the agent handler raises an unexpected generic Exception."""
    mock_agent, client = test_app
    error_message = "Something completely unexpected broke"
    mock_agent.configure_error(ValueError(error_message)) # Use ValueError as example

    params = {"id": "task-unexpected"}
    response = make_rpc_request(client, "tasks/get", params, req_id="agent-err-2")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert "result" not in resp_data
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INTERNAL_ERROR
    assert "Internal agent error: ValueError" in resp_data["error"]["message"]
    assert resp_data["id"] == "agent-err-2"

# --- ADDED: SSE Unit Tests (Testing SSEResponse directly) ---

@pytest.mark.asyncio
async def test_sse_response_formatting():
    """Unit test the SSE formatting logic."""
    now = datetime.datetime.now(datetime.timezone.utc)
    task_id = "sse-task-1"

    async def event_generator():
        yield TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
        yield TaskMessageEvent(
            taskId=task_id,
            message=Message(role="assistant", parts=[TextPart(content="Hello there!")]),
            timestamp=now
        )
        yield TaskArtifactUpdateEvent(
            taskId=task_id,
            artifact=Artifact(id="art-1", type="file", url="http://example.com/file.txt"),
            timestamp=now
        )
        yield {"unexpected": "item"} # Simulate unknown event type

    sse_resp = SSEResponse(content=event_generator())
    # Access the internal publisher directly for unit testing
    publisher = sse_resp.body_iterator # type: ignore

    results = []
    async for chunk in publisher:
        results.append(chunk.decode('utf-8'))

    full_response = "".join(results)

    # Assertions on the formatted string
    assert f"event: task_status\ndata: {{\"taskId\":\"{task_id}\",\"state\":\"WORKING\",\"timestamp\":\"{now.isoformat().replace('+00:00', 'Z')}\",\"message\":null}}\n\n" in full_response
    assert f"event: task_message\ndata: {{\"taskId\":\"{task_id}\",\"message\":{{\"role\":\"assistant\",\"parts\":[{{\"type\":\"text\",\"content\":\"Hello there!\"}}],\"metadata\":null}},\"timestamp\":\"{now.isoformat().replace('+00:00', 'Z')}\"}}\n\n" in full_response
    assert f"event: task_artifact\ndata: {{\"taskId\":\"{task_id}\",\"artifact\":{{\"id\":\"art-1\",\"type\":\"file\",\"content\":null,\"url\":\"http://example.com/file.txt\",\"mediaType\":null,\"metadata\":null}},\"timestamp\":\"{now.isoformat().replace('+00:00', 'Z')}\"}}\n\n" in full_response
    # Check that the unknown event was skipped (not present in output)
    assert "unexpected" not in full_response

@pytest.mark.asyncio
async def test_sse_response_empty_generator():
    """Test SSEResponse with an empty generator."""
    async def empty_gen():
        if False: yield # pragma: no cover

    sse_resp = SSEResponse(content=empty_gen())
    publisher = sse_resp.body_iterator # type: ignore
    results = [chunk async for chunk in publisher]
    assert len(results) == 0

@pytest.mark.asyncio
async def test_sse_response_generator_error(caplog):
    """Test SSEResponse when the source generator raises an error."""
    async def error_gen():
        yield TaskStatusUpdateEvent(taskId="t1", state=TaskState.WORKING, timestamp=datetime.datetime.now())
        raise ValueError("Generator failed!")

    sse_resp = SSEResponse(content=error_gen())
    publisher = sse_resp.body_iterator # type: ignore

    results = []
    with caplog.at_level(logging.ERROR):
        async for chunk in publisher:
            results.append(chunk.decode('utf-8'))

    assert len(results) == 1 # Should yield the first event
    assert "Error in source event generator for SSE: Generator failed!" in caplog.text


# --- ADDED: SSE Integration Tests (Testing the endpoint) ---

def test_tasks_send_subscribe_success(test_app: Tuple[MockAgent, TestClient]):
    """Test successful subscription request."""
    mock_agent, client = test_app
    task_id = "task-sub-test"
    # Pre-populate task so subscribe doesn't fail finding it
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_agent.tasks[task_id] = Task(id=task_id, state=TaskState.WORKING, createdAt=now, updatedAt=now, messages=[], artifacts=[])

    params = {"id": task_id}
    # Use stream=True with TestClient
    with client.stream("POST", "/a2a/", json={"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": params, "id": "sub-1"}) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Consume the stream immediately to avoid blocking issues in tests
        response.read()

def test_tasks_send_subscribe_stream_content(test_app: Tuple[MockAgent, TestClient]):
    """Test the actual content streamed via SSE."""
    mock_agent, client = test_app
    task_id = "task-stream-content"
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_agent.tasks[task_id] = Task(id=task_id, state=TaskState.WORKING, createdAt=now, updatedAt=now, messages=[], artifacts=[])

    # Configure mock agent to yield specific events
    events_to_yield = [
        TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now),
        TaskMessageEvent(taskId=task_id, message=Message(role="assistant", parts=[TextPart(content="Streamed Message")]), timestamp=now)
    ]
    mock_agent.configure_sse_events(events_to_yield)

    params = {"id": task_id}
    expected_sse_parts = [
        f"event: task_status\ndata: {events_to_yield[0].model_dump_json(by_alias=True)}\n\n",
        f"event: task_message\ndata: {events_to_yield[1].model_dump_json(by_alias=True)}\n\n",
    ]

    received_content = b""
    with client.stream("POST", "/a2a/", json={"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": params, "id": "sub-2"}) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Read the streamed bytes
        for chunk in response.iter_bytes():
            received_content += chunk

    decoded_content = received_content.decode('utf-8')
    # Check if expected parts are present (order might vary slightly with async sleeps)
    for part in expected_sse_parts:
        assert part in decoded_content

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
    """Test tasks/sendSubscribe when agent handler raises A2AError."""
    mock_agent, client = test_app
    task_id = "task-sub-fail"
    mock_agent.configure_error(A2AError("Subscription failed"))

    params = {"id": task_id}
    response = make_rpc_request(client, "tasks/sendSubscribe", params=params, req_id="sub-err-1")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert "result" not in resp_data
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_APP_ERROR
    assert "Subscription failed" in resp_data["error"]["message"]
    assert resp_data["id"] == "sub-err-1"

def test_tasks_send_subscribe_agent_unexpected_error(test_app: Tuple[MockAgent, TestClient]):
    """Test tasks/sendSubscribe when agent handler raises generic Exception."""
    mock_agent, client = test_app
    task_id = "task-sub-fail-unexpected"
    mock_agent.configure_error(RuntimeError("Something broke"))

    params = {"id": task_id}
    response = make_rpc_request(client, "tasks/sendSubscribe", params=params, req_id="sub-err-2")

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert "result" not in resp_data
    assert "error" in resp_data
    assert resp_data["error"]["code"] == JSONRPC_INTERNAL_ERROR
    assert "Internal agent error: RuntimeError" in resp_data["error"]["message"]
    assert resp_data["id"] == "sub-err-2"
