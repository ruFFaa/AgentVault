"""
Provides FastAPI integration helpers for exposing BaseA2AAgent instances
as A2A compliant API endpoints.
"""

import logging
import json # Import json for JSONDecodeError handling
# --- MODIFIED: Added AsyncGenerator ---
from typing import Any, Dict, Optional, Union, AsyncGenerator
# --- END MODIFIED ---


# --- ADDED: Import pydantic ---
import pydantic
# --- END ADDED ---

# --- MODIFIED: Import StreamingResponse ---
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
# --- END MODIFIED ---


# Import the base agent class
from .agent import BaseA2AAgent

# Import necessary models from the core library
try:
    from agentvault.models import (
        Message, Task, TaskState, A2AEvent,
        TaskSendParams, TaskSendResult, TaskGetParams, GetTaskResult,
        TaskCancelParams, TaskCancelResult,
        # --- ADDED: Import specific event types for mapping ---
        TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent
        # --- END ADDED ---
    )
    # Import exceptions for potential error handling later
    from agentvault.exceptions import A2AError, A2ARemoteAgentError, A2AMessageError
    _AGENTVAULT_IMPORTED = True
except ImportError:
    logging.getLogger(__name__).error("Failed to import from 'agentvault' library. FastAPI integration may not function correctly.")
    # Define placeholders if import fails
    class Message: pass # type: ignore
    class Task: pass # type: ignore
    class TaskState: pass # type: ignore
    class A2AEvent: pass # type: ignore
    class TaskSendParams: pass # type: ignore
    class TaskSendResult: pass # type: ignore
    class TaskGetParams: pass # type: ignore
    class GetTaskResult: pass # type: ignore
    class TaskCancelParams: pass # type: ignore
    class TaskCancelResult: pass # type: ignore
    class A2AError(Exception): pass # type: ignore
    class A2ARemoteAgentError(A2AError): pass # type: ignore
    class A2AMessageError(A2AError): pass # type: ignore
    # --- ADDED: Placeholders for event types ---
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    # --- END ADDED ---
    _AGENTVAULT_IMPORTED = False


logger = logging.getLogger(__name__)

# --- JSON-RPC Error Codes (subset) ---
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
# Application specific errors: -32000 to -32099
JSONRPC_APP_ERROR = -32000 # Generic application error

def create_jsonrpc_error_response(
    req_id: Union[str, int, None], code: int, message: str, data: Optional[Any] = None
) -> Dict[str, Any]:
    """Helper to create a standard JSON-RPC error response dictionary."""
    error_obj: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error_obj["data"] = data
    return {"jsonrpc": "2.0", "error": error_obj, "id": req_id}

# --- ADDED: Helper for Success Response ---
def create_jsonrpc_success_response(
    req_id: Union[str, int, None], result: Any
) -> Dict[str, Any]:
    """Helper to create a standard JSON-RPC success response dictionary."""
    return {"jsonrpc": "2.0", "result": result, "id": req_id}
# --- END ADDED ---

# --- ADDED: SSEResponse Class ---
class SSEResponse(StreamingResponse):
    """
    Custom FastAPI response class for Server-Sent Events (SSE).

    Formats A2AEvent objects yielded by an async generator into
    the text/event-stream format.
    """
    media_type = "text/event-stream"

    def __init__(
        self,
        content: AsyncGenerator[A2AEvent, None],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        # Define the internal generator that formats and encodes events
        async def event_publisher(event_generator: AsyncGenerator[A2AEvent, None]) -> AsyncGenerator[bytes, None]:
            try:
                async for event in event_generator:
                    event_type: Optional[str] = None
                    if isinstance(event, TaskStatusUpdateEvent):
                        event_type = "task_status"
                    elif isinstance(event, TaskMessageEvent):
                        event_type = "task_message"
                    elif isinstance(event, TaskArtifactUpdateEvent):
                        event_type = "task_artifact"
                    else:
                        logger.warning(f"SSEResponse received unknown event type: {type(event)}. Skipping.")
                        continue

                    try:
                        # Serialize the event data to JSON, using aliases
                        json_data = event.model_dump_json(by_alias=True)
                        # Format the SSE message
                        sse_message = f"event: {event_type}\ndata: {json_data}\n\n"
                        yield sse_message.encode("utf-8")
                    except Exception as e:
                        logger.error(f"Failed to serialize or format SSE event (type: {event_type}): {e}", exc_info=True)
                        # Optionally yield an error event to the client? For now, just log and continue.
            except Exception as e:
                 # Log errors from the source generator itself
                 logger.error(f"Error in source event generator for SSE: {e}", exc_info=True)
                 # Optionally yield a final error event to the client here
                 # error_event = f"event: error\ndata: {json.dumps({'message': 'Internal server error generating events.'})}\n\n"
                 # yield error_event.encode("utf-8")
            finally:
                 logger.debug("SSE event generator finished.")

        # Call the parent StreamingResponse init with the formatted content generator
        super().__init__(
            content=event_publisher(content),
            status_code=status_code,
            headers=headers,
            media_type=self.media_type,
            **kwargs,
        )
# --- END ADDED ---


def create_a2a_router(
    agent: BaseA2AAgent,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    # dependencies: Optional[Sequence[Depends]] = None, # Add later if needed
    # responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None, # Add later if needed
) -> APIRouter:
    """
    Creates a FastAPI APIRouter that exposes the A2A protocol methods
    (tasks/send, tasks/get, tasks/cancel, tasks/sendSubscribe) based on the
    provided agent instance.

    Handles JSON-RPC request parsing, routing to the appropriate agent handler
    method, basic error handling, and response formatting.

    Args:
        agent: An instance of a class derived from BaseA2AAgent.
        prefix: An optional path prefix for the router (e.g., "/a2a").
        tags: Optional list of tags for OpenAPI documentation.
        # dependencies: Optional sequence of FastAPI dependencies for the router.
        # responses: Optional dictionary defining additional OpenAPI responses.

    Returns:
        A FastAPI APIRouter instance configured with the A2A endpoints.
    """
    if tags is None:
        tags = ["A2A Protocol"]

    router = APIRouter(
        prefix=prefix,
        tags=tags,
        # dependencies=dependencies,
        # responses=responses,
    )

    logger.info(f"Creating A2A router for agent: {agent.__class__.__name__} with prefix '{prefix}'")

    @router.post(
        "/", # Mount at the root of the router's prefix
        # Define response model later when handling success cases
        # response_model=Union[Dict[str, Any], StreamingResponse], # Example
        summary="A2A JSON-RPC Endpoint",
        description="Handles all A2A JSON-RPC requests (tasks/send, tasks/get, etc.)."
    )
    async def handle_a2a_request(
        request: Request,
        # Inject the agent instance provided when creating the router
        agent_instance: BaseA2AAgent = Depends(lambda: agent)
    ) -> Response:
        """Handles incoming A2A JSON-RPC requests over POST."""
        req_id: Union[str, int, None] = None # Initialize request ID
        payload: Optional[Dict[str, Any]] = None # Initialize payload scope

        try:
            # 1. Parse JSON body
            try:
                payload = await request.json()
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse request body as JSON: {e}")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_PARSE_ERROR, "Parse error")
                return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            # 2. Basic JSON-RPC structure validation
            if not isinstance(payload, dict):
                logger.warning("Invalid request: Payload is not a dictionary.")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: Payload must be a JSON object.")
                return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            jsonrpc_version = payload.get("jsonrpc")
            method = payload.get("method")
            params = payload.get("params") # Can be dict or list, validation later
            req_id = payload.get("id") # Can be null, str, int

            # Validate required fields and jsonrpc version
            if not isinstance(method, str) or not method:
                logger.warning("Invalid request: 'method' field is missing or not a string.")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'method' is required and must be a string.")
                return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            if jsonrpc_version != "2.0":
                logger.warning(f"Invalid request: 'jsonrpc' field is not '2.0' (got: {jsonrpc_version}).")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'jsonrpc' must be '2.0'.")
                return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            if "id" not in payload:
                 logger.warning("Invalid request: 'id' field is missing.")
                 error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'id' is missing.")
                 return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            logger.info(f"Received valid JSON-RPC request: method='{method}', id='{req_id}'")

            # --- Method Routing Logic ---
            if method == "tasks/send":
                try:
                    # Validate parameters using the Pydantic model
                    if not isinstance(params, dict):
                         # --- MODIFIED: Raise specific error ---
                         raise pydantic.ValidationError.from_exception_data(
                             title="TaskSendParams",
                             line_errors=[{"type": "dict_type", "loc": ("params",), "msg": "Input should be a valid dictionary"}]
                         )
                         # --- END MODIFIED ---
                    validated_params = TaskSendParams.model_validate(params)
                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for tasks/send: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

                try:
                    # Call the agent's handler method
                    task_id_result: str = await agent_instance.handle_task_send(
                        task_id=validated_params.id,
                        message=validated_params.message
                    )
                    # Wrap the result in the expected response model
                    send_result = TaskSendResult(id=task_id_result)
                    # Create and return success response
                    success_resp = create_jsonrpc_success_response(req_id, send_result.model_dump(mode='json'))
                    return Response(content=json.dumps(success_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except A2AError as e: # Catch specific application errors from the agent
                     logger.error(f"Agent error during tasks/send for id={req_id}: {e}", exc_info=True)
                     # Use a generic application error code for now
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except Exception as e: # Catch unexpected errors in the agent handler
                     logger.exception(f"Unexpected agent error during tasks/send for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            elif method == "tasks/get":
                try:
                    # Validate parameters
                    if not isinstance(params, dict):
                         raise pydantic.ValidationError.from_exception_data(
                             title="TaskGetParams",
                             line_errors=[{"type": "dict_type", "loc": ("params",), "msg": "Input should be a valid dictionary"}]
                         )
                    validated_params = TaskGetParams.model_validate(params)
                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for tasks/get: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

                try:
                    # Call the agent's handler method
                    task_result: Task = await agent_instance.handle_task_get(
                        task_id=validated_params.id
                    )
                    # The result itself is the Task object
                    # Use GetTaskResult alias if needed, but Task is the actual model
                    # Ensure the returned object is actually a Task model instance
                    if not isinstance(task_result, Task):
                         logger.error(f"Agent handler for tasks/get returned unexpected type: {type(task_result)}")
                         raise TypeError("Agent handler must return a Task object for tasks/get")

                    # Create and return success response
                    success_resp = create_jsonrpc_success_response(req_id, task_result.model_dump(mode='json', by_alias=True))
                    return Response(content=json.dumps(success_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except A2AError as e: # Catch specific application errors
                     logger.error(f"Agent error during tasks/get for id={req_id}: {e}", exc_info=True)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except Exception as e: # Catch unexpected errors
                     logger.exception(f"Unexpected agent error during tasks/get for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            elif method == "tasks/cancel":
                try:
                    # Validate parameters
                    if not isinstance(params, dict):
                         raise pydantic.ValidationError.from_exception_data(
                             title="TaskCancelParams",
                             line_errors=[{"type": "dict_type", "loc": ("params",), "msg": "Input should be a valid dictionary"}]
                         )
                    validated_params = TaskCancelParams.model_validate(params)
                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for tasks/cancel: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

                try:
                    # Call the agent's handler method
                    cancel_accepted: bool = await agent_instance.handle_task_cancel(
                        task_id=validated_params.id
                    )
                    # Wrap the boolean result in the TaskCancelResult model
                    cancel_result = TaskCancelResult(success=cancel_accepted)
                    # Create and return success response
                    success_resp = create_jsonrpc_success_response(req_id, cancel_result.model_dump(mode='json'))
                    return Response(content=json.dumps(success_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except A2AError as e: # Catch specific application errors
                     logger.error(f"Agent error during tasks/cancel for id={req_id}: {e}", exc_info=True)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except Exception as e: # Catch unexpected errors
                     logger.exception(f"Unexpected agent error during tasks/cancel for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            elif method == "tasks/sendSubscribe":
                task_id: Optional[str] = None
                try:
                    # Basic validation: params must be a dict with a non-empty string 'id'
                    if not isinstance(params, dict):
                        raise ValueError("Params must be a dictionary.")
                    task_id = params.get("id")
                    if not isinstance(task_id, str) or not task_id:
                        raise ValueError("'id' parameter is required and must be a non-empty string.")

                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid params for tasks/sendSubscribe: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

                try:
                    # Call the agent's handler method to get the event generator
                    event_generator = agent_instance.handle_subscribe_request(task_id=task_id)

                    # --- MODIFIED: Return SSEResponse ---
                    logger.info(f"Subscription request successful for task {task_id}. Starting SSE stream.")
                    # Return the SSEResponse, passing the generator
                    return SSEResponse(content=event_generator)
                    # --- END MODIFIED ---

                except A2AError as e: # Catch specific application errors
                     logger.error(f"Agent error during tasks/sendSubscribe for id={req_id}: {e}", exc_info=True)
                     # Need to return a JSON-RPC error *before* starting the stream
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")
                except Exception as e: # Catch unexpected errors
                     logger.exception(f"Unexpected agent error during tasks/sendSubscribe for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

            else:
                # Handle Method Not Found error
                logger.warning(f"Method not found: '{method}'")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_METHOD_NOT_FOUND, "Method not found")
                return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

        except Exception as e:
            # --- TODO: Task 2.1.A.16: Refine top-level exception handling ---
            logger.exception(f"Unexpected internal server error processing request id={req_id}")
            # Ensure req_id is captured even if parsing failed early
            final_req_id = req_id if payload and "id" in payload else None
            error_resp = create_jsonrpc_error_response(final_req_id, JSONRPC_INTERNAL_ERROR, f"Internal server error: {type(e).__name__}")
            return Response(content=json.dumps(error_resp), status_code=status.HTTP_200_OK, media_type="application/json")

    return router
