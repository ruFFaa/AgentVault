"""
Mock implementations of AgentVault core components for testing purposes.
"""
import logging
import asyncio
# --- ADDED: Import sys for debugging ---
import sys
# --- END ADDED ---
from typing import Optional, Dict, Any, Union, AsyncGenerator, List, Tuple
from unittest.mock import MagicMock, AsyncMock, call

# --- ADDED: Debugging sys.path ---
# print("\n--- sys.path in agentvault_testing_utils/mocks.py ---")
# print(sys.path)
# print("--- End sys.path ---\n")
# --- END ADDED ---


# Import core types from the agentvault library with fallback
try:
    from agentvault.models import AgentCard, Message, Task, A2AEvent
    from agentvault.key_manager import KeyManager
    _AGENTVAULT_IMPORTED = True
except ImportError as e: # --- MODIFIED: Log the actual error ---
    logging.getLogger(__name__).warning(f"Failed to import core types from 'agentvault'. Using MagicMock placeholders. Error: {e}")
    # --- END MODIFIED ---
    AgentCard = MagicMock # type: ignore
    Message = MagicMock # type: ignore
    Task = MagicMock # type: ignore
    A2AEvent = MagicMock # type: ignore
    KeyManager = MagicMock # type: ignore
    _AGENTVAULT_IMPORTED = False


logger = logging.getLogger(__name__)


class MockAgentVaultClient:
    """
    A mock implementation of agentvault.client.AgentVaultClient for testing.

    Allows configuring return values and side effects (exceptions) for each
    asynchronous method and records calls made to them.
    """
    def __init__(self):
        logger.debug("Initializing MockAgentVaultClient")
        # Configurable return values
        self.initiate_task_return_value: Optional[str] = "mock-task-id-init"
        self.send_message_return_value: bool = True
        self.get_task_status_return_value: Optional[Task] = None # Default to None or a mock Task
        self.terminate_task_return_value: bool = True
        self.receive_messages_return_value: List[A2AEvent] = [] # List of events to yield

        # Configurable side effects (exceptions)
        self.initiate_task_side_effect: Optional[Exception] = None
        self.send_message_side_effect: Optional[Exception] = None
        self.get_task_status_side_effect: Optional[Exception] = None
        self.terminate_task_side_effect: Optional[Exception] = None
        self.receive_messages_side_effect: Optional[Exception] = None

        # Call recorder
        # --- MODIFIED: Use AsyncMock for recorder to allow await ---
        self.call_recorder = AsyncMock()
        # --- END MODIFIED ---

        # Context manager state
        self._closed = False

        # Initialize a default mock Task if models are available
        if _AGENTVAULT_IMPORTED and self.get_task_status_return_value is None:
            try:
                # Attempt to create a default Task with minimal valid fields
                from agentvault.models import TaskState # Import locally if needed
                import datetime
                self.get_task_status_return_value = Task(
                    id="mock-task-id-get", state=TaskState.COMPLETED,
                    createdAt=datetime.datetime.now(datetime.timezone.utc),
                    updatedAt=datetime.datetime.now(datetime.timezone.utc),
                    messages=[], artifacts=[]
                )
            except Exception:
                 logger.warning("Failed to create default mock Task object.")
                 self.get_task_status_return_value = MagicMock(spec=Task) # Fallback to MagicMock


    async def initiate_task(
        self, agent_card: AgentCard, initial_message: Message, key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None
    ) -> str:
        """Mock implementation of initiate_task."""
        logger.debug(f"Mock initiate_task called with agent: {agent_card}, message: {initial_message}, webhook: {webhook_url}")
        await self.call_recorder.initiate_task( # Await recorder call
            agent_card=agent_card, initial_message=initial_message, key_manager=key_manager,
            mcp_context=mcp_context, webhook_url=webhook_url
        )
        if self.initiate_task_side_effect:
            raise self.initiate_task_side_effect
        if self.initiate_task_return_value is None:
             raise ValueError("MockAgentVaultClient.initiate_task_return_value cannot be None") # Must return str
        return self.initiate_task_return_value

    async def send_message(
        self, agent_card: AgentCard, task_id: str, message: Message, key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mock implementation of send_message."""
        logger.debug(f"Mock send_message called with task_id: {task_id}, message: {message}")
        await self.call_recorder.send_message( # Await recorder call
            agent_card=agent_card, task_id=task_id, message=message, key_manager=key_manager,
            mcp_context=mcp_context
        )
        if self.send_message_side_effect:
            raise self.send_message_side_effect
        return self.send_message_return_value

    async def get_task_status(
        self, agent_card: AgentCard, task_id: str, key_manager: KeyManager
    ) -> Task:
        """Mock implementation of get_task_status."""
        logger.debug(f"Mock get_task_status called with task_id: {task_id}")
        await self.call_recorder.get_task_status( # Await recorder call
            agent_card=agent_card, task_id=task_id, key_manager=key_manager
        )
        if self.get_task_status_side_effect:
            raise self.get_task_status_side_effect
        if self.get_task_status_return_value is None:
             raise ValueError("MockAgentVaultClient.get_task_status_return_value is not configured.")
        return self.get_task_status_return_value

    async def terminate_task(
        self, agent_card: AgentCard, task_id: str, key_manager: KeyManager
    ) -> bool:
        """Mock implementation of terminate_task."""
        logger.debug(f"Mock terminate_task called with task_id: {task_id}")
        await self.call_recorder.terminate_task( # Await recorder call
            agent_card=agent_card, task_id=task_id, key_manager=key_manager
        )
        if self.terminate_task_side_effect:
            raise self.terminate_task_side_effect
        return self.terminate_task_return_value

    async def receive_messages(
        self, agent_card: AgentCard, task_id: str, key_manager: KeyManager
    ) -> AsyncGenerator[A2AEvent, None]:
        """Mock implementation of receive_messages."""
        logger.debug(f"Mock receive_messages called for task_id: {task_id}")
        await self.call_recorder.receive_messages( # Await recorder call
            agent_card=agent_card, task_id=task_id, key_manager=key_manager
        )
        if self.receive_messages_side_effect:
            raise self.receive_messages_side_effect

        # Yield configured events
        if self.receive_messages_return_value:
            for event in self.receive_messages_return_value:
                logger.debug(f"Mock receive_messages yielding: {event}")
                yield event
                await asyncio.sleep(0) # Allow context switching
        else:
             logger.debug("Mock receive_messages has no events to yield.")
             # Need this to make it a generator even if list is empty
             if False: # pragma: no cover
                 yield # pragma: no cover

    # --- Context Manager Methods ---
    async def close(self) -> None:
        """Mock close method."""
        logger.debug("Mock close called")
        await self.call_recorder.close() # Await recorder call
        self._closed = True

    async def __aenter__(self) -> "MockAgentVaultClient":
        """Mock async context manager enter."""
        logger.debug("Mock __aenter__ called")
        await self.call_recorder.__aenter__() # Await recorder call
        self._closed = False # Reset closed state on enter
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Mock async context manager exit."""
        logger.debug("Mock __aexit__ called")
        await self.call_recorder.__aexit__(exc_type, exc_val, exc_tb) # Await recorder call
        await self.close()

    @property
    def is_closed(self) -> bool:
        """Check if the mock client is closed."""
        return self._closed
