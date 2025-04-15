# Developer Guide: Server SDK (`agentvault-server-sdk`)

The `agentvault-server-sdk` provides tools and abstractions to simplify the development of A2A-compliant agent servers in Python, particularly when using the FastAPI web framework. It helps you focus on your agent's core logic while the SDK handles much of the A2A protocol boilerplate.

## Installation

Install the SDK from PyPI:

```bash
pip install agentvault-server-sdk
```
*(Note: This automatically installs the `agentvault` client library as a dependency).*

See the main [Installation Guide](../installation.md) for more details, including setting up a development environment to run from source.

## Core Concepts

The SDK revolves around implementing an agent logic class (inheriting from `BaseA2AAgent`) and integrating it with a web framework (currently FastAPI).

### 1. `BaseA2AAgent` (`agent.py`)

This is the abstract base class your agent logic should inherit from.

*   **Purpose:** Defines the standard interface the A2A protocol expects an agent server to fulfill.
*   **Required Methods:** If you are *not* using the `@a2a_method` decorator for all standard methods, you *must* implement these `async` methods in your subclass:
    *   `handle_task_send(task_id: Optional[str], message: Message) -> str`: Processes incoming messages (`tasks/send` JSON-RPC method). Should handle task creation or updates and return the task ID.
    *   `handle_task_get(task_id: str) -> Task`: Retrieves the full state (`Task` model) of a specific task (`tasks/get` JSON-RPC method).
    *   `handle_task_cancel(task_id: str) -> bool`: Attempts to cancel a task (`tasks/cancel` JSON-RPC method), returning `True` if the request is accepted.
    *   `handle_subscribe_request(task_id: str) -> AsyncGenerator[A2AEvent, None]`: Returns an async generator yielding `A2AEvent` objects for SSE streaming (`tasks/sendSubscribe` JSON-RPC method). The SDK router consumes this generator.
*   **Alternative (`@a2a_method`):** For agents handling only specific or custom methods, or if you prefer a decorator-based approach, you can use the `@a2a_method` decorator on individual methods instead of implementing all `handle_...` methods (see below).

### 2. Task State Management (`state.py`)

Handling asynchronous tasks requires managing their state (Submitted, Working, Completed, etc.) and potentially associated data (messages, artifacts). The SDK provides tools for this.

*   **`TaskContext`:** A basic dataclass holding `task_id`, `current_state`, `created_at`, `updated_at`. You can subclass this to store agent-specific task data.
    ```python
    # Example of extending TaskContext
    from dataclasses import dataclass, field
    from typing import List
    from agentvault.models import Message, Artifact
    from agentvault_server_sdk.state import TaskContext

    @dataclass
    class MyAgentTaskContext(TaskContext):
        conversation_history: List[Message] = field(default_factory=list)
        generated_artifacts: List[Artifact] = field(default_factory=list)
        # Add other fields your agent needs to track per task
    ```
*   **`BaseTaskStore`:** An abstract base class defining the interface for storing, retrieving, updating, and deleting `TaskContext` objects (e.g., `create_task`, `get_task`, `update_task_state`, `delete_task`). It also defines the interface for managing SSE event listeners (`add_listener`, `remove_listener`) and notifying them (`notify_status_update`, `notify_message_event`, `notify_artifact_event`).
*   **`InMemoryTaskStore`:** A simple, **non-persistent** dictionary-based implementation of `BaseTaskStore`. **Suitable only for development or single-instance agents where task state loss on restart is acceptable.** Production agents typically require implementing a custom `BaseTaskStore` backed by a persistent database (SQL, NoSQL) or a distributed cache (Redis).
*   **Notification Helpers:** When using a `BaseTaskStore` implementation (like `InMemoryTaskStore` or your own), your agent logic (e.g., background processing tasks) should call methods like `task_store.notify_status_update(...)`, `task_store.notify_message_event(...)`, `task_store.notify_artifact_event(...)` whenever a relevant event occurs (e.g., state change, message generation, artifact creation). The `create_a2a_router` integration uses these notifications to automatically format and send the correct SSE events to subscribed clients via the `handle_subscribe_request` stream.

### 3. FastAPI Integration (`fastapi_integration.py`)

The `create_a2a_router` function bridges your agent logic (either a `BaseA2AAgent` subclass or a class using `@a2a_method`) with the FastAPI web framework.

*   **Purpose:** Creates a FastAPI `APIRouter` that automatically exposes the standard A2A JSON-RPC methods (`tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/sendSubscribe`) and routes them to your agent implementation's corresponding `handle_...` methods or decorated methods. It also handles JSON-RPC request parsing, basic validation, and SSE stream setup.
*   **Authentication:** Note that authentication (e.g., checking `X-Api-Key` or `Authorization` headers) is typically handled *before* the request reaches the A2A router, usually via FastAPI Dependencies applied to the router or the main app. The SDK router itself does not perform authentication checks.
*   **Usage:** The following steps outline how to integrate the router into your FastAPI application:

    1.  **Instantiate Agent and Task Store:**
        ```python
        from fastapi import FastAPI
        from agentvault_server_sdk import BaseA2AAgent
        from agentvault_server_sdk.state import InMemoryTaskStore # Or your custom store
        # Import your agent class
        from my_agent_logic import MyAgent

        task_store = InMemoryTaskStore()
        my_agent_instance = MyAgent(task_store_ref=task_store) # Pass store if needed
        ```

    2.  **Create the A2A Router:** Pass the agent instance and the task store to the factory function.
        ```python
        from agentvault_server_sdk import create_a2a_router

        a2a_router = create_a2a_router(
            agent=my_agent_instance,
            task_store=task_store # Required for SSE notifications
        )
        ```

    3.  **Create FastAPI App and Include Router:** Mount the router at your desired prefix (typically `/a2a`).
        ```python
        app = FastAPI(title="My A2A Agent")
        app.include_router(a2a_router, prefix="/a2a") # Mount at standard /a2a path
        ```

    4.  **Add Exception Handlers (CRITICAL):** You **must** add the SDK's exception handlers to your main FastAPI `app` instance. These handlers translate internal Python exceptions raised by your agent or the SDK (like `TaskNotFoundError`, `ValueError`, `AgentServerError`) into correctly formatted JSON-RPC error responses that clients expect. Without these, clients will receive generic HTTP 500 errors instead of specific, actionable JSON-RPC errors.
        ```python
        from fastapi import Request
        from fastapi.responses import JSONResponse
        from pydantic import ValidationError as PydanticValidationError
        # from pydantic_core import ValidationError as PydanticValidationError # If using Pydantic v2
        from agentvault_server_sdk.exceptions import AgentServerError, TaskNotFoundError
        from agentvault_server_sdk.fastapi_integration import (
            task_not_found_handler, validation_exception_handler,
            agent_server_error_handler, generic_exception_handler
        )

        # Assuming 'app' is your FastAPI instance from step 3
        app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
        app.add_exception_handler(ValueError, validation_exception_handler)
        app.add_exception_handler(TypeError, validation_exception_handler)
        app.add_exception_handler(PydanticValidationError, validation_exception_handler)
        app.add_exception_handler(AgentServerError, agent_server_error_handler)
        app.add_exception_handler(Exception, generic_exception_handler) # Catch-all
        ```

### 4. A2A Method Decorator (`@a2a_method`)

An alternative or supplement to implementing the full `BaseA2AAgent` interface.

*   **Purpose:** Expose individual `async def` methods within your agent class as specific JSON-RPC methods. Useful for simpler agents, custom methods beyond the standard A2A set, or overriding specific standard methods with custom logic.
*   **Usage:**
    ```python
    from agentvault_server_sdk import BaseA2AAgent, a2a_method
    from agentvault.models import Task # Example import

    class DecoratedAgent(BaseA2AAgent): # Still inherit for structure

        @a2a_method("custom/ping")
        async def ping_handler(self) -> str:
            # No parameters needed
            return "pong"

        @a2a_method("tasks/get") # Override standard method
        async def custom_get_task(self, task_id: str) -> Task: # Params validated from type hints
            # ... custom logic to fetch task ...
            task_data = await get_my_task_data(task_id)
            # Return value validated against type hint
            return Task(**task_data)

        # If using only decorators for standard methods, you don't *need*
        # to implement the corresponding handle_ methods. The router will
        # prioritize decorated methods and return "Method not found" for others.
    ```
*   **Validation:** The `create_a2a_router` automatically validates incoming JSON-RPC `params` against the decorated function's type hints (using Pydantic internally). If validation fails (e.g., client sends wrong type for `task_id`), a `ValueError` or `PydanticValidationError` will likely be raised, which should be caught by the `validation_exception_handler` registered on the FastAPI app, returning a JSON-RPC `Invalid Params` error. The return value is also validated against the function's return type hint.

### 5. Packaging Tool (`agentvault-sdk package`) (`packager/cli.py`)

A CLI tool to help prepare your agent project for deployment, typically via Docker.

*   **Command:** `agentvault-sdk package [OPTIONS]`
*   **Functionality:** Generates a standard multi-stage `Dockerfile`, a `.dockerignore` file, and copies `requirements.txt` and optionally `agent-card.json` to a specified output directory, ready for `docker build`.
*   **Key Options:**
    *   `--output-dir DIRECTORY` / `-o DIRECTORY`: **(Required)** Directory to write Dockerfile and other artifacts.
    *   `--entrypoint TEXT`: **(Required)** Python import path to the FastAPI app instance (e.g., `my_agent.main:app`).
    *   `--python TEXT`: Python version for the base image tag (e.g., 3.10, 3.11). [default: 3.11]
    *   `--suffix TEXT`: Suffix for the python base image (e.g., slim-bookworm, alpine). [default: slim-bookworm]
    *   `--port INTEGER`: Port the application will listen on inside the container. [default: 8000]
    *   `--requirements PATH` / `-r PATH`: Path to the requirements.txt file. If not provided, it looks for `./requirements.txt` in the current directory and copies it if found. Issues a warning if the SDK dependency seems missing.
    *   `--agent-card PATH` / `-c PATH`: Path to the agent-card.json file. If provided, it will be copied into the output directory.
    *   `--app-dir TEXT`: Directory inside the container where the application code will reside. [default: /app]
*   **Example:**
    ```bash
    # Assuming FastAPI app is in src/my_agent/main.py as 'app'
    # and requirements.txt / agent-card.json are in the current directory
    agentvault-sdk package \
        --output-dir ./build \
        --entrypoint my_agent.main:app \
        --requirements ./requirements.txt \
        --agent-card ./agent-card.json \
        --python 3.11

    # Then build the image from the project root:
    # docker build -t my-agent-image:latest -f ./build/Dockerfile .
    ```

## Building a Basic Agent (Conceptual Steps)

1.  **Define Agent Logic:** Create a class inheriting from `BaseA2AAgent` (or use decorators).
2.  **Implement Handlers/Methods:** Implement the required `async handle_...` methods (or decorate specific methods) to handle A2A requests.
3.  **Manage State:** Choose or implement a `BaseTaskStore` (start with `InMemoryTaskStore` for development). Pass it to your agent instance. **Crucially, call `task_store.notify_...` methods from your agent's background processing logic** (e.g., the code handling the actual work initiated by `handle_task_send`) to send SSE updates to subscribed clients.
4.  **Create FastAPI App:** Set up a standard FastAPI application (`main.py`).
5.  **Instantiate Agent & Store:** Create instances of your agent class and task store.
6.  **Create & Include Router:** Use `create_a2a_router(agent=..., task_store=...)` and include the returned router in your FastAPI app (e.g., at prefix `/a2a`).
7.  **Add Exception Handlers:** **Add the required SDK exception handlers** (`task_not_found_handler`, etc.) to your main FastAPI app instance using `app.add_exception_handler(...)`.
8.  **Create Agent Card:** Write an `agent-card.json` describing your agent, ensuring the `url` points to your FastAPI A2A endpoint (e.g., `http://your-host/a2a`). Include appropriate `authSchemes`.
9.  **Run:** Use `uvicorn main:app --host ... --port ...`.
10. **(Optional) Package:** Use `agentvault-sdk package` to generate Docker artifacts for deployment.

Refer to the [Basic A2A Server Example](../examples.md) for a complete, runnable implementation.
