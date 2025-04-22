import logging
import asyncio
import datetime
import uuid
import os
import json
from typing import Optional, AsyncGenerator, Dict, Any

# Import from agentvault client
from agentvault.client import AgentVaultClient
# Try to import KeyManager from different possible locations
try:
    from agentvault.keymanager import KeyManager
except ImportError:
    try:
        from agentvault.security import KeyManager
    except ImportError:
        # If KeyManager is not available, we'll create a mock one or just pass None
        logger = logging.getLogger(__name__)
        logger.warning("KeyManager not found, using None for now")
        class KeyManager:  # type: ignore
            pass

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
REGISTRY_QUERY_AGENT_URL = os.environ.get("REGISTRY_QUERY_AGENT_URL")
TASK_LOGGER_AGENT_URL = os.environ.get("TASK_LOGGER_AGENT_URL")
REGISTRY_QUERY_AGENT_ID = os.environ.get("REGISTRY_QUERY_AGENT_ID")
TASK_LOGGER_AGENT_ID = os.environ.get("TASK_LOGGER_AGENT_ID")


class QueryAndLogAgent(BaseA2AAgent):
    """
    Orchestrator agent that demonstrates agent-to-agent communication.
    It queries one agent and logs results with another.
    """
    def __init__(self, task_store_ref: BaseTaskStore):
        super().__init__(agent_metadata={"name": "Query And Log Agent"})
        self.task_store = task_store_ref
        self._background_tasks: Dict[str, asyncio.Task] = {}
        logger.info("Query And Log Agent initialized.")
        
        # Create a client instance with proper import handling
        self.client = None
        self.key_manager = None
        
        try:
            self.client = AgentVaultClient()
            self.key_manager = KeyManager() if hasattr(KeyManager, '__init__') else None
        except Exception as e:
            logger.error(f"Error initializing client or KeyManager: {e}")
            # We'll still continue, but might need to handle these None values later
        
        # Validate configuration
        if not ((REGISTRY_QUERY_AGENT_URL or REGISTRY_QUERY_AGENT_ID) and 
                (TASK_LOGGER_AGENT_URL or TASK_LOGGER_AGENT_ID)):
            logger.critical("Agent configuration is incomplete. Required: agent URLs or IDs for both agents")
            raise ConfigurationError("Agent configuration is incomplete")

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        """Initiates a new orchestrated task."""
        logger.info(f"QueryAndLogAgent handling task send: task_id={task_id}")
        if task_id:
            logger.warning(f"Received message for existing task '{task_id}'. This agent only handles new task initiation.")
            raise AgentProcessingError(f"This agent only supports initiating new tasks, not continuing existing ones (task_id='{task_id}').")

        # Extract input text (search term)
        search_term = ""
        if message.parts and isinstance(message.parts[0], TextPart):
            search_term = message.parts[0].content.strip()
        if not search_term:
            raise AgentProcessingError("Input message must contain non-empty text.")

        new_task_id = f"query-log-{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating new orchestrated task: {new_task_id} for search term: '{search_term}'")
        await self.task_store.create_task(new_task_id)  # Creates SUBMITTED state

        # Start background processing
        bg_task = asyncio.create_task(self._orchestrate_query_log(new_task_id, search_term))
        self._background_tasks[new_task_id] = bg_task
        bg_task.add_done_callback(
            lambda fut: self._background_tasks.pop(new_task_id, None)
        )
        return new_task_id

    async def _orchestrate_query_log(self, task_id: str, search_term: str):
        """Orchestrates the query and logging workflow."""
        logger.info(f"Starting orchestration for task {task_id}")
        await self.task_store.update_task_state(task_id, TaskState.WORKING)
        
        response_text = "Error orchestrating workflow."
        final_state = TaskState.FAILED
        
        try:
            # Step 1: Call the Registry Query Agent (currently LLM test agent)
            logger.info(f"Step 1: Calling Registry Query Agent with search term: {search_term}")
            
            # Load agent card for Registry Query Agent
            query_agent_id = REGISTRY_QUERY_AGENT_ID or REGISTRY_QUERY_AGENT_URL
            logger.info(f"Loading agent card for Registry Query Agent: {query_agent_id}")
            
            # First, load the agent card
            try:
                query_agent_card = await self.client.get_remote_agent(query_agent_id)
            except Exception as e:
                logger.error(f"Failed to load agent card for {query_agent_id}: {e}")
                # If loading fails, try alternative method
                query_agent_card = query_agent_id
            
            # Create message for the query agent
            query_message = Message(role="user", parts=[TextPart(content=search_term)])
            
            # Initiate task with the Query Agent
            logger.info(f"Initiating task with Registry Query Agent")
            query_task_id = await self.client.initiate_task(query_agent_card, query_message, self.key_manager)
            logger.info(f"Registry Query Agent task ID: {query_task_id}")
            
            # Receive messages from the Query Agent
            query_result = None
            async for message in self.client.receive_messages(query_agent_card, query_task_id, self.key_manager):
                logger.info(f"Received message from Query Agent: {message}")
                if message.parts and isinstance(message.parts[0], TextPart):
                    query_result = message.parts[0].content
                    break
            
            if not query_result:
                logger.error("No result received from Registry Query Agent")
                raise AgentProcessingError("No result received from Registry Query Agent")
            
            # Step 2: Call the Task Logger Agent
            logger.info(f"Step 2: Calling Task Logger Agent to log search term and result")
            
            # Load agent card for Task Logger Agent
            logger_agent_id = TASK_LOGGER_AGENT_ID or TASK_LOGGER_AGENT_URL
            logger.info(f"Loading agent card for Task Logger Agent: {logger_agent_id}")
            
            # First, load the agent card
            try:
                logger_agent_card = await self.client.get_remote_agent(logger_agent_id)
            except Exception as e:
                logger.error(f"Failed to load agent card for {logger_agent_id}: {e}")
                # If loading fails, try alternative method
                logger_agent_card = logger_agent_id
            
            # Create message for the logger agent
            log_content = f"Search term: {search_term}\nResult: {query_result}"
            logger_message = Message(role="user", parts=[TextPart(content=log_content)])
            
            # Initiate task with the Logger Agent
            logger.info(f"Initiating task with Task Logger Agent")
            logger_task_id = await self.client.initiate_task(logger_agent_card, logger_message, self.key_manager)
            logger.info(f"Task Logger Agent task ID: {logger_task_id}")
            
            # Wait for Logger Agent confirmation
            logger_result = None
            async for message in self.client.receive_messages(logger_agent_card, logger_task_id, self.key_manager):
                logger.info(f"Received message from Logger Agent: {message}")
                if message.parts and isinstance(message.parts[0], TextPart):
                    logger_result = message.parts[0].content
                    break
            
            if not logger_result:
                logger.error("No confirmation received from Task Logger Agent")
                raise AgentProcessingError("No confirmation received from Task Logger Agent")
            
            # Success response
            response_text = f"Successfully orchestrated workflow:\n1. Query result: {query_result[:200]}...\n2. Logging status: {logger_result}"
            final_state = TaskState.COMPLETED
            logger.info(f"Orchestration completed successfully for task {task_id}")
            
        except Exception as e:
            logger.exception(f"Error during orchestration for task {task_id}")
            response_text = f"Orchestration error: {str(e)}"
            final_state = TaskState.FAILED
        finally:
            # Notify result message
            response_message = Message(role="assistant", parts=[TextPart(content=response_text)])
            await self.task_store.notify_message_event(task_id, response_message)
            # Set final state
            await self.task_store.update_task_state(task_id, final_state)

    async def handle_task_get(self, task_id: str) -> Task:
        """Retrieve task status from the store."""
        logger.info(f"QueryAndLogAgent handling task get: task_id={task_id}")
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
            metadata={"agent_type": "query_and_log"}
        )

    async def handle_task_cancel(self, task_id: str) -> bool:
        """Cancel task (marks state, attempts to cancel background task)."""
        logger.info(f"QueryAndLogAgent handling task cancel: task_id={task_id}")
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
                logger.info(f"Cancelled background orchestration task for {task_id}")
            # Update state via store
            await self.task_store.update_task_state(task_id, TaskState.CANCELED)
            return True
        else:
            logger.warning(f"Task {task_id} already terminal.")
            return False

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        """Handles SSE subscription request (relies on store notifications)."""
        logger.info(f"QueryAndLogAgent handling subscribe request: task_id={task_id}")
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

        logger.info(f"Subscription stream ending for orchestration task {task_id}")
        if False: yield  # pragma: no cover

    async def close(self):
        """Clean up resources when the agent shuts down."""
        await self.client.close()
        logger.info("QueryAndLogAgent shutting down")
