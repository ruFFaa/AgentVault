# AgentVault

**AgentVault is an open-source ecosystem designed to facilitate secure and interoperable communication between AI agents (Agent-to-Agent or A2A).**

This project provides libraries, tools, and specifications to enable seamless interaction in a multi-agent world.

---

**➡️ Public Registry & UI Available!**

A live instance of the AgentVault Registry API and its associated Web UI is hosted at:
**[`https://agentvault-registry-api.onrender.com`](https://agentvault-registry-api.onrender.com)**

*   **Public Discovery UI:** [`https://agentvault-registry-api.onrender.com/ui`](https://agentvault-registry-api.onrender.com/ui)
*   **Developer Portal UI:** [`https://agentvault-registry-api.onrender.com/ui/developer`](https://agentvault-registry-api.onrender.com/ui/developer)
*   **API Base:** `https://agentvault-registry-api.onrender.com/api/v1`
*   **Note (Cold Start):** This is hosted on Render's free tier. If inactive, it may take **up to 60 seconds** to "wake up" on the first request. You can visit the `/health` endpoint or the UI to wake it up.

---

**➡️ For detailed documentation, please visit the [AgentVault Documentation Hub](index.md) ⬅️**
*(Note: Documentation is actively being developed)*

---

## Components

The AgentVault monorepo contains the following key components:

*   **`agentvault_library`**: ([Developer Guide](developer_guide/library.md)) Core Python client library for interacting with A2A agents, managing keys, and handling protocols (A2A, MCP).
*   **`agentvault_cli`**: ([User Guide](user_guide/cli.md)) Command-line interface for users and developers to manage credentials, discover agents, and run tasks.
*   **`agentvault_registry`**: ([Developer Guide](developer_guide/registry.md)) Backend API server (FastAPI) acting as the central discovery point for registered agents. Also serves a **Web UI** for public discovery (`/ui`) and developer management (`/ui/developer`). *(Live instance available above)*
*   **`agentvault_server_sdk`**: ([Developer Guide](developer_guide/server_sdk.md)) Python SDK to help developers build A2A-compliant agent servers easily, integrating with frameworks like FastAPI. Includes packaging tools.
*   **`agentvault_testing_utils`**: ([Developer Guide](developer_guide/testing.md)) Shared mocks, fixtures, factories, and helpers for testing AgentVault components.
*   **`examples/`**: Contains practical examples demonstrating how to use the SDK and library (e.g., basic A2A server, LangChain integration). See the [Examples Overview](examples.md).
*   **`automation_scripts/`**: (Coming Soon) Scripts to automate common workflows like agent packaging and deployment.
*   **`docs/`**: Source files for this documentation website (built with MkDocs).

## Installation

Please refer to the [Installation Guide](installation.md). For development setup, see the [Contributing Guide](CONTRIBUTING.md).

## Contributing

Contributions are welcome! Please see the [Contributing Guide](CONTRIBUTING.md) for details on setting up the development environment, running tests, and submitting changes.

## License

AgentVault is licensed under the Apache License, Version 2.0. See the [LICENSE](../LICENSE) file in the project root for details.
