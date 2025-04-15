import logging
import uuid
import datetime
import asyncio
from pathlib import Path
import json
from typing import Optional, AsyncGenerator, Dict, Any, List

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
import uvicorn

# SDK Imports
try:
    from agentvault_server_sdk import BaseA2AAgent, create_a2a_router, a2a_method
    from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
    from agentvault_server_sdk.state import BaseTaskStore, InMemoryTaskStore, TaskContext
    _SDK_AVAILABLE = True
except ImportError as e:
    logging.critical(f"Failed to import agentvault_server_sdk: {e}. Install with 'pip install -e ../../agentvault_server_sdk'")
    exit(1)

# Core Model Imports
try:
    from agentvault.models import (
        Message, Task, TaskState, TextPart, A2AEvent,
        TaskStatusUpdateEvent, TaskMessageEvent, Artifact
    )
    _MODELS_AVAILABLE = True
except ImportError as e:
    logging.critical(f"Failed to import agentvault models: {e}. Install with 'pip install -e ../../agentvault_library'")
    exit(1)


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use the SDK's store for better integration with the router
task_store: BaseTaskStore = InMemoryTaskStore()


class MySimpleAgent(BaseA2AAgent):
    """A very basic agent demonstrating the SDK structure."""

    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__()
        self.task_store = task_store_ref
        logger.info("MySimpleAgent initialized.")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Creates a task, stores the message, returns ID."""
        logger.info(f"MySimpleAgent received task send: task_id={task_id}, message_role={getattr(message, 'role', 'N/A')}")
        if task_id:
            task_context = await self.task_store.get_task(task_id)
            if task_context is None:
                logger.error(f"Task ID '{task_id}' provided but not found.")
                raise TaskNotFoundError(task_id=task_id)
            # Store message or update state as needed
            # For this simple example, just update timestamp and maybe state
            task_context.updated_at = datetime.datetime.now(datetime.timezone.utc)
            # You might want to store the message in the context if TaskContext is extended
            # await self.task_store.update_task_state(task_id, TaskState.SUBMITTED) # Or keep current state?
            logger.debug(f"Received message for existing task '{task_id}'.")
            return task_id
        else:
            new_task_id = f"simple-{uuid.uuid4().hex[:6]}"
            # Create task using the store
            await self.task_store.create_task(new_task_id)
            # Store message associated with task - requires extending TaskContext
            # task_ctx = await self.task_store.get_task(new_task_id)
            # if task_ctx: task_ctx.messages = [message] # Example
            logger.info(f"Created task {new_task_id} via task store.")
            return new_task_id

    async def handle_task_get(self, task_id: str) -> Task:
        """Returns a simplified Task object using the store."""
        logger.info(f"MySimpleAgent received task get: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            raise TaskNotFoundError(task_id=task_id)

        if _MODELS_AVAILABLE:
            current_state_enum = task_context.current_state if isinstance(task_context.current_state, TaskState) else TaskState(task_context.current_state)
            messages_to_return = getattr(task_context, 'messages', [])
            return Task(
                id=task_context.task_id,
                state=current_state_enum,
                createdAt=task_context.created_at,
                updatedAt=task_context.updated_at,
                messages=messages_to_return,
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
        """Marks task as canceled using the store."""
        logger.info(f"MySimpleAgent received task cancel: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            raise TaskNotFoundError(task_id=task_id)

        terminal_states = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        current_state_enum = task_context.current_state if isinstance(task_context.current_state, TaskState) else TaskState(task_context.current_state)

        if current_state_enum not in terminal_states:
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            logger.info(f"Task {task_id} canceled via task store.")
            return True
        else:
            logger.warning(f"Task '{task_id}' is already in a terminal state ({current_state_enum}). Cannot cancel.")
            return False

    async def _event_generator(self, task_id: str, task_data: Any) -> AsyncGenerator[A2AEvent, None]:
        """The actual async generator logic."""
        if not _MODELS_AVAILABLE:
             logger.warning("Cannot yield events as core models are unavailable.")
             return

        logger.info(f"Starting _event_generator for task '{task_id}'")
        # 1. Send WORKING status
        await self.task_store.update_task_state(task_id, TaskState.WORKING)
        await asyncio.sleep(0.5)

        # 2. Send echo message
        echo_content = f"Processed task {task_id}"
        # Add logic here to retrieve original message if stored in task_data
        echo_message = Message(role="assistant", parts=[TextPart(content=echo_content)])
        await self.task_store.notify_message_event(task_id, echo_message)
        await asyncio.sleep(0.5)

        # 3. Send COMPLETED status
        await self.task_store.update_task_state(task_id, TaskState.COMPLETED)
        logger.info(f"Finished _event_generator for task '{task_id}'.")
        # Ensure the generator actually yields something if needed by type checker, even if logic is handled by notify
        if False: # pragma: no cover
             yield # pragma: no cover


    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Calls the actual generator and yields its events."""
        logger.info(f"MySimpleAgent received subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            logger.error(f"Task ID '{task_id}' not found for subscribe request.")
            raise TaskNotFoundError(task_id=task_id)

        # --- CORRECTED: Await the call to get the generator, then iterate ---
        # Call the generator function and iterate over the resulting async generator
        event_gen = self._event_generator(task_id, task_context) # Get the generator object
        async for event in event_gen: # Iterate over the generator
             yield event
        # --- END CORRECTION ---

# --- FastAPI App Setup ---

app = FastAPI(title="AgentVault Basic A2A Server Example")

my_agent = MySimpleAgent(task_store_ref=task_store)
a2a_router = create_a2a_router(agent=my_agent, task_store=task_store)
app.include_router(a2a_router, prefix="/a2a")

from agentvault_server_sdk.fastapi_integration import (
    task_not_found_handler, validation_exception_handler,
    agent_server_error_handler, generic_exception_handler
)
from pydantic import ValidationError as PydanticValidationError

app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValueError, validation_exception_handler)
app.add_exception_handler(TypeError, validation_exception_handler)
app.add_exception_handler(PydanticValidationError, validation_exception_handler)
app.add_exception_handler(AgentServerError, agent_server_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/", tags=["Status"])
async def read_root():
    """Simple root endpoint."""
    return {"message": "AgentVault Basic A2A Server Example Running"}

@app.get("/agent-card.json", tags=["Agent Card"], response_model=Dict[str, Any])
async def get_agent_card_json():
    """Serves the agent-card.json file."""
    card_path = Path(__file__).parent / "agent-card.json"
    if not card_path.is_file():
        raise HTTPException(status_code=500, detail="agent-card.json not found on server.")
    try:
        with open(card_path, 'r', encoding='utf-8') as f:
            card_data = json.load(f)
        return card_data
    except Exception as e:
        logger.exception("Failed to load or parse agent-card.json")
        raise HTTPException(status_code=500, detail=f"Failed to load agent card: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0, port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
