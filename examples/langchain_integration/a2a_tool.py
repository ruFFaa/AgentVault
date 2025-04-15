import asyncio
import logging
from typing import Type, Optional, Any, Dict, List
from pydantic import BaseModel, Field

# LangChain imports
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun

# AgentVault imports
try:
    from agentvault import (
        AgentVaultClient, KeyManager, Message, TextPart,
        agent_card_utils, exceptions as av_exceptions, models as av_models
    )
    _AGENTVAULT_AVAILABLE = True
except ImportError:
    logging.error("Failed to import agentvault library. A2AAgentTool will not function.")
    # Define placeholders
    class AgentVaultClient: pass
    class KeyManager: pass
    class Message: pass
    class TextPart: pass
    class agent_card_utils:
        @staticmethod
        async def fetch_agent_card_from_url(url): raise NotImplementedError()
        @staticmethod
        def load_agent_card_from_file(path): raise NotImplementedError()
    class av_exceptions:
        AgentCardError = Exception
        A2AError = Exception
    class av_models:
        AgentCard = Any
        TaskStatusUpdateEvent = Any
        TaskMessageEvent = Any
        TaskArtifactUpdateEvent = Any
        TaskState = Any

    _AGENTVAULT_AVAILABLE = False


logger = logging.getLogger(__name__)

# Define the input schema for the tool using Pydantic
class A2AToolInput(BaseModel):
    agent_ref: str = Field(description="Agent identifier: ID (e.g., 'org/agent'), URL (https://...), or local file path.")
    input_text: str = Field(description="The input text prompt or query for the agent.")
    # Add other potential inputs like key_service_id if needed later
    # key_service_id: Optional[str] = Field(None, description="Optional service ID for key lookup.")

class A2AAgentTool(BaseTool):
    """
    LangChain Tool to interact with an AgentVault A2A compliant agent.
    """
    name: str = "a2a_agent_interaction"
    description: str = (
        "Use this tool to send a prompt or query to a specific remote AI agent "
        "identified by its reference (ID, URL, or file path) and get its response. "
        "Input should be the agent reference and the text prompt."
    )
    args_schema: Type[BaseModel] = A2AToolInput

    # Allow extra fields to be passed to the tool initialization if needed
    # Example: registry_url: str = "http://localhost:8000"
    registry_url: str = Field(default="http://localhost:8000", description="URL of the AgentVault Registry API.")

    # This tool performs async operations
    def _run(
        self, *args: Any, run_manager: Optional[CallbackManagerForToolRun] = None, **kwargs: Any
    ) -> str:
        """Use the async version `_arun` instead."""
        raise NotImplementedError("A2AAgentTool does not support synchronous execution.")

    async def _arun(
        self,
        agent_ref: str,
        input_text: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any # Allow extra kwargs from LangChain if any
    ) -> str:
        """
        Asynchronously runs the query against the specified A2A agent.

        Handles loading the agent card, initiating the task, streaming events,
        and returning the final text response from the agent.
        """
        if not _AGENTVAULT_AVAILABLE:
            return "Error: AgentVault library is not available."

        logger.info(f"A2ATool executing for agent_ref: {agent_ref}")
        # Use default KeyManager (will load from env, file, keyring as configured)
        key_manager = KeyManager(use_keyring=True) # Enable keyring by default for tools
        agent_card: Optional[av_models.AgentCard] = None
        final_response_parts: List[str] = []
        task_id: Optional[str] = None

        try:
            # 1. Load Agent Card (using a simplified context for example)
            # In a real scenario, you might pass ctx or handle errors more robustly
            mock_ctx = MagicMock() # Mock context for loading helper
            mock_ctx.exit.side_effect = lambda code: logger.error(f"Mock context exit called with code {code}")
            agent_card = await agent_card_utils._load_agent_card(agent_ref, self.registry_url, mock_ctx) # Use internal helper directly for simplicity here
            if agent_card is None:
                raise ValueError(f"Could not load Agent Card for reference: {agent_ref}")

            # 2. Prepare Initial Message
            initial_message = Message(role="user", parts=[TextPart(content=input_text)])

            # 3. Run Task via AgentVaultClient
            async with AgentVaultClient() as client:
                logger.debug(f"Initiating task with agent {agent_ref}...")
                task_id = await client.initiate_task(
                    agent_card=agent_card,
                    initial_message=initial_message,
                    key_manager=key_manager
                )
                logger.info(f"Task initiated with ID: {task_id}")

                # 4. Stream and Process Events
                async for event in client.receive_messages(
                    agent_card=agent_card, task_id=task_id, key_manager=key_manager
                ):
                    if isinstance(event, av_models.TaskMessageEvent):
                        if event.message.role == "assistant":
                            for part in event.message.parts:
                                if isinstance(part, TextPart):
                                    final_response_parts.append(part.content)
                                    # Optionally call run_manager.on_tool_chunk or similar for streaming
                                    if run_manager:
                                        await run_manager.on_text(part.content, verbose=self.verbose)
                    elif isinstance(event, av_models.TaskStatusUpdateEvent):
                        logger.debug(f"Task {task_id} status update: {event.state}")
                        if event.state in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                            if event.state == av_models.TaskState.FAILED:
                                logger.error(f"Task {task_id} failed: {event.message}")
                                # Optionally append error to response or raise specific exception
                                final_response_parts.append(f"\n[Task Failed: {event.message or 'Unknown reason'}]")
                            break # Stop streaming on terminal state

        except (av_exceptions.AgentCardError, av_exceptions.A2AError, ValueError) as e:
            logger.exception(f"Error interacting with A2A agent {agent_ref} (Task ID: {task_id}): {e}")
            # Return error message to LangChain
            return f"Error communicating with agent {agent_ref}: {e}"
        except Exception as e:
            logger.exception(f"Unexpected error in A2ATool for agent {agent_ref}: {e}")
            return f"Unexpected error in A2ATool: {e}"

        logger.info(f"A2ATool finished for agent_ref: {agent_ref}. Response length: {len(final_response_parts)}")
        return "\n".join(final_response_parts)
