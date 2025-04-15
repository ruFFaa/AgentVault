# AgentVault Server SDK - Stateful Agent Example

This example demonstrates how to build an A2A agent that maintains state across multiple interactions within a single task lifecycle using the `agentvault-server-sdk`.

## Concept

Many agent tasks aren't single-shot requests but involve a conversation or a process that evolves over time. This requires the agent to:

1.  **Store Task-Specific State:** Remember information relevant to the ongoing task (e.g., conversation history, intermediate results, user preferences).
2.  **Update State:** Modify the stored state based on new messages or internal processing.
3.  **Handle Multiple Interactions:** Accept subsequent `tasks/send` requests for the *same* task ID and use the stored state to continue processing.

This example implements a simple chat agent that stores the message history in memory for each task.

## Components

*   **`agent-card.json`**: Describes the agent.
*   **`requirements.txt`**: Python dependencies (`fastapi`, `uvicorn`, `agentvault-server-sdk`).
*   **`src/stateful_agent_example/state.py`**: Defines `ChatTaskContext` which inherits from the SDK's `TaskContext` and adds a `history` list to store messages.
*   **`src/stateful_agent_example/agent.py`**: Defines the `StatefulChatAgent` logic:
    *   Uses `InMemoryTaskStore` to store `ChatTaskContext` instances.
    *   `handle_task_send`: Creates a new task context on the first call, storing the initial message. For subsequent calls with the same task ID, it appends the new message to the existing context's history and signals a background processing loop using an `asyncio.Event`.
    *   `_process_task`: A background `asyncio` task started for each new chat task. It waits for new messages (signaled via the `asyncio.Event`) and generates simple responses based on the message count.
    *   Other handlers (`get`, `cancel`, `subscribe`) interact with the task store.
*   **`src/stateful_agent_example/main.py`**: Sets up the FastAPI application, includes the SDK's A2A router, and required exception handlers.

## Setup

1.  **Navigate:** Open your terminal in this directory (`examples/stateful_agent_example`).
2.  **Install Dependencies:** Create and activate a virtual environment, then install the requirements.
    ```bash
    # Create venv (optional, recommended)
    # python -m venv .venv
    # source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate    # On Windows

    pip install -r requirements.txt
    ```
    *Note:* This installs the SDK and core library from your local source tree.

## Running the Server

Start the FastAPI server using Uvicorn:

```bash
uvicorn src.stateful_agent_example.main:app --reload --port 8003
```
*   `--reload`: Enables auto-reloading for development.
*   `--port 8003`: Specifies the port (matches `agent-card.json`).

The server should start, hosting the `/a2a` endpoint.

## Testing with AgentVault CLI

You can test the stateful interaction using the `agentvault_cli`:

1.  **Initiate Task:** Send the first message. Note the `Task ID` returned.
    ```bash
    agentvault run --agent http://localhost:8003/agent-card.json --input "Hello stateful agent!"
    # --> SUCCESS: Task initiated successfully. Task ID: stateful-task-xxxxxx
    # --> INFO: Waiting for events...
    # --> INFO: Task Status: WORKING
    # --> Message from Assistant: Received message 1. History length is now 1.
    # --> INFO: Task Status: WORKING # (Agent waits for more input)
    # (Press Ctrl+C here or leave it running)
    ```
    *Note:* The agent stays in the `WORKING` state, waiting for more input or cancellation.

2.  **Send Subsequent Message:** Open a *new terminal* (or stop the previous `run` command with Ctrl+C if desired) and use the *same Task ID* obtained in step 1 to send another message.
    ```bash
    # Replace stateful-task-xxxxxx with the actual ID from step 1
    agentvault run --agent http://localhost:8003/agent-card.json --input "This is the second message." --task-id stateful-task-xxxxxx
    # --> SUCCESS: Task message sent successfully to task stateful-task-xxxxxx
    # --> INFO: Waiting for events...
    # --> Message from Assistant: Received message 2. History length is now 2.
    # --> INFO: Task Status: WORKING
    # (Press Ctrl+C or leave running)
    ```
    The running agent (or its background task) should detect the new message and send another response via SSE.

3.  **(Optional) Cancel Task:** You can cancel the task using its ID.
    ```bash
    # Replace stateful-task-xxxxxx with the actual ID
    agentvault run --agent http://localhost:8003/agent-card.json --cancel --task-id stateful-task-xxxxxx
    # --> SUCCESS: Task cancellation request sent successfully for task stateful-task-xxxxxx
    # --> INFO: Waiting for events...
    # --> INFO: Task Status: CANCELED
    ```

This demonstrates how the agent uses the `task_id` to access and update the correct state (`ChatTaskContext`) stored by the `InMemoryTaskStore` across multiple `run` command invocations. In a real application, you would likely use a persistent store instead of `InMemoryTaskStore`.
