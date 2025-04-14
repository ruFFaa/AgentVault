"""
Defines the base class for creating AgentVault A2A compliant agents.
"""

import logging
from typing import AsyncGenerator, Optional, Dict, Any, Union # Added Union

# Import core types from the agentvault library
try:
    from agentvault.models import Message, Task, TaskState
    # Import the Union type for events if defined, otherwise import individual events
    try:
        from agentvault.models import A2AEvent
    except ImportError:
        from agentvault.models import TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent
        A2AEvent = Union[TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent] # type: ignore

    _agentvault_models_imported = True
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import core models from 'agentvault': {e}. SDK functionality will be limited.")
    # Define placeholders if import fails to allow basic SDK structure
    class Message: pass # type: ignore
    class Task: pass # type: ignore
    class TaskState: pass # type: ignore
    A2AEvent = Any # type: ignore
    _agentvault_models_imported = False


logger = logging.getLogger(__name__)


class BaseA2AAgent:
    """
    Abstract base class for AgentVault A2A agents.

    Developers should inherit from this class and implement the required
    `handle_...` methods to define the agent's behavior in response to
    A2A protocol requests (tasks/send, tasks/get, tasks/cancel, tasks/sendSubscribe).

    The `agentvault_server_sdk.fastapi_integration` module provides helpers
    to expose subclasses of `BaseA2AAgent` via a FastAPI router.
    """

    def __init__(self, agent_metadata: Optional[Dict[str, Any]] = None):
        """
        Initializes the base agent.

        Args:
            agent_metadata: Optional dictionary containing metadata specific
                            to this agent instance (e.g., configuration, loaded models).
        """
        self.agent_metadata = agent_metadata or {}
        logger.info(f"Initialized BaseA2AAgent: {self.__class__.__name__}")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """
        Handle an incoming message for a task (initiation or continuation).

        This method is called when the A2A endpoint receives a 'tasks/send' request.
        Implementations should process the message, potentially update internal
        task state, start background work, and return the task ID.

        Args:
            task_id: The ID of the task if it's an existing task, None if initiating.
            message: The message received from the client.

        Returns:
            The unique ID of the task (either existing or newly created).

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
            A2AError (or subclass): Can be raised for specific processing errors
                                   (e.g., invalid input, task failure).
        """
        raise NotImplementedError("Subclasses must implement handle_task_send")

    async def handle_task_get(self, task_id: str) -> Task:
        """
        Handle a request to retrieve the current state of a task.

        This method is called when the A2A endpoint receives a 'tasks/get' request.
        Implementations should fetch the current status, message history, and
        artifacts for the specified task ID and return them as a Task object.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            A Task object representing the current state of the task.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
            A2AError (or subclass): Can be raised if the task is not found or
                                   an error occurs during retrieval.
        """
        raise NotImplementedError("Subclasses must implement handle_task_get")

    async def handle_task_cancel(self, task_id: str) -> bool:
        """
        Handle a request to cancel an ongoing task.

        This method is called when the A2A endpoint receives a 'tasks/cancel' request.
        Implementations should attempt to stop the processing for the specified
        task ID and update its state to CANCELED.

        Args:
            task_id: The ID of the task to cancel.

        Returns:
            True if the cancellation request was accepted (even if cancellation
            is asynchronous), False otherwise.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
            A2AError (or subclass): Can be raised if the task cannot be canceled
                                   (e.g., already completed, not found).
        """
        raise NotImplementedError("Subclasses must implement handle_task_cancel")

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """
        Handle a request to subscribe to Server-Sent Events (SSE) for a task.

        This method is called when the A2A endpoint receives a 'tasks/sendSubscribe'
        request. Implementations should return an async generator that yields
        A2AEvent objects (TaskStatusUpdateEvent, TaskMessageEvent,
        TaskArtifactUpdateEvent) as they occur for the specified task ID.

        The generator should typically run indefinitely until the task reaches a
        terminal state or the client disconnects. The framework handles formatting
        these events into the SSE protocol.

        Args:
            task_id: The ID of the task to subscribe to.

        Yields:
            A2AEvent: Events related to the task's progress.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
            A2AError (or subclass): Can be raised if the task is not found or
                                   subscription is not possible.
        """
        raise NotImplementedError("Subclasses must implement handle_subscribe_request")
        # Required to make it an async generator type hint-wise, even if never reached
        if False: # pragma: no cover
            yield # pragma: no cover


# Ensure the logger is configured if this module is run standalone (e.g., for testing)
if __name__ == "__main__":
     logging.basicConfig(level=logging.INFO)
     logger.info("BaseA2AAgent class defined.")
