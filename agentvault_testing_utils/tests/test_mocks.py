import pytest
import asyncio
import datetime
from unittest.mock import MagicMock, call, AsyncMock

# Import the mock client
from agentvault_testing_utils.mocks import MockAgentVaultClient

# Import core types for type hints and creating test data
try:
    from agentvault.models import AgentCard, Message, Task, A2AEvent, TaskState, TextPart, TaskStatusUpdateEvent
    from agentvault.key_manager import KeyManager
    from agentvault.exceptions import A2AError, A2AConnectionError
    _MODELS_AVAILABLE = True
except ImportError:
    pytest.skip("agentvault core library not available, skipping mock tests", allow_module_level=True)
    # Define placeholders if needed, though skip should prevent execution
    class AgentCard: pass # type: ignore
    class Message: pass # type: ignore
    class Task: pass # type: ignore
    class A2AEvent: pass # type: ignore
    class TaskState: pass # type: ignore
    class TextPart: pass # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    class KeyManager: pass # type: ignore
    class A2AError(Exception): pass # type: ignore
    class A2AConnectionError(A2AError): pass # type: ignore


@pytest.fixture
def mock_client() -> MockAgentVaultClient:
    """Provides a fresh instance of MockAgentVaultClient for each test."""
    return MockAgentVaultClient()

# --- Test Instantiation ---

def test_mock_client_instantiation(mock_client: MockAgentVaultClient):
    """Test default attributes after instantiation."""
    assert mock_client.initiate_task_return_value == "mock-task-id-init"
    assert mock_client.send_message_return_value is True
    assert mock_client.terminate_task_return_value is True
    assert mock_client.receive_messages_return_value == []
    assert mock_client.get_task_status_return_value is not None # Should have default mock Task
    assert mock_client.initiate_task_side_effect is None
    assert isinstance(mock_client.call_recorder, AsyncMock)
    assert mock_client.is_closed is False

# --- Test Default Returns ---

@pytest.mark.asyncio
async def test_mock_client_default_returns(mock_client: MockAgentVaultClient):
    """Test calling methods return default configured values."""
    mock_card = MagicMock(spec=AgentCard)
    mock_msg = MagicMock(spec=Message)
    mock_km = MagicMock(spec=KeyManager)

    init_id = await mock_client.initiate_task(mock_card, mock_msg, mock_km)
    assert init_id == "mock-task-id-init"

    send_ok = await mock_client.send_message(mock_card, "t1", mock_msg, mock_km)
    assert send_ok is True

    term_ok = await mock_client.terminate_task(mock_card, "t1", mock_km)
    assert term_ok is True

    status = await mock_client.get_task_status(mock_card, "t1", mock_km)
    assert status is mock_client.get_task_status_return_value

    events = [ev async for ev in mock_client.receive_messages(mock_card, "t1", mock_km)]
    assert events == []

# --- Test Configuring Returns ---

@pytest.mark.asyncio
async def test_mock_client_configure_return(mock_client: MockAgentVaultClient):
    """Test configuring and retrieving a specific return value."""
    mock_card = MagicMock(spec=AgentCard)
    mock_km = MagicMock(spec=KeyManager)
    new_task_id = "new-task-456"
    mock_client.initiate_task_return_value = new_task_id

    init_id = await mock_client.initiate_task(mock_card, MagicMock(spec=Message), mock_km)
    assert init_id == new_task_id

# --- Test Configuring Side Effects ---

@pytest.mark.asyncio
async def test_mock_client_configure_side_effect(mock_client: MockAgentVaultClient):
    """Test configuring and triggering a side effect (exception)."""
    mock_card = MagicMock(spec=AgentCard)
    mock_km = MagicMock(spec=KeyManager)
    mock_client.get_task_status_side_effect = A2AConnectionError("Connection failed")

    with pytest.raises(A2AConnectionError, match="Connection failed"):
        await mock_client.get_task_status(mock_card, "t1", mock_km)

# --- Test Call Recording ---

@pytest.mark.asyncio
async def test_mock_client_call_recording(mock_client: MockAgentVaultClient):
    """Test that calls to methods are recorded."""
    mock_card = MagicMock(spec=AgentCard, name="TestCard") # Give mock a name
    mock_msg = MagicMock(spec=Message, name="TestMessage")
    mock_km = MagicMock(spec=KeyManager, name="TestKeyManager")
    task_id = "record-task"

    await mock_client.initiate_task(mock_card, mock_msg, mock_km, webhook_url="http://hook.test")
    await mock_client.get_task_status(mock_card, task_id, mock_km)

    expected_calls = [
        call.initiate_task(
            agent_card=mock_card, initial_message=mock_msg, key_manager=mock_km,
            mcp_context=None, webhook_url="http://hook.test"
        ),
        call.get_task_status(agent_card=mock_card, task_id=task_id, key_manager=mock_km)
    ]
    # assert_has_calls itself is not async
    mock_client.call_recorder.assert_has_calls(expected_calls, any_order=False)
    assert mock_client.call_recorder.initiate_task.call_count == 1
    assert mock_client.call_recorder.get_task_status.call_count == 1


# --- Test receive_messages Generator ---

@pytest.mark.asyncio
async def test_mock_client_receive_messages_generator(mock_client: MockAgentVaultClient):
    """Test the async generator behavior of receive_messages."""
    mock_card = MagicMock(spec=AgentCard)
    mock_km = MagicMock(spec=KeyManager)
    task_id = "receive-gen"
    event1 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=datetime.datetime.now(datetime.timezone.utc))
    event2 = TaskStatusUpdateEvent(taskId=task_id, state=TaskState.COMPLETED, timestamp=datetime.datetime.now(datetime.timezone.utc))
    mock_client.receive_messages_return_value = [event1, event2]

    received = []
    async for event in mock_client.receive_messages(mock_card, task_id, mock_km):
        received.append(event)

    assert received == [event1, event2]
    # assert_called_once_with *on AsyncMock* IS NOT awaitable
    mock_client.call_recorder.receive_messages.assert_called_once_with(
        agent_card=mock_card, task_id=task_id, key_manager=mock_km
    )

@pytest.mark.asyncio
async def test_mock_client_receive_messages_side_effect(mock_client: MockAgentVaultClient):
    """Test receive_messages raising a configured side effect."""
    mock_card = MagicMock(spec=AgentCard)
    mock_km = MagicMock(spec=KeyManager)
    task_id = "receive-err"
    mock_client.receive_messages_side_effect = A2AError("Stream failed")

    with pytest.raises(A2AError, match="Stream failed"):
        async for _ in mock_client.receive_messages(mock_card, task_id, mock_km):
            pass # pragma: no cover

    # assert_called_once_with *on AsyncMock* IS NOT awaitable
    mock_client.call_recorder.receive_messages.assert_called_once_with(
        agent_card=mock_card, task_id=task_id, key_manager=mock_km
    )

# --- Test Context Manager ---

@pytest.mark.asyncio
async def test_mock_client_context_manager(mock_client: MockAgentVaultClient):
    """Test using the mock client as an async context manager."""
    assert mock_client.is_closed is False
    async with mock_client as client:
        assert client is mock_client
        assert client.is_closed is False
        # Make a call within the context
        await client.terminate_task(MagicMock(), "ctx-task", MagicMock())

    # Should be closed after exiting context
    assert mock_client.is_closed is True
    # Magic methods on the recorder mock are not awaited
    mock_client.call_recorder.__aenter__.assert_called_once()
    mock_client.call_recorder.__aexit__.assert_called_once()
    # --- MODIFIED: Removed await from close assertion ---
    mock_client.call_recorder.close.assert_called_once()
    # --- END MODIFIED ---
    # --- MODIFIED: Removed await from terminate_task assertion ---
    mock_client.call_recorder.terminate_task.assert_called_once()
    # --- END MODIFIED ---
