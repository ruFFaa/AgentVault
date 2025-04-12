# AgentVault Core Library (`agentvault`)

This directory contains the source code for the core `agentvault` Python library.

**Purpose:**

This library provides the foundational components for interacting with the AgentVault ecosystem:

*   Implementation of the client-side Agent-to-Agent (A2A) protocol.
*   Support for formatting and embedding Model Context Protocol (MCP) payloads within A2A messages.
*   Secure utilities for managing local API keys needed for authenticating with remote agents (via Environment Variables, Secure Files, or OS Keyring).
*   Tools for parsing and validating A2A Agent Cards.

**Key Modules:**

*   `client.py`: Contains the main `AgentVaultClient` class for managing A2A connections and task lifecycles.
*   `key_manager.py`: Implements the `KeyManager` class for secure local API key handling.
*   `agent_card_utils.py`: Provides functions for loading and validating Agent Card JSON.
*   `mcp_utils.py`: Contains helpers for formatting MCP context data.
*   `models/`: Pydantic models defining Agent Card structure, A2A protocol messages/events, and internal data structures.
*   `exceptions.py`: Defines custom exception classes used throughout the library.

**Protocol Considerations (Phase 1)**

*   **A2A Protocol Version:** This initial version of the library implements a baseline A2A protocol based on common JSON-RPC patterns and structures inspired by early A2A drafts (e.g., `a2a.json.txt` if provided). It assumes agents adhere to this baseline. Future versions will need to incorporate explicit version checking based on `AgentCard.capabilities.a2aVersion` and potentially support negotiation or different protocol versions.
*   **MCP Support:** Phase 1 includes basic support for embedding Model Context Protocol data. The `mcp_utils.py` module provides initial formatting, and the `AgentVaultClient` embeds the resulting dictionary into `message.metadata['mcp_context']`. This implementation will be refined to align with the official MCP specification as it stabilizes, potentially including more robust schema validation and structured object mapping.

**Installation:**

This library is intended to be used as a dependency by applications like `agentvault-cli` or your own custom integrations.

```bash
# Install from PyPI (once published)
pip install agentvault

# Install locally for development (from the agentvault_library directory)
# Ensure root .venv is created and activated first (see main project README)
pip install -e ".[os_keyring,dev]"
```

**Usage:**

See the main project documentation and user guides for detailed usage examples. Basic interaction involves:

1.  Instantiating `KeyManager` to load necessary API keys.
2.  Loading/Fetching an `AgentCard` model using `agent_card_utils`.
3.  Instantiating `AgentVaultClient`.
4.  Calling methods like `client.initiate_task`, `client.send_message`, `client.receive_messages` using the loaded `AgentCard` and `KeyManager`.

**Development:**

See the main project `README.md` for contribution guidelines and development setup. Tests are located in `agentvault_library/tests/library/`.

**Future Enhancements (Ideas):**

*   Full alignment with finalized A2A and MCP specifications.
*   Support for additional authentication schemes (e.g., OAuth2).
*   Client-side configuration file support (e.g., `~/.config/agentvault/config.toml`) for setting defaults like registry URL, timeouts, etc.
*   Helper functions for common agent interaction patterns.
