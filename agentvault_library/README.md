# AgentVault Core Library (`agentvault`)

This directory contains the source code for the core `agentvault` Python library.

**Purpose:**

This library provides the foundational components for interacting with the AgentVault ecosystem:

*   Implementation of the client-side Agent-to-Agent (A2A) protocol.
*   Support for formatting and embedding Model Context Protocol (MCP) payloads within A2A messages.
*   Secure utilities for managing local API keys needed for authenticating with remote agents (via Environment Variables, Secure Files, or OS Keyring).
*   Tools for parsing and validating A2A Agent Cards.

**Key Modules (Planned):**

*   `client.py`: Contains the main `AgentVaultClient` class for managing A2A connections and task lifecycles.
*   `key_manager.py`: Implements the `KeyManager` class for secure local API key handling.
*   `agent_card_utils.py`: Provides functions for loading and validating Agent Card JSON.
*   `mcp_utils.py`: Contains helpers for formatting MCP context data.
*   `models/`: Pydantic models defining Agent Card structure, A2A protocol messages/events, and internal data structures.
*   `exceptions.py`: Defines custom exception classes used throughout the library.

**Installation:**

This library is intended to be used as a dependency by applications like `agentvault-cli` or your own custom integrations.

```bash
# Install from PyPI (once published)
pip install agentvault

# Install locally for development (from the agentvault_library directory)
poetry install --all-extras
```

**Usage:**

See the main project documentation and user guides for detailed usage examples. Basic interaction involves:

1.  Instantiating `KeyManager` to load necessary API keys.
2.  Loading/Fetching an `AgentCard` model using `agent_card_utils`.
3.  Instantiating `AgentVaultClient`.
4.  Calling methods like `client.initiate_task`, `client.send_message`, `client.receive_messages` using the loaded `AgentCard` and `KeyManager`.

**Development:**

See the main project `README.md` for contribution guidelines and development setup. Tests are located in `agentvault_library/tests/library/`.
