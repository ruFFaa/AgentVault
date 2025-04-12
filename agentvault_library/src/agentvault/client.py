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
    Message, Task, TaskState, TaskStatusUpdateEvent, TaskArtifactUpdateEvent,
    TaskMessageEvent, TaskSendParams, TaskSendResult, TaskGetParams,
    GetTaskResult, TaskCancelParams, TaskCancelResult
)
# Import local exceptions
from .exceptions import (
    AgentVaultError, A2AError, A2AConnectionError, A2AAuthenticationError,
    A2ARemoteAgentError, A2ATimeoutError, A2AMessageError, KeyManagementError
)
# Import KeyManager
from .key_manager import KeyManager
# --- ADDED IMPORT ---
from .mcp_utils import format_mcp_context
# --- END ADDED IMPORT ---

logger = logging.getLogger(__name__)
A2AEvent = Union[TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent]
SSE_EVENT_TYPE_MAP = {
    "task_status": TaskStatusUpdateEvent, "task_message": TaskMessageEvent,
    "task_artifact": TaskArtifactUpdateEvent, "message": TaskMessageEvent,
}

class AgentVaultClient:
    """ Client for interacting with remote agents using A2A protocol. """
    # (__init__, close, __aenter__, __aexit__ unchanged)
    def __init__(
        self, http_client: Optional[httpx.AsyncClient] = None, default_timeout: float = 30.0
    ):
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
        if self._should_close_client and not self._http_client.is_closed:
            logger.debug("Closing internally managed httpx.AsyncClient instance.")
            await self._http_client.aclose()
        elif not self._should_close_client:
             logger.debug("Using externally managed httpx.AsyncClient, not closing.")

    async def __aenter__(self) -> "AgentVaultClient": return self
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: await self.close()

    # --- Public A2A Methods ---
    # (receive_messages, _process_sse_stream, get_task_status, terminate_task - unchanged)
    async def initiate_task(
        self, agent_card: AgentCard, initial_message: Message, key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> str:
        logger.info(f"Initiating task with agent: {agent_card.human_readable_id}")
        try:
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            message_to_send = initial_message
            # --- MODIFIED MCP HANDLING ---
            if mcp_context:
                formatted_mcp = format_mcp_context(mcp_context)
                if formatted_mcp is not None:
                    current_metadata = message_to_send.metadata or {}
                    # Embed the formatted MCP dict
                    updated_metadata = {**current_metadata, "mcp_context": formatted_mcp}
                    message_to_send = message_to_send.model_copy(update={'metadata': updated_metadata})
                    logger.debug("Successfully formatted and embedded MCP context into message metadata.")
                else:
                    # Log warning if formatting failed, but proceed without MCP context
                    logger.warning("Failed to format provided MCP context data. Proceeding without embedding it.")
            # --- END MODIFIED MCP HANDLING ---

            task_send_params = TaskSendParams(message=message_to_send, id=None)
            request_id = f"req-init-{uuid.uuid4()}"
            request_params = task_send_params.model_dump(mode='json', exclude_none=True, by_alias=True)
            request_payload = {"jsonrpc": "2.0", "method": "tasks/send", "params": request_params, "id": request_id}
            logger.debug(f"Initiate task request payload (id: {request_id})")
            response_data = await self._make_request('POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload)
            if not isinstance(response_data, dict): raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")
            if "error" in response_data:
                error_data = response_data["error"]; logger.error(f"Agent returned error during task initiation: {error_data}")
                err_code = error_data.get("code", -1); err_msg = error_data.get("message", "Unknown remote agent error"); err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data)
            if "result" not in response_data: raise A2AMessageError("Invalid response format: missing 'result' key.")
            try: result_obj = TaskSendResult.model_validate(response_data["result"])
            except pydantic.ValidationError as e: raise A2AMessageError(f"Failed to validate task initiation result: {e}") from e
            task_id = result_obj.id
            if not task_id: raise A2AMessageError("Invalid response format: 'result.id' is missing or empty.")
            logger.info(f"Task successfully initiated with agent {agent_card.human_readable_id}. Task ID: {task_id}")
            return task_id
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error during task initiation: {type(e).__name__}: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error during task initiation: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during task initiation with agent {agent_card.human_readable_id}: {e}")
            raise A2AError(f"An unexpected error occurred during task initiation: {e}") from e

    async def send_message(
        self, agent_card: AgentCard, task_id: str, message: Message, key_manager: KeyManager,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        logger.info(f"Sending message to task {task_id} on agent: {agent_card.human_readable_id}")
        try:
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            message_to_send = message
            # --- MODIFIED MCP HANDLING ---
            if mcp_context:
                formatted_mcp = format_mcp_context(mcp_context)
                if formatted_mcp is not None:
                    current_metadata = message_to_send.metadata or {}
                    # Embed the formatted MCP dict
                    updated_metadata = {**current_metadata, "mcp_context": formatted_mcp}
                    message_to_send = message_to_send.model_copy(update={'metadata': updated_metadata})
                    logger.debug("Successfully formatted and embedded MCP context into message metadata.")
                else:
                    # Log warning if formatting failed, but proceed without MCP context
                    logger.warning("Failed to format provided MCP context data. Proceeding without embedding it.")
            # --- END MODIFIED MCP HANDLING ---

            task_send_params = TaskSendParams(message=message_to_send, id=task_id)
            request_id = f"req-send-{uuid.uuid4()}"
            request_params = task_send_params.model_dump(mode='json', exclude_none=True, by_alias=True)
            request_payload = {"jsonrpc": "2.0", "method": "tasks/send", "params": request_params, "id": request_id}
            logger.debug(f"Send message request payload (id: {request_id})")
            response_data = await self._make_request('POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload)
            if not isinstance(response_data, dict): raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")
            if "error" in response_data:
                error_data = response_data["error"]; logger.error(f"Agent returned error sending message to task {task_id}: {error_data}")
                err_code = error_data.get("code", -1); err_msg = error_data.get("message", "Unknown remote agent error"); err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data)
            if "result" not in response_data: raise A2AMessageError("Invalid response format: missing 'result' key.")
            try: TaskSendResult.model_validate(response_data["result"])
            except pydantic.ValidationError as e: raise A2AMessageError(f"Failed to validate send message result: {e}") from e
            logger.info(f"Message successfully sent to task {task_id} on agent {agent_card.human_readable_id}.")
            return True
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error sending message to task {task_id}: {type(e).__name__}: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error sending message to task {task_id}: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error sending message to task {task_id} on agent {agent_card.human_readable_id}: {e}")
            return False # Return False on unexpected errors

    async def _process_sse_stream(self, byte_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[Dict[str, Any], None]:
        buffer = ""; current_event_type = None; data_buffer = ""
        try:
            async for chunk in byte_stream:
                try: buffer += chunk.decode('utf-8')
                except UnicodeDecodeError: logger.warning("Received non-UTF8 chunk in SSE stream, skipping."); buffer = ""; continue
                while '\n' in buffer or '\r' in buffer:
                    line, separator, buffer = buffer.partition('\n')
                    if not separator and '\r' in line: line, separator, buffer = line.partition('\r') + buffer
                    elif separator == '\n' and line.endswith('\r'): line = line[:-1]
                    if not line:
                        if data_buffer:
                            event_type = current_event_type or "message"
                            logger.debug(f"Received SSE event: type='{event_type}', data='{data_buffer[:100]}...'")
                            try: yield {"event_type": event_type, "data": json.loads(data_buffer)}
                            except json.JSONDecodeError as e: logger.error(f"Failed to decode JSON data for SSE event type '{event_type}': {e}. Data: {data_buffer[:200]}...")
                            data_buffer = ""; current_event_type = None
                        continue
                    if line.startswith(':'): continue
                    try:
                        field, value = line.split(":", 1); value = value.strip()
                        if field == "event": current_event_type = value
                        elif field == "data": data_buffer += ("\n" if data_buffer else "") + value
                    except ValueError: logger.warning(f"Ignoring malformed SSE line: {line}")
        except Exception as e: logger.error(f"Error processing SSE stream: {e}", exc_info=True); raise A2AConnectionError(f"Error reading from SSE stream: {e}") from e
        finally: logger.debug("SSE byte stream processing finished.")

    async def receive_messages(self, agent_card: AgentCard, task_id: str, key_manager: KeyManager) -> AsyncGenerator[A2AEvent, None]:
        logger.info(f"Subscribing to events for task {task_id} on agent: {agent_card.human_readable_id}")
        byte_stream = None
        try:
            auth_headers = self._get_auth_headers(agent_card, key_manager); auth_headers["Accept"] = "text/event-stream"
            request_id = f"req-sub-{uuid.uuid4()}"
            request_payload = {"jsonrpc": "2.0", "method": "tasks/sendSubscribe", "params": {"id": task_id}, "id": request_id}
            logger.debug(f"Subscribe request payload (id: {request_id})")
            byte_stream = await self._make_request('POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload, stream=True)
            if not isinstance(byte_stream, typing.AsyncGenerator): raise A2AError(f"_make_request did not return an AsyncGenerator for stream=True (got {type(byte_stream)})")
            async for event_dict in self._process_sse_stream(byte_stream):
                event_type = event_dict.get("event_type"); event_data = event_dict.get("data")
                if not event_type or not isinstance(event_data, dict): logger.warning(f"Skipping malformed event: {event_dict}"); continue
                event_model = SSE_EVENT_TYPE_MAP.get(event_type)
                if not event_model: logger.warning(f"Received unknown SSE event type: '{event_type}'. Data: {event_data}"); continue
                try: validated_event = event_model.model_validate(event_data); logger.debug(f"Yielding validated event: {validated_event!r}"); yield validated_event
                except pydantic.ValidationError as e: logger.error(f"Failed to validate SSE event type '{event_type}': {e}. Data: {event_data}"); continue
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error during event subscription or processing for task {task_id}: {type(e).__name__}: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error during event subscription for task {task_id}: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during event subscription for task {task_id} on agent {agent_card.human_readable_id}: {e}")
            raise A2AError(f"An unexpected error occurred during event subscription: {e}") from e

    async def get_task_status(self, agent_card: AgentCard, task_id: str, key_manager: KeyManager) -> Task:
        logger.info(f"Getting status for task {task_id} on agent: {agent_card.human_readable_id}")
        try:
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            task_get_params = TaskGetParams(id=task_id)
            request_id = f"req-get-{uuid.uuid4()}"
            request_params = task_get_params.model_dump(mode='json', by_alias=True)
            request_payload = {"jsonrpc": "2.0", "method": "tasks/get", "params": request_params, "id": request_id}
            logger.debug(f"Get task status request payload (id: {request_id})")
            response_data = await self._make_request('POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload)
            if not isinstance(response_data, dict): raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")
            if "error" in response_data:
                error_data = response_data["error"]; logger.error(f"Agent returned error getting status for task {task_id}: {error_data}")
                err_code = error_data.get("code", -1); err_msg = error_data.get("message", "Unknown remote agent error"); err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data)
            if "result" not in response_data: raise A2AMessageError("Invalid response format: missing 'result' key.")
            try: task_object = GetTaskResult.model_validate(response_data["result"]); logger.info(f"Successfully retrieved status for task {task_id}. State: {task_object.state}"); return task_object
            except pydantic.ValidationError as e: raise A2AMessageError(f"Failed to validate task status result: {e}") from e
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error getting status for task {task_id}: {type(e).__name__}: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error getting status for task {task_id}: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error getting status for task {task_id} on agent {agent_card.human_readable_id}: {e}")
            raise A2AError(f"An unexpected error occurred getting task status: {e}") from e

    async def terminate_task(self, agent_card: AgentCard, task_id: str, key_manager: KeyManager) -> bool:
        logger.info(f"Requesting termination for task {task_id} on agent: {agent_card.human_readable_id}")
        try:
            auth_headers = self._get_auth_headers(agent_card, key_manager)
            task_cancel_params = TaskCancelParams(id=task_id)
            request_id = f"req-cancel-{uuid.uuid4()}"
            request_params = task_cancel_params.model_dump(mode='json', by_alias=True)
            request_payload = {"jsonrpc": "2.0", "method": "tasks/cancel", "params": request_params, "id": request_id}
            logger.debug(f"Terminate task request payload (id: {request_id})")
            response_data = await self._make_request('POST', str(agent_card.url), headers=auth_headers, json_payload=request_payload)
            if not isinstance(response_data, dict): raise A2AMessageError(f"Invalid response format: Expected dictionary, got {type(response_data)}")
            if "error" in response_data:
                error_data = response_data["error"]; logger.error(f"Agent returned error terminating task {task_id}: {error_data}")
                err_code = error_data.get("code", -1); err_msg = error_data.get("message", "Unknown remote agent error"); err_data = error_data.get("data")
                raise A2ARemoteAgentError(message=err_msg, status_code=err_code, response_body=err_data)
            if "result" not in response_data: raise A2AMessageError("Invalid response format: missing 'result' key.")
            try: TaskCancelResult.model_validate(response_data["result"])
            except pydantic.ValidationError as e: raise A2AMessageError(f"Failed to validate terminate task result: {e}") from e
            logger.info(f"Termination request for task {task_id} acknowledged by agent {agent_card.human_readable_id}.")
            return True
        except (A2AAuthenticationError, A2AConnectionError, A2ARemoteAgentError, A2AMessageError, A2ATimeoutError) as e:
            logger.error(f"A2A error terminating task {task_id}: {type(e).__name__}: {e}")
            raise
        except KeyManagementError as e:
             logger.error(f"Key management error terminating task {task_id}: {e}")
             raise A2AAuthenticationError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error terminating task {task_id} on agent {agent_card.human_readable_id}: {e}")
            return False # Return False on unexpected errors

    # --- Private Helper Methods ---
    def _get_auth_headers(self, agent_card: AgentCard, key_manager: KeyManager) -> Dict[str, str]:
        """(Docstring unchanged)"""
        # --- FIX: Access agent_card.auth_schemes (snake_case) ---
        agent_schemes = agent_card.auth_schemes
        supported_schemes_str = [s.scheme for s in agent_schemes] # For logging
        logger.debug(f"Agent supports auth schemes: {supported_schemes_str}")

        # Check for apiKey FIRST
        api_key_scheme = next((s for s in agent_schemes if s.scheme == 'apiKey'), None)
        if api_key_scheme:
            service_id = api_key_scheme.service_identifier or agent_card.human_readable_id
            if not service_id: raise A2AAuthenticationError(f"Cannot determine service identifier for apiKey scheme on agent {agent_card.human_readable_id}.")
            logger.debug(f"Attempting to retrieve key for service_id '{service_id}' using apiKey scheme.")
            api_key = key_manager.get_key(service_id)
            if not api_key: raise A2AAuthenticationError(f"Missing API key for service '{service_id}' required by agent '{agent_card.human_readable_id}' (scheme: apiKey).")
            logger.debug(f"Using apiKey scheme for service_id '{service_id}'.")
            return {"X-Api-Key": api_key}

        # Check for none SECOND
        none_scheme_present = any(s.scheme == 'none' for s in agent_schemes)
        if none_scheme_present:
            logger.debug("Using 'none' authentication scheme.")
            return {}

        # If NEITHER apiKey NOR none was found, THEN raise error
        client_supported = ['apiKey', 'none']
        log_msg = (f"No compatible authentication scheme found for agent {agent_card.human_readable_id}. "
                   f"Agent supports: {supported_schemes_str}. Client supports: {client_supported}.")
        logger.error(log_msg)
        raise A2AAuthenticationError(log_msg)

    async def _make_request(
        self, method: str, url: str, headers: Optional[Dict[str, str]] = None,
        json_payload: Optional[Dict[str, Any]] = None, stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[bytes, None]]:
        """(Implementation unchanged)"""
        request_kwargs = {"method": method, "url": url, "headers": headers or {}, "json": json_payload}
        logger.debug(f"Making A2A request: {method} {url}") # Simplified logging
        try:
            if stream:
                response = await self._http_client.stream(**request_kwargs)
                try:
                    response.raise_for_status()
                    logger.debug(f"Stream request successful ({response.status_code}), returning byte stream.")
                    return response.aiter_bytes()
                except httpx.HTTPStatusError as e:
                    await response.aread(); await response.aclose()
                    logger.error(f"HTTP error on stream request {method} {url}: {e.response.status_code}")
                    raise A2ARemoteAgentError(message=f"HTTP error {e.response.status_code} for {url}: {e.response.text}", status_code=e.response.status_code, response_body=e.response.text) from e
                except Exception as e_inner:
                     await response.aclose()
                     logger.error(f"Error setting up stream for {method} {url}: {e_inner}", exc_info=True)
                     raise A2AConnectionError(f"Failed to establish SSE stream: {e_inner}") from e_inner
            else:
                response = await self._http_client.request(**request_kwargs)
                response.raise_for_status()
                try:
                    response_data = response.json()
                    log_resp_str = f"{response_data}"
                    if len(log_resp_str) > 500: log_resp_str = log_resp_str[:500] + "..."
                    logger.debug(f"Request successful ({response.status_code}). Response: {log_resp_str}")
                    return response_data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON response from {method} {url}: {e}. Response text: {response.text[:200]}...")
                    raise A2AMessageError(f"Failed to decode JSON response from {url}. Status: {response.status_code}. Body: {response.text[:200]}...") from e
        except httpx.TimeoutException as e: logger.error(f"Request timeout for {method} {url}: {e}"); raise A2ATimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e: logger.error(f"Connection error for {method} {url}: {e}"); raise A2AConnectionError(f"Connection failed: {e}") from e
        except httpx.NetworkError as e: logger.error(f"Network error for {method} {url}: {e}"); raise A2AConnectionError(f"Network error: {e}") from e
        except httpx.HTTPStatusError as e: logger.error(f"HTTP error on request {method} {url}: {e.response.status_code}"); raise A2ARemoteAgentError(message=f"HTTP error {e.response.status_code} for {url}: {e.response.text}", status_code=e.response.status_code, response_body=e.response.text) from e
        except httpx.RequestError as e: logger.error(f"HTTP request error for {method} {url}: {e}"); raise A2AConnectionError(f"HTTP request failed: {e}") from e
        except (A2AMessageError) as e:
             logger.error(f"A2A message error during request processing: {e}")
             raise
        except Exception as e:
            logger.exception(f"Unexpected error during request {method} {url}: {e}")
            raise A2AError(f"An unexpected error occurred during the request: {e}") from e

#
