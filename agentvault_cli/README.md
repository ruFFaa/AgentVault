# AgentVault CLI Client (`agentvault-cli`)

This directory contains the source code for the `agentvault-cli`, a reference command-line client for the AgentVault ecosystem.

**Purpose:**

This tool demonstrates how to use the `agentvault` core library to:

*   Securely configure local API keys and OAuth 2.0 credentials required by remote agents.
*   Discover agents listed in the AgentVault Registry API.
*   Load agent definitions directly via URL or local file.
*   Initiate and interact with remote agents using the A2A protocol.

**Installation:**

```bash
# Install from PyPI (once published)
pip install agentvault-cli

# For development (from the agentvault root directory)
# Ensure root .venv is created and activated first (see main project README)
pip install -e ".\agentvault_cli\[dev]"```

**Usage:**

*(Usage examples remain the same)*

### Discovering Agents
...
### Running an Agent Task
... *(Ensure any state examples use SUBMITTED, WORKING, COMPLETED, etc.)*

**Configuration:**

Local API keys and OAuth 2.0 credentials are managed using the `config` subcommand. See `agentvault_cli config --help`.

*   **API Keys:** Use `config set <service-id> --env`, `config set <service-id> --file <path>`, or `config set <service-id> --keyring` to configure how the CLI finds API keys.
*   **OAuth 2.0 Credentials:** Use `config set <service-id> --oauth-configure` to securely store Client ID and Client Secret (prefers OS keyring).
*   **Checking Configuration:** Use `config get <service-id>` to see how credentials for a service are being sourced. Use `--show-key` (with caution) or `--show-oauth-id` to view masked keys or Client IDs.

Keys/credentials are loaded based on environment variables, specified files, or the OS keyring as configured.

**Future Enhancements:**

*   Support for a client-side configuration file (e.g., `~/.config/agentvault/config.toml`) to set defaults for registry URL, timeouts, etc.
*   More detailed output formatting options.
*   Support for additional A2A features as the protocol evolves.
