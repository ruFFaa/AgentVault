"""
Basic Agent implementations for testing purposes.
"""
import logging
import uuid
import datetime
import asyncio
# --- MODIFIED: Import dataclasses ---
from dataclasses import dataclass, field
# --- END MODIFIED ---
from typing import AsyncGenerator, Optional, Dict, Any, List, Union # Added Union

# Import SDK base class
try:
    from agentvault_server_sdk.agent import BaseA2AAgent
    from agentvault_server_sdk.exceptions import TaskNotFoundError
    _SDK_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("agentvault_server_sdk not found. Using placeholder for BaseA2AAgent.")
    class BaseA2AAgent: pass # type: ignore
    class TaskNotFoundError(Exception): pass # type: ignore
    _SDK_AVAILABLE = False

# Import core types from the agentvault library with fallback
try:
    from agentvault.models import (
        Message, Task, TaskState, TextPart, A2AEvent,
        TaskStatusUpdateEvent, TaskMessageEvent
    )
    _MODELS_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("Core agentvault models not found. EchoAgent functionality will be limited.")
    # Define placeholders if import fails
    class Message: pass # type: ignore
    class Task: pass # type: ignore
    class TaskState: # type: ignore
        SUBMITTED = "SUBMITTED"; WORKING = "WORKING"; COMPLETED = "COMPLETED"; CANCELED = "CANCELED" # type: ignore
    class TextPart: pass # type: ignore
    A2AEvent = Any # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    _MODELS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class EchoTaskData:
    """Simple dataclass to hold state for the EchoAgent."""
    task_id: str
    messages: List[Message] = field(default_factory=list)
    state: Union[TaskState, str] = TaskState.SUBMITTED # Allow string fallback
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class EchoAgent(BaseA2AAgent):
    """
    A simple agent that echoes back the input message and completes.
    Useful for basic integration testing.
    """
    def __init__(self):
        super().__init__()
        self._tasks: Dict[str, EchoTaskData] = {}
        logger.info("EchoAgent initialized.")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Handles incoming messages, stores them, and returns a task ID."""
        logger.info(f"EchoAgent received task send: task_id={task_id}, message_role={getattr(message, 'role', 'N/A')}")
        if task_id:
            if task_id not in self._tasks:
                logger.error(f"Task ID '{task_id}' provided but not found.")
                raise TaskNotFoundError(task_id=task_id)
            self._tasks[task_id].messages.append(message)
            self._tasks[task_id].updated_at = datetime.datetime.now(datetime.timezone.utc)
            logger.debug(f"Appended message to existing task '{task_id}'.")
            return task_id
        else:
            new_task_id = f"echo-task-{uuid.uuid4().hex[:8]}"
            self._tasks[new_task_id] = EchoTaskData(task_id=new_task_id, messages=[message])
            logger.info(f"Created new task '{new_task_id}' for echo.")
            return new_task_id

    async def handle_task_get(self, task_id: str) -> Task:
        """Returns the current state of the echo task."""
        logger.info(f"EchoAgent received task get: task_id={task_id}")
        task_data = self._tasks.get(task_id)
        if task_data is None:
            logger.error(f"Task ID '{task_id}' not found for get request.")
            raise TaskNotFoundError(task_id=task_id)

        if _MODELS_AVAILABLE:
            # Ensure state is the correct enum type before creating Task model
            current_state_enum = task_data.state if isinstance(task_data.state, TaskState) else TaskState(task_data.state)
            return Task(
                id=task_data.task_id,
                state=current_state_enum,
                createdAt=task_data.created_at,
                updatedAt=task_data.updated_at,
                messages=list(task_data.messages), # Return a copy
                artifacts=[],
                metadata=None
            )
        else:
            return { # type: ignore
                "id": task_data.task_id, "state": task_data.state,
                "createdAt": task_data.created_at.isoformat(), "updatedAt": task_data.updated_at.isoformat(),
                "messages": [], "artifacts": [], "metadata": None
            }


    async def handle_task_cancel(self, task_id: str) -> bool:
        """Marks the task as canceled."""
        logger.info(f"EchoAgent received task cancel: task_id={task_id}")
        task_data = self._tasks.get(task_id)
        if task_data is None:
            logger.error(f"Task ID '{task_id}' not found for cancel request.")
            raise TaskNotFoundError(task_id=task_id)

        # Use string comparison if TaskState enum isn't available
        terminal_states = {"COMPLETED", "FAILED", "CANCELED"} if not _MODELS_AVAILABLE else {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}

        if task_data.state not in terminal_states:
            task_data.state = TaskState.CANCELED if _MODELS_AVAILABLE else "CANCELED"
            task_data.updated_at = datetime.datetime.now(datetime.timezone.utc)
            logger.info(f"Marked task '{task_id}' as CANCELED.")
            return True
        else:
            logger.warning(f"Task '{task_id}' is already in a terminal state ({task_data.state}). Cannot cancel.")
            return False

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Yields status updates and echoes the first message."""
        logger.info(f"EchoAgent received subscribe request: task_id={task_id}")
        task_data = self._tasks.get(task_id)
        if task_data is None:
            logger.error(f"Task ID '{task_id}' not found for subscribe request.")
            raise TaskNotFoundError(task_id=task_id)

        if _MODELS_AVAILABLE:
            now = datetime.datetime.now(datetime.timezone.utc)
            yield TaskStatusUpdateEvent(taskId=task_id, state=TaskState.WORKING, timestamp=now)
            await asyncio.sleep(0.05)

            if task_data.messages:
                 first_message_content = "Could not extract text content"
                 try:
                     first_part = task_data.messages[0].parts[0]
                     if isinstance(first_part, TextPart):
                         first_message_content = first_part.content
                 except Exception: pass

                 echo_message = Message(role="assistant", parts=[TextPart(content=f"Echo: {first_message_content}")])
                 yield TaskMessageEvent(taskId=task_id, message=echo_message, timestamp=datetime.datetime.now(datetime.timezone.utc))
                 await asyncio.sleep(0.05)

            task_data.state = TaskState.COMPLETED
            task_data.updated_at = datetime.datetime.now(datetime.timezone.utc)
            yield TaskStatusUpdateEvent(taskId=task_id, state=TaskState.COMPLETED, timestamp=task_data.updated_at)
            logger.info(f"EchoAgent finished streaming for task '{task_id}'.")
        else:
             logger.warning("Cannot yield events as core models are unavailable.")
             if False: yield # pragma: no cover
