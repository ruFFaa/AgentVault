"""
Provides the AgentVaultClient for interacting with remote agents via the A2A protocol.
"""

import asyncio
import json
import logging
import httpx
import typing
import uuid # Added import
import pydantic # Added import
from typing import Optional, Dict, Any, Union, AsyncGenerator

# Import local models
from .models.agent_card import AgentCard, AgentAuthentication
from .models.a2a_protocol import (
    Message,
    Task,
    TaskState,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskMessageEvent,
    # Import request/response param/result models
    TaskSendParams,
    TaskSendResult,
)

# Import local exceptions
from .exceptions import (
    AgentVaultError,
    A2AError,
    A2AConnectionError,
    A2AAuthenticationError,
    A2ARemoteAgentError,
    A2ATimeoutError,
    A2AMessageError,
    KeyManagementError,
)

# Import KeyManager
from .key_manager import KeyManager

# Set up logging
logger = logging.getLogger(__name__)

# Define the type alias for events yielded by receive_messages
A2AEvent = Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, TaskMessageEvent]


class AgentVaultClient:
    """
    Client for interacting with remote agents using the Agent-to-Agent (A2A) protocol.

    Manages HTTP connections and handles the request/response flow for A2A operations.
    Can be used as an async context manager.
    """

    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        default_timeout: float = 30.0
    ):
        """
        Initializes the AgentVaultClient.

        Args:
            http_client: An optional existing httpx.AsyncClient instance to use.
                         If None, a new client will be created internally.
            default_timeout: Default timeout in seconds for HTTP requests if
                             a new client is created.
        """
        self.default_timeout = default_timeout
        if http_client:
            self._http_client = http_client
            self._should_close_client = False
            logger.debug("Using provided httpx.AsyncClient instance.")
        else:
            logger.debug(f"Creating internal httpx.AsyncClient instance with timeout {default_timeout}s.")
            self._http_client = httpx.AsyncClient(timeout=default_timeout)
            self._should_close_client = True

    async def close(self) -> None:
        """
        Closes the underlying httpx client if it was created internally.
        """
        if self._should_close_client and not self._http_client.is_closed:
            logger.debug("Closing internally managed httpx.AsyncClient instance.")
            await self._http_client.aclose()
        elif not self._should_close_client:
             logger.debug("Using externally managed httpx.AsyncClient, not closing.")

    async def __aenter__(self) -> "AgentVaultClient":
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager, closing the client if necessary."""
        await self.close()

    # --- Public A2A Methods ---

    async def initiate_task(
        self,
        agent_card: AgentCard,
        initial_message: Message,
        key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initiates a new task with the remote agent using the 'tasks/send' method.

        Args:
            agent_card: The AgentCard of the target agent.
            initial_message: The first message to send (typically from the user).
            key_manager: The KeyManager instance to retrieve authentication keys.
            mcp_context: Optional dictionary representing MCP context data to be
                         embedded in the message metadata.

        Returns:
            The unique ID assigned to the newly created task.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If connection to the agent endpoint fails.
            A2ARemoteAgentError: If the agent returns an error response.
            A2AMessageError: If there's an issue formatting the request or parsing the response.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Initiating task with agent: {agent_card.human_readable_id}")
        try:
            # 1. Get Authentication Headers
            auth_headers = self._get_auth_headers(agent_card, key_manager)

            # 2. Prepare Message (handle potential immutability and MCP context)
            message_to_send = initial_message
            if mcp_context:
                # Since Message model is frozen, create a new one with updated metadata
                current_metadata = message_to_send.metadata or {}
                updated_metadata = {**current_metadata, "mcp_context": mcp_context}
                # Use model_copy for Pydantic v2 to create a mutable copy and update
                message_to_send = message_to_send.model_copy(update={'metadata': updated_metadata})
                logger.debug("Embedded MCP context into message metadata.")

            # 3. Construct Parameters
            task_send_params = TaskSendParams(message=message_to_send, id=None)

            # 4. Construct JSON-RPC Request Payload
            request_id = f"req-init-{uuid.uuid4()}"
            request_payload = {
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "params": task_send_params.model_dump(mode='json', exclude_none=True), # Use mode='json' for proper serialization
                "id": request_id
            }
            logger.debug(f"Initiate task request payload (id: {request_id}): {request_payload}")

            # 5. Make the Request (ASSUMES _make_request is implemented and returns parsed dict)
            # TODO: Replace placeholder call once _make_request is implemented
            # response_data = await self._make_request(
            #     'POST',
            #     str(agent_card.url), # Ensure URL is string
            #     headers=auth_headers,
            #     json_payload=request_payload
            # )
            # --- Placeholder for _make_request ---
            logger.warning("Using placeholder for _make_request. Response parsing assumes successful call.")
            # Simulate a successful response structure for now
            # In reality, this dict would come from the parsed JSON of the HTTP response
            response_data: Dict[str, Any] = {
                 "jsonrpc": "2.0",
                 "result": {"id": f"task-{uuid.uuid4()}"}, # Simulate a successful result
                 "id": request_id
            }
            # --- End Placeholder ---


            # 6. Parse and Validate Response
            if not isinstance(response_data, dict):
                 raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")

            if "error" in response_data:
                error_data = response_data["error"]
                logger.error(f"Agent returned error during task initiation: {error_data}")
                # TODO: Parse error_data structure more robustly if defined by A2A spec
                err_code = error_data.get("code", -1)
                err_msg = error_data.get("message", "Unknown remote agent error")
                err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data) # Using status_code for JSON-RPC code

            if "result" not in response_data:
                raise A2AMessageError("Invalid response format: missing 'result' key.")

            try:
                result_obj = TaskSendResult.model_validate(response_data["result"])
            except pydantic.ValidationError as e:
                raise A2AMessageError(f"Failed to validate task initiation result: {e}") from e

            task_id = result_obj.id
            if not task_id:
                 raise A2AMessageError("Invalid response format: 'result.id' is missing or empty.")

            logger.info(f"Task successfully initiated with agent {agent_card.human_readable_id}. Task ID: {task_id}")
            return task_id

        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError) as e:
            # Re-raise specific A2A errors
            logger.error(f"A2A error during task initiation: {e}")
            raise
        except KeyManagementError as e:
             # Convert KeyManager errors to A2AAuthenticationError
             logger.error(f"Key management error during task initiation: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error during task initiation with agent {agent_card.human_readable_id}: {e}")
            raise A2AError(f"An unexpected error occurred during task initiation: {e}") from e


    async def send_message(
        self,
        agent_card: AgentCard,
        task_id: str,
        message: Message,
        key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Sends a subsequent message to an existing task.

        Args:
            agent_card: The AgentCard of the target agent.
            task_id: The ID of the existing task.
            message: The message to send.
            key_manager: The KeyManager instance to retrieve authentication keys.
            mcp_context: Optional dictionary representing MCP context data.

        Returns:
            True if the message was sent successfully (agent acknowledged), False otherwise.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If connection to the agent endpoint fails.
            A2ARemoteAgentError: If the agent returns an error response for the task ID.
            A2AMessageError: If there's an issue formatting the request.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Sending message to task {task_id} on agent: {agent_card.human_readable_id}")
        # Implementation will follow in REQ-LIB-A2ACLIENT-003
        raise NotImplementedError

    async def receive_messages(
        self,
        agent_card: AgentCard,
        task_id: str,
        key_manager: KeyManager
    ) -> AsyncGenerator[A2AEvent, None]:
        """
        Subscribes to and yields events (status updates, messages, artifacts)
        for a specific task using Server-Sent Events (SSE).

        This generator will run until the connection is closed, the task reaches
        a terminal state, or an error occurs.

        Args:
            agent_card: The AgentCard of the target agent.
            task_id: The ID of the task to subscribe to.
            key_manager: The KeyManager instance to retrieve authentication keys.

        Yields:
            A2AEvent: Objects representing task status changes, new messages,
                      or artifact updates.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If the initial connection or the stream fails.
            A2ARemoteAgentError: If the agent returns an error during subscription.
            A2AMessageError: If received event data is malformed.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Subscribing to events for task {task_id} on agent: {agent_card.human_readable_id}")
        # Implementation will follow in REQ-LIB-A2ACLIENT-004
        if False: # pragma: no cover
             yield # This makes it an async generator placeholder
        raise NotImplementedError


    async def get_task_status(
        self,
        agent_card: AgentCard,
        task_id: str,
        key_manager: KeyManager
    ) -> Task:
        """
        Retrieves the current status and details of a specific task.

        Args:
            agent_card: The AgentCard of the target agent.
            task_id: The ID of the task to query.
            key_manager: The KeyManager instance to retrieve authentication keys.

        Returns:
            A Task object representing the current state of the task.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If connection to the agent endpoint fails.
            A2ARemoteAgentError: If the agent returns an error for the task ID.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Getting status for task {task_id} on agent: {agent_card.human_readable_id}")
        # Implementation will follow in REQ-LIB-A2ACLIENT-005
        raise NotImplementedError

    async def terminate_task(
        self,
        agent_card: AgentCard,
        task_id: str,
        key_manager: KeyManager
    ) -> bool:
        """
        Requests the termination (cancellation) of a running task.

        Args:
            agent_card: The AgentCard of the target agent.
            task_id: The ID of the task to terminate.
            key_manager: The KeyManager instance to retrieve authentication keys.

        Returns:
            True if the termination request was successfully acknowledged by the agent,
            False otherwise. Note: Acknowledgement does not guarantee immediate termination.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If connection to the agent endpoint fails.
            A2ARemoteAgentError: If the agent returns an error for the task ID.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Requesting termination for task {task_id} on agent: {agent_card.human_readable_id}")
        # Implementation will follow in REQ-LIB-A2ACLIENT-005
        raise NotImplementedError

    # --- Private Helper Methods ---

    def _get_auth_headers(
        self,
        agent_card: AgentCard,
        key_manager: KeyManager
    ) -> Dict[str, str]:
        """
        Determines and retrieves the necessary authentication headers for the agent.

        Currently supports only 'apiKey' scheme.

        Args:
            agent_card: The AgentCard containing auth scheme information.
            key_manager: The KeyManager to retrieve keys from.

        Returns:
            A dictionary containing the required HTTP headers for authentication.

        Raises:
            A2AAuthenticationError: If no supported auth scheme is found, or if the
                                    required key is missing from the KeyManager.
        """
        supported_schemes = [auth.scheme for auth in agent_card.auth_schemes]
        logger.debug(f"Agent supports auth schemes: {supported_schemes}")

        # Prioritize apiKey for now
        api_key_scheme: Optional[AgentAuthentication] = next(
            (s for s in agent_card.auth_schemes if s.scheme == 'apiKey'), None
        )

        if api_key_scheme:
            service_id = api_key_scheme.service_identifier or agent_card.human_readable_id
            if not service_id:
                 raise A2AAuthenticationError(
                     f"Cannot determine service identifier for apiKey scheme on agent {agent_card.human_readable_id}. "
                     "AgentCard needs 'authSchemes[].service_identifier' or a top-level 'humanReadableId'."
                 )

            logger.debug(f"Attempting to retrieve key for service_id '{service_id}' using apiKey scheme.")
            api_key = key_manager.get_key(service_id)
            if not api_key:
                raise A2AAuthenticationError(
                    f"Missing API key for service '{service_id}' required by agent "
                    f"'{agent_card.human_readable_id}' (scheme: apiKey). "
                    f"Configure it using the CLI or environment variables."
                )
            logger.debug(f"Using apiKey scheme for service_id '{service_id}'.")
            return {"X-Api-Key": api_key} # Standard header for API keys
        # elif add bearer support...
        # elif add oauth2 support...
        else:
            # Check for 'none' scheme
            if any(s.scheme == 'none' for s in agent_card.auth_schemes):
                logger.debug("Using 'none' authentication scheme.")
                return {} # No auth headers needed

            raise A2AAuthenticationError(
                f"No supported authentication scheme found for agent {agent_card.human_readable_id}. "
                f"Supported by agent: {supported_schemes}. Supported by client: ['apiKey', 'none']." # Update as client supports more
            )

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        stream: bool = False # Added for potential SSE use
    ) -> Union[httpx.Response, AsyncGenerator[bytes, None]]:
        """
        Internal helper to make HTTP requests using the client's httpx instance
        and handle common errors, converting them to A2A exceptions.

        Args:
            method: HTTP method (e.g., 'GET', 'POST').
            url: The target URL.
            headers: Request headers.
            json_payload: Dictionary to be sent as JSON body (for POST/PUT etc.).
            stream: Whether to return a streaming response.

        Returns:
            An httpx.Response object for regular requests or an async generator
            yielding bytes for streaming requests.

        Raises:
            A2AConnectionError: For connection issues (DNS, refused, etc.).
            A2ATimeoutError: For request timeouts.
            A2AError: For other unexpected httpx errors.
        """
        # Implementation will wrap self._http_client calls and exception handling
        # TODO: Implement this method properly.
        logger.warning(f"_make_request called (method={method}, url={url}, stream={stream}) - Returning placeholder/raising error.")
        if stream:
             # Placeholder for async generator
             async def _dummy_stream():
                  yield b'data: {"event": "placeholder"}\n\n' # pragma: no cover
             return _dummy_stream()
        else:
             # Placeholder for regular response - raise error until implemented
             # Or return a dummy success dict if needed for testing initiate_task
             # raise NotImplementedError("_make_request is not fully implemented yet.")
             # Simulate successful JSON-RPC response for initiate_task testing
             if method == 'POST' and json_payload and json_payload.get("method") == "tasks/send":
                 req_id = json_payload.get("id", "unknown")
                 return { # Return dict directly, assuming successful parse
                     "jsonrpc": "2.0",
                     "result": {"id": f"task-placeholder-{uuid.uuid4()}"},
                     "id": req_id
                 }
             else:
                 # Fallback for other methods until implemented
                 raise NotImplementedError(f"_make_request placeholder cannot handle {method} to {url} yet.")


#
