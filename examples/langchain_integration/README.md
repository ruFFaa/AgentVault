# AgentVault LangChain Integration Example

This directory contains a basic example demonstrating how to integrate an AgentVault A2A compliant agent as a tool within the LangChain framework.

## Components

*   **`requirements.txt`**: Defines the necessary Python dependencies (`langchain-core`, `agentvault`, `httpx`).
*   **`a2a_tool.py`**: Contains the `A2AAgentTool` class, which inherits from LangChain's `BaseTool`. This tool handles the interaction with a remote A2A agent using the `agentvault` client library.
*   **`example_usage.py`**: A simple script showing how to instantiate and invoke the `A2AAgentTool`.

## Setup

1.  **Install Dependencies:** Navigate to this directory (`examples/langchain_integration`) in your terminal and install the requirements. This includes installing the local `agentvault` library in editable mode.
    ```bash
    pip install -r requirements.txt
    ```
    *Note:* This assumes your virtual environment is activated and you are in the correct directory. The `-e ../../agentvault_library` line installs the library from your local source tree.

2.  **Configure Agent Reference:** Open `example_usage.py` and modify the `EXAMPLE_AGENT_REF` variable to point to a valid agent:
    *   **Agent ID:** If using an ID from a running AgentVault Registry (e.g., `test-org/my-agent`), ensure the `AGENTVAULT_REGISTRY_URL` environment variable is set correctly or modify the default in `a2a_tool.py`.
    *   **Agent URL:** Provide the direct URL to the agent's `agent-card.json` (e.g., `http://localhost:8001/agent-card.json`).
    *   **Local File:** Provide the path to a local `agent-card.json` file (e.g., `./path/to/your/agent-card.json`).

3.  **Configure Credentials:** If the target agent requires authentication (e.g., `apiKey` or `oauth2`), ensure the necessary credentials are set up using the AgentVault CLI (`agentvault config set ...`) or environment variables, matching the `service_identifier` specified in the agent's card.

## Running the Example

Once set up, you can run the example script:

```bash
python example_usage.py
```

The script will:

1.  Instantiate the `A2AAgentTool`.
2.  Prepare the input (agent reference and text prompt).
3.  Invoke the tool's `_arun` method.
4.  The tool will internally use `AgentVaultClient` to:
    *   Load the agent card.
    *   Initiate a task.
    *   Stream events (though only assistant text messages are captured in this basic example).
    *   Wait for the task to complete.
5.  Print the final aggregated text response from the agent.

**Note:** This example primarily demonstrates the tool's structure and integration. For it to fully succeed, you need a running A2A agent accessible at the specified `EXAMPLE_AGENT_REF` that can handle the input prompt. You can use the `agentvault-server-sdk` examples or your own agent implementation.
