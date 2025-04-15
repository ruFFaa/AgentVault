# AgentVault Library Usage Example

This example demonstrates how to use the core `agentvault` Python client library directly to interact with an A2A-compliant agent, without using the `agentvault_cli`.

## Concept

The `agentvault` library provides the `AgentVaultClient` class, which handles the complexities of the A2A protocol (JSON-RPC, SSE, authentication via `KeyManager`). This script shows the basic workflow:

1.  Load the target agent's `AgentCard`.
2.  Instantiate `KeyManager` to handle potential authentication credentials.
3.  Instantiate `AgentVaultClient` (using `async with`).
4.  Call `client.initiate_task` to start the interaction.
5.  Use `async for event in client.receive_messages(...)` to stream and process events (status updates, messages, artifacts) from the agent.
6.  Handle potential exceptions.

## Components

*   **`requirements.txt`**: Lists the `agentvault` library dependency.
*   **`main.py`**: The Python script demonstrating the library usage. It takes the agent reference and input text as command-line arguments.

## Setup

1.  **Navigate:** Open your terminal in this directory (`examples/library_usage_example`).
2.  **Install Dependencies:** Create and activate a virtual environment, then install the requirements.
    ```bash
    # Create venv (optional, recommended)
    # python -m venv .venv
    # source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate    # On Windows

    pip install -r requirements.txt
    ```
    *Note:* This installs the `agentvault` library from your local source tree.
3.  **Target Agent:** By default, the script targets the Basic A2A Server example agent card URL (`http://localhost:8000/agent-card.json`). Ensure that agent is running if you use the default. You can target other agents using the `--agent-ref` argument.
4.  **Credentials (If Needed):** If the target agent requires authentication (e.g., `apiKey` or `oauth2`), ensure the necessary credentials are configured using the AgentVault CLI (`agentvault config set ...`) or environment variables, matching the `service_identifier` specified in the agent's card. The `KeyManager` within the script will automatically pick them up.

## Running the Example

Execute the Python script from your terminal, providing the input text:

```bash
# Run against the default Basic Echo Agent (make sure it's running on port 8000)
python main.py --input "Hello from the library!"

# Run against a different agent (e.g., one requiring auth)
# Ensure 'my-api-key-service' is configured via `agentvault config` if needed
# python main.py --agent-ref "https://some-other-agent.com/card.json" --input "Process this data" --key-service "my-api-key-service"
```

**Expected Output:**

The script will print logs indicating the steps it's taking (loading card, initiating task) and then print details for each event received from the agent via the SSE stream (status changes, messages, artifacts).

```
INFO:root:Loading agent card: http://localhost:8000/agent-card.json
INFO:root:Loaded Agent: SDK Basic Echo Agent
INFO:root:Initiating task...
INFO:agentvault.client:Initiating task with agent: examples/simple-agent
INFO:agentvault.client:Task successfully initiated with agent examples/simple-agent. Task ID: simple-xxxxxx
INFO:root:Task initiated: simple-xxxxxx
INFO:root:Streaming events...
INFO:agentvault.client:Subscribing to events for task simple-xxxxxx on agent: examples/simple-agent
INFO:root:  Status Update: WORKING (Msg: N/A)
INFO:root:  Message Received (Role: assistant):
INFO:root:    Text: Echo response for task simple-xxxxxx
INFO:root:  Status Update: COMPLETED (Msg: N/A)
INFO:root:  Terminal state reached.
INFO:root:
--- Final Aggregated Agent Response ---
Echo response for task simple-xxxxxx
---------------------------------------
```
