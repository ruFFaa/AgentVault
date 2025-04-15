# AgentVault Examples

This section provides practical examples demonstrating how to use the various components of the AgentVault ecosystem.

These examples are designed to help you get started quickly, whether you are building an A2A-compliant agent, using the client library to interact with agents, or utilizing the command-line interface.

## Available Examples

The source code for these examples can be found in the `/examples/` directory of the [AgentVault GitHub repository](https://github.com/SecureAgentTools/AgentVault/tree/main/examples).

*   **[Basic A2A Server](../../examples/basic_a2a_server/README.md)**
    *   **Focus:** Demonstrates the minimal setup required to create an A2A-compliant agent server using the `agentvault-server-sdk` and FastAPI.
    *   **Features:** Implements a simple "EchoAgent", uses the SDK's router integration (`create_a2a_router`), includes a basic `agent-card.json`, and shows how to run the server with Uvicorn.
    *   **Good for:** Developers starting to build their first A2A agent.

*   **[LangChain Integration](../../examples/langchain_integration/README.md)**
    *   **Focus:** Shows how to wrap an AgentVault A2A agent as a custom `Tool` within the LangChain framework.
    *   **Features:** Defines an `A2AAgentTool` class that uses the `agentvault` client library internally to communicate with a remote agent based on an agent reference (ID, URL, or file path). Includes example usage.
    *   **Good for:** Developers wanting to integrate existing or new A2A agents into LangChain applications and agentic workflows.

*   **(Coming Soon) OAuth Agent Example:** An example agent demonstrating the implementation of the `oauth2` (Client Credentials) authentication scheme using the Server SDK.

*   **(Coming Soon) Stateful Agent Example:** An example agent showcasing how to manage task state across multiple interactions using the Server SDK's state management features.

*   **(Coming Soon) Library Usage Example:** A Python script demonstrating direct usage of the `agentvault` client library to discover and interact with an agent, bypassing the CLI.

## Running the Examples

Please refer to the `README.md` file within each specific example directory for detailed setup and execution instructions. Generally, you will need to:

1.  Ensure you have the main development environment set up (see [Installation Guide](installation.md)).
2.  Navigate to the specific example directory (e.g., `cd examples/basic_a2a_server`).
3.  Install any example-specific requirements (usually via `pip install -r requirements.txt`).
4.  Follow the instructions in the example's `README.md` to run the server or script.

We encourage you to explore these examples and adapt them for your own use cases!
