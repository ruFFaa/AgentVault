import logging
import uuid
import datetime
import asyncio
from typing import Optional, AsyncGenerator

# SDK Imports
from agentvault_server_sdk import BaseA2AAgent
from agentvault_server_sdk.state import BaseTaskStore
from agentvault_server_sdk.exceptions import TaskNotFoundError

# Core Model Imports
from agentvault.models import Message, Task, TaskState, A2AEvent, TextPart, TaskStatusUpdateEvent, TaskMessageEvent

logger = logging.getLogger(__name__)

class OAuthProtectedAgent(BaseA2AAgent):
    """
    Simple agent logic that runs behind OAuth2 authentication.
    Uses the injected task store.
    """
    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__(agent_metadata={"name": "OAuth Protected Agent"})
        self.task_store = task_store_ref
        logger.info("OAuthProtectedAgent initialized.")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Handle task initiation. Authentication is handled by FastAPI dependency."""
        logger.info(f"OAuthProtectedAgent handling task send: task_id={task_id}")
        if task_id:
            # This simple agent doesn't support continuing tasks
            logger.warning(f"Received message for existing task '{task_id}', but only new tasks are handled.")
            raise TaskNotFoundError(task_id=task_id) # Or handle differently
        else:
            new_task_id = f"oauth-task-{uuid.uuid4().hex[:6]}"
            await self.task_store.create_task(new_task_id)
            # Start background processing
            asyncio.create_task(self._process_task(new_task_id, message))
            return new_task_id

    async def handle_task_get(self, task_id: str) -> Task:
        """Retrieve task status."""
        logger.info(f"OAuthProtectedAgent handling task get: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)
        return Task(
            id=task_context.task_id, state=task_context.current_state,
            createdAt=task_context.created_at, updatedAt=task_context.updated_at,
            messages=[], artifacts=[], metadata={"info": "OAuth protected task"}
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        """Handle task cancellation request."""
        logger.info(f"OAuthProtectedAgent handling task cancel: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)
        terminal_states = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        if task_context.current_state not in terminal_states:
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            return True
        return False

    async def _process_task(self, task_id: str, initial_message: Message):
        """Simulates processing and sends notifications via the store."""
        logger.info(f"Starting background processing for OAuth task {task_id}")
        try:
            await self.task_store.update_task_state(task_id, TaskState.WORKING)
            await asyncio.sleep(0.2)

            input_text = "Default input"
            if initial_message.parts and isinstance(initial_message.parts[0], TextPart):
                input_text = initial_message.parts[0].content

            response_text = f"Authenticated access successful! Processed: {input_text}"
            response_message = Message(role="assistant", parts=[TextPart(content=response_text)])
            await self.task_store.notify_message_event(task_id, response_message)
            await asyncio.sleep(0.2)

            await self.task_store.update_task_state(task_id, TaskState.COMPLETED)
            logger.info(f"Successfully completed processing OAuth task {task_id}")
        except Exception as e:
            logger.exception(f"Error processing OAuth task {task_id}")
            await self.task_store.update_task_state(task_id, TaskState.FAILED, message=str(e))

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Handles SSE subscription request (events are sent via store notifications)."""
        logger.info(f"OAuthProtectedAgent handling subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)

        # Keep connection open while task is running
        terminal_states = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        while task_context.current_state not in terminal_states:
            await asyncio.sleep(1)
            task_context = await self.task_store.get_task(task_id)
            if task_context is None: break
        logger.info(f"Subscription stream ending for OAuth task {task_id}")
        if False: yield # pragma: no cover
