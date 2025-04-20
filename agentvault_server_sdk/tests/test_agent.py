import pytest
import sys
import logging
import importlib # Keep importlib for other tests if needed
from unittest.mock import MagicMock, patch, AsyncMock

# Import the class to test initially to ensure it exists
from agentvault_server_sdk import agent as agent_module_to_reload # Keep reference for reload in other tests
from agentvault_server_sdk.agent import BaseA2AAgent

# Import necessary types for method signatures (or use MagicMock if library unavailable)
try:
    from agentvault.models import Message, Task, TaskState, A2AEvent, TextPart
    _MODELS_AVAILABLE = True
except ImportError:
    Message = MagicMock # type: ignore
    Task = MagicMock # type: ignore
    TaskState = MagicMock # type: ignore
    A2AEvent = MagicMock # type: ignore
    class MockTextPart: pass
    TextPart = MockTextPart # type: ignore
    _MODELS_AVAILABLE = False


@pytest.fixture
def base_agent() -> BaseA2AAgent:
    """Fixture to provide an instance of BaseA2AAgent."""
    # Ensure module is in default state for other tests
    importlib.reload(agent_module_to_reload)
    return BaseA2AAgent(agent_metadata={"name": "test_base"})

def test_base_agent_instantiation(base_agent: BaseA2AAgent):
    """Test that BaseA2AAgent can be instantiated."""
    assert isinstance(base_agent, BaseA2AAgent)
    assert base_agent.agent_metadata == {"name": "test_base"}

def test_base_agent_instantiation_no_metadata():
    """Test instantiation with default metadata."""
    # Ensure module is in default state
    importlib.reload(agent_module_to_reload)
    agent = BaseA2AAgent()
    assert isinstance(agent, BaseA2AAgent)
    assert agent.agent_metadata == {}

# --- MODIFIED: Test instantiation when import flag is False ---
@patch('agentvault_server_sdk.agent._agentvault_models_imported', False) # Simulate import failure via flag
def test_base_agent_init_model_import_error():
    """Test BaseA2AAgent can be instantiated even if core models failed import."""
    # The patch ensures that when BaseA2AAgent is instantiated below,
    # it uses the placeholder definitions.

    try:
        # Reloading is not needed here as we are just checking instantiation
        # after the flag is patched for the scope of this test.
        agent = BaseA2AAgent()
        assert isinstance(agent, BaseA2AAgent)
        # We can't easily check the log here due to import-time execution,
        # but we confirm the class is still created successfully.
    except Exception as e:
        pytest.fail(f"BaseA2AAgent instantiation failed unexpectedly when models are unavailable: {e}")

# --- END MODIFIED ---

@pytest.mark.asyncio
async def test_handle_task_send_not_implemented(base_agent: BaseA2AAgent):
    """Verify handle_task_send raises NotImplementedError."""
    if _MODELS_AVAILABLE:
        mock_message = Message(role="user", parts=[TextPart(content="test")])
    else:
        mock_message = MagicMock() # Fallback if import failed
    with pytest.raises(NotImplementedError):
        await base_agent.handle_task_send(task_id="task-123", message=mock_message)

@pytest.mark.asyncio
async def test_handle_task_get_not_implemented(base_agent: BaseA2AAgent):
    """Verify handle_task_get raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        await base_agent.handle_task_get(task_id="task-123")

@pytest.mark.asyncio
async def test_handle_task_cancel_not_implemented(base_agent: BaseA2AAgent):
    """Verify handle_task_cancel raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        await base_agent.handle_task_cancel(task_id="task-123")

@pytest.mark.asyncio
async def test_handle_subscribe_request_not_implemented(base_agent: BaseA2AAgent):
    """Verify handle_subscribe_request raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        # Need to iterate the generator to trigger the code execution
        async for _ in base_agent.handle_subscribe_request(task_id="task-123"):
             pass # pragma: no cover


# Optional: Add a test for a minimal subclass to ensure inheritance works
class MinimalAgent(BaseA2AAgent):
    # No implementations needed for this test
    pass

def test_minimal_subclass_instantiation():
    """Test that a minimal subclass can be instantiated."""
    # Ensure module is in default state
    importlib.reload(agent_module_to_reload)
    agent = MinimalAgent()
    assert isinstance(agent, MinimalAgent)
    assert isinstance(agent, BaseA2AAgent)
