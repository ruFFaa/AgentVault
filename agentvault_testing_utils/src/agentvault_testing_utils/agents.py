"""
Basic Agent implementations for testing purposes.
"""
import logging
import uuid
import datetime
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any, List, Union

# Import SDK base class and state management
try:
    from agentvault_server_sdk.agent import BaseA2AAgent
    from agentvault_server_sdk.exceptions import TaskNotFoundError
    from agentvault_server_sdk.state import BaseTaskStore, InMemoryTaskStore, TaskContext
    _SDK_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("agentvault_server_sdk not found. Using placeholder for BaseA2AAgent.")
    class BaseA2AAgent: pass # type: ignore
    class TaskNotFoundError(Exception): pass # type: ignore
    class BaseTaskStore: pass # type: ignore
    class InMemoryTaskStore: pass # type: ignore
    class TaskContext: pass # type: ignore
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


class EchoAgent(BaseA2AAgent):
    """
    A simple agent that echoes back the input message and completes.
    Uses the SDK's BaseTaskStore for state management.
    Useful for basic integration testing.
    """
    def __init__(self, task_store: Optional[BaseTaskStore] = None):
        """Initializes the EchoAgent, optionally accepting a task store."""
        super().__init__()
        # Use provided task store or default to InMemoryTaskStore
        self.task_store = task_store if task_store is not None else InMemoryTaskStore()
        logger.info(f"EchoAgent initialized with task store: {self.task_store.__class__.__name__}")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Creates/updates task state using the task store."""
        logger.info(f"EchoAgent received task send: task_id={task_id}, message_role={getattr(message, 'role', 'N/A')}")
        if task_id:
            task_context = await self.task_store.get_task(task_id)
            if task_context is None:
                logger.error(f"Task ID '{task_id}' provided but not found in store.")
                raise TaskNotFoundError(task_id=task_id)
            await self.task_store.update_task_state(task_id, task_context.current_state) # Update timestamp
            logger.debug(f"Received message for existing task '{task_id}'.")
            return task_id
        else:
            new_task_id = f"echo-task-{uuid.uuid4().hex[:8]}"
            await self.task_store.create_task(new_task_id)
            logger.info(f"Created new task '{new_task_id}' via task store.")
            return new_task_id

    async def handle_task_get(self, task_id: str) -> Task:
        """Returns the current state of the echo task from the store."""
        logger.info(f"EchoAgent received task get: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            logger.error(f"Task ID '{task_id}' not found for get request.")
            raise TaskNotFoundError(task_id=task_id)

        if _MODELS_AVAILABLE:
            current_state_enum = task_context.current_state if isinstance(task_context.current_state, TaskState) else TaskState(task_context.current_state)
            return Task(
                id=task_context.task_id,
                state=current_state_enum,
                createdAt=task_context.created_at,
                updatedAt=task_context.updated_at,
                messages=[],
                artifacts=[],
                metadata={"info": "Basic echo agent task"}
            )
        else: # Fallback
            return { # type: ignore
                "id": task_context.task_id, "state": task_context.current_state,
                "createdAt": task_context.created_at.isoformat(), "updatedAt": task_context.updated_at.isoformat(),
                "messages": [], "artifacts": [], "metadata": None
            }


    async def handle_task_cancel(self, task_id: str) -> bool:
        """Marks the task as canceled using the store."""
        logger.info(f"EchoAgent received task cancel: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            logger.error(f"Task ID '{task_id}' not found for cancel request.")
            raise TaskNotFoundError(task_id=task_id)

        terminal_states = {"COMPLETED", "FAILED", "CANCELED"} if not _MODELS_AVAILABLE else {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        current_state_resolved = task_context.current_state
        if _MODELS_AVAILABLE and isinstance(current_state_resolved, str):
             current_state_resolved = TaskState(current_state_resolved)

        if current_state_resolved not in terminal_states:
            updated_context = await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            if updated_context:
                logger.info(f"Task '{task_id}' canceled via task store.")
                return True
            else:
                logger.warning(f"Failed to update task '{task_id}' state to CANCELED via store.")
                return False
        else:
            logger.warning(f"Task '{task_id}' is already in a terminal state ({task_context.current_state}). Cannot cancel.")
            # --- MODIFIED: Explicitly return False ---
            return False
            # --- END MODIFIED ---

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """
        Uses the task store to drive state changes and notifications for the echo process.
        This generator itself doesn't need to yield events if the store handles notifications.
        """
        logger.info(f"EchoAgent received subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            logger.error(f"Task ID '{task_id}' not found for subscribe request.")
            raise TaskNotFoundError(task_id=task_id)

        if _MODELS_AVAILABLE:
            try:
                await self.task_store.update_task_state(task_id, TaskState.WORKING)
                await asyncio.sleep(0.05)

                echo_content = f"Echo response for task {task_id}"
                echo_message = Message(role="assistant", parts=[TextPart(content=echo_content)])
                await self.task_store.notify_message_event(task_id, echo_message)
                await asyncio.sleep(0.05)

                await self.task_store.update_task_state(task_id, TaskState.COMPLETED)
                logger.info(f"EchoAgent finished processing task '{task_id}' via store notifications.")

            except Exception as e:
                 logger.exception(f"Error during EchoAgent subscribe processing for task {task_id}: {e}")
                 try:
                     await self.task_store.update_task_state(task_id, TaskState.FAILED)
                 except Exception as final_err:
                     logger.error(f"Failed to set FAILED state for task {task_id} after error: {final_err}")
        else:
            logger.warning("Cannot perform echo logic as core models are unavailable.")

        if False: # pragma: no cover
            yield # pragma: no cover
