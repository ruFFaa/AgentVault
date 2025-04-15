# AgentVault Server SDK - Basic A2A Server Example

This example demonstrates the minimal setup required to create an A2A-compliant agent server using the `agentvault-server-sdk` and FastAPI.

## Components

*   **`requirements.txt`**: Defines Python dependencies (`fastapi`, `uvicorn`, `agentvault-server-sdk`).
*   **`main.py`**:
    *   Defines a simple `MySimpleAgent` class inheriting from `BaseA2AAgent`.
    *   Implements basic logic for the required A2A methods (`handle_task_send`, `handle_task_get`, `handle_task_cancel`, `handle_subscribe_request`).
    *   Uses the SDK's `create_a2a_router` to automatically generate the `/a2a` JSON-RPC endpoint.
    *   Includes necessary FastAPI exception handlers required by the router.
    *   Sets up a FastAPI application.
    *   Serves the agent's `agent-card.json` at `/agent-card.json`.
    *   Includes a `uvicorn` runner block.
*   **`agent-card.json`**: A minimal, valid Agent Card describing this example agent.

## Setup

1.  **Navigate:** Open your terminal in this directory (`examples/basic_a2a_server`).
2.  **Install Dependencies:** Create and activate a virtual environment, then install the requirements. This will install the local SDK package.
    ```bash
    # Create venv (optional, recommended)
    # python -m venv .venv
    # source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate    # On Windows

    pip install -r requirements.txt
    ```
    *Note:* This assumes the `agentvault-server-sdk` and `agentvault_library` directories are located correctly relative to this example as specified in `requirements.txt`. Adjust the `-e ../../...` paths if your structure differs.

## Running the Server

Start the FastAPI server using Uvicorn:

```bash
uvicorn main:app --reload --port 8000
```

*   `--reload`: Enables auto-reloading when code changes (useful for development).
*   `--port 8000`: Specifies the port to run on (matches the default `url` in `agent-card.json`).

You should see Uvicorn startup messages indicating the server is running on `http://127.0.0.1:8000`.

## Testing with AgentVault CLI

Once the server is running, you can interact with it using the `agentvault-cli`:

1.  **Check Agent Card:** Open `http://localhost:8000/agent-card.json` in your browser or use `curl` to verify the card is served correctly.

2.  **Run a Task:** Use the `agentvault run` command, pointing the `--agent` flag to the card URL.
    ```bash
    agentvault run --agent http://localhost:8000/agent-card.json --input "Hello SDK Agent!"
    ```

You should see output similar to this:

```
SUCCESS: Successfully loaded agent: SDK Basic Echo Agent (examples/simple-agent)
INFO: Agent A2A Endpoint: http://localhost:8000/a2a
INFO: Initiating task with agent...
SUCCESS: Task initiated successfully. Task ID: simple-xxxxxxxx
INFO: Waiting for events... (Press Ctrl+C to request cancellation)
INFO: Task Status: WORKING
┌ Message from Assistant ───────────────────────────────────────────────────┐
│ Echo: Hello SDK Agent!                                                    │
└───────────────────────────────────────────────────────────────────────────┘
INFO: Task Status: COMPLETED
INFO: Task reached terminal state.
INFO: --------------------
INFO: Final Task State: COMPLETED
SUCCESS: Task completed.
```

This confirms the CLI can load the card, initiate a task via the SDK-generated router, stream the status updates and the echo message, and recognize task completion.
