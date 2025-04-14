import pytest
import asyncio
import datetime # Added datetime import
# --- ADDED: Import freezegun ---
from freezegun import freeze_time
# --- END ADDED ---
# --- REMOVED: MockerFixture import ---
# from pytest_mock import MockerFixture
# --- END REMOVED ---
from agentvault_server_sdk.state import InMemoryTaskStore, TaskContext, TaskState

# --- ADDED: Import models needed for tests ---
try:
    from agentvault.models import (
        TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent,
        Message, TextPart, Artifact
    )
    _MODELS_AVAILABLE_FOR_TEST = True
except ImportError:
    # Define placeholders if import fails
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    class Message: pass # type: ignore
    class TextPart: pass # type: ignore
    class Artifact: pass # type: ignore
    _MODELS_AVAILABLE_FOR_TEST = False

# Skip notification tests if models aren't available
pytestmark_notify = pytest.mark.skipif(not _MODELS_AVAILABLE_FOR_TEST, reason="Core agentvault models not available for notification tests")
# --- END ADDED ---


@pytest.fixture
def task_store() -> InMemoryTaskStore:
    """Provides a fresh InMemoryTaskStore for each test."""
    return InMemoryTaskStore()

@pytest.mark.asyncio
async def test_create_task_success(task_store: InMemoryTaskStore):
    """Test creating a new task."""
    task_id = "task-create-1"
    context = await task_store.create_task(task_id)
    assert isinstance(context, TaskContext)
    assert context.task_id == task_id
    assert context.current_state == TaskState.SUBMITTED
    assert task_id in task_store._tasks
    # --- ADDED: Check listener list initialized ---
    assert task_id in task_store._listeners
    assert task_store._listeners[task_id] == []
    # --- END ADDED ---


@pytest.mark.asyncio
async def test_create_task_already_exists(task_store: InMemoryTaskStore):
    """Test creating a task that already exists returns the existing one."""
    task_id = "task-exists-1"
    context1 = await task_store.create_task(task_id)
    context2 = await task_store.create_task(task_id) # Create again
    assert context1 is context2 # Should return the same instance
    assert len(task_store._tasks) == 1

@pytest.mark.asyncio
async def test_get_task_success(task_store: InMemoryTaskStore):
    """Test getting an existing task."""
    task_id = "task-get-1"
    created_context = await task_store.create_task(task_id)
    retrieved_context = await task_store.get_task(task_id)
    assert retrieved_context is created_context
    assert retrieved_context.task_id == task_id

@pytest.mark.asyncio
async def test_get_task_not_found(task_store: InMemoryTaskStore):
    """Test getting a non-existent task."""
    retrieved_context = await task_store.get_task("task-not-found")
    assert retrieved_context is None

@pytest.mark.asyncio
async def test_update_task_state_success(task_store: InMemoryTaskStore):
    """Test updating the state of an existing task."""
    task_id = "task-update-1"
    await task_store.create_task(task_id)
    updated_context = await task_store.update_task_state(task_id, TaskState.WORKING)
    assert updated_context is not None
    assert updated_context.current_state == TaskState.WORKING
    # Check internal state
    assert task_store._tasks[task_id].current_state == TaskState.WORKING

@pytest.mark.asyncio
async def test_update_task_state_not_found(task_store: InMemoryTaskStore):
    """Test updating the state of a non-existent task."""
    updated_context = await task_store.update_task_state("task-not-found", TaskState.FAILED)
    assert updated_context is None

# --- MODIFIED: Test for multiple state updates using freezegun context manager ---
@pytest.mark.asyncio
# --- REMOVED: Decorator ---
# @freeze_time("2024-01-01 12:00:00", tz_offset=0, tick=False)
# --- END REMOVED ---
async def test_update_state_multiple_times(task_store: InMemoryTaskStore):
    """Test updating state multiple times and checking timestamps."""
    task_id = "task-multi-update"
    start_time = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Use freeze_time as a context manager for initial creation
    with freeze_time(start_time) as freezer:
        context = await task_store.create_task(task_id)
        assert context.created_at == start_time
        assert context.updated_at == start_time
        original_updated_at = context.updated_at

        # First update
        time_update1 = start_time + datetime.timedelta(seconds=10)
        freezer.move_to(time_update1)
        context1 = await task_store.update_task_state(task_id, TaskState.WORKING)
        assert context1 is context # Ensure it's the same object
        assert context.current_state == TaskState.WORKING
        assert context.updated_at == time_update1
        updated_at_1 = context.updated_at # Capture timestamp after update 1

        # Second update
        time_update2 = start_time + datetime.timedelta(seconds=20)
        freezer.move_to(time_update2)
        context2 = await task_store.update_task_state(task_id, TaskState.COMPLETED)
        assert context2 is context
        assert context.current_state == TaskState.COMPLETED
        assert context.updated_at == time_update2
        updated_at_2 = context.updated_at # Capture timestamp after update 2

        # Third update (testing transition logic placeholder - currently allows any)
        time_update3 = start_time + datetime.timedelta(seconds=30)
        freezer.move_to(time_update3)
        context3 = await task_store.update_task_state(task_id, TaskState.WORKING)
        assert context3 is context
        assert context.current_state == TaskState.WORKING
        assert context.updated_at == time_update3
        updated_at_3 = context.updated_at # Capture timestamp after update 3

    # Assertions using captured timestamps
    assert updated_at_1 > original_updated_at
    assert updated_at_2 > updated_at_1
    assert updated_at_3 > updated_at_2
# --- END MODIFIED ---


@pytest.mark.asyncio
async def test_delete_task_success(task_store: InMemoryTaskStore):
    """Test deleting an existing task."""
    task_id = "task-delete-1"
    await task_store.create_task(task_id)
    # Add a listener to ensure it gets cleaned up
    q = asyncio.Queue()
    await task_store.add_listener(task_id, q)
    assert task_id in task_store._tasks
    assert task_id in task_store._listeners

    deleted = await task_store.delete_task(task_id)
    assert deleted is True
    assert task_id not in task_store._tasks
    assert task_id not in task_store._listeners # Check listeners also removed
    # Verify getting it now returns None
    assert await task_store.get_task(task_id) is None

@pytest.mark.asyncio
async def test_delete_task_not_found(task_store: InMemoryTaskStore):
    """Test deleting a non-existent task."""
    deleted = await task_store.delete_task("task-not-found")
    assert deleted is False

# --- Tests for Listener Management ---

@pytest.mark.asyncio
async def test_add_get_remove_listener(task_store: InMemoryTaskStore):
    """Test adding, getting, and removing listeners."""
    task_id = "task-listener-1"
    q1 = asyncio.Queue()
    q2 = asyncio.Queue()

    # Task doesn't exist initially, listeners should be empty
    assert await task_store.get_listeners(task_id) == []

    # Add first listener (task should be implicitly created if needed by store logic)
    await task_store.add_listener(task_id, q1)
    listeners = await task_store.get_listeners(task_id)
    assert listeners == [q1]

    # Add second listener
    await task_store.add_listener(task_id, q2)
    listeners = await task_store.get_listeners(task_id)
    assert q1 in listeners
    assert q2 in listeners
    assert len(listeners) == 2

    # Add first listener again (should not duplicate)
    await task_store.add_listener(task_id, q1)
    listeners = await task_store.get_listeners(task_id)
    assert len(listeners) == 2

    # Remove first listener
    await task_store.remove_listener(task_id, q1)
    listeners = await task_store.get_listeners(task_id)
    assert listeners == [q2]

    # Remove second listener
    await task_store.remove_listener(task_id, q2)
    listeners = await task_store.get_listeners(task_id)
    assert listeners == []

    # Remove listener that doesn't exist
    await task_store.remove_listener(task_id, q1) # Should not raise error
    listeners = await task_store.get_listeners(task_id)
    assert listeners == []

@pytest.mark.asyncio
async def test_remove_listener_non_existent_task(task_store: InMemoryTaskStore):
    """Test removing listener from a task ID that never had listeners."""
    q = asyncio.Queue()
    await task_store.remove_listener("non-existent-task", q) # Should not raise error
    assert await task_store.get_listeners("non-existent-task") == []

# --- Tests for Notification Methods ---

@pytestmark_notify
@pytest.mark.asyncio
async def test_notify_status_update(task_store: InMemoryTaskStore):
    """Test notifying listeners about status updates."""
    task_id = "task-notify-status"
    await task_store.create_task(task_id)
    q1 = asyncio.Queue()
    q2 = asyncio.Queue()
    await task_store.add_listener(task_id, q1)
    await task_store.add_listener(task_id, q2)

    # Notify
    new_state = TaskState.WORKING
    status_message = "Processing started"
    await task_store.notify_status_update(task_id, new_state, status_message)

    # Verify queues received the event
    event1 = q1.get_nowait()
    event2 = q2.get_nowait()

    assert isinstance(event1, TaskStatusUpdateEvent)
    # --- MODIFIED: Access using field name ---
    assert event1.task_id == task_id
    # --- END MODIFIED ---
    assert event1.state == new_state
    assert event1.message == status_message
    assert isinstance(event1.timestamp, datetime.datetime)

    assert event1 == event2 # Events should be identical

@pytestmark_notify
@pytest.mark.asyncio
async def test_notify_message_event(task_store: InMemoryTaskStore):
    """Test notifying listeners about message events."""
    task_id = "task-notify-msg"
    await task_store.create_task(task_id)
    q1 = asyncio.Queue()
    await task_store.add_listener(task_id, q1)

    # Create a message
    test_message = Message(role="assistant", parts=[TextPart(content="Hello!")])

    # Notify
    await task_store.notify_message_event(task_id, test_message)

    # Verify queue
    event = q1.get_nowait()
    assert isinstance(event, TaskMessageEvent)
    # --- MODIFIED: Access using field name ---
    assert event.task_id == task_id
    # --- END MODIFIED ---
    assert event.message == test_message
    assert isinstance(event.timestamp, datetime.datetime)

@pytestmark_notify
@pytest.mark.asyncio
async def test_notify_artifact_event(task_store: InMemoryTaskStore):
    """Test notifying listeners about artifact events."""
    task_id = "task-notify-artifact"
    await task_store.create_task(task_id)
    q1 = asyncio.Queue()
    await task_store.add_listener(task_id, q1)

    # Create an artifact
    test_artifact = Artifact(id="art-1", type="file", url="http://example.com/file.txt")

    # Notify
    await task_store.notify_artifact_event(task_id, test_artifact)

    # Verify queue
    event = q1.get_nowait()
    assert isinstance(event, TaskArtifactUpdateEvent)
    # --- MODIFIED: Access using field name ---
    assert event.task_id == task_id
    # --- END MODIFIED ---
    assert event.artifact == test_artifact
    assert isinstance(event.timestamp, datetime.datetime)

@pytestmark_notify
@pytest.mark.asyncio
async def test_notify_no_listeners(task_store: InMemoryTaskStore):
    """Test that notifying with no listeners doesn't raise errors."""
    task_id = "task-notify-none"
    await task_store.create_task(task_id) # Task exists, but no listeners added

    # Call notify methods - should complete without error
    await task_store.notify_status_update(task_id, TaskState.FAILED, "Error occurred")
    await task_store.notify_message_event(task_id, Message(role="system", parts=[TextPart(content="System message")]))
    await task_store.notify_artifact_event(task_id, Artifact(id="art-2", type="log", content="Log data"))

    # No queues to check, just ensure no exceptions were raised

@pytestmark_notify
@pytest.mark.asyncio
async def test_update_task_state_notifies_listeners(task_store: InMemoryTaskStore):
    """Test that update_task_state correctly triggers notify_status_update."""
    task_id = "task-update-notify"
    await task_store.create_task(task_id)
    q1 = asyncio.Queue()
    await task_store.add_listener(task_id, q1)

    # Update state
    new_state = TaskState.FAILED
    await task_store.update_task_state(task_id, new_state)

    # Verify queue received the status update event
    event = q1.get_nowait()
    assert isinstance(event, TaskStatusUpdateEvent)
    # --- MODIFIED: Access using field name ---
    assert event.task_id == task_id
    # --- END MODIFIED ---
    assert event.state == new_state
    assert event.message is None # No message passed to update_task_state
