"""
Provides FastAPI integration helpers for exposing BaseA2AAgent instances
as A2A compliant API endpoints.
"""

import logging
import json # Import json for JSONDecodeError handling
import inspect
import asyncio # Keep asyncio import
from typing import Any, Dict, Optional, Union, AsyncGenerator, Callable, TypeVar, List

import pydantic
from pydantic import RootModel

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, JSONResponse

# Import the base agent class and state management
from .agent import BaseA2AAgent
# --- MODIFIED: Import state classes ---
from .state import BaseTaskStore, InMemoryTaskStore, TaskContext
# --- END MODIFIED ---


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

# --- Decorator Definition ---
F = TypeVar('F', bound=Callable[..., Any])

def a2a_method(method_name: str) -> Callable[[F], F]:
    """
    Decorator to mark agent methods as handlers for specific A2A JSON-RPC methods.

    Args:
        method_name: The JSON-RPC method string (e.g., "tasks/send", "custom/my_method").
    """
    def _decorator(func: F) -> F:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"A2A method handler '{func.__name__}' must be an async function (defined with 'async def').")
        setattr(func, '_a2a_method_name', method_name)
        logger.debug(f"Marking method '{func.__name__}' as handler for A2A method '{method_name}'")
        return func
    return _decorator


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
    # --- ADDED: task_store argument ---
    task_store: Optional[BaseTaskStore] = None,
    # --- END ADDED ---
) -> APIRouter:
    """
    Creates a FastAPI APIRouter that exposes the A2A protocol methods...
    """
    if tags is None:
        tags = ["A2A Protocol"]

    # --- ADDED: Instantiate default task store if none provided ---
    if task_store is None:
        logger.info("No task store provided, using default InMemoryTaskStore.")
        task_store = InMemoryTaskStore()
    final_task_store = task_store # Use final variable for closure
    # --- END ADDED ---

    router = APIRouter(
        prefix=prefix,
        tags=tags,
    )

    logger.info(f"Creating A2A router for agent: {agent.__class__.__name__} with prefix '{prefix}' using task store: {final_task_store.__class__.__name__}")

    # --- ADDED: Inspect agent for decorated methods ---
    decorated_methods: Dict[str, Callable] = {}
    logger.debug(f"Inspecting agent instance '{agent.__class__.__name__}' for @a2a_method decorators...")
    try:
        for name, method_func in inspect.getmembers(agent, predicate=inspect.iscoroutinefunction):
            if hasattr(method_func, '_a2a_method_name'):
                a2a_name = getattr(method_func, '_a2a_method_name')
                if isinstance(a2a_name, str) and a2a_name:
                    if a2a_name in decorated_methods:
                         logger.warning(f"Duplicate @a2a_method name '{a2a_name}' found on method '{name}'. Overwriting previous handler ({decorated_methods[a2a_name].__name__}).")
                    decorated_methods[a2a_name] = method_func
                    logger.info(f"  Found A2A method: '{a2a_name}' handled by '{name}'")
                else:
                    logger.warning(f"Method '{name}' has '_a2a_method_name' attribute, but it's not a valid string: {a2a_name!r}")
    except Exception as inspect_err:
        logger.error(f"Error during inspection of agent methods: {inspect_err}", exc_info=True)
        # Decide if this should be fatal or just log and continue without decorators
        # raise RuntimeError("Failed to inspect agent for decorated methods.") from inspect_err
    logger.debug(f"Finished inspection. Found {len(decorated_methods)} decorated methods.")
    # --- END ADDED ---

    # --- ADDED: Dependency function for task store ---
    def get_task_store_dependency() -> BaseTaskStore:
        return final_task_store
    # --- END ADDED ---

    @router.post(
        "/",
        summary="A2A JSON-RPC Endpoint",
        description="Handles all A2A JSON-RPC requests (tasks/send, tasks/get, etc.)."
    )
    async def handle_a2a_request(
        request: Request,
        agent_instance: BaseA2AAgent = Depends(lambda: agent),
        # --- ADDED: Inject task store dependency ---
        task_store_dep: BaseTaskStore = Depends(get_task_store_dependency)
        # --- END ADDED ---
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
            params = payload.get("params") # Keep as raw dict/list/None for now
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


            # --- MODIFIED: Method Routing Logic ---
            handler_func: Optional[Callable] = decorated_methods.get(method)

            if handler_func:
                logger.info(f"Routing request for method '{method}' to decorated handler '{handler_func.__name__}'")
                # --- ADDED: Dynamic parameter validation and handler call ---
                try:
                    # 1. Get signature and build Pydantic fields
                    sig = inspect.signature(handler_func)
                    param_fields: Dict[str, Any] = {}
                    # --- MODIFIED: Inject task_store dependency if requested ---
                    handler_needs_task_store = False
                    for param_name, param in sig.parameters.items():
                        if param_name in ('self', 'cls'): # Skip self/cls
                            continue
                        # Check if the handler expects the task store
                        if param.annotation is BaseTaskStore or \
                           (isinstance(param.annotation, type) and issubclass(param.annotation, BaseTaskStore)):
                            handler_needs_task_store = True
                            continue # Don't add task_store to the dynamic model

                        param_annotation = param.annotation
                        param_default = param.default
                        default_value = ... if param_default is inspect.Parameter.empty else param_default
                        annotation_to_use = Any if param_annotation is inspect.Parameter.empty else param_annotation
                        param_fields[param_name] = (annotation_to_use, default_value)
                    # --- END MODIFIED ---

                    # 2. Create dynamic model
                    ParamsModel = pydantic.create_model(
                        f'{handler_func.__name__}Params',
                        **param_fields # type: ignore
                    )
                    logger.debug(f"Created dynamic Pydantic model for params: {ParamsModel.__name__} with fields {param_fields}")

                    # 3. Validate incoming params
                    params_dict = params if isinstance(params, dict) else {}
                    validated_params_model = ParamsModel.model_validate(params_dict)
                    validated_params_dict = validated_params_model.model_dump()
                    logger.debug(f"Validated params for '{method}': {validated_params_dict}")

                    # --- MODIFIED: Add task_store to call if needed ---
                    call_kwargs = validated_params_dict
                    if handler_needs_task_store:
                        call_kwargs['task_store'] = task_store_dep
                        logger.debug(f"Injecting task_store dependency into handler '{handler_func.__name__}'")
                    # --- END MODIFIED ---

                    # 4. Call the handler with validated parameters
                    result = await handler_func(**call_kwargs)

                    # --- ADDED: Return value validation ---
                    return_annotation = sig.return_annotation
                    # --- MODIFIED: Check for None and empty ---
                    if return_annotation is not inspect.Parameter.empty and return_annotation is not type(None):
                    # --- END MODIFIED ---
                        try:
                            # --- MODIFIED: Use RootModel for non-BaseModel types ---
                            is_pydantic_model = False
                            if inspect.isclass(return_annotation) and issubclass(return_annotation, pydantic.BaseModel):
                                is_pydantic_model = True

                            if is_pydantic_model:
                                return_annotation.model_validate(result) # type: ignore
                            else:
                                ReturnTypeModel = RootModel[return_annotation] # type: ignore
                                ReturnTypeModel.model_validate(result)
                            # --- END MODIFIED ---
                            logger.debug(f"Return value validated successfully against annotation: {return_annotation}")
                        except pydantic.ValidationError as e:
                            logger.error(f"Invalid return value type from handler '{handler_func.__name__}' for method '{method}'. Expected '{return_annotation}', got '{type(result)}'. Validation error: {e}")
                            error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: Invalid return type from handler for method '{method}'.")
                            return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        except Exception as e: # Catch other potential validation/create_model errors
                             logger.exception(f"Unexpected error during return value validation for handler '{handler_func.__name__}'")
                             error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, "Internal agent error during return validation.")
                             return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    # --- END ADDED ---

                    success_resp = create_jsonrpc_success_response(req_id, result)
                    return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)

                except pydantic.ValidationError as e:
                    logger.warning(f"Invalid params for decorated method '{method}': {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                except A2AError as e:
                     logger.error(f"Agent error during decorated method '{method}' for id={req_id}: {e}", exc_info=False)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent processing error: {e}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                except TypeError as e: # Catch issues calling handler with wrong args
                     logger.error(f"TypeError calling decorated method '{method}' for id={req_id}: {e}", exc_info=True)
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid parameters for method '{method}': {e}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
                except Exception as e:
                     logger.exception(f"Unexpected agent error during decorated method '{method}' for id={req_id}: {e}")
                     error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal agent error: {type(e).__name__}")
                     return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                # --- END ADDED ---

            # Fallback to standard handle_ methods if no decorator found
            elif method == "tasks/send":
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
                    # --- MODIFIED: Pass task_store_dep ---
                    task_id_result: str = await agent_instance.handle_task_send(
                        task_id=validated_params.id, message=validated_params.message #, task_store=task_store_dep # Add if handle_task_send needs it
                    )
                    # --- END MODIFIED ---
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
                    # --- MODIFIED: Pass task_store_dep ---
                    task_result: Task = await agent_instance.handle_task_get(
                        task_id=validated_params.id #, task_store=task_store_dep # Add if handle_task_get needs it
                    )
                    # --- END MODIFIED ---
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
                    # --- MODIFIED: Pass task_store_dep ---
                    cancel_accepted: bool = await agent_instance.handle_task_cancel(
                        task_id=validated_params.id #, task_store=task_store_dep # Add if handle_task_cancel needs it
                    )
                    # --- END MODIFIED ---
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

                    # --- MODIFIED: Pass task_store_dep ---
                    event_generator = agent_instance.handle_subscribe_request(
                        task_id=task_id #, task_store=task_store_dep # Add if handle_subscribe_request needs it
                    )
                    # --- END MODIFIED ---
                    logger.info(f"Subscription request successful for task {task_id}. Starting SSE stream.")
                    return SSEResponse(content=event_generator)

                except (ValueError, TypeError, pydantic.ValidationError) as e: # Catch validation errors
                    logger.warning(f"Invalid params for tasks/sendSubscribe: {e}")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid params: {e}")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

            # --- REMOVED temporary elif handler_func block ---

            else:
                # Handle Method Not Found error
                logger.warning(f"Method not found: '{method}'")
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_METHOD_NOT_FOUND, "Method not found")
                return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
            # --- END MODIFIED ---

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
