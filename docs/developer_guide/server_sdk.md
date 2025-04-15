# Developer Guide: Server SDK (`agentvault-server-sdk`)

The `agentvault-server-sdk` provides tools and abstractions to simplify the development of A2A-compliant agent servers in Python, particularly when using the FastAPI web framework.

## Key Components

### `BaseA2AAgent`

*   **Purpose:** This is the abstract base class that your agent logic class should inherit from. It defines the core interface expected by the A2A protocol handlers.
*   **Implementation:** You must implement the following asynchronous methods in your subclass:
    *   `handle_task_send(task_id: Optional[str], message: Message) -> str`: Handles task initiation (`task_id` is `None`) or subsequent messages (`task_id` is provided). Should return the task ID.
    *   `handle_task_get(task_id: str) -> Task`: Retrieves the current state and details of a specific task.
    *   `handle_task_cancel(task_id: str) -> bool`: Attempts to cancel an ongoing task. Returns `True` if the request was accepted.
    *   `handle_subscribe_request(task_id: str) -> AsyncGenerator[A2AEvent, None]`: Returns an async generator that yields `A2AEvent` objects (status updates, messages, artifacts) for Server-Sent Event streaming.
*   **Alternative:** For simpler agents or specific method handling, you can use the `@a2a_method` decorator instead of implementing all `handle_...` methods (see below).

### FastAPI Integration (`create_a2a_router`)

*   **Purpose:** A helper function that takes an instance of your `BaseA2AAgent` subclass and returns a FastAPI `APIRouter`.
*   **Functionality:**
    *   Creates a single POST endpoint (typically mounted at `/a2a`).
    *   Handles incoming JSON-RPC 2.0 requests.
    *   Parses the request payload (`method`, `params`, `id`).
    *   Validates `params` against the expected Pydantic models defined in `agentvault.models` (e.g., `TaskSendParams`).
    *   Routes the request to the corresponding `handle_...` method or a decorated method on your agent instance.
    *   Handles the `tasks/sendSubscribe` method specifically, setting up an `SSEResponse` to stream events from your agent's `handle_subscribe_request` generator.
    *   Formats successful results and errors into standard JSON-RPC responses.
*   **Usage:**
    ```python
    from fastapi import FastAPI
    from agentvault_server_sdk import create_a2a_router, BaseA2AAgent
    # Import your agent implementation
    from my_agent_module import MyAgent

    app = FastAPI()
    my_agent_instance = MyAgent()
    task_store = # ... initialize your task store (e.g., InMemoryTaskStore()) ...

    # Create the router, passing the agent and store
    a2a_router = create_a2a_router(agent=my_agent_instance, task_store=task_store)

    # Include the router in your FastAPI app
    app.include_router(a2a_router, prefix="/a2a")

    # IMPORTANT: Add required exception handlers to the main app
    # (See Exceptions section below and example server)
    ```
*   **Exception Handling:** The router relies on specific exception handlers being added to the main FastAPI `app` instance to correctly translate internal errors (like `TaskNotFoundError`, `ValueError`, `AgentServerError`) into appropriate JSON-RPC error responses. See the [Basic A2A Server Example](../../examples/basic_a2a_server/main.py) for required handlers.

### A2A Method Decorator (`@a2a_method`)

*   **Purpose:** Provides an alternative way to handle specific A2A methods without implementing the full suite of `handle_...` methods in `BaseA2AAgent`. Useful for agents that only support a subset of methods or custom methods.
*   **Usage:** Decorate an `async def` method within your agent class.
    ```python
    from agentvault_server_sdk import BaseA2AAgent, a2a_method
    from pydantic import BaseModel

    class EchoParams(BaseModel):
        text_to_echo: str

    class MyAgentWithDecorator(BaseA2AAgent):
        # No need to implement handle_task_send, etc. if only using decorators

        @a2a_method("custom/echo")
        async def echo_handler(self, text_to_echo: str) -> str:
            # Parameter 'text_to_echo' is automatically validated from params
            return f"You sent: {text_to_echo}"

        @a2a_method("tasks/get") # Override specific standard methods
        async def custom_get_handler(self, id: str) -> Dict: # Return type validated
             # Custom logic for getting task 'id'
             return {"id": id, "status": "custom_handled"}
    ```
*   **Features:**
    *   The router automatically discovers and routes calls to decorated methods based on the provided method name string.
    *   It automatically validates incoming `params` against the decorated function's type hints (using Pydantic).
    *   It automatically validates the return value against the function's return type hint.

### Task State Management (`state.py`)

*   **Purpose:** Provides abstractions and a basic implementation for managing the state of ongoing A2A tasks, essential for handling `tasks/get`, `tasks/cancel`, and SSE notifications.
*   **Components:**
    *   `TaskContext`: A simple dataclass holding basic task info (`task_id`, `current_state`, timestamps). Can be subclassed to store more agent-specific state.
    *   `BaseTaskStore`: An abstract base class defining the interface for task storage (`get_task`, `create_task`, `update_task_state`, `delete_task`) and listener management (`add_listener`, `remove_listener`, `get_listeners`, `notify_...`).
    *   `InMemoryTaskStore`: A basic, non-persistent implementation of `BaseTaskStore` using Python dictionaries. Suitable for development and simple agents.
*   **Integration:** The `create_a2a_router` accepts a `task_store` instance. If provided, the router uses it for:
    *   Checking task existence before calling `handle_task_get`, `handle_task_cancel`, `handle_subscribe_request`.
    *   The agent implementation should also use the *same* `task_store` instance to update state (`update_task_state`) and trigger notifications (`notify_status_update`, `notify_message_event`, `notify_artifact_event`). The SDK's notification methods automatically handle fanning out events to subscribed SSE listeners.

### Exceptions (`exceptions.py`)

Defines custom exceptions specific to server-side agent errors:

*   `AgentServerError` (Base exception)
*   `TaskNotFoundError`: Raised when an operation targets a non-existent task ID. Handled by the router to return a specific JSON-RPC error.
*   `InvalidStateTransitionError`: (Conceptual) Can be used by agent logic to signal invalid state changes.
*   `AgentProcessingError`: Generic error during agent's internal processing.
*   `ConfigurationError`: Agent configuration issue.

### MCP Utilities (`mcp_utils.py`)

*   **Purpose:** Provides server-side utilities for handling Model Context Protocol data.
*   **Key Functions:**
    *   `get_mcp_context(message: Message) -> Optional[Dict]`: Safely extracts the `mcp_context` dictionary potentially embedded within an incoming A2A `Message`'s metadata.

### Packager CLI (`agentvault-sdk`)

*   **Purpose:** A command-line tool to help package your SDK-based agent for deployment, typically using Docker.
*   **Command:** `agentvault-sdk package [OPTIONS]`
*   **Functionality:** Generates a standardized multi-stage `Dockerfile`, a `.dockerignore` file, and copies necessary files (like `requirements.txt`, `agent-card.json`) into an output directory, preparing the agent for containerization.
*   **Documentation:** *(Link to dedicated Packager documentation - coming soon)*
