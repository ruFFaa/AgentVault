import pytest
import uuid
import asyncio
from unittest.mock import MagicMock

# Import the agent to test
from agentvault_testing_utils.agents import EchoAgent, EchoTaskData

# Import necessary models and exceptions (with fallback)
try:
    from agentvault.models import Message, TextPart, Task, TaskState, A2AEvent, TaskStatusUpdateEvent, TaskMessageEvent
    from agentvault_server_sdk.exceptions import TaskNotFoundError
    _IMPORTS_AVAILABLE = True
except ImportError:
    pytest.skip("Core agentvault or SDK components not available, skipping EchoAgent tests", allow_module_level=True)
    # Define placeholders if needed, though skip should prevent execution
    class Message: pass # type: ignore
    class TextPart: pass # type: ignore
    class Task: pass # type: ignore
    class TaskState: # type: ignore
        SUBMITTED="SUBMITTED"; WORKING="WORKING"; COMPLETED="COMPLETED"; CANCELED="CANCELED" # type: ignore
    class A2AEvent: pass # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskNotFoundError(Exception): pass # type: ignore


@pytest.fixture
def echo_agent() -> EchoAgent:
    """Provides a fresh EchoAgent instance."""
    return EchoAgent()

@pytest.fixture
def sample_message() -> Message:
    """Provides a sample Message object."""
    return Message(role="user", parts=[TextPart(content="Hello echo")])

# --- Test handle_task_send ---

@pytest.mark.asyncio
async def test_send_new_task(echo_agent: EchoAgent, sample_message: Message):
    """Test sending a message to initiate a new task."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    assert isinstance(task_id, str)
    assert task_id.startswith("echo-task-")
    assert task_id in echo_agent._tasks
    assert echo_agent._tasks[task_id].messages == [sample_message]
    assert echo_agent._tasks[task_id].state == TaskState.SUBMITTED

@pytest.mark.asyncio
async def test_send_existing_task(echo_agent: EchoAgent, sample_message: Message):
    """Test sending a message to an existing task."""
    # Create task first
    initial_message = Message(role="user", parts=[TextPart(content="Initial")])
    task_id = await echo_agent.handle_task_send(task_id=None, message=initial_message)
    assert len(echo_agent._tasks[task_id].messages) == 1

    # Send second message
    returned_id = await echo_agent.handle_task_send(task_id=task_id, message=sample_message)
    assert returned_id == task_id
    assert len(echo_agent._tasks[task_id].messages) == 2
    assert echo_agent._tasks[task_id].messages[0] == initial_message
    assert echo_agent._tasks[task_id].messages[1] == sample_message

@pytest.mark.asyncio
async def test_send_non_existent_task(echo_agent: EchoAgent, sample_message: Message):
    """Test sending a message to a non-existent task ID raises error."""
    with pytest.raises(TaskNotFoundError):
        await echo_agent.handle_task_send(task_id="non-existent", message=sample_message)

# --- Test handle_task_get ---

@pytest.mark.asyncio
async def test_get_task_success(echo_agent: EchoAgent, sample_message: Message):
    """Test getting the state of an existing task."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    task_data = await echo_agent.handle_task_get(task_id)

    assert isinstance(task_data, Task)
    assert task_data.id == task_id
    assert task_data.state == TaskState.SUBMITTED # Initial state
    assert task_data.messages == [sample_message]

@pytest.mark.asyncio
async def test_get_task_not_found(echo_agent: EchoAgent):
    """Test getting a non-existent task raises error."""
    with pytest.raises(TaskNotFoundError):
        await echo_agent.handle_task_get("non-existent")

# --- Test handle_task_cancel ---

@pytest.mark.asyncio
async def test_cancel_task_success(echo_agent: EchoAgent, sample_message: Message):
    """Test canceling an active task."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    assert echo_agent._tasks[task_id].state == TaskState.SUBMITTED

    result = await echo_agent.handle_task_cancel(task_id)
    assert result is True
    assert echo_agent._tasks[task_id].state == TaskState.CANCELED

@pytest.mark.asyncio
async def test_cancel_task_already_terminal(echo_agent: EchoAgent, sample_message: Message):
    """Test canceling an already completed/canceled task."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    echo_agent._tasks[task_id].state = TaskState.COMPLETED # Manually set state

    result = await echo_agent.handle_task_cancel(task_id)
    assert result is False # Indicates already terminal
    assert echo_agent._tasks[task_id].state == TaskState.COMPLETED # State remains unchanged

@pytest.mark.asyncio
async def test_cancel_task_not_found(echo_agent: EchoAgent):
    """Test canceling a non-existent task raises error."""
    with pytest.raises(TaskNotFoundError):
        await echo_agent.handle_task_cancel("non-existent")

# --- Test handle_subscribe_request ---

@pytest.mark.asyncio
async def test_subscribe_success(echo_agent: EchoAgent, sample_message: Message):
    """Test the SSE event stream generation."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    received_events = []
    async for event in echo_agent.handle_subscribe_request(task_id):
        received_events.append(event)

    assert len(received_events) == 3 # WORKING status, MESSAGE echo, COMPLETED status
    assert isinstance(received_events[0], TaskStatusUpdateEvent)
    assert received_events[0].state == TaskState.WORKING
    assert isinstance(received_events[1], TaskMessageEvent)
    assert received_events[1].message.role == "assistant"
    assert "Echo: Hello echo" in received_events[1].message.parts[0].content
    assert isinstance(received_events[2], TaskStatusUpdateEvent)
    assert received_events[2].state == TaskState.COMPLETED

    # Check internal state was updated
    assert echo_agent._tasks[task_id].state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_subscribe_task_not_found(echo_agent: EchoAgent):
    """Test subscribing to a non-existent task raises error."""
    with pytest.raises(TaskNotFoundError):
        async for _ in echo_agent.handle_subscribe_request("non-existent"):
            pass # pragma: no cover
