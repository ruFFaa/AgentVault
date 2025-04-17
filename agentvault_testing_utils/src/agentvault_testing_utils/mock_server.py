"""
Utilities for setting up mock A2A server endpoints using respx.
Includes stateful handling via passed-in stores.
"""

import logging
import json
import uuid
import datetime
import asyncio
from typing import Optional, Dict, Any, List, Callable, Tuple, AsyncGenerator, Union

import respx
import httpx
from urllib.parse import parse_qs

# Import core types from the agentvault library with fallback
try:
    from agentvault.models import Task, TaskState, A2AEvent, Message, TextPart, TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent
    _MODELS_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("Failed to import core types from 'agentvault'. Using dummy types for mock server.")
    class Task: pass # type: ignore
    class TaskState: # type: ignore
        SUBMITTED = "SUBMITTED"; WORKING = "WORKING"; COMPLETED = "COMPLETED"; FAILED = "FAILED"; CANCELED = "CANCELED" # type: ignore
    class Message: pass # type: ignore
    class TextPart: pass # type: ignore
    A2AEvent = Any # type: ignore
    class TaskStatusUpdateEvent: pass # type: ignore
    class TaskMessageEvent: pass # type: ignore
    class TaskArtifactUpdateEvent: pass # type: ignore
    _MODELS_AVAILABLE = False

logger = logging.getLogger(__name__)

# --- JSON-RPC Error Codes ---
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_APP_ERROR = -32000
JSONRPC_TASK_NOT_FOUND = -32001

# --- Helper Functions ---
def create_jsonrpc_error_response(req_id: Union[str, int, None], code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    """Helper to create a standard JSON-RPC error response dictionary."""
    error_obj: Dict[str, Any] = {"code": code, "message": message}
    if data is not None: error_obj["data"] = data
    return {"jsonrpc": "2.0", "error": error_obj, "id": req_id}

def create_jsonrpc_success_response(req_id: Union[str, int, None], result: Any) -> Dict[str, Any]:
    """Helper to create a standard JSON-RPC success response dictionary."""
    return {"jsonrpc": "2.0", "result": result, "id": req_id}

# --- MODIFIED: Default Mock Task Helper (accepts state) ---
def create_default_mock_task(task_id="mock-task-from-get", state: Union[TaskState, str] = TaskState.COMPLETED if _MODELS_AVAILABLE else "COMPLETED") -> Dict[str, Any]:
    """Creates a dictionary representing a valid Task for mocking JSON responses."""
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.isoformat().replace('+00:00', 'Z')

    # Ensure state is a string for JSON serialization if it's an enum
    state_str = state.value if _MODELS_AVAILABLE and isinstance(state, TaskState) else str(state)

    default_message_dict = {
        "role": "user",
        "parts": [{"type": "text", "content": "Mock initial"}],
        "metadata": None
    }

    return {
        "id": task_id,
        "state": state_str, # Use the potentially converted state string
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "messages": [default_message_dict],
        "artifacts": [],
        "metadata": None
    }
# --- END MODIFIED ---

DEFAULT_OAUTH_TOKEN_RESPONSE = {
    "access_token": "mock_access_token_12345",
    "token_type": "Bearer",
    "expires_in": 3600
}

# --- SSE Stream Helper ---
async def generate_sse_stream(events: List[A2AEvent]) -> AsyncGenerator[bytes, None]:
    """Generates an SSE byte stream from a list of events (for mock)."""
    logger.debug(f"Mock SSE stream starting, yielding {len(events)} pre-configured events.")
    event_count = 0
    try:
        for i, event in enumerate(events):
            event_type: Optional[str] = None
            if _MODELS_AVAILABLE:
                if isinstance(event, TaskStatusUpdateEvent): event_type = "task_status"
                elif isinstance(event, TaskMessageEvent): event_type = "task_message"
                elif isinstance(event, TaskArtifactUpdateEvent): event_type = "task_artifact"
            else: # Fallback
                 if "TaskStatusUpdateEvent" in str(type(event)): event_type = "task_status"
                 elif "TaskMessageEvent" in str(type(event)): event_type = "task_message"
                 elif "TaskArtifactUpdateEvent" in str(type(event)): event_type = "task_artifact"

            if event_type is None:
                 logger.warning(f"Could not determine event type for mock SSE: {type(event)}. Using 'message'.")
                 event_type = "message"

            try:
                if _MODELS_AVAILABLE and hasattr(event, 'model_dump_json'):
                    # Use exclude_none=True to match potential client expectations
                    data_str = event.model_dump_json(by_alias=True, exclude_none=True)
                else:
                    data_str = json.dumps(event if isinstance(event, dict) else {"data": str(event)})

                # --- MODIFIED: Ensure correct SSE format (single data line, double newline) ---
                sse_msg = f"event: {event_type}\ndata: {data_str}\n\n"
                # --- END MODIFIED ---
                logger.info(f"Mock SSE stream YIELDING event {i+1}/{len(events)}: {sse_msg.strip()!r}")
                yield sse_msg.encode('utf-8')
                event_count += 1
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error formatting mock SSE event {i+1}: {e}")
                error_data = json.dumps({"error": "mock_sse_format_error", "detail": str(e)})
                logger.info(f"Mock SSE stream YIELDING error event: event: error\\ndata: {error_data}\\n\\n")
                yield f"event: error\ndata: {error_data}\n\n".encode('utf-8')
                event_count += 1
        await asyncio.sleep(0.02)
    except Exception as e:
         logger.error(f"Error in mock SSE generator itself: {e}", exc_info=True)
         try:
             error_data = json.dumps({"error": "generator_error", "message": f"Generator failed: {type(e).__name__}: {str(e)}"})
             logger.info(f"Mock SSE stream YIELDING generator error event: event: error\\ndata: {error_data}\\n\\n")
             yield f"event: error\ndata: {error_data}\n\n".encode('utf-8')
             event_count += 1
         except Exception as format_err:
             logger.error(f"Failed to format SSE generator error event: {format_err}")
    finally:
        logger.debug(f"Mock SSE stream finished. Yielded {event_count} events.")


# --- Route Setup Function ---
# --- MODIFIED: Accept task_store and sse_event_store ---
def setup_mock_a2a_routes(
    mock_router: respx.mock,
    base_url: str,
    a2a_endpoint: str = "/a2a",
    token_endpoint: str = "/token",
    task_store: Optional[Dict[str, Dict]] = None, # Accept task store
    sse_event_store: Optional[Dict[str, List[A2AEvent]]] = None, # Accept event store
    token_endpoint_handler: Optional[Callable[[httpx.Request], httpx.Response]] = None,
    # --- MODIFIED: Correct type hint for handler ---
    a2a_endpoint_handler: Optional[Callable[[httpx.Request], httpx.Response]] = None,
    # --- END MODIFIED ---
    default_auth_check: Optional[Callable[[httpx.Request], Optional[httpx.Response]]] = None
):
    """ Sets up mock routes for A2A and OAuth, interacting with provided stores. """
    # --- END MODIFIED ---
    a2a_url = f"{base_url.rstrip('/')}{a2a_endpoint}"
    token_url = f"{base_url.rstrip('/')}{token_endpoint}"

    # Ensure stores are initialized if None
    _task_store = task_store if task_store is not None else {}
    _sse_event_store = sse_event_store if sse_event_store is not None else {}

    # --- Default Token Endpoint Handler (unchanged) ---
    def default_token_handler(request: httpx.Request) -> httpx.Response:
        # ... (implementation omitted for brevity) ...
        logger.debug(f"Mock Token Endpoint received request: {request.url}")
        try:
            body = request.content.decode('utf-8'); data = parse_qs(body)
            grant_type = data.get("grant_type", [None])[0]; client_id = data.get("client_id", [None])[0]; client_secret = data.get("client_secret", [None])[0]
            if grant_type == "client_credentials" and client_id and client_secret:
                logger.info(f"Mock Token Endpoint issuing token for client_id: {client_id}"); return httpx.Response(200, json=DEFAULT_OAUTH_TOKEN_RESPONSE)
            else:
                logger.warning(f"Mock Token Endpoint received invalid grant/creds: grant={grant_type}, id={client_id}"); return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Invalid client credentials or grant type."})
        except Exception as e:
            logger.error(f"Error in mock token handler: {e}", exc_info=True); return httpx.Response(500, json={"error": "server_error", "error_description": "Mock token server error."})

    # --- MODIFIED: Restored Default A2A Endpoint Handler ---
    def _default_a2a_handler_internal(request: httpx.Request) -> httpx.Response:
        # This internal handler now uses the _task_store and _sse_event_store from the outer scope
        logger.debug(f"Mock A2A Endpoint received request: {request.url} Method: {request.method}")
        req_id: Union[str, int, None] = None; payload: Optional[Dict[str, Any]] = None

        # Auth Check (unchanged)
        if default_auth_check:
            auth_response = default_auth_check(request)
            if auth_response: logger.warning(f"Mock A2A auth check failed: {auth_response.status_code}"); error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, "Authentication failed"); return httpx.Response(200, json=error_resp, headers={"Content-Type": "application/json"})

        # JSON-RPC Parsing (unchanged)
        try:
            payload = json.loads(request.content);
            if not isinstance(payload, dict): raise ValueError("Payload not a dict")
            method = payload.get("method"); params = payload.get("params", {}); req_id = payload.get("id")
            if not method or "id" not in payload or payload.get("jsonrpc") != "2.0": raise ValueError("Invalid JSON-RPC structure")
        except Exception as e:
            logger.warning(f"Mock A2A failed JSON-RPC parsing: {e}"); error_resp = create_jsonrpc_error_response(None, JSONRPC_PARSE_ERROR, "Parse error / Invalid Request"); return httpx.Response(200, json=error_resp, headers={"Content-Type": "application/json"})

        logger.info(f"Mock A2A processing method: {method}, id: {req_id}")

        # Method Routing (modified to use stores)
        try:
            if method == "tasks/send":
                task_id = params.get("id") # Existing task ID or None
                new_task = task_id is None
                task_id = task_id or f"mock-task-{uuid.uuid4().hex[:8]}" # Generate if new

                # --- MODIFIED: Use captured store ---
                current_state = TaskState.SUBMITTED if _MODELS_AVAILABLE else "SUBMITTED"
                if new_task:
                    _task_store[task_id] = {"state": current_state, "received_messages": 1}
                    logger.debug(f"Mock task store: Added new task '{task_id}' with state {current_state}")
                elif task_id in _task_store:
                    _task_store[task_id]["received_messages"] = _task_store[task_id].get("received_messages", 0) + 1
                    _task_store[task_id]["state"] = current_state
                    logger.debug(f"Mock task store: Updated task '{task_id}' state to {current_state}")
                else:
                    _task_store[task_id] = {"state": current_state, "received_messages": 1}
                    logger.warning(f"Mock task store: Task ID '{task_id}' provided but not found, creating.")
                # --- END MODIFIED ---

                result = {"id": task_id}; resp_json = create_jsonrpc_success_response(req_id, result); return httpx.Response(200, json=resp_json)

            elif method == "tasks/get":
                task_id = params.get("id")
                # --- MODIFIED: Use captured store ---
                if not task_id or task_id not in _task_store:
                # --- END MODIFIED ---
                    logger.warning(f"Mock A2A tasks/get: Task ID '{task_id}' not found in store.")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_TASK_NOT_FOUND, "Task not found"); return httpx.Response(200, json=error_resp)

                # Retrieve state from store and build response
                # --- MODIFIED: Use captured store ---
                task_state = _task_store[task_id].get("state", TaskState.COMPLETED if _MODELS_AVAILABLE else "COMPLETED")
                # --- END MODIFIED ---
                task_data_dict = create_default_mock_task(task_id, state=task_state) # Use helper with state
                resp_json = create_jsonrpc_success_response(req_id, task_data_dict); return httpx.Response(200, json=resp_json)

            elif method == "tasks/cancel":
                task_id = params.get("id")
                # --- MODIFIED: Use captured store ---
                if not task_id or task_id not in _task_store:
                # --- END MODIFIED ---
                    logger.warning(f"Mock A2A tasks/cancel: Task ID '{task_id}' not found in store.")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_TASK_NOT_FOUND, "Task not found"); return httpx.Response(200, json=error_resp)

                # Update state in store
                # --- MODIFIED: Use captured store ---
                _task_store[task_id]["state"] = TaskState.CANCELED if _MODELS_AVAILABLE else "CANCELED"
                # --- END MODIFIED ---
                logger.debug(f"Mock task store: Updated task '{task_id}' state to CANCELED")
                result = {"success": True}; resp_json = create_jsonrpc_success_response(req_id, result); return httpx.Response(200, json=resp_json)

            elif method == "tasks/sendSubscribe":
                task_id = params.get("id")
                # Check task existence first
                # --- MODIFIED: Use captured store ---
                if not task_id or task_id not in _task_store:
                # --- END MODIFIED ---
                    logger.warning(f"Mock A2A tasks/sendSubscribe: Task ID '{task_id}' not found in store.")
                    error_resp = create_jsonrpc_error_response(req_id, JSONRPC_TASK_NOT_FOUND, "Task not found"); return httpx.Response(200, json=error_resp)

                # Get events from store or default empty list
                # --- MODIFIED: Use captured store ---
                events = _sse_event_store.get(task_id, [])
                # --- END MODIFIED ---
                logger.info(f"Mock A2A sendSubscribe for {task_id}, returning SSE stream (events configured: {len(events)})")
                # --- MODIFIED: Return generator directly in 'content' ---
                return httpx.Response(
                    200,
                    headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"},
                    content=generate_sse_stream(events) # Pass the async generator to content
                )
                # --- END MODIFIED ---

            else:
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_METHOD_NOT_FOUND, "Method not found"); return httpx.Response(200, json=error_resp)
        except Exception as e:
            logger.exception(f"Error in mock A2A handler for method {method}: {e}"); error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, "Internal mock server error"); return httpx.Response(500, json=error_resp)
    # --- END MODIFIED ---

    # Register routes
    final_token_handler = token_endpoint_handler or default_token_handler
    # --- MODIFIED: Removed token route registration ---
    # mock_router.post(token_url).mock(side_effect=final_token_handler)
    # logger.info(f"Skipping mock token endpoint registration.")
    # --- END MODIFIED ---

    # --- MODIFIED: Use the internal handler ---
    final_a2a_handler = a2a_endpoint_handler or _default_a2a_handler_internal
    # --- END MODIFIED ---
    mock_router.post(a2a_url).mock(side_effect=final_a2a_handler)
    logger.info(f"Registered mock A2A endpoint at POST {a2a_url}")
