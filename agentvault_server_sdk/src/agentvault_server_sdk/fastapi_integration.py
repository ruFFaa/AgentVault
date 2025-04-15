"""
Provides FastAPI integration helpers for exposing BaseA2AAgent instances
as A2A compliant API endpoints.
"""

import logging
import json
import inspect
import asyncio
from typing import Any, Dict, Optional, Union, AsyncGenerator, Callable, TypeVar, List

import pydantic
from pydantic import RootModel, create_model


from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, JSONResponse

# Import the base agent class and state management
from .agent import BaseA2AAgent
from .state import BaseTaskStore, InMemoryTaskStore, TaskContext
from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError


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

# JSON-RPC Error Codes
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_APP_ERROR = -32000
JSONRPC_TASK_NOT_FOUND = -32001

# Decorator Definition
F = TypeVar('F', bound=Callable[..., Any])

def a2a_method(method_name: str) -> Callable[[F], F]:
    """
    Decorator to mark agent methods as handlers for specific A2A JSON-RPC methods.

    Attaches the specified `method_name` as the '_a2a_method_name' attribute
    to the decorated async function. Raises TypeError if applied to a sync function.

    Args:
        method_name: The JSON-RPC method name (e.g., "custom/my_action").
    """
    if not isinstance(method_name, str) or not method_name:
        raise ValueError("a2a_method decorator requires a non-empty string method_name.")

    def _decorator(func: F) -> F:
        """Inner decorator function."""
        # Ensure the decorated function is async
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"A2A method handler '{func.__name__}' must be an async function (defined with 'async def').")

        # Attach the method name as an attribute
        setattr(func, '_a2a_method_name', method_name)
        logger.debug(f"Marking method '{func.__name__}' as handler for A2A method '{method_name}'")
        return func
    return _decorator

# JSON-RPC Response Helpers
def create_jsonrpc_error_response(req_id: Union[str, int, None], code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    error_obj: Dict[str, Any] = {"code": code, "message": message}
    if data is not None: error_obj["data"] = data
    return {"jsonrpc": "2.0", "error": error_obj, "id": req_id}

def create_jsonrpc_success_response(req_id: Union[str, int, None], result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": req_id}

# SSE Response Class
class SSEResponse(StreamingResponse):
    """ Custom FastAPI response class for Server-Sent Events (SSE). """
    media_type = "text/event-stream"

    def __init__(
        self,
        content: AsyncGenerator[A2AEvent, None],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        async def event_publisher(event_generator: AsyncGenerator[A2AEvent, None]) -> AsyncGenerator[bytes, None]:
            try:
                async for event in event_generator: # This is where the error occurred
                    event_type: Optional[str] = None
                    if _AGENTVAULT_IMPORTED:
                        if isinstance(event, TaskStatusUpdateEvent): event_type = "task_status"
                        elif isinstance(event, TaskMessageEvent): event_type = "task_message"
                        elif isinstance(event, TaskArtifactUpdateEvent): event_type = "task_artifact"

                    if event_type is None:
                        logger.warning(f"SSEResponse received unknown or unidentifiable event type: {type(event)}. Skipping.")
                        continue

                    try:
                        if _AGENTVAULT_IMPORTED and hasattr(event, 'model_dump_json'):
                             json_data = event.model_dump_json(by_alias=True)
                        else:
                             json_data = json.dumps(event if isinstance(event, dict) else {"data": str(event)})
                        sse_message = f"event: {event_type}\ndata: {json_data}\n\n"
                        yield sse_message.encode("utf-8")
                    except Exception as e:
                        logger.error(f"Failed to serialize or format SSE event (type: {event_type}): {e}", exc_info=True)
                        try:
                            error_data = json.dumps({"error": "serialization_error", "message": f"Failed to format event: {type(e).__name__}"})
                            error_event = f"event: error\ndata: {error_data}\n\n"
                            yield error_event.encode("utf-8")
                        except Exception as format_err: logger.error(f"Failed to format SSE serialization error event: {format_err}")
            except Exception as e:
                 logger.error(f"Error in source event generator for SSE: {e}", exc_info=True)
                 try:
                     error_data = json.dumps({"error": "stream_error", "message": f"Error generating events: {type(e).__name__}: {str(e)}"})
                     error_event = f"event: error\ndata: {error_data}\n\n"
                     yield error_event.encode("utf-8")
                 except Exception as format_err: logger.error(f"Failed to format SSE stream error event: {format_err}")
            finally: logger.debug("SSE event generator finished.")

        super().__init__(content=event_publisher(content), status_code=status_code, headers=headers, media_type=self.media_type, **kwargs)


# Exception Handler Definitions
async def task_not_found_handler(request: Request, exc: TaskNotFoundError) -> JSONResponse:
    logger.warning(f"Task not found error: {exc}")
    req_id = getattr(request.state, 'json_rpc_request_id', None)
    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_TASK_NOT_FOUND, str(exc))
    return JSONResponse(status_code=status.HTTP_200_OK, content=error_resp) # Return 200 OK for JSON-RPC errors

async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.warning(f"Validation error (ValueError/TypeError/Pydantic): {exc}", exc_info=False)
    req_id = getattr(request.state, 'json_rpc_request_id', None)
    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_PARAMS, f"Invalid parameters: {exc}")
    return JSONResponse(status_code=status.HTTP_200_OK, content=error_resp)

async def agent_server_error_handler(request: Request, exc: AgentServerError) -> JSONResponse:
    logger.error(f"Agent server error: {exc}", exc_info=True)
    req_id = getattr(request.state, 'json_rpc_request_id', None)
    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, f"Agent error: {exc}")
    return JSONResponse(status_code=status.HTTP_200_OK, content=error_resp)

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled internal server error: {exc}")
    req_id = getattr(request.state, 'json_rpc_request_id', None)
    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal server error: {type(exc).__name__}")
    # Keep 500 for truly unexpected internal server errors
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_resp)


def create_a2a_router(
    agent: BaseA2AAgent,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    task_store: Optional[BaseTaskStore] = None,
) -> APIRouter:
    """ Creates a FastAPI APIRouter that exposes A2A methods... """
    if tags is None: tags = ["A2A Protocol"]
    if task_store is None:
        logger.info("No task store provided, using default InMemoryTaskStore.")
        task_store = InMemoryTaskStore()
    final_task_store = task_store

    router = APIRouter(prefix=prefix, tags=tags)
    logger.info(f"Creating A2A router for agent: {agent.__class__.__name__} with prefix '{prefix}' using task store: {final_task_store.__class__.__name__}")

    # Inspect agent for decorated methods
    decorated_methods: Dict[str, Callable] = {}
    logger.debug(f"Inspecting agent instance '{agent.__class__.__name__}' for @a2a_method decorators...")
    try:
        # Iterate through methods that are coroutine functions
        for name, method_func in inspect.getmembers(agent, predicate=inspect.iscoroutinefunction):
            # Check if the method has our specific attribute
            if hasattr(method_func, '_a2a_method_name'):
                a2a_name = getattr(method_func, '_a2a_method_name')
                # Ensure the attached name is a valid string
                if isinstance(a2a_name, str) and a2a_name:
                    # Check for duplicates and warn/overwrite
                    if a2a_name in decorated_methods:
                        logger.warning(f"Duplicate @a2a_method name '{a2a_name}' found on method '{name}'. Overwriting previous handler ({decorated_methods[a2a_name].__name__}).")
                    decorated_methods[a2a_name] = method_func
                    logger.info(f"  Found A2A method: '{a2a_name}' handled by '{name}'")
                else:
                    logger.warning(f"Method '{name}' has '_a2a_method_name' attribute, but it's not a valid string: {a2a_name!r}")
    except Exception as inspect_err:
        logger.error(f"Error during inspection of agent methods: {inspect_err}", exc_info=True)
    logger.debug(f"Finished inspection. Found {len(decorated_methods)} decorated methods.")

    def get_task_store_dependency() -> BaseTaskStore: return final_task_store

    @router.post("/", summary="A2A JSON-RPC Endpoint", description="Handles all A2A JSON-RPC requests (tasks/send, tasks/get, etc.).")
    async def handle_a2a_request(
        request: Request,
        agent_instance: BaseA2AAgent = Depends(lambda: agent),
        task_store_dep: BaseTaskStore = Depends(get_task_store_dependency)
    ) -> Response:
        """Handles incoming A2A JSON-RPC requests over POST."""
        req_id: Union[str, int, None] = None; payload: Optional[Dict[str, Any]] = None
        try: payload = await request.json()
        except json.JSONDecodeError as e: logger.warning(f"Failed to parse request body as JSON: {e}"); error_resp = create_jsonrpc_error_response(None, JSONRPC_PARSE_ERROR, "Parse error"); return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

        if not isinstance(payload, dict): logger.warning("Invalid request: Payload is not a dictionary."); error_resp = create_jsonrpc_error_response(None, JSONRPC_INVALID_REQUEST, "Invalid Request: Payload must be a JSON object."); return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
        jsonrpc_version = payload.get("jsonrpc"); method = payload.get("method"); params = payload.get("params"); req_id = payload.get("id")
        request.state.json_rpc_request_id = req_id

        if not isinstance(method, str) or not method: logger.warning("Invalid request: 'method' field is missing or not a string."); error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'method' is required and must be a string."); return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)
        if jsonrpc_version != "2.0": logger.warning(f"Invalid request: 'jsonrpc' field is not '2.0' (got: {jsonrpc_version})."); error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INVALID_REQUEST, "Invalid Request: 'jsonrpc' must be '2.0'."); return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

        logger.info(f"Received valid JSON-RPC request: method='{method}', id='{req_id}'")

        handler_func = decorated_methods.get(method)

        if handler_func:
            logger.info(f"Routing request for method '{method}' to decorated handler '{handler_func.__name__}'")
            sig = inspect.signature(handler_func)
            param_fields: Dict[str, Any] = {}
            handler_needs_task_store = False
            python_param_names = [] # Store expected python names

            # --- MODIFIED: Build dynamic model fields ---
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'): continue
                python_param_names.append(param_name) # Store python name
                if param.annotation is BaseTaskStore or \
                   (isinstance(param.annotation, type) and issubclass(param.annotation, BaseTaskStore)):
                    handler_needs_task_store = True
                    continue # Don't add task store to the dynamic model

                param_annotation = param.annotation
                param_default = param.default
                default_value = ... if param_default is inspect.Parameter.empty else param_default
                annotation_to_use = Any if param_annotation is inspect.Parameter.empty else param_annotation
                param_fields[param_name] = (annotation_to_use, default_value)
            # --- END MODIFIED ---

            # --- MODIFIED: Map common aliases before validation ---
            params_dict = params if isinstance(params, dict) else {}
            mapped_params_dict = params_dict.copy() # Start with original params

            # Example mapping: JSON "id" -> Python "task_id"
            if "task_id" in python_param_names and "id" in params_dict:
                logger.debug(f"Mapping incoming param 'id' to 'task_id' for validation.")
                mapped_params_dict['task_id'] = params_dict.get('id')
            # Add other mappings here if needed (e.g., "message" -> "input_message")

            # Create and validate using the *mapped* dictionary
            ParamsModel = create_model(f'{handler_func.__name__}Params', **param_fields) # type: ignore
            validated_params_model = ParamsModel.model_validate(mapped_params_dict)
            # --- END MODIFIED ---

            # Dump validated data - keys will match Python param names
            validated_params_dict = validated_params_model.model_dump()

            # Prepare arguments for the handler function
            call_kwargs = validated_params_dict
            if handler_needs_task_store:
                call_kwargs['task_store'] = task_store_dep # Inject the store dependency

            # Call the decorated agent method
            result = await handler_func(**call_kwargs)

            # Optional: Validate return type if specified
            return_annotation = sig.return_annotation
            if return_annotation is not inspect.Parameter.empty and return_annotation is not type(None):
                is_pydantic_model = False
                if inspect.isclass(return_annotation) and issubclass(return_annotation, pydantic.BaseModel):
                    is_pydantic_model = True

                try:
                    if is_pydantic_model:
                        return_annotation.model_validate(result) # type: ignore
                    else:
                        ReturnTypeModel = RootModel[return_annotation] # type: ignore
                        ReturnTypeModel.model_validate(result)
                except pydantic.ValidationError as e:
                    logger.error(f"Return value validation failed for method '{method}': {e}", exc_info=True)
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, f"Internal Error: Invalid return type from handler for method '{method}'.")
                    return JSONResponse(content=error_resp, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Return success response
            success_resp = create_jsonrpc_success_response(req_id, result)
            return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)

        # Fallback to standard handle_... methods
        elif method == "tasks/send":
            validated_params = TaskSendParams.model_validate(params or {})
            task_id_result: str = await agent_instance.handle_task_send(task_id=validated_params.id, message=validated_params.message)
            send_result = TaskSendResult(id=task_id_result)
            success_resp = create_jsonrpc_success_response(req_id, send_result.model_dump(mode='json'))
            return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)

        elif method == "tasks/get":
            validated_params = TaskGetParams.model_validate(params or {})
            task_result: Task = await agent_instance.handle_task_get(task_id=validated_params.id)
            if not isinstance(task_result, Task): raise TypeError("Agent handler must return a Task object for tasks/get")
            success_resp = create_jsonrpc_success_response(req_id, task_result.model_dump(mode='json', by_alias=True))
            return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)

        elif method == "tasks/cancel":
            validated_params = TaskCancelParams.model_validate(params or {})
            cancel_accepted: bool = await agent_instance.handle_task_cancel(task_id=validated_params.id)
            cancel_result = TaskCancelResult(success=cancel_accepted)
            success_resp = create_jsonrpc_success_response(req_id, cancel_result.model_dump(mode='json'))
            return JSONResponse(content=success_resp, status_code=status.HTTP_200_OK)

        elif method == "tasks/sendSubscribe":
            if not isinstance(params, dict): raise ValueError("Params must be a dictionary.")
            task_id = params.get("id")
            if not isinstance(task_id, str) or not task_id: raise ValueError("'id' parameter is required.")

            task_context = await task_store_dep.get_task(task_id)
            if task_context is None: raise TaskNotFoundError(task_id=task_id)

            async def stream_wrapper() -> AsyncGenerator[A2AEvent, None]:
                agent_event_generator = agent_instance.handle_subscribe_request(task_id=task_id)
                async for event in agent_event_generator:
                    yield event

            logger.info(f"Subscription request successful for task {task_id}. Starting SSE stream.")
            return SSEResponse(content=stream_wrapper())

        # Final fallback for unknown methods
        else:
            logger.warning(f"Method not found: '{method}'")
            error_resp = create_jsonrpc_error_response(req_id, JSONRPC_METHOD_NOT_FOUND, "Method not found")
            return JSONResponse(content=error_resp, status_code=status.HTTP_200_OK)

    return router
