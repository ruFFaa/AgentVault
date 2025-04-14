"""
Utilities for setting up mock A2A server endpoints using respx.
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

# --- Default Mock Data ---
def create_default_mock_task(task_id="mock-task-from-get") -> Dict[str, Any]:
    """Creates a dictionary representing a valid Task for mocking JSON responses."""
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.isoformat().replace('+00:00', 'Z')

    # --- MODIFIED: Create message dict directly for consistency ---
    default_message_dict = {
        "role": "user",
        "parts": [{"type": "text", "content": "Mock initial"}],
        "metadata": None
    }
    # --- END MODIFIED ---

    return {
        "id": task_id,
        "state": TaskState.COMPLETED if _MODELS_AVAILABLE else "COMPLETED",
        "createdAt": now_iso, # Use alias for JSON representation
        "updatedAt": now_iso, # Use alias for JSON representation
        "messages": [default_message_dict], # Ensure list contains a valid message dict
        "artifacts": [],
        "metadata": None
    }


DEFAULT_OAUTH_TOKEN_RESPONSE = {
    "access_token": "mock_access_token_12345",
    "token_type": "Bearer",
    "expires_in": 3600
}

# --- JSON-RPC Error Helper ---
# (Helpers remain the same)
# ... (create_jsonrpc_error_response, create_jsonrpc_success_response) ...
JSONRPC_PARSE_ERROR = -32700; JSONRPC_INVALID_REQUEST = -32600; JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602; JSONRPC_INTERNAL_ERROR = -32603; JSONRPC_APP_ERROR = -32000

def create_jsonrpc_error_response(req_id: Union[str, int, None], code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    error_obj: Dict[str, Any] = {"code": code, "message": message};
    if data is not None: error_obj["data"] = data
    return {"jsonrpc": "2.0", "error": error_obj, "id": req_id}

def create_jsonrpc_success_response(req_id: Union[str, int, None], result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


# --- SSE Stream Helper ---
# (generate_sse_stream remains the same)
async def generate_sse_stream(events: List[A2AEvent]) -> AsyncGenerator[bytes, None]:
    """Generates an SSE byte stream from a list of events (for mock)."""
    logger.debug(f"Mock SSE stream starting, yielding {len(events)} pre-configured events.")
    event_count = 0
    try:
        for i, event in enumerate(events): # Add index for logging
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
                    data_dict = event.model_dump(mode='json', by_alias=True)
                    data_str = json.dumps(data_dict)
                else:
                    data_str = json.dumps(event if isinstance(event, dict) else {"data": str(event)})

                sse_msg = f"event: {event_type}\ndata: {data_str}\n\n"
                logger.info(f"Mock SSE stream YIELDING event {i+1}/{len(events)}: {sse_msg.strip()!r}") # Log before yield
                yield sse_msg.encode('utf-8')
                event_count += 1
                await asyncio.sleep(0.01) # Keep small delay
            except Exception as e:
                logger.error(f"Error formatting mock SSE event {i+1}: {e}")
                error_data = json.dumps({"error": "mock_sse_format_error", "detail": str(e)})
                logger.info(f"Mock SSE stream YIELDING error event: event: error\\ndata: {error_data}\\n\\n")
                yield f"event: error\ndata: {error_data}\n\n".encode('utf-8')
                event_count += 1
        # --- MODIFIED: Add final separator ---
        logger.info("Mock SSE stream YIELDING final separator: b'\\n\\n'")
        yield b'\n\n' # Send a final separator to ensure last event is processed
        # --- END MODIFIED ---
        await asyncio.sleep(0.02) # Add a slightly longer sleep after finishing
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
# (setup_mock_a2a_routes function remains the same, using the corrected helpers)
def setup_mock_a2a_routes(
    mock_router: respx.mock,
    base_url: str,
    a2a_endpoint: str = "/a2a",
    token_endpoint: str = "/token",
    task_store: Optional[Dict[str, Dict]] = None,
    sse_event_store: Optional[Dict[str, List[A2AEvent]]] = None,
    token_endpoint_handler: Optional[Callable[[httpx.Request], httpx.Response]] = None,
    a2a_endpoint_handler: Optional[Callable[[httpx.Request], httpx.Response]] = None,
    default_auth_check: Optional[Callable[[httpx.Request], Optional[httpx.Response]]] = None
):
    """ Sets up mock routes... """
    a2a_url = f"{base_url.rstrip('/')}{a2a_endpoint}"
    token_url = f"{base_url.rstrip('/')}{token_endpoint}"

    # --- Default Token Endpoint Handler ---
    # (Remains the same)
    def default_token_handler(request: httpx.Request) -> httpx.Response:
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

    # --- Default A2A Endpoint Handler ---
    def default_a2a_handler(request: httpx.Request) -> httpx.Response:
        # (Auth Check and JSON-RPC parsing remain the same)
        # ... (code omitted for brevity) ...
        logger.debug(f"Mock A2A Endpoint received request: {request.url} Method: {request.method}")
        req_id: Union[str, int, None] = None; payload: Optional[Dict[str, Any]] = None
        if default_auth_check:
            auth_response = default_auth_check(request)
            if auth_response: logger.warning(f"Mock A2A auth check failed: {auth_response.status_code}"); error_resp = create_jsonrpc_error_response(req_id, -32000, "Authentication failed"); return httpx.Response(200, json=error_resp, headers={"Content-Type": "application/json"})
        try:
            payload = json.loads(request.content);
            if not isinstance(payload, dict): raise ValueError("Payload not a dict")
            method = payload.get("method"); params = payload.get("params", {}); req_id = payload.get("id")
            if not method or "id" not in payload or payload.get("jsonrpc") != "2.0": raise ValueError("Invalid JSON-RPC structure")
        except Exception as e:
            logger.warning(f"Mock A2A failed JSON-RPC parsing: {e}"); error_resp = create_jsonrpc_error_response(None, JSONRPC_PARSE_ERROR, "Parse error / Invalid Request"); return httpx.Response(200, json=error_resp, headers={"Content-Type": "application/json"})

        logger.info(f"Mock A2A processing method: {method}, id: {req_id}")

        # Method Routing
        try:
            if method == "tasks/send":
                task_id = params.get("id") or f"mock-task-{uuid.uuid4()}";
                if task_store is not None: task_store[task_id] = {"state": TaskState.SUBMITTED, "received_messages": 1}
                result = {"id": task_id}; resp_json = create_jsonrpc_success_response(req_id, result); return httpx.Response(200, json=resp_json)
            elif method == "tasks/get":
                task_id = params.get("id");
                if not task_id or (task_store is not None and task_id not in task_store): error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, "Task not found"); return httpx.Response(200, json=error_resp)
                # Use corrected default data function
                task_data_obj = (task_store or {}).get(task_id, create_default_mock_task(task_id))
                # Serialize the Task object (or dict fallback) to JSON
                if _MODELS_AVAILABLE and isinstance(task_data_obj, Task):
                    task_json = task_data_obj.model_dump(mode='json', by_alias=True)
                elif isinstance(task_data_obj, dict):
                     task_json = task_data_obj # Assume dict is already JSON-like
                else:
                     # Should not happen with corrected create_default_mock_task
                     logger.error(f"Mock task store contained invalid type for task {task_id}: {type(task_data_obj)}")
                     raise TypeError("Mock task store contained invalid type")
                resp_json = create_jsonrpc_success_response(req_id, task_json); return httpx.Response(200, json=resp_json)
            elif method == "tasks/cancel":
                task_id = params.get("id");
                if not task_id or (task_store is not None and task_id not in task_store): error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, "Task not found"); return httpx.Response(200, json=error_resp)
                if task_store is not None: task_store[task_id]["state"] = TaskState.CANCELED
                result = {"success": True}; resp_json = create_jsonrpc_success_response(req_id, result); return httpx.Response(200, json=resp_json)
            elif method == "tasks/sendSubscribe":
                task_id = params.get("id");
                if not task_id or (task_store is not None and task_id not in task_store): error_resp = create_jsonrpc_error_response(req_id, JSONRPC_APP_ERROR, "Task not found"); return httpx.Response(200, json=error_resp)
                events = (sse_event_store or {}).get(task_id, []); logger.info(f"Mock A2A sendSubscribe for {task_id}, returning SSE stream (events configured: {len(events)})")
                return httpx.Response(200, headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, stream=generate_sse_stream(events))
            else:
                error_resp = create_jsonrpc_error_response(req_id, JSONRPC_METHOD_NOT_FOUND, "Method not found"); return httpx.Response(200, json=error_resp)
        except Exception as e:
            logger.exception(f"Error in mock A2A handler for method {method}: {e}"); error_resp = create_jsonrpc_error_response(req_id, JSONRPC_INTERNAL_ERROR, "Internal mock server error"); return httpx.Response(500, json=error_resp)

    # Register routes
    final_token_handler = token_endpoint_handler or default_token_handler; mock_router.post(token_url).mock(side_effect=final_token_handler); logger.info(f"Registered mock token endpoint at POST {token_url}")
    final_a2a_handler = a2a_endpoint_handler or default_a2a_handler; mock_router.post(a2a_url).mock(side_effect=final_a2a_handler); logger.info(f"Registered mock A2A endpoint at POST {a2a_url}")
