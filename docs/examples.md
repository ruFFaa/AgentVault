# AgentVault Examples

This section provides practical examples demonstrating how to use the various components of the AgentVault ecosystem.

These examples are designed to help you get started quickly, whether you are building an A2A-compliant agent, using the client library to interact with agents, or utilizing the command-line interface.

## Available Examples

The source code for these examples can be found in the `/examples/` directory of the [AgentVault GitHub repository](https://github.com/SecureAgentTools/AgentVault/tree/main/examples).

*   **[Basic A2A Server](examples/basic_a2a_server.md):** ([View Code](https://github.com/SecureAgentTools/AgentVault/tree/main/examples/basic_a2a_server))
    *   **Focus:** Demonstrates the minimal setup required to create an A2A-compliant agent server using the `agentvault-server-sdk` and FastAPI.
    *   **Features:** Implements a simple "EchoAgent", uses the SDK's router integration (`create_a2a_router`), includes a basic `agent-card.json`, and shows how to run the server with Uvicorn.
    *   **Good for:** Developers starting to build their first A2A agent.

*   **[LangChain Integration](examples/langchain_integration.md):** ([View Code](https://github.com/SecureAgentTools/AgentVault/tree/main/examples/langchain_integration))
    *   **Focus:** Shows how to wrap an AgentVault A2A agent as a custom `Tool` within the LangChain framework.
    *   **Features:** Defines an `A2AAgentTool` class that uses the `agentvault` client library internally to communicate with a remote agent based on an agent reference (ID, URL, or file path). Includes example usage.
    *   **Good for:** Developers wanting to integrate existing or new A2A agents into LangChain applications and agentic workflows.

*   **[OAuth Agent Example](examples/oauth_agent_example.md):** ([View Code](https://github.com/SecureAgentTools/AgentVault/tree/main/examples/oauth_agent_example))
    *   **Focus:** Demonstrates implementing the `oauth2` (Client Credentials) authentication scheme using the Server SDK and FastAPI.
    *   **Features:** Includes a custom `/token` endpoint, uses environment variables for mock credentials, and protects the `/a2a` endpoint using a FastAPI dependency.
    *   **Good for:** Developers needing to implement OAuth2 authentication for their agents.

*   **[Stateful Agent Example](examples/stateful_agent_example.md):** ([View Code](https://github.com/SecureAgentTools/AgentVault/tree/main/examples/stateful_agent_example))
    *   **Focus:** Demonstrates managing task state (like chat history) across multiple client interactions within a single task ID using the Server SDK.
    *   **Features:** Uses a custom `TaskContext` subclass, `InMemoryTaskStore`, and `asyncio.Event` to handle multi-turn interactions and background processing.
    *   **Good for:** Developers building conversational agents or agents that require maintaining context over several requests.

*   **(Coming Soon) Library Usage Example:** A Python script demonstrating direct usage of the `agentvault` client library to discover and interact with an agent, bypassing the CLI.

## Running the Examples

Please refer to the `README.md` file within each specific example directory (linked via "[View Code]" above) for detailed setup and execution instructions. Generally, you will need to:

1.  Ensure you have the main development environment set up (see [Installation Guide](installation.md)).
2.  Navigate to the specific example directory (e.g., `cd examples/basic_a2a_server`).
3.  Install any example-specific requirements (usually via `pip install -r requirements.txt`).
4.  Follow the instructions in the example's `README.md` to run the server or script.

We encourage you to explore these examples and adapt them for your own use cases!
