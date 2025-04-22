import logging
import asyncio
import datetime
import uuid
import os
from typing import Optional, AsyncGenerator, Dict, Any

import asyncpg

# SDK Imports
from agentvault_server_sdk import BaseA2AAgent
from agentvault_server_sdk.state import BaseTaskStore, TaskContext
from agentvault_server_sdk.exceptions import TaskNotFoundError, AgentProcessingError, ConfigurationError

# Import core types from the agentvault library with fallback
_MODELS_AVAILABLE = False

try:
    from agentvault.models import (
        Message, Task, TaskState, TextPart, A2AEvent,
        TaskStatusUpdateEvent, TaskMessageEvent
    )
    _MODELS_AVAILABLE = True
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
    # Define placeholders for other models
    A2AEvent = Any # type: ignore
    TaskStatusUpdateEvent = Any # type: ignore
    TaskMessageEvent = Any # type: ignore
    Message = Any # type: ignore
    TextPart = Any # type: ignore
    Task = Any # type: ignore
    _MODELS_AVAILABLE = False


logger = logging.getLogger(__name__)

# --- Configuration ---
DATABASE_HOST = os.environ.get("DATABASE_HOST", "localhost")
DATABASE_PORT = int(os.environ.get("DATABASE_PORT", 5432))
DATABASE_USER = os.environ.get("DATABASE_USER", "postgres")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", "")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "agentvault_dev")


class TaskLoggerAgent(BaseA2AAgent):
    """
    Agent that logs messages to a PostgreSQL database.
    """
    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__(agent_metadata={"name": "Task Logger Agent"})
        self.task_store = task_store_ref
        self._background_tasks: Dict[str, asyncio.Task] = {}
        logger.info("Task Logger Agent initialized.")
        
        # Validate configuration
        if not all([DATABASE_HOST, DATABASE_USER, DATABASE_NAME]):
            logger.critical("Database configuration is incomplete. Required: DATABASE_HOST, DATABASE_USER, DATABASE_NAME")
            raise ConfigurationError("Database configuration is incomplete")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Initiates a new task to log a message to the database."""
        logger.info(f"TaskLoggerAgent handling task send: task_id={task_id}")
        if task_id:
            logger.warning(f"Received message for existing task '{task_id}'. This agent only handles new task initiation.")
            raise AgentProcessingError(f"This agent only supports initiating new tasks, not continuing existing ones (task_id='{task_id}').")

        # Extract input text
        input_text = ""
        if message.parts and isinstance(message.parts[0], TextPart):
            input_text = message.parts[0].content.strip()
        if not input_text:
            raise AgentProcessingError("Input message must contain non-empty text.")

        new_task_id = f"tasklog-{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating new task logger task: {new_task_id} for input: '{input_text[:50]}...'")
        await self.task_store.create_task(new_task_id) # Creates SUBMITTED state

        # Start background processing
        bg_task = asyncio.create_task(self._log_to_db(new_task_id, input_text))
        self._background_tasks[new_task_id] = bg_task
        bg_task.add_done_callback(
            lambda fut: self._background_tasks.pop(new_task_id, None)
        )
        return new_task_id

    async def _log_to_db(self, task_id: str, message_text: str):
        """Logs the message to the PostgreSQL database."""
        logger.info(f"Starting database logging for task {task_id}")
        await self.task_store.update_task_state(task_id, TaskState.WORKING)
        
        response_text = "Error logging message to database."
        final_state = TaskState.FAILED
        
        try:
            # Establish connection to PostgreSQL
            connection_params = {
                "host": DATABASE_HOST,
                "port": DATABASE_PORT,
                "user": DATABASE_USER,
                "password": DATABASE_PASSWORD,
                "database": DATABASE_NAME,
            }
            
            logger.info(f"Connecting to database at {DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}")
            conn = await asyncpg.connect(**connection_params)
            
            try:
                # Ensure the table exists (create if not)
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS agent_logs (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        message TEXT
                    )
                ''')
                
                # Insert the message
                timestamp = datetime.datetime.now(datetime.timezone.utc)
                await conn.execute(
                    'INSERT INTO agent_logs (timestamp, message) VALUES ($1, $2)',
                    timestamp, message_text
                )
                
                response_text = f"Message successfully logged to database at {timestamp.isoformat()}"
                final_state = TaskState.COMPLETED
                logger.info(f"Successfully logged message for task {task_id}")
                
            finally:
                await conn.close()
                logger.info("Database connection closed")
        
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"PostgreSQL error for task {task_id}: {e}", exc_info=True)
            response_text = f"Database error: {str(e)}"
        except Exception as e:
            logger.exception(f"Unexpected error processing task {task_id}")
            response_text = f"An unexpected error occurred: {type(e).__name__}: {str(e)}"
        finally:
            # Notify result message
            response_message = Message(role="assistant", parts=[TextPart(content=response_text)])
            await self.task_store.notify_message_event(task_id, response_message)
            # Set final state
            await self.task_store.update_task_state(task_id, final_state)

    async def handle_task_get(self, task_id: str) -> Task:
        """Retrieve task status from the store."""
        logger.info(f"TaskLoggerAgent handling task get: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: 
            raise TaskNotFoundError(task_id=task_id)
        
        # Ensure state is enum
        current_state_enum = task_context.current_state if isinstance(task_context.current_state, TaskState) else TaskState(task_context.current_state)
        
        return Task(
            id=task_context.task_id, 
            state=current_state_enum,
            createdAt=task_context.created_at, 
            updatedAt=task_context.updated_at,
            messages=[], 
            artifacts=[], 
            metadata={"agent_type": "task_logger"}
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        """Cancel task (marks state, attempts to cancel background task)."""
        logger.info(f"TaskLoggerAgent handling task cancel: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: 
            raise TaskNotFoundError(task_id=task_id)

        terminal_states_str = {"COMPLETED", "FAILED", "CANCELED"}
        current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        if current_state_str not in terminal_states_str:
            # Cancel background task if it's running
            bg_task = self._background_tasks.pop(task_id, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()
                logger.info(f"Cancelled background task for {task_id}")
            # Update state via store
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            return True
        else:
            logger.warning(f"Task {task_id} already terminal.")
            return False

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Handles SSE subscription request (relies on store notifications)."""
        logger.info(f"TaskLoggerAgent handling subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: 
            raise TaskNotFoundError(task_id=task_id)

        # Keep connection open while task is running
        terminal_states_str = {"COMPLETED", "FAILED", "CANCELED"}
        current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        while current_state_str not in terminal_states_str:
            await asyncio.sleep(1) # Check periodically
            task_context = await self.task_store.get_task(task_id)
            if task_context is None: 
                break
            current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        logger.info(f"Subscription stream ending for task {task_id}")
        if False: yield # pragma: no cover

    async def close(self):
        """Clean up resources when the agent shuts down."""
        logger.info("TaskLoggerAgent shutting down")
