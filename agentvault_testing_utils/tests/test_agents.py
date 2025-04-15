import pytest
import uuid
import asyncio
# --- ADDED: Import datetime ---
import datetime
# --- END ADDED ---
from unittest.mock import MagicMock, patch # Added patch
from typing import Any

# Import the agent to test
from agentvault_testing_utils.agents import EchoAgent


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
    # Note: This will now use the default InMemoryTaskStore internally
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
    # Verify task exists in the *store* now
    task_context = await echo_agent.task_store.get_task(task_id)
    assert task_context is not None
    assert task_context.task_id == task_id
    assert task_context.current_state == TaskState.SUBMITTED
    # Note: We are not testing message storage within the context in this simple version

@pytest.mark.asyncio
async def test_send_existing_task(echo_agent: EchoAgent, sample_message: Message):
    """Test sending a message to an existing task."""
    # Create task first
    initial_message = Message(role="user", parts=[TextPart(content="Initial")])
    task_id = await echo_agent.handle_task_send(task_id=None, message=initial_message)
    task_context_before = await echo_agent.task_store.get_task(task_id)
    assert task_context_before is not None

    # Send second message
    returned_id = await echo_agent.handle_task_send(task_id=task_id, message=sample_message)
    assert returned_id == task_id
    task_context_after = await echo_agent.task_store.get_task(task_id)
    assert task_context_after is not None
    # Check timestamp updated (or state if send logic changes state)
    assert task_context_after.updated_at >= task_context_before.updated_at

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
    # Manually update state via store for testing get
    await echo_agent.task_store.update_task_state(task_id, TaskState.WORKING)

    task_data = await echo_agent.handle_task_get(task_id)

    assert isinstance(task_data, Task)
    assert task_data.id == task_id
    assert task_data.state == TaskState.WORKING # Check the updated state
    assert task_data.messages == [] # EchoAgent doesn't store messages in context

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
    await echo_agent.task_store.update_task_state(task_id, TaskState.WORKING) # Set to working first
    task_context = await echo_agent.task_store.get_task(task_id)
    assert task_context.current_state == TaskState.WORKING

    result = await echo_agent.handle_task_cancel(task_id)
    assert result is True
    # Verify state in store
    task_context_after = await echo_agent.task_store.get_task(task_id)
    assert task_context_after.current_state == TaskState.CANCELED

@pytest.mark.asyncio
async def test_cancel_task_already_terminal(echo_agent: EchoAgent, sample_message: Message):
    """Test canceling an already completed/canceled task."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    # --- MODIFIED: Use valid state transitions ---
    # Set state to terminal using valid transitions first
    await echo_agent.task_store.update_task_state(task_id, TaskState.WORKING)
    await echo_agent.task_store.update_task_state(task_id, TaskState.COMPLETED) # Now this transition is valid
    # --- END MODIFIED ---

    result = await echo_agent.handle_task_cancel(task_id)
    assert result is False # Indicates already terminal
    # Verify state in store remains unchanged
    task_context_after = await echo_agent.task_store.get_task(task_id)
    assert task_context_after.current_state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_cancel_task_not_found(echo_agent: EchoAgent):
    """Test canceling a non-existent task raises error."""
    with pytest.raises(TaskNotFoundError):
        await echo_agent.handle_task_cancel("non-existent")

# --- Test handle_subscribe_request ---

@pytest.mark.asyncio
async def test_subscribe_success_triggers_notifications(echo_agent: EchoAgent, sample_message: Message):
    """Test the subscribe handler triggers store notifications."""
    task_id = await echo_agent.handle_task_send(task_id=None, message=sample_message)
    listener_queue = asyncio.Queue()
    await echo_agent.task_store.add_listener(task_id, listener_queue)

    # Run the subscribe handler (it doesn't yield directly anymore)
    # We run it in the background as it now completes quickly after triggering store updates
    subscribe_task = asyncio.create_task(anext(echo_agent.handle_subscribe_request(task_id), None))


    # Check the listener queue for expected events triggered by the store
    received_events = []
    try:
        # Event 1: WORKING status
        event1 = await asyncio.wait_for(listener_queue.get(), timeout=0.5)
        received_events.append(event1)
        assert isinstance(event1, TaskStatusUpdateEvent)
        assert event1.state == TaskState.WORKING

        # Event 2: MESSAGE echo
        event2 = await asyncio.wait_for(listener_queue.get(), timeout=0.5)
        received_events.append(event2)
        assert isinstance(event2, TaskMessageEvent)
        assert event2.message.role == "assistant"
        # Note: Echo content might be generic now as original message isn't stored
        assert "Echo response for task" in event2.message.parts[0].content

        # Event 3: COMPLETED status
        event3 = await asyncio.wait_for(listener_queue.get(), timeout=0.5)
        received_events.append(event3)
        assert isinstance(event3, TaskStatusUpdateEvent)
        assert event3.state == TaskState.COMPLETED

    except asyncio.TimeoutError:
        pytest.fail(f"Timeout waiting for SSE events. Received: {received_events}")
    finally:
        # Ensure the background task finishes (it should have already)
        await asyncio.wait_for(subscribe_task, timeout=0.1)


    # Check final state in store
    task_context = await echo_agent.task_store.get_task(task_id)
    assert task_context.current_state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_subscribe_task_not_found(echo_agent: EchoAgent):
    """Test subscribing to a non-existent task raises error."""
    with pytest.raises(TaskNotFoundError):
        async for _ in echo_agent.handle_subscribe_request("non-existent"):
            pass # pragma: no cover

# Helper to iterate async generator fully
async def anext(generator, default=None):
    try:
        return await generator.__anext__()
    except StopAsyncIteration:
        return default
