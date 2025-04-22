import logging
import asyncio
import datetime
import uuid
import os
import json
from typing import Optional, AsyncGenerator, Dict, Any, List

import httpx

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
LOCAL_API_BASE_URL = os.environ.get("LOCAL_API_BASE_URL")
WRAPPER_MODEL_NAME = os.environ.get("WRAPPER_MODEL_NAME")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY")  # Optional key for local server
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are a helpful assistant that creates concise summaries.")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", 120.0))


class SimpleSummaryAgent(BaseA2AAgent):
    """
    Agent that generates summaries of text using a local LLM.
    """
    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__(agent_metadata={"name": "Simple Summary Agent"})
        self.task_store = task_store_ref
        # Create a persistent httpx client for LLM calls
        self.http_client = httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS + 5.0)
        self._background_tasks: Dict[str, asyncio.Task] = {}
        logger.info("Simple Summary Agent initialized.")
        if not LOCAL_API_BASE_URL or not WRAPPER_MODEL_NAME:
            logger.critical("LOCAL_API_BASE_URL or WRAPPER_MODEL_NAME not set in environment. Agent cannot function.")
            raise ConfigurationError("LLM configuration is incomplete")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Initiates a new task to generate a summary."""
        logger.info(f"SimpleSummaryAgent handling task send: task_id={task_id}")
        if task_id:
            logger.warning(f"Received message for existing task '{task_id}'. This agent only handles new task initiation.")
            raise AgentProcessingError(f"This agent only supports initiating new tasks, not continuing existing ones (task_id='{task_id}').")

        # Extract input text
        input_text = ""
        if message.parts and isinstance(message.parts[0], TextPart):
            input_text = message.parts[0].content.strip()
        if not input_text:
            raise AgentProcessingError("Input message must contain non-empty text.")

        new_task_id = f"summary-task-{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating new summary task: {new_task_id} for input of length: {len(input_text)} characters")
        await self.task_store.create_task(new_task_id)  # Creates SUBMITTED state

        # Start background processing
        bg_task = asyncio.create_task(self._generate_summary(new_task_id, input_text))
        self._background_tasks[new_task_id] = bg_task
        bg_task.add_done_callback(
            lambda fut: self._background_tasks.pop(new_task_id, None)
        )
        return new_task_id

    async def _generate_summary(self, task_id: str, input_text: str):
        """Makes the actual call to the configured local LLM to generate a summary."""
        logger.info(f"Starting summary generation for task {task_id}")
        await self.task_store.update_task_state(task_id, TaskState.WORKING)
        response_text = "Error generating summary."
        final_state = TaskState.FAILED
        error_message_detail = None

        if not LOCAL_API_BASE_URL or not WRAPPER_MODEL_NAME:
            logger.error("LLM endpoint or model name not configured.")
            await self.task_store.update_task_state(task_id, TaskState.FAILED)
            return

        try:
            # Prepare Request
            headers: Dict[str, str] = {"Content-Type": "application/json"}
            target_url: str = f"{LOCAL_API_BASE_URL.rstrip('/')}/chat/completions"

            if LOCAL_API_KEY:
                headers["Authorization"] = f"Bearer {LOCAL_API_KEY}"
            
            # Create messages with system prompt and user input
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Please summarize the following text:\n\n{input_text}"}
            ]
            
            payload = {
                "model": WRAPPER_MODEL_NAME,
                "messages": messages,
                "stream": False,
                "max_tokens": 512,  # Adjust as needed for summary length
                "temperature": 0.7  # Adjust for creativity in summarization
            }

            # Make HTTP Request
            logger.info(f"Sending request to local LLM: {target_url} for task {task_id}")
            response = await self.http_client.post(target_url, json=payload, headers=headers, timeout=LLM_TIMEOUT_SECONDS)
            response.raise_for_status()  # Raise HTTPStatusError for 4xx/5xx

            # Parse Response (OpenAI compatible structure)
            response_data = response.json()
            assistant_reply = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not assistant_reply:
                logger.warning(f"Could not extract assistant reply from LLM response for task {task_id}. Response: {response_data}")
                raise AgentProcessingError("LLM returned an unexpected response structure.")

            response_text = assistant_reply  # Store successful response
            final_state = TaskState.COMPLETED
            logger.info(f"Summary successfully generated for task {task_id}")

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500]
            logger.error(f"HTTP error calling local LLM for task {task_id}: {e.response.status_code} - {error_body}", exc_info=False)
            response_text = f"Error calling LLM ({e.response.status_code})."
            error_message_detail = f"LLM API Error: {error_body}"
        except httpx.RequestError as e:
            logger.error(f"Network error calling local LLM for task {task_id}: {e}", exc_info=True)
            response_text = f"Network error connecting to LLM: {e}"
            error_message_detail = response_text
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing LLM response for task {task_id}: {e}", exc_info=True)
            response_text = f"Error parsing LLM response."
            error_message_detail = response_text
        except Exception as e:
            logger.exception(f"Unexpected error processing summary task {task_id}")
            response_text = f"An unexpected error occurred: {type(e).__name__}"
            error_message_detail = response_text
        finally:
            # Notify result message
            response_message = Message(role="assistant", parts=[TextPart(content=response_text)])
            await self.task_store.notify_message_event(task_id, response_message)
            # Set final state
            await self.task_store.update_task_state(task_id, final_state)

    async def handle_task_get(self, task_id: str) -> Task:
        """Retrieve task status from the store."""
        logger.info(f"SimpleSummaryAgent handling task get: task_id={task_id}")
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
            metadata={"agent_type": "simple_summary"}
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        """Cancel task (marks state, attempts to cancel background task)."""
        logger.info(f"SimpleSummaryAgent handling task cancel: task_id={task_id}")
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
                logger.info(f"Cancelled background summary task for {task_id}")
            # Update state via store
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            return True
        else:
            logger.warning(f"Task {task_id} already terminal.")
            return False

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Handles SSE subscription request (relies on store notifications)."""
        logger.info(f"SimpleSummaryAgent handling subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None:
            raise TaskNotFoundError(task_id=task_id)

        # Keep connection open while task is running
        terminal_states_str = {"COMPLETED", "FAILED", "CANCELED"}
        current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        while current_state_str not in terminal_states_str:
            await asyncio.sleep(1)  # Check periodically
            task_context = await self.task_store.get_task(task_id)
            if task_context is None:
                break
            current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        logger.info(f"Subscription stream ending for summary task {task_id}")
        if False: yield  # pragma: no cover

    async def close(self):
        """Close the httpx client when the agent shuts down."""
        await self.http_client.aclose()
        logger.info("Closed internal httpx client for SimpleSummaryAgent.")
