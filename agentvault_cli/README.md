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
