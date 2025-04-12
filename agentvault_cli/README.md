# AgentVault CLI Client (`agentvault-cli`)

This directory contains the source code for the `agentvault-cli`, a reference command-line client for the AgentVault ecosystem.

**Purpose:**

This tool demonstrates how to use the `agentvault` core library to:

*   Securely configure local API keys required by remote agents.
*   Discover agents listed in the AgentVault Registry API.
*   Load agent definitions directly via URL or local file.
*   Initiate and interact with remote agents using the A2A protocol.

**Installation:**

```bash
# From PyPI (once published)
pip install agentvault-cli

# For development (from the agentvault_cli directory, assumes library is sibling)
poetry install --with dev
```

**Usage:**

See the main project documentation (`docs/user_guides/cli/`) or use the built-in help.

```bash
agentvault_cli --help
agentvault_cli config --help
agentvault_cli discover --help
agentvault_cli run --help
```

**Key Commands:**

*   `agentvault_cli config set <service_id> [--env | --file <path> | --keyring]`: Configure key source.
*   `agentvault_cli config get <service_id>`: Check key source.
*   `agentvault_cli discover [SEARCH_QUERY] [--registry <url>]`: Find agents.
*   `agentvault_cli run --agent <id|url|file> --input <text|@file>`: Execute agent task.

**Development:**

See the main project `README.md` for contribution guidelines and development setup. Tests are located in `agentvault_cli/tests/cli/`.
