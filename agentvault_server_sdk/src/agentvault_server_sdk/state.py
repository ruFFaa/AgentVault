"""
Defines base classes and an in-memory implementation for task state management
within the AgentVault Server SDK.
"""

import logging
import datetime
import asyncio # Import asyncio directly
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
# --- MODIFIED: Added Any ---
from typing import Optional, Dict, Any, Union, List
# --- END MODIFIED ---

from .exceptions import InvalidStateTransitionError


# Import core types from the agentvault library with fallback
try:
    from agentvault.models import (
        TaskState, A2AEvent, TaskStatusUpdateEvent, TaskMessageEvent,
        TaskArtifactUpdateEvent, Message, Artifact
    )
    _MODELS_AVAILABLE = True # Define flag based on import success
except ImportError:
    logging.getLogger(__name__).warning("Core agentvault models not found. Using string/Any placeholders.")
    # Define TaskState as a simple class with string constants if import fails
    class TaskState: # type: ignore
        SUBMITTED = "SUBMITTED"
        WORKING = "WORKING"
        INPUT_REQUIRED = "INPUT_REQUIRED"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
        CANCELED = "CANCELED"
    # Define placeholders for other models used in notification tests (even if skipped)
    A2AEvent = Any # type: ignore
    TaskStatusUpdateEvent = Any # type: ignore
    TaskMessageEvent = Any # type: ignore
    TaskArtifactUpdateEvent = Any # type: ignore
    Message = Any # type: ignore
    Artifact = Any # type: ignore
    _MODELS_AVAILABLE = False


logger = logging.getLogger(__name__)

# State Transition Logic - Use strings for keys
ALLOWED_TRANSITIONS = {
    "SUBMITTED": {"WORKING", "CANCELED"},
    "WORKING": {"INPUT_REQUIRED", "COMPLETED", "FAILED", "CANCELED"},
    "INPUT_REQUIRED": {"WORKING", "CANCELED"},
    "COMPLETED": {"COMPLETED"},
    "FAILED": {"FAILED"},
    "CANCELED": {"CANCELED"},
}
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELED"}


@dataclass
class TaskContext:
    """Holds the basic context and state for a single task."""
    task_id: str
    current_state: Union[TaskState, str] # Allow string fallback if model not loaded
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    def update_state(self, new_state_input: Union[TaskState, str]):
        """
        Updates the state and timestamp, validating the transition.

        Raises:
            InvalidStateTransitionError: If the requested transition is not allowed.
            ValueError: If the new_state_input cannot be resolved to a valid state.
        """
        current_state_resolved = self.current_state
        new_state_resolved = new_state_input

        # Resolve to enum members if possible (using the flag defined in THIS module)
        if _MODELS_AVAILABLE:
            try:
                if isinstance(current_state_resolved, str):
                    current_state_resolved = TaskState(current_state_resolved)
                if isinstance(new_state_resolved, str):
                    new_state_resolved = TaskState(new_state_resolved)
            except ValueError as e:
                logger.error(f"Invalid state value provided for task {self.task_id}: {e}")
                raise ValueError(f"Invalid target state value: {new_state_input}") from e

        logger.debug(f"Attempting state update for task {self.task_id} from {current_state_resolved} to {new_state_resolved}")

        # Use string representation for checks
        current_state_str = str(current_state_resolved.value if _MODELS_AVAILABLE and isinstance(current_state_resolved, TaskState) else current_state_resolved)
        new_state_str = str(new_state_resolved.value if _MODELS_AVAILABLE and isinstance(new_state_resolved, TaskState) else new_state_resolved)


        if new_state_str == current_state_str:
            logger.debug(f"Task {self.task_id} already in state {new_state_str}. Updating timestamp only.")
            self.updated_at = datetime.datetime.now(datetime.timezone.utc)
            return

        if current_state_str in TERMINAL_STATES:
            msg = f"Task {self.task_id} is already in a terminal state ({current_state_str}) and cannot transition to {new_state_str}."
            logger.warning(msg)
            raise InvalidStateTransitionError(self.task_id, current_state_str, new_state_str, msg)

        allowed_next_states = ALLOWED_TRANSITIONS.get(current_state_str)
        if allowed_next_states is None or new_state_str not in allowed_next_states:
            msg = f"Invalid state transition for task {self.task_id}: Cannot move from {current_state_str} to {new_state_str}."
            logger.warning(msg)
            raise InvalidStateTransitionError(self.task_id, current_state_str, new_state_str, msg)

        logger.debug(f"Valid state transition for task {self.task_id}. Updating state to {new_state_resolved}.")
        self.current_state = new_state_resolved # Store the original input type (Enum or str)
        self.updated_at = datetime.datetime.now(datetime.timezone.utc)


class BaseTaskStore(ABC):
    """Abstract base class for task state storage."""

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        """Retrieve task context by ID."""
        pass

    @abstractmethod
    async def create_task(self, task_id: str) -> TaskContext:
        """Create and store context for a new task."""
        pass

    @abstractmethod
    async def update_task_state(self, task_id: str, new_state: Union[TaskState, str], message: Optional[str] = None) -> Optional[TaskContext]: # Added message
        """Update the state of an existing task."""
        pass

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """Remove task context from the store."""
        pass

    # --- Listener Management Methods ---
    @abstractmethod
    async def add_listener(self, task_id: str, listener_queue: asyncio.Queue):
        """Adds a queue to listen for events for a specific task."""
        pass

    @abstractmethod
    async def remove_listener(self, task_id: str, listener_queue: asyncio.Queue):
        """Removes a listener queue for a specific task."""
        pass

    @abstractmethod
    async def get_listeners(self, task_id: str) -> List[asyncio.Queue]:
        """Gets all active listener queues for a specific task."""
        pass

    # --- Event Notification Methods ---
    @abstractmethod
    async def notify_status_update(
        self,
        task_id: str,
        new_state: Union[TaskState, str],
        message: Optional[str] = None
    ):
        """Notify listeners about a task status change."""
        pass

    @abstractmethod
    async def notify_message_event(
        self,
        task_id: str,
        message: Message
    ):
        """Notify listeners about a new message added to the task."""
        pass

    @abstractmethod
    async def notify_artifact_event(
        self,
        task_id: str,
        artifact: Artifact
    ):
        """Notify listeners about a new or updated artifact."""
        pass


class InMemoryTaskStore(BaseTaskStore):
    """
    Simple in-memory implementation of the task store using a dictionary.
    Suitable for single-process development and testing. Not persistent.
    """
    def __init__(self):
        self._tasks: Dict[str, TaskContext] = {}
        self._listeners: Dict[str, List[asyncio.Queue]] = {} # task_id -> list of queues
        logger.info("Initialized InMemoryTaskStore.")

    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        logger.debug(f"Getting task '{task_id}' from InMemoryTaskStore.")
        return self._tasks.get(task_id)

    async def create_task(self, task_id: str) -> TaskContext:
        if task_id in self._tasks:
            logger.warning(f"Task '{task_id}' already exists in InMemoryTaskStore. Returning existing.")
            return self._tasks[task_id]

        logger.info(f"Creating new task '{task_id}' in InMemoryTaskStore.")
        # Use string state if models unavailable (using SDK's flag)
        initial_state = TaskState.SUBMITTED if _MODELS_AVAILABLE else "SUBMITTED"
        new_task_context = TaskContext(task_id=task_id, current_state=initial_state)
        self._tasks[task_id] = new_task_context
        self._listeners[task_id] = [] # Initialize listener list
        # Notify initial state
        await self.notify_status_update(task_id, new_task_context.current_state)
        return new_task_context

    async def update_task_state(self, task_id: str, new_state: Union[TaskState, str], message: Optional[str] = None) -> Optional[TaskContext]: # Added message
        task_context = self._tasks.get(task_id)
        if task_context:
            try:
                original_state = task_context.current_state
                task_context.update_state(new_state) # Calls context update (which includes validation)
                try:
                    # Pass message to notify
                    await self.notify_status_update(task_id, task_context.current_state, message=message)
                except Exception as notify_err:
                    logger.error(f"Failed to notify listeners for task '{task_id}' state change from {original_state} to {new_state}: {notify_err}", exc_info=True)
                return task_context
            except InvalidStateTransitionError as e:
                 # Log the error but return None as the update failed
                 logger.warning(f"Invalid state transition prevented for task '{task_id}': {e}")
                 return None
            except ValueError as e:
                 logger.error(f"Invalid state value '{new_state}' provided for task '{task_id}'.")
                 return None
        else:
            logger.warning(f"Task '{task_id}' not found for state update.")
            return None

    async def delete_task(self, task_id: str) -> bool:
        task_deleted = self._tasks.pop(task_id, None) is not None
        listeners_deleted = self._listeners.pop(task_id, None) is not None
        if task_deleted:
            logger.info(f"Deleted task '{task_id}' from InMemoryTaskStore.")
            if listeners_deleted:
                logger.debug(f"Also removed listener list for deleted task '{task_id}'.")
            return True
        else:
            logger.warning(f"Task '{task_id}' not found for deletion.")
            return False

    # --- Listener Management Implementation ---
    async def add_listener(self, task_id: str, listener_queue: asyncio.Queue):
        if task_id not in self._listeners:
            self._listeners[task_id] = []
        if listener_queue not in self._listeners[task_id]:
            self._listeners[task_id].append(listener_queue)
            logger.debug(f"Added listener queue to task '{task_id}'. Total listeners: {len(self._listeners[task_id])}")
        else:
            logger.debug(f"Listener queue already present for task '{task_id}'.")


    async def remove_listener(self, task_id: str, listener_queue: asyncio.Queue):
        if task_id in self._listeners:
            try:
                self._listeners[task_id].remove(listener_queue)
                logger.debug(f"Removed listener queue from task '{task_id}'. Remaining listeners: {len(self._listeners[task_id])}")
            except ValueError:
                logger.warning(f"Attempted to remove a listener queue not present for task '{task_id}'.")
        else:
            logger.warning(f"Attempted to remove listener from non-existent task '{task_id}' listener list.")


    async def get_listeners(self, task_id: str) -> List[asyncio.Queue]:
        listeners = self._listeners.get(task_id, [])
        logger.debug(f"Retrieved {len(listeners)} listeners for task '{task_id}'.")
        return list(listeners) # Return a copy

    # --- Event Notification Implementation ---
    async def _notify_listeners(self, task_id: str, event: A2AEvent):
        """Internal helper to send an event to all listeners for a task."""
        if task_id not in self._tasks:
            logger.debug(f"Task '{task_id}' deleted before notification could be sent for event {type(event).__name__}.")
            return

        listeners = await self.get_listeners(task_id)
        if not listeners:
            logger.debug(f"No listeners found for task '{task_id}' when trying to notify.")
            return

        logger.info(f"Notifying {len(listeners)} listeners for task '{task_id}' with event: {type(event).__name__}")
        put_tasks = [listener.put(event) for listener in listeners]
        results = await asyncio.gather(*put_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to put event onto listener queue {i} for task '{task_id}': {result}", exc_info=result)

    async def notify_status_update(
        self,
        task_id: str,
        new_state: Union[TaskState, str],
        message: Optional[str] = None
    ):
        """Notify listeners about a task status change."""
        # --- MODIFIED: Re-introduce _MODELS_AVAILABLE check ---
        if not _MODELS_AVAILABLE:
            logger.warning("Cannot create TaskStatusUpdateEvent: Core models not available.")
            return # Cannot create the specific event object
        # --- END MODIFIED ---

        event = None
        try:
            # Ensure state_value is the correct type (Enum or string)
            state_value = new_state
            if _MODELS_AVAILABLE and isinstance(new_state, str):
                try:
                    state_value = TaskState(new_state)
                except ValueError:
                    logger.error(f"Invalid state string '{new_state}' passed to notify_status_update for task '{task_id}'.")
                    return # Don't proceed if state is invalid
            elif not _MODELS_AVAILABLE and not isinstance(new_state, str):
                 state_value = str(new_state) # Fallback to string

            now = datetime.datetime.now(datetime.timezone.utc)
            logger.debug(f"Creating TaskStatusUpdateEvent with: task_id='{task_id}', state='{state_value}', timestamp='{now}', message='{message}'")
            # Use the imported (or placeholder) class
            event = TaskStatusUpdateEvent(
                taskId=task_id, # Use alias
                state=state_value,
                timestamp=now,
                message=message
            )
            logger.debug(f"Successfully created event object: {event!r}")
        except Exception as e:
            logger.error(f"Failed to create TaskStatusUpdateEvent instance for task '{task_id}': {e}", exc_info=True)
            return

        if event:
            await self._notify_listeners(task_id, event)

    async def notify_message_event(
        self,
        task_id: str,
        message: Message
    ):
        """Notify listeners about a new message added to the task."""
        # --- MODIFIED: Re-introduce _MODELS_AVAILABLE check ---
        if not _MODELS_AVAILABLE:
            logger.warning("Cannot create TaskMessageEvent: Core models not available.")
            return
        # --- END MODIFIED ---
        event = None
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            logger.debug(f"Creating TaskMessageEvent with: task_id='{task_id}', message='{message!r}', timestamp='{now}'")
            # Use the imported (or placeholder) class
            event = TaskMessageEvent(
                taskId=task_id, # Use alias
                message=message,
                timestamp=now
            )
            logger.debug(f"Successfully created event object: {event!r}")
        except Exception as e:
            logger.error(f"Failed to create TaskMessageEvent instance for task '{task_id}': {e}", exc_info=True)
            return

        if event:
            await self._notify_listeners(task_id, event)

    async def notify_artifact_event(
        self,
        task_id: str,
        artifact: Artifact
    ):
        """Notify listeners about a new or updated artifact."""
        # --- MODIFIED: Re-introduce _MODELS_AVAILABLE check ---
        if not _MODELS_AVAILABLE:
            logger.warning("Cannot create TaskArtifactUpdateEvent: Core models not available.")
            return
        # --- END MODIFIED ---
        event = None
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            logger.debug(f"Creating TaskArtifactUpdateEvent with: task_id='{task_id}', artifact='{artifact!r}', timestamp='{now}'")
            # Use the imported (or placeholder) class
            event = TaskArtifactUpdateEvent(
                taskId=task_id, # Use alias
                artifact=artifact,
                timestamp=now
            )
            logger.debug(f"Successfully created event object: {event!r}")
        except Exception as e:
            logger.error(f"Failed to create TaskArtifactUpdateEvent instance for task '{task_id}': {e}", exc_info=True)
            return

        if event:
            await self._notify_listeners(task_id, event)
