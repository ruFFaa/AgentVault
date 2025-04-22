import logging
import asyncio
import datetime
import uuid
import os
import json
from typing import Optional, AsyncGenerator, Dict, Any, List

import httpx # Ensure httpx is installed

# SDK Imports
from agentvault_server_sdk import BaseA2AAgent
from agentvault_server_sdk.state import BaseTaskStore, TaskContext
from agentvault_server_sdk.exceptions import TaskNotFoundError, AgentProcessingError, ConfigurationError

# Import core types from the agentvault library with fallback
# Initialize _MODELS_AVAILABLE at module level
_MODELS_AVAILABLE = False

try:
    from agentvault.models import (
        Message, Task, TaskState, TextPart, A2AEvent,
        TaskStatusUpdateEvent, TaskMessageEvent
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
    Message = Any # type: ignore
    TextPart = Any # type: ignore
    Task = Any # type: ignore
    _MODELS_AVAILABLE = False


logger = logging.getLogger(__name__)

# --- Configuration ---
# --- MODIFIED: Load LLM config instead of Registry URL ---
LOCAL_API_BASE_URL = os.environ.get("LOCAL_API_BASE_URL")
WRAPPER_MODEL_NAME = os.environ.get("WRAPPER_MODEL_NAME")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY") # Optional key for local server
LLM_TIMEOUT_SECONDS = 120.0
# --- END MODIFIED ---

class RegistryQueryAgent(BaseA2AAgent):
    """
    Agent that queries the AgentVault Registry based on a search term.
    *** TEMPORARILY MODIFIED TO CALL LOCAL LLM FOR DEBUGGING ***
    """
    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__(agent_metadata={"name": "Registry Query Agent (LLM Test Mode)"}) # Updated name
        self.task_store = task_store_ref
        # Create a persistent httpx client for backend calls
        self.http_client = httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS + 5.0)
        self._background_tasks: Dict[str, asyncio.Task] = {}
        logger.info("Registry Query Agent (LLM Test Mode) initialized.")
        if not LOCAL_API_BASE_URL or not WRAPPER_MODEL_NAME:
            logger.critical("LOCAL_API_BASE_URL or WRAPPER_MODEL_NAME not set in environment. Agent cannot function.")
            # Optionally raise ConfigurationError here

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Initiates a new task to call the local LLM."""
        logger.info(f"RegistryQueryAgent (LLM Test Mode) handling task send: task_id={task_id}")
        if task_id:
            logger.warning(f"Received message for existing task '{task_id}'. This agent only handles new task initiation.")
            raise AgentProcessingError(f"This agent only supports initiating new tasks, not continuing existing ones (task_id='{task_id}').")

        # Extract input text
        input_text = ""
        if message.parts and isinstance(message.parts[0], TextPart):
            input_text = message.parts[0].content.strip()
        if not input_text:
            raise AgentProcessingError("Input message must contain non-empty text.")

        new_task_id = f"llmtest-task-{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating new LLM test task: {new_task_id} for input: '{input_text[:50]}...'")
        await self.task_store.create_task(new_task_id) # Creates SUBMITTED state

        # Start background processing
        # --- MODIFIED: Call _call_local_llm ---
        bg_task = asyncio.create_task(self._call_local_llm(new_task_id, input_text))
        # --- END MODIFIED ---
        self._background_tasks[new_task_id] = bg_task
        bg_task.add_done_callback(
            lambda fut: self._background_tasks.pop(new_task_id, None)
        )
        return new_task_id

    # --- ADDED: _call_local_llm (adapted from simple_wrapper) ---
    async def _call_local_llm(self, task_id: str, input_text: str):
        """Makes the actual call to the configured local LLM."""
        logger.info(f"Starting LLM backend call for task {task_id}")
        await self.task_store.update_task_state(task_id, TaskState.WORKING)
        response_text = "Error communicating with local LLM."
        final_state = TaskState.FAILED
        error_message_detail = None

        if not LOCAL_API_BASE_URL or not WRAPPER_MODEL_NAME:
            logger.error("LLM endpoint or model name not configured.")
            await self.task_store.update_task_state(task_id, TaskState.FAILED)
            return

        try:
            # Prepare Request
            headers: Dict[str, str] = {"Content-Type": "application/json"}
            payload: Dict[str, Any] = {}
            target_url: str = f"{LOCAL_API_BASE_URL.rstrip('/')}/chat/completions"

            if LOCAL_API_KEY: headers["Authorization"] = f"Bearer {LOCAL_API_KEY}"
            messages = [{"role": "user", "content": input_text}]
            # Add system prompt if needed (can be added to .env)
            # system_prompt = os.environ.get("SYSTEM_PROMPT")
            # if system_prompt: messages.insert(0, {"role": "system", "content": system_prompt})
            payload = {"model": WRAPPER_MODEL_NAME, "messages": messages, "stream": False}

            # Make HTTP Request
            logger.info(f"Sending request to local LLM: {target_url} for task {task_id}")
            response = await self.http_client.post(target_url, json=payload, headers=headers, timeout=LLM_TIMEOUT_SECONDS)
            response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx

            # Parse Response (OpenAI compatible structure)
            response_data = response.json()
            assistant_reply = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not assistant_reply:
                logger.warning(f"Could not extract assistant reply from LLM response for task {task_id}. Response: {response_data}")
                raise AgentProcessingError("LLM returned an unexpected response structure.")

            response_text = assistant_reply # Store successful response
            final_state = TaskState.COMPLETED
            logger.info(f"Received successful response from local LLM for task {task_id}")

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
            logger.exception(f"Unexpected error processing LLM task {task_id}")
            response_text = f"An unexpected error occurred: {type(e).__name__}"
            error_message_detail = response_text
        finally:
            # Notify result message
            response_message = Message(role="assistant", parts=[TextPart(content=response_text)])
            await self.task_store.notify_message_event(task_id, response_message)
            # Set final state
            await self.task_store.update_task_state(task_id, final_state)
    # --- END ADDED ---

    # --- REMOVED _query_registry method ---
    # async def _query_registry(self, task_id: str, search_term: str): ...
    # --- END REMOVED ---

    async def handle_task_get(self, task_id: str) -> Task:
        """Retrieve task status from the store."""
        logger.info(f"RegistryQueryAgent (LLM Test Mode) handling task get: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)
        # Ensure state is enum
        current_state_enum = task_context.current_state if isinstance(task_context.current_state, TaskState) else TaskState(task_context.current_state)
        # Use imported Task
        return Task(
            id=task_context.task_id, state=current_state_enum,
            createdAt=task_context.created_at, updatedAt=task_context.updated_at,
            messages=[], artifacts=[], metadata={"agent_type": "registry_query_llm_test"} # Updated metadata
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        """Cancel task (marks state, attempts to cancel background task)."""
        logger.info(f"RegistryQueryAgent (LLM Test Mode) handling task cancel: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)

        # Use string constants for terminal state check
        terminal_states_str = {"COMPLETED", "FAILED", "CANCELED"}
        # Convert current state to string for comparison
        current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        if current_state_str not in terminal_states_str:
            # Cancel background task if it's running
            bg_task = self._background_tasks.pop(task_id, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()
                logger.info(f"Cancelled background LLM task for {task_id}") # Updated log
            # Update state via store
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            return True
        else:
            logger.warning(f"Task {task_id} already terminal.")
            return False

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Handles SSE subscription request (relies on store notifications)."""
        logger.info(f"RegistryQueryAgent (LLM Test Mode) handling subscribe request: task_id={task_id}")
        task_context = await self.task_store.get_task(task_id)
        if task_context is None: raise TaskNotFoundError(task_id=task_id)

        # Keep connection open while task is running
        terminal_states_str = {"COMPLETED", "FAILED", "CANCELED"}
        current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        while current_state_str not in terminal_states_str:
            await asyncio.sleep(1) # Check periodically
            task_context = await self.task_store.get_task(task_id)
            if task_context is None: break
            current_state_str = str(task_context.current_state.value if isinstance(task_context.current_state, TaskState) else task_context.current_state)

        logger.info(f"Subscription stream ending for LLM test task {task_id}")
        if False: yield # pragma: no cover

    async def close(self):
        """Close the httpx client when the agent shuts down."""
        await self.http_client.aclose()
        logger.info("Closed internal httpx client for RegistryQueryAgent (LLM Test Mode).")
