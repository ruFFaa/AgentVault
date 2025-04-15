import logging
import uuid
import datetime
import asyncio
from typing import Optional, AsyncGenerator, cast

# SDK Imports
from agentvault_server_sdk import BaseA2AAgent
from agentvault_server_sdk.state import BaseTaskStore, TaskContext
from agentvault_server_sdk.exceptions import TaskNotFoundError, InvalidStateTransitionError

# Core Model Imports
from agentvault.models import (
    Message, Task, TaskState, TextPart, A2AEvent,
    TaskStatusUpdateEvent, TaskMessageEvent
)

# Local state import
from .state import ChatTaskContext

logger = logging.getLogger(__name__)

class StatefulChatAgent(BaseA2AAgent):
    """
    Agent demonstrating state management across multiple interactions.
    Stores message history in memory using a custom TaskContext.
    """
    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__(agent_metadata={"name": "Stateful Chat Agent"})
        self.task_store = task_store_ref
        # Keep track of background processing tasks
        self._background_tasks: Dict[str, asyncio.Task] = {}
        logger.info("StatefulChatAgent initialized.")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Handles task initiation or appends message to existing task history."""
        logger.info(f"StatefulChatAgent handling task send: task_id={task_id}")

        if task_id:
            # Existing task: Retrieve context, append message, signal background task
            task_context = await self.task_store.get_task(task_id)
            if task_context is None or not isinstance(task_context, ChatTaskContext):
                logger.error(f"Task ID '{task_id}' not found or has incorrect context type.")
                raise TaskNotFoundError(task_id=task_id)

            logger.debug(f"Appending message to history for task '{task_id}'")
            task_context.history.append(message)
            task_context.updated_at = datetime.datetime.now(datetime.timezone.utc)
            # No need to explicitly save back for InMemoryTaskStore as it's mutable
            # For persistent stores, you would call an update method here.

            # Signal the background task that a new message arrived
            task_context.new_message_event.set()
            return task_id
        else:
            # New task: Create context, store message, start background task
            new_task_id = f"stateful-task-{uuid.uuid4().hex[:6]}"
            logger.info(f"Creating new stateful task: {new_task_id}")
            # Create the specific context type
            new_task_context = ChatTaskContext(
                task_id=new_task_id,
                current_state=TaskState.SUBMITTED,
                history=[message] # Store the initial message
            )
            # Store it using the abstract store's method (which InMemoryTaskStore implements)
            await self.task_store.create_task(new_task_id) # Creates basic context
            self.task_store._tasks[new_task_id] = new_task_context # Overwrite with specific type

            # Start background processing task
            bg_task = asyncio.create_task(self._process_task(new_task_id))
            self._background_tasks[new_task_id] = bg_task
            # Optional: Add callback to remove task from dict when done
            bg_task.add_done_callback(
                lambda fut: self._background_tasks.pop(new_task_id, None)
            )

            return new_task_id

    async def handle_task_get(self, task_id: str) -> Task:
        """Retrieve task status and history."""
        logger.info(f"StatefulChatAgent handling task get: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None or not isinstance(task_context, ChatTaskContext):
            raise TaskNotFoundError(task_id=task_id)

        return Task(
            id=task_context.task_id,
            state=task_context.current_state,
            createdAt=task_context.created_at,
            updatedAt=task_context.updated_at,
            messages=task_context.history, # Include history
            artifacts=[],
            metadata={"info": "Stateful chat agent task"}
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        """Marks the task as canceled and signals the background task."""
        logger.info(f"StatefulChatAgent handling task cancel: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None or not isinstance(task_context, ChatTaskContext):
            raise TaskNotFoundError(task_id=task_id)

        terminal_states = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        if task_context.current_state not in terminal_states:
            # Signal the background task to stop
            task_context.cancel_event.set()
            # Update state via store (which also notifies listeners)
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            logger.info(f"Task {task_id} marked as canceled and background task signaled.")
            return True
        else:
            logger.warning(f"Task {task_id} already terminal.")
            return False # Already terminal

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Handles SSE subscription; relies on store notifications."""
        logger.info(f"StatefulChatAgent handling subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)

        # Keep connection open while task is running
        terminal_states = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        while task_context.current_state not in terminal_states:
            await asyncio.sleep(1) # Check periodically
            task_context = await self.task_store.get_task(task_id)
            if task_context is None: break
        logger.info(f"Subscription stream ending for stateful task {task_id}")
        if False: yield # pragma: no cover

    async def _process_task(self, task_id: str):
        """Background task to process messages as they arrive."""
        logger.info(f"Background task started for {task_id}")
        task_context = await self.task_store.get_task(task_id)
        if not isinstance(task_context, ChatTaskContext):
            logger.error(f"Incorrect context type for task {task_id} in background processing.")
            await self.task_store.update_task_state(task_id, TaskState.FAILED, message="Internal context error")
            return

        try:
            await self.task_store.update_task_state(task_id, TaskState.WORKING)

            while True:
                # Wait for either a new message or a cancellation signal
                new_message_waiter = asyncio.create_task(task_context.new_message_event.wait())
                cancel_waiter = asyncio.create_task(task_context.cancel_event.wait())

                done, pending = await asyncio.wait(
                    {new_message_waiter, cancel_waiter},
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending waiters
                for task in pending:
                    task.cancel()
                    try: await task # Allow cancellation to propagate
                    except asyncio.CancelledError: pass

                if cancel_waiter in done:
                    logger.info(f"Cancellation received for task {task_id}. Exiting processing loop.")
                    # State already set by handle_task_cancel
                    break

                if new_message_waiter in done:
                    task_context.new_message_event.clear() # Reset event for next message
                    logger.info(f"New message detected for task {task_id}. Processing...")

                    # Refetch context in case state changed concurrently (less likely with event)
                    current_context = await self.task_store.get_task(task_id)
                    if not isinstance(current_context, ChatTaskContext): break # Exit if context gone/wrong

                    # Simple response logic based on history length
                    history_len = len(current_context.history)
                    last_message = current_context.history[-1] if current_context.history else None
                    input_text = "(No input found)"
                    if last_message and last_message.parts and isinstance(last_message.parts[0], TextPart):
                         input_text = last_message.parts[0].content

                    response_text = f"Received message {history_len}. Last input: '{input_text[:20]}...'. History length is now {history_len}."
                    response_message = Message(role="assistant", parts=[TextPart(content=response_text)])

                    # Send response via store notification
                    await self.task_store.notify_message_event(task_id, response_message)

                    # Decide if task is complete (e.g., after N messages) - simple example
                    if history_len >= 3:
                        logger.info(f"Task {task_id} reached message limit. Completing.")
                        await self.task_store.update_task_state(task_id, TaskState.COMPLETED)
                        break
                    else:
                        # Stay in WORKING state, waiting for next message
                        await self.task_store.update_task_state(task_id, TaskState.WORKING)


        except asyncio.CancelledError:
             logger.info(f"Background task for {task_id} was cancelled.")
             # Ensure state is CANCELED if not already terminal
             current_context = await self.task_store.get_task(task_id)
             if current_context and current_context.current_state not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}:
                 await self.task_store.update_task_state(task_id, TaskState.CANCELED, message="Processing cancelled")
        except Exception as e:
            logger.exception(f"Error in background processing for task {task_id}")
            await self.task_store.update_task_state(task_id, TaskState.FAILED, message=f"Background error: {e}")
        finally:
             logger.info(f"Background processing task for {task_id} finished.")
