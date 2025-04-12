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
# Install from PyPI (once published)
pip install agentvault-cli

# For development (from the agentvault root directory)
# Ensure root .venv is created and activated first (see main project README)
pip install -e ".\agentvault_cli\[dev]"
```

**Usage:**

*(Usage examples remain the same)*

### Discovering Agents
...
### Running an Agent Task
...

**Configuration:**

Local API keys are managed using the `config` subcommand. See `agentvault_cli config --help`. Keys are loaded based on environment variables, specified files, or the OS keyring as configured.

**Future Enhancements:**

*   Support for a client-side configuration file (e.g., `~/.config/agentvault/config.toml`) to set defaults for registry URL, timeouts, etc.
*   More detailed output formatting options.
*   Support for additional A2A features as the protocol evolves.
