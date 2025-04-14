"""
Provides FastAPI integration helpers for exposing BaseA2AAgent instances
as A2A compliant API endpoints.
"""

import logging
import json # Import json for JSONDecodeError handling
from typing import Any, Dict, Optional, Union, AsyncGenerator

import pydantic

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, JSONResponse


# Import the base agent class
from .agent import BaseA2AAgent

# Import necessary models from the core library
try:
    from agentvault.models import (
        Message, Task, TaskState, A2AEvent,
        TaskSendParams, TaskSendResult, TaskGetParams, GetTaskResult,
        TaskCancelParams, TaskCancelResult,
        TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent, Artifact
    )
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
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    class Artifact: pass # type: ignore
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

def create_jsonrpc_success_response(
    req_id: Union[str, int, None], result: Any
) -> Dict[str, Any]:
    """Helper to create a standard JSON-RPC success response dictionary."""
    return {"jsonrpc": "2.0", "result": result, "id": req_id}

class SSEResponse(StreamingResponse):
    """
    Custom FastAPI response class for Server-Sent Events (SSE).

    Formats A2AEvent objects yielded by an async generator into
    the text/event-stream format. Includes error handling for the generator.
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
                        # Yield an error event if serialization fails mid-stream
                        try:
                            error_data = json.dumps({"error": "serialization_error", "message": f"Failed to format event: {type(e).__name__}"})
                            error_event = f"event: error\ndata: {error_data}\n\n"
                            yield error_event.encode("utf-8")
                        except Exception as format_err:
                             logger.error(f"Failed to format SSE serialization error event: {format_err}")
            except Exception as e:
                 # Log errors from the source generator itself
                 logger.error(f"Error in source event generator for SSE: {e}", exc_info=True)
                 # --- MODIFIED: Include error message in SSE data ---
                 try:
                     # Include the actual error message string
                     error_data = json.dumps({"error": "stream_error", "message": f"Error generating events: {type(e).__name__}: {str(e)}"})
                     error_event = f"event: error\ndata: {error_data}\n\n"
                     yield error_event.encode("utf-8")
                 except Exception as format_err:
                     logger.error(f"Failed to format SSE stream error event: {format_err}")
                 # --- END MODIFIED ---
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


def create_a2a_router(
    agent: BaseA2AAgent,
    prefix: str = "",
    tags: Optional[list[str]] = None,
) -> APIRouter:
    """
    Creates a FastAPI APIRouter that exposes the A2A protocol methods...
    """
    if tags is None:
        tags = ["A2A Protocol"]

    router = APIRouter(
        prefix=prefix,
        tags=tags,
    )

    logger.info(f"Creating A2A router for agent: {agent.__class__.__name__} with prefix '{prefix}'")

    @router.post(
        "/",
        summary="A2A JSON-RPC Endpoint",
        description="Handles all A2A JSON-RPC requests (tasks/send, tasks/get, etc.)."
    )
    async def handle_a2a_request(
        request: Request,
        agent_instance: BaseA2AAgent = Depends(lambda: agent)
    ) -> Response:
        """Handles incoming A2A JSON-RPC requests over POST."""
        req_id: Union[str, int, None] = None
        payload: Optional[Dict[str, Any]] = None

        try:
            # 1. Parse JSON body
            try:
                payload = await request.json()
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse request body as JSON: {e}")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_PARSE_ERROR, "Parse error")
                return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

            # 2. Basic JSON-RPC structure validation
            # ... (validation logic remains the same) ...
            if not isinstance(payload, dict):
                logger.warning("Invalid request: Payload is not a dictionary.")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: Payload must be a JSON object.")
                return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

            jsonrpc_version = payload.get("jsonrpc")
            method = payload.get("method")
            params = payload.get("params")
            req_id = payload.get("id")

            if not isinstance(method, str) or not method:
                logger.warning("Invalid request: 'method' field is missing or not a string.")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'method' is required and must be a string.")
                return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

            if jsonrpc_version != "2.0":
                logger.warning(f"Invalid request: 'jsonrpc' field is not '2.0' (got: {jsonrpc_version}).")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'jsonrpc' must be '2.0'.")
                return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

            if "id" not in payload:
                 logger.warning("Invalid request: 'id' field is missing.")
                 error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'id' is missing.")
                 return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

            logger.info(f"Received valid JSON-RPC request: method='{method}', id='{req_id}'")


            # --- Method Routing Logic ---
            # ... (tasks/send, tasks/get, tasks/cancel logic remains the same, returning JSONResponse) ...

            if method == "tasks/send":
                try:
                    if not isinstance(params, dict):
                         raise pydantic.ValidationError.from_exception_data(
                             title="TaskSendParams",
                             line_errors=[{"type": "dict_type", "loc": ("params",), "msg": "Input should be a valid dictionary"}]
                         )
                    validated_params = TaskSendParams.model_validate(params)
                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for tasks/send: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                try:
                    task_id_result: str = await agent_instance.handle_task_send(
                        task_id=validated_params.id, message=validated_params.message
                    )
                    send_result = TaskSendResult(id=task_id_result)
                    success_resp = create_jsonrpc_success_response(req_id, send_result.model_dump(mode='json'))
                    return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)
                except A2AError as e:
                     logger.error(f"Agent error during tasks/send for id={req_id}: {e}", exc_info=False)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                except Exception as e:
                     logger.exception(f"Unexpected agent error during tasks/send for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif method == "tasks/get":
                try:
                    if not isinstance(params, dict):
                         raise pydantic.ValidationError.from_exception_data(
                             title="TaskGetParams",
                             line_errors=[{"type": "dict_type", "loc": ("params",), "msg": "Input should be a valid dictionary"}]
                         )
                    validated_params = TaskGetParams.model_validate(params)
                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for tasks/get: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                try:
                    task_result: Task = await agent_instance.handle_task_get(
                        task_id=validated_params.id
                    )
                    if not isinstance(task_result, Task):
                         logger.error(f"Agent handler for tasks/get returned unexpected type: {type(task_result)}")
                         raise TypeError("Agent handler must return a Task object for tasks/get")
                    success_resp = create_jsonrpc_success_response(req_id, task_result.model_dump(mode='json', by_alias=True))
                    return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)
                except A2AError as e:
                     logger.error(f"Agent error during tasks/get for id={req_id}: {e}", exc_info=False)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                except Exception as e:
                     logger.exception(f"Unexpected agent error during tasks/get for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif method == "tasks/cancel":
                try:
                    if not isinstance(params, dict):
                         raise pydantic.ValidationError.from_exception_data(
                             title="TaskCancelParams",
                             line_errors=[{"type": "dict_type", "loc": ("params",), "msg": "Input should be a valid dictionary"}]
                         )
                    validated_params = TaskCancelParams.model_validate(params)
                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for tasks/cancel: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                try:
                    cancel_accepted: bool = await agent_instance.handle_task_cancel(
                        task_id=validated_params.id
                    )
                    cancel_result = TaskCancelResult(success=cancel_accepted)
                    success_resp = create_jsonrpc_success_response(req_id, cancel_result.model_dump(mode='json'))
                    return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)
                except A2AError as e:
                     logger.error(f"Agent error during tasks/cancel for id={req_id}: {e}", exc_info=False)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                except Exception as e:
                     logger.exception(f"Unexpected agent error during tasks/cancel for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif method == "tasks/sendSubscribe":
                task_id: Optional[str] = None
                try:
                    # Basic validation
                    if not isinstance(params, dict):
                        raise ValueError("Params must be a dictionary.")
                    task_id = params.get("id")
                    if not isinstance(task_id, str) or not task_id:
                        raise ValueError("'id' parameter is required and must be a non-empty string.")

                    # --- MODIFIED: Call agent handler directly, let exceptions propagate to SSEResponse ---
                    # If this call succeeds, it returns the generator for SSEResponse
                    # If it fails, the exception will be caught by the outer try/except
                    event_generator = agent_instance.handle_subscribe_request(task_id=task_id)
                    logger.info(f"Subscription request successful for task {task_id}. Starting SSE stream.")
                    return SSEResponse(content=event_generator)
                    # --- END MODIFIED ---

                except (ValueError, TypeError, pydantic.ValidationError) as e: # Catch validation errors
                    logger.warning(f"Invalid params for tasks/sendSubscribe: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                # --- REMOVED: Specific error handling here, let outer handler or SSEResponse handle ---

            else:
                # Handle Method Not Found error
                logger.warning(f"Method not found: '{method}'")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_METHOD_NOT_FOUND, "Method not found")
                return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

        except Exception as e:
            # --- MODIFIED: Catch A2AError specifically here too ---
            if isinstance(e, A2AError):
                 logger.error(f"Agent error processing request id={req_id}: {e}", exc_info=False)
                 error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                 return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK) # Return 200 for JSON-RPC app errors
            else:
                 # --- END MODIFIED ---
                 logger.exception(f"Unexpected internal server error processing request id={req_id}")
                 final_req_id = req_id if payload and "id" in payload else None
                 error_resp = create_jsonrpc_error_response(final_req_id, JSONRPC_INTERNAL_ERROR, f"Internal server error: {type(e).__name__}")
                 # --- MODIFIED: Return 500 for truly unexpected errors ---
                 return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                 # --- END MODIFIED ---

    return router
