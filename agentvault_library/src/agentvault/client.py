"""
Provides the AgentVaultClient for interacting with remote agents via the A2A protocol.
"""

import asyncio
import json
import logging
import httpx
import typing
import uuid
import pydantic
from typing import Optional, Dict, Any, Union, AsyncGenerator, Tuple

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
    # Import specific event models for validation mapping
    TaskStatusUpdateEvent,
    TaskMessageEvent,
    TaskArtifactUpdateEvent,
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
A2AEvent = Union[TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent]

# Mapping from SSE event types to Pydantic models
SSE_EVENT_TYPE_MAP = {
    "task_status": TaskStatusUpdateEvent,
    "task_message": TaskMessageEvent,
    "task_artifact": TaskArtifactUpdateEvent,
    "message": TaskMessageEvent, # Default event type if none specified
}


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
            self._http_client = httpx.AsyncClient(timeout=default_timeout, follow_redirects=True)
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
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            message_to_send = initial_message
            if mcp_context:
                current_metadata = message_to_send.metadata or {}
                updated_metadata = {**current_metadata, "mcp_context": mcp_context}
                message_to_send = message_to_send.model_copy(update={'metadata': updated_metadata})
                logger.debug("Embedded MCP context into message metadata.")

            task_send_params = TaskSendParams(message=message_to_send, id=None)
            request_id = f"req-init-{uuid.uuid4()}"
            request_payload = {
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "params": task_send_params.model_dump(mode='json', exclude_none=True),
                "id": request_id
            }
            logger.debug(f"Initiate task request payload (id: {request_id}): {request_payload}")

            response_data = await self._make_request(
                'POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload
            )

            if not isinstance(response_data, dict):
                 raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")
            if "error" in response_data:
                error_data = response_data["error"]
                logger.error(f"Agent returned error during task initiation: {error_data}")
                err_code = error_data.get("code", -1)
                err_msg = error_data.get("message", "Unknown remote agent error")
                err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data)
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
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error during task initiation: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error during task initiation: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
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
        Sends a subsequent message to an existing task using the 'tasks/send' method.

        Args:
            agent_card: The AgentCard of the target agent.
            task_id: The ID of the existing task.
            message: The message to send.
            key_manager: The KeyManager instance to retrieve authentication keys.
            mcp_context: Optional dictionary representing MCP context data.

        Returns:
            True if the message was sent successfully and acknowledged by the agent.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If connection to the agent endpoint fails.
            A2ARemoteAgentError: If the agent returns an error response for the task ID.
            A2AMessageError: If there's an issue formatting the request or parsing the response.
            AgentVaultError: For other unexpected errors not caught by the generic handler.
        """
        logger.info(f"Sending message to task {task_id} on agent: {agent_card.human_readable_id}")
        try:
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            message_to_send = message
            if mcp_context:
                current_metadata = message_to_send.metadata or {}
                updated_metadata = {**current_metadata, "mcp_context": mcp_context}
                message_to_send = message_to_send.model_copy(update={'metadata': updated_metadata})
                logger.debug("Embedded MCP context into message metadata.")

            task_send_params = TaskSendParams(message=message_to_send, id=task_id)
            request_id = f"req-send-{uuid.uuid4()}"
            request_payload = {
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "params": task_send_params.model_dump(mode='json', exclude_none=True),
                "id": request_id
            }
            logger.debug(f"Send message request payload (id: {request_id}): {request_payload}")

            response_data = await self._make_request(
                'POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload
            )

            if not isinstance(response_data, dict):
                 raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")
            if "error" in response_data:
                error_data = response_data["error"]
                logger.error(f"Agent returned error sending message to task {task_id}: {error_data}")
                err_code = error_data.get("code", -1)
                err_msg = error_data.get("message", "Unknown remote agent error")
                err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data)
            if "result" not in response_data:
                raise A2AMessageError("Invalid response format: missing 'result' key.")
            try:
                TaskSendResult.model_validate(response_data["result"])
            except pydantic.ValidationError as e:
                raise A2AMessageError(f"Failed to validate send message result: {e}") from e

            logger.info(f"Message successfully sent to task {task_id} on agent {agent_card.human_readable_id}.")
            return True
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error sending message to task {task_id}: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error sending message to task {task_id}: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error sending message to task {task_id} on agent {agent_card.human_readable_id}: {e}")
            return False

    async def _process_sse_stream(
        self, byte_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Helper to process a raw byte stream according to SSE protocol.

        Parses event type and data, handling multi-line data and comments.
        Yields dictionaries containing the parsed event type and data.
        """
        buffer = ""
        current_event_type = None
        data_buffer = ""
        try:
            async for chunk in byte_stream:
                try:
                    buffer += chunk.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning("Received non-UTF8 chunk in SSE stream, skipping.")
                    buffer = "" # Reset buffer on decode error
                    continue

                while '\n' in buffer or '\r' in buffer:
                    # Process line by line, handling different line endings
                    line, separator, buffer = buffer.partition('\n')
                    if not separator and '\r' in line: # Handle \r line ending
                        line, separator, buffer = line.partition('\r') + buffer
                    elif separator == '\n' and line.endswith('\r'): # Handle \r\n
                        line = line[:-1]

                    # Process the complete line
                    if not line: # Empty line signifies end of event
                        if data_buffer:
                            event_type = current_event_type or "message" # Default type
                            logger.debug(f"Received SSE event: type='{event_type}', data='{data_buffer[:100]}...'")
                            try:
                                parsed_data = json.loads(data_buffer)
                                yield {"event_type": event_type, "data": parsed_data}
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to decode JSON data for SSE event type '{event_type}': {e}. Data: {data_buffer[:200]}...")
                                # Optionally raise A2AMessageError or just continue
                            # Reset for next event
                            data_buffer = ""
                            current_event_type = None
                        continue # Move to next line

                    if line.startswith(':'): # Ignore comments
                        continue

                    field, value = line.split(":", 1)
                    value = value.strip() # Remove leading/trailing whitespace

                    if field == "event":
                        current_event_type = value
                    elif field == "data":
                        if data_buffer:
                            data_buffer += "\n" # Add newline for multi-line data
                        data_buffer += value
                    elif field == "id": # Optional SSE field, ignore for now
                        pass
                    elif field == "retry": # Optional SSE field, ignore for now
                        pass
                    else:
                        logger.warning(f"Ignoring unknown SSE field: '{field}'")

        except Exception as e:
             # Catch errors during stream iteration (e.g., connection closed)
             logger.error(f"Error processing SSE stream: {e}", exc_info=True)
             raise A2AConnectionError(f"Error reading from SSE stream: {e}") from e
        finally:
            logger.debug("SSE byte stream processing finished.")
            # Note: Closing the underlying httpx stream is handled by _make_request/httpx client context


    async def receive_messages(
        self,
        agent_card: AgentCard,
        task_id: str,
        key_manager: KeyManager
    ) -> AsyncGenerator[A2AEvent, None]:
        """
        Subscribes to and yields events (status updates, messages, artifacts)
        for a specific task using Server-Sent Events (SSE).

        Assumes the agent supports SSE via a POST request to its main URL
        with the method 'tasks/sendSubscribe'.

        This generator will run until the connection is closed by the server,
        the consumer breaks the loop, or an error occurs.

        Args:
            agent_card: The AgentCard of the target agent.
            task_id: The ID of the task to subscribe to.
            key_manager: The KeyManager instance to retrieve authentication keys.

        Yields:
            A2AEvent: Validated Pydantic objects representing task status changes,
                      new messages, or artifact updates.

        Raises:
            A2AAuthenticationError: If required authentication key is missing or invalid.
            A2AConnectionError: If the initial connection or the stream fails during processing.
            A2ARemoteAgentError: If the agent returns an error during the initial subscription request.
            A2AMessageError: If received event data is malformed or cannot be validated.
            AgentVaultError: For other unexpected errors.
        """
        logger.info(f"Subscribing to events for task {task_id} on agent: {agent_card.human_readable_id}")
        byte_stream = None
        try:
            # 1. Get Authentication Headers
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            # Ensure headers allow streaming
            auth_headers["Accept"] = "text/event-stream"

            # 2. Construct JSON-RPC Request Payload for Subscription
            request_id = f"req-sub-{uuid.uuid4()}"
            request_payload = {
                "jsonrpc": "2.0",
                "method": "tasks/sendSubscribe", # Assuming this method name
                "params": {"id": task_id},
                "id": request_id
            }
            logger.debug(f"Subscribe request payload (id: {request_id}): {request_payload}")

            # 3. Initiate Streaming Request
            byte_stream = await self._make_request(
                'POST',
                str(agent_card.url),
                headers=auth_headers,
                json_payload=request_payload,
                stream=True
            )

            # Type check for safety, _make_request should raise if stream=True fails early
            if not isinstance(byte_stream, typing.AsyncGenerator):
                 raise A2AError(f"_make_request did not return an AsyncGenerator for stream=True (got {type(byte_stream)})") # Should not happen

            # 4. Process the SSE Stream
            async for event_dict in self._process_sse_stream(byte_stream):
                event_type = event_dict.get("event_type")
                event_data = event_dict.get("data")

                if not event_type or not isinstance(event_data, dict):
                    logger.warning(f"Skipping malformed event: {event_dict}")
                    continue

                # 5. Map event type to Pydantic model and validate
                event_model = SSE_EVENT_TYPE_MAP.get(event_type)
                if not event_model:
                    logger.warning(f"Received unknown SSE event type: '{event_type}'. Data: {event_data}")
                    continue

                try:
                    validated_event = event_model.model_validate(event_data)
                    logger.debug(f"Yielding validated event: {validated_event!r}")
                    yield validated_event
                except pydantic.ValidationError as e:
                    logger.error(f"Failed to validate SSE event type '{event_type}': {e}. Data: {event_data}")
                    # Optionally raise A2AMessageError or just log and continue
                    # raise A2AMessageError(f"Failed to validate SSE event type '{event_type}': {e}") from e
                    continue # Continue processing stream

        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error during event subscription or processing for task {task_id}: {e}")
            raise # Re-raise specific A2A errors
        except KeyManagementError as e:
             logger.error(f"Key management error during event subscription for task {task_id}: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error during event subscription for task {task_id} on agent {agent_card.human_readable_id}: {e}")
            raise A2AError(f"An unexpected error occurred during event subscription: {e}") from e
        # Note: No explicit finally block needed here to close stream,
        # as _make_request and httpx handle the underlying connection closure.


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

        Currently supports only 'apiKey' and 'none' schemes.

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
            return {"X-Api-Key": api_key}
        elif any(s.scheme == 'none' for s in agent_card.auth_schemes):
            logger.debug("Using 'none' authentication scheme.")
            return {}
        else:
            raise A2AAuthenticationError(
                f"No supported authentication scheme found for agent {agent_card.human_readable_id}. "
                f"Supported by agent: {supported_schemes}. Supported by client: ['apiKey', 'none']."
            )

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[bytes, None]]:
        """
        Internal helper to make HTTP requests using the client's httpx instance
        and handle common errors, converting them to A2A exceptions.
        """
        request_kwargs = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "json": json_payload
        }

        log_payload_str = f" Payload: {json.dumps(json_payload)}" if json_payload else "" # Log serialized payload
        logger.debug(f"Making A2A request: {method} {url}{log_payload_str}")

        try:
            if stream:
                response = await self._http_client.stream(**request_kwargs) # type: ignore[arg-type]
                try:
                    response.raise_for_status()
                    logger.debug(f"Stream request successful ({response.status_code}), returning byte stream.")
                    return response.aiter_bytes()
                except httpx.HTTPStatusError as e:
                    await response.aread() # Consume body before raising
                    await response.aclose()
                    logger.error(f"HTTP error on stream request {method} {url}: {e.response.status_code}")
                    raise A2ARemoteAgentError(
                        message=f"HTTP error {e.response.status_code} for {url}: {e.response.text}",
                        status_code=e.response.status_code,
                        response_body=e.response.text
                    ) from e
                except Exception as e_inner: # Catch errors during initial stream setup/check
                     await response.aclose() # Ensure closed on error
                     logger.error(f"Error setting up stream for {method} {url}: {e_inner}", exc_info=True)
                     raise A2AConnectionError(f"Failed to establish SSE stream: {e_inner}") from e_inner

            else: # Regular, non-streaming request
                response = await self._http_client.request(**request_kwargs) # type: ignore[arg-type]
                response.raise_for_status()
                try:
                    response_data = response.json()
                    # Truncate potentially large responses for logging
                    log_resp_data = response_data
                    if isinstance(log_resp_data, dict) and len(json.dumps(log_resp_data)) > 500:
                        log_resp_data = str(log_resp_data)[:500] + "..."
                    logger.debug(f"Request successful ({response.status_code}). Response JSON: {log_resp_data}")
                    return response_data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON response from {method} {url}: {e}. Response text: {response.text[:200]}...")
                    raise A2AMessageError(
                        f"Failed to decode JSON response from {url}. Status: {response.status_code}. Body: {response.text[:200]}..."
                    ) from e

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout for {method} {url}: {e}")
            raise A2ATimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error for {method} {url}: {e}")
            raise A2AConnectionError(f"Connection failed: {e}") from e
        except httpx.NetworkError as e: # Includes ConnectError but broader
            logger.error(f"Network error for {method} {url}: {e}")
            raise A2AConnectionError(f"Network error: {e}") from e
        except httpx.HTTPStatusError as e:
             # This catches errors from raise_for_status in non-stream case
             logger.error(f"HTTP error on request {method} {url}: {e.response.status_code}")
             raise A2ARemoteAgentError(
                 message=f"HTTP error {e.response.status_code} for {url}: {e.response.text}",
                 status_code=e.response.status_code,
                 response_body=e.response.text
             ) from e
        except httpx.RequestError as e:
            # Catch other httpx request-related errors
            logger.error(f"HTTP request error for {method} {url}: {e}")
            raise A2AConnectionError(f"HTTP request failed: {e}") from e
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error during request {method} {url}: {e}")
            raise A2AError(f"An unexpected error occurred during the request: {e}") from e


#
