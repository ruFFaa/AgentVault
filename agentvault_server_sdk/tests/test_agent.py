import pytest
from unittest.mock import MagicMock

# Import the class to test
from agentvault_server_sdk.agent import BaseA2AAgent

# Import necessary types for method signatures (or use MagicMock if library unavailable)
try:
    from agentvault.models import Message, Task, TaskState, A2AEvent
    _MODELS_AVAILABLE = True
except ImportError:
    Message = MagicMock # type: ignore
    Task = MagicMock # type: ignore
    TaskState = MagicMock # type: ignore
    A2AEvent = MagicMock # type: ignore
    _MODELS_AVAILABLE = False


@pytest.fixture
def base_agent() -> BaseA2AAgent:
    """Fixture to provide an instance of BaseA2AAgent."""
    return BaseA2AAgent(agent_metadata={"name": "test_base"})

def test_base_agent_instantiation(base_agent: BaseA2AAgent):
    """Test that BaseA2AAgent can be instantiated."""
    assert isinstance(base_agent, BaseA2AAgent)
    assert base_agent.agent_metadata == {"name": "test_base"}

def test_base_agent_instantiation_no_metadata():
    """Test instantiation with default metadata."""
    agent = BaseA2AAgent()
    assert isinstance(agent, BaseA2AAgent)
    assert agent.agent_metadata == {}

@pytest.mark.asyncio
async def test_handle_task_send_not_implemented(base_agent: BaseA2AAgent):
    """Verify handle_task_send raises NotImplementedError."""
    # Create a mock message object or use MagicMock if models aren't available
    mock_message = Message() if _MODELS_AVAILABLE else MagicMock()
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
    agent = MinimalAgent()
    assert isinstance(agent, MinimalAgent)
    assert isinstance(agent, BaseA2AAgent)
