# Developer Guide: Server SDK (`agentvault-server-sdk`)

The `agentvault-server-sdk` provides tools and abstractions to simplify the development of A2A-compliant agent servers in Python, particularly when using the FastAPI web framework. It helps you focus on your agent's core logic while the SDK handles much of the A2A protocol boilerplate.

## Installation

Install the SDK from PyPI:

```bash
pip install agentvault-server-sdk
```

See the main [Installation Guide](../installation.md) for more details, including setting up a development environment.

## Core Concepts

The SDK revolves around implementing an agent logic class and integrating it with a web framework (currently FastAPI).

### 1. `BaseA2AAgent`

This is the abstract base class your agent logic should inherit from.

*   **Purpose:** Defines the standard interface the A2A protocol expects.
*   **Required Methods:** You *must* implement these `async` methods in your subclass:
    *   `handle_task_send(task_id: Optional[str], message: Message) -> str`: Processes incoming messages, manages task creation/updates, returns the task ID.
    *   `handle_task_get(task_id: str) -> Task`: Retrieves the full state (`Task` model) of a specific task.
    *   `handle_task_cancel(task_id: str) -> bool`: Attempts to cancel a task, returning `True` if the request is accepted.
    *   `handle_subscribe_request(task_id: str) -> AsyncGenerator[A2AEvent, None]`: Returns an async generator yielding `A2AEvent` objects (status updates, messages, artifacts) for SSE streaming.
*   **Alternative (`@a2a_method`):** For agents handling only specific or custom methods, you can use the `@a2a_method` decorator instead of implementing all `handle_...` methods.

### 2. Task State Management (`agentvault_server_sdk.state`)

Handling asynchronous tasks requires managing their state (Submitted, Working, Completed, etc.) and potentially associated data (messages, artifacts).

*   **`TaskContext`:** A basic dataclass holding `task_id`, `current_state`, timestamps. Subclass this to store agent-specific task data.
*   **`BaseTaskStore`:** An abstract class defining the interface for storing and retrieving `TaskContext` objects (`create_task`, `get_task`, `update_task_state`, `delete_task`). It also defines interfaces for managing SSE listeners and notifying them.
*   **`InMemoryTaskStore`:** A simple, non-persistent dictionary-based implementation of `BaseTaskStore`. Suitable for development or single-instance agents where persistence isn't required. **Production agents typically require a persistent store (e.g., Redis, Database).**
*   **Notification Helpers:** When using a `BaseTaskStore`, call methods like `task_store.notify_status_update(...)`, `task_store.notify_message_event(...)`, `task_store.notify_artifact_event(...)` from your agent logic. The SDK's router integration uses these to automatically send SSE events to subscribed clients.

### 3. FastAPI Integration (`create_a2a_router`)

This function bridges your agent logic with the FastAPI web framework.

*   **Purpose:** Creates a FastAPI `APIRouter` that automatically exposes the standard A2A JSON-RPC methods (`tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/sendSubscribe`) and routes them to your `BaseA2AAgent` implementation's corresponding `handle_...` methods (or decorated methods).
*   **Usage:**
    ```python
    # In your main FastAPI app file (e.g., main.py)
    from fastapi import FastAPI
    from agentvault_server_sdk import create_a2a_router, BaseA2AAgent
    from agentvault_server_sdk.state import InMemoryTaskStore
    # Import your agent class
    from my_agent_logic import MyAgent

    # 1. Instantiate your agent and task store
    task_store = InMemoryTaskStore()
    my_agent_instance = MyAgent(task_store_ref=task_store) # Pass store if needed

    # 2. Create the A2A router
    a2a_router = create_a2a_router(
        agent=my_agent_instance,
        task_store=task_store # Provide the store instance
    )

    # 3. Create the FastAPI app and include the router
    app = FastAPI(title="My A2A Agent")
    app.include_router(a2a_router, prefix="/a2a") # Mount at /a2a

    # 4. IMPORTANT: Add required exception handlers
    # (See example below and basic_a2a_server example)
    # ... add exception handlers ...
    ```
*   **Exception Handling:** The router relies on specific exception handlers being added to the *main FastAPI app* to translate internal errors (like `TaskNotFoundError`, `ValueError`, `AgentServerError`) into correct JSON-RPC error responses. You **must** add these handlers:
    ```python
    from fastapi import Request, FastAPI
    from fastapi.responses import JSONResponse
    from pydantic import ValidationError as PydanticValidationError
    from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
    from agentvault_server_sdk.fastapi_integration import (
        task_not_found_handler, validation_exception_handler,
        agent_server_error_handler, generic_exception_handler
    )

    app = FastAPI() # Your app instance
    # ... include router ...

    app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    app.add_exception_handler(ValueError, validation_exception_handler)
    app.add_exception_handler(TypeError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, validation_exception_handler)
    app.add_exception_handler(AgentServerError, agent_server_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler) # Catch-all
    ```

### 4. A2A Method Decorator (`@a2a_method`)

An alternative for exposing specific methods without implementing the full `BaseA2AAgent` interface.

*   **Purpose:** Expose individual `async def` methods in your class as specific JSON-RPC methods. Useful for simpler agents or custom methods.
*   **Usage:**
    ```python
    from agentvault_server_sdk import BaseA2AAgent, a2a_method
    from agentvault.models import Task # Example import

    class DecoratedAgent(BaseA2AAgent):

        @a2a_method("custom/ping")
        async def ping_handler(self) -> str:
            return "pong"

        @a2a_method("tasks/get") # Override standard method
        async def custom_get(self, id: str) -> Task: # Params validated from type hints
            # ... custom logic to fetch task ...
            task_data = await get_my_task_data(id)
            # Return value validated against type hint
            return Task(**task_data)

        # No need to implement handle_task_send, handle_task_cancel etc.
        # if only using decorators for the methods you support.
        # The router will return "Method not found" for others.
    ```
*   **Validation:** The router automatically validates incoming `params` against the decorated function's type hints and validates the return value against the function's return type hint using Pydantic.

### 5. Packaging Tool (`agentvault-sdk package`)

A CLI tool to help prepare your agent for deployment, typically via Docker.

*   **Command:** `agentvault-sdk package [OPTIONS]`
*   **Functionality:** Generates a standard multi-stage `Dockerfile`, a `.dockerignore` file, and copies `requirements.txt` and optionally `agent-card.json` to an output directory.
*   **Key Options:**
    *   `--output-dir` / `-o` (Required): Where to put generated files.
    *   `--entrypoint` / `-e` (Required): Import path to your FastAPI app instance (e.g., `my_agent.main:app`).
    *   `--python`: Python version for Docker image (default: 3.11).
    *   `--suffix`: Base image suffix (default: slim-bookworm).
    *   `--port`: Port inside the container (default: 8000).
    *   `--requirements` / `-r`: Path to `requirements.txt` (defaults to `./requirements.txt`).
    *   `--agent-card` / `-c`: Path to `agent-card.json` to copy.
*   **Example:**
    ```bash
    agentvault-sdk package -o ./build -e my_agent.main:app -r ./requirements.txt -c ./agent-card.json
    # Then build: docker build -t my-agent-image -f ./build/Dockerfile .
    ```

## Building a Basic Agent (Conceptual Steps)

1.  **Define Agent Logic:** Create a class inheriting from `BaseA2AAgent`.
2.  **Implement Handlers/Methods:** Implement the required `handle_...` methods or use the `@a2a_method` decorator for the A2A methods your agent supports. Use a `TaskStore` (like `InMemoryTaskStore` initially) to manage state. Use `notify_...` methods on the store to trigger SSE events.
3.  **Create FastAPI App:** Set up a basic FastAPI application (`main.py`).
4.  **Instantiate Agent & Store:** Create instances of your agent class and task store.
5.  **Create & Include Router:** Use `create_a2a_router(agent=..., task_store=...)` and include it in your FastAPI app (e.g., at prefix `/a2a`).
6.  **Add Exception Handlers:** Add the required handlers (shown above) to your main FastAPI app instance.
7.  **Create Agent Card:** Write an `agent-card.json` describing your agent, ensuring the `url` points to your FastAPI endpoint (e.g., `http://your-host/a2a`).
8.  **Run:** Use `uvicorn main:app --host ... --port ...`.
9.  **(Optional) Package:** Use `agentvault-sdk package` to create Docker artifacts.

Refer to the [Basic A2A Server Example](../../examples/basic_a2a_server/) for a runnable implementation.
