"""
Provides the AgentVaultClient for interacting with remote agents via the A2A protocol.
"""

import asyncio
import json
import logging
import httpx
import typing
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
    # Import request/response param/result models if needed later
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
        # Optionally initialize or check client state here if needed
        # await self._http_client.__aenter__() # Let httpx manage its context if needed? No, manage explicitly.
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager, closing the client if necessary."""
        await self.close()

    # --- Public A2A Methods (Placeholders) ---

    async def initiate_task(
        self,
        agent_card: AgentCard,
        initial_message: Message,
        key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initiates a new task with the remote agent.

        Args:
            agent_card: The AgentCard of the target agent.
            initial_message: The first message to send (typically from the user).
            key_manager: The KeyManager instance to retrieve authentication keys.
            mcp_context: Optional dictionary representing MCP context data.

        Returns:
            The unique ID assigned to the newly created task.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If connection to the agent endpoint fails.
            A2ARemoteAgentError: If the agent returns an error response.
            A2AMessageError: If there's an issue formatting the request.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Initiating task with agent: {agent_card.human_readable_id}")
        # Implementation will follow in REQ-LIB-A2ACLIENT-002
        raise NotImplementedError

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
        # Need to yield events, so this placeholder needs special handling
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

    # --- Private Helper Methods (Placeholders) ---

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
            # Determine the service ID to look up in KeyManager
            # Use explicit identifier if provided, otherwise default (e.g., humanReadableId)
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
            # Assuming apiKey scheme uses 'X-Api-Key' header by convention
            logger.debug(f"Using apiKey scheme for service_id '{service_id}'.")
            return {"X-Api-Key": api_key}
        else:
            # Add support for other schemes (Bearer, OAuth2) later
            raise A2AAuthenticationError(
                f"No supported authentication scheme found for agent {agent_card.human_readable_id}. "
                f"Supported by agent: {supported_schemes}. Supported by client: ['apiKey']."
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
        raise NotImplementedError


#
