# AgentVault

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI version](https://badge.fury.io/py/agentvault.svg)](https://badge.fury.io/py/agentvault) <!-- Placeholder - Needs actual PyPI release -->
[![Python Version](https://img.shields.io/pypi/pyversions/agentvault.svg)](https://pypi.org/project/agentvault/) <!-- Placeholder -->
<!-- Add Build Status, Coverage badges later -->

**AgentVault: Secure, Decentralized AI Agent Interoperability**

## Overview

AgentVault is an open-source ecosystem designed to empower users and developers in the evolving landscape of AI agents. Its primary goal is to enable **secure discovery and interaction with diverse, remote AI agents** while ensuring **users retain full control over their sensitive API keys**.

Built upon emerging open standards like the **Agent-to-Agent (A2A)** protocol and leveraging the **Model Context Protocol (MCP)** for structuring context exchange, AgentVault aims to be a foundational layer for a more open, secure, and interoperable agentic future.

**Core Principles:**

1.  **Local Key Management:** Your primary AI provider API keys stay securely on your local machine.
2.  **Decentralized Execution:** Remote agents run on their providers' infrastructure.
3.  **Standardized Communication:** Uses A2A protocol and MCP.
4.  **Open Discovery:** Central registry for Agent Card metadata only.
5.  **Open Source:** Core components are Apache 2.0 licensed.

**Phase 1 Components:**

*   **`agentvault` (Core Python Library):** A2A client, MCP context, secure local key management. ([agentvault_library/README.md](agentvault_library/README.md))
*   **`agentvault-registry` (Backend API):** FastAPI backend for Agent Card discovery and developer submissions. ([agentvault_registry/README.md](agentvault_registry/README.md))
*   **`agentvault-cli` (CLI Client):** Reference client using the library. ([agentvault_cli/README.md](agentvault_cli/README.md))

## Security Model & Trust

AgentVault prioritizes user control over API keys, but operating within a decentralized agent ecosystem requires understanding the trust model:

1.  **Your Keys Stay Local:** The `agentvault` library and `agentvault-cli` load and use your API keys from your local environment (environment variables, secure files, or OS keyring). **These keys are NOT sent to the AgentVault Registry.**
2.  **Communication Requires Trust:** When you interact with a remote agent:
    *   Your client connects **directly** to the agent's A2A endpoint (HTTPS).
    *   Authentication credentials *for that specific agent service* (configured locally) are sent directly to the agent.
    *   Task input and context are sent directly to the agent.
3.  **Trusting Remote Agents:** You are trusting the developer/operator hosting the remote agent endpoint. **AgentVault cannot enforce or guarantee the security or privacy practices of independent remote agent providers.**
4.  **Risk Mitigation:**
    *   **Review Agent Cards:** Check the card in the registry for provider info, links to their privacy policy ([`PRIVACY_POLICY.md`](PRIVACY_POLICY.md)) and terms of service ([`TERMS_OF_SERVICE.md`](TERMS_OF_SERVICE.md)) before interacting. Also review the [AgentVault Registry Policy](REGISTRY_POLICY.md).
    *   **Prefer Trusted Agents:** Prioritize agents from known developers or open-source projects.
    *   **Minimize Sensitive Data:** Be cautious about the data sent to unknown agents.
    *   **Secure Key Management:** Use the most secure local method available (OS Keyring recommended).

**The AgentVault Registry only stores metadata (Agent Cards) for discovery. It does not execute agents, handle A2A communication traffic, or process your primary API keys.** For details on reporting security issues with AgentVault itself, see our [Security Policy](SECURITY.md).

## Architecture (Phase 1)

```
+-------------------+      (Registry API Call)      +------------------------+
| User via          |<----------------------------->| AgentVault Registry    |
| `agentvault-cli`  |     (GET /agent-cards/...)    | (FastAPI Backend + DB) |
| (Runs Locally)    |                               | (Hosted Service)       |
+-------------------+                               +------------------------+
      |     ^                                                | (Metadata Only)
      |     | (Uses Library)                                 |
      v     |                                                |
+-------------------+      (A2A Protocol via HTTPS)     +-------------------+
| `agentvault`      |----------------------------------->| Remote Agent Host |
| (Python Library)  |<-----------------------------------| (Developer's Infra)|
| (Runs Locally,    |      (Handles Keys Locally)       | (Executes Agent)  |
|  Manages Keys)    |                                   +-------------------+
+-------------------+
      |
      v
(OS Keyring / .env / File on User Machine)
```

## Getting Started (Using the CLI)

### Prerequisites

*   Python >= 3.10, < 3.12
*   [pip](https://pip.pypa.io/en/stable/installation/) (Python package installer)
*   [Git](https://git-scm.com/downloads) (Optional, for installing from source)

### Installation

*(Note: Assumes `agentvault-cli` is published to PyPI. Until then, installation would be from source using the Development Setup instructions below).*

```bash
# Install the CLI tool (this will also install the agentvault library)
pip install agentvault-cli

# Verify installation
agentvault_cli --version
```

### Configuration: Setting Up Your Local API Keys

The CLI needs access to API keys required by the remote agents you want to use. Keys are identified by a `service_id` (e.g., `openai`, `anthropic`, or a specific agent's ID like `premium-weather-agent`).

**Recommended Methods:**

1.  **OS Keyring (Most Secure - If Available):**
    *   Requires the `keyring` library and its backends to be installed and configured on your OS. Install the extra: `pip install agentvault-library[os_keyring]` (or `pip install agentvault[os_keyring]` if installing the combined package later).
    *   Set a key:
        ```bash
        # You will be prompted securely for the key value
        agentvault_cli config set <service_id> --keyring
        ```
2.  **Environment Variables (Good Security):**
    *   Set an environment variable **before** running the CLI:
        ```bash
        # PowerShell Example
        $env:AGENTVAULT_KEY_<SERVICE_ID_UPPERCASE> = "your_api_key_value"

        # Bash/Zsh Example
        export AGENTVAULT_KEY_<SERVICE_ID_UPPERCASE>="your_api_key_value"
        ```
        *   Replace `<SERVICE_ID_UPPERCASE>` with the service ID in uppercase (e.g., `AGENTVAULT_KEY_OPENAI`). The default prefix is `AGENTVAULT_KEY_`.
    *   The library will automatically pick these up. You can optionally run `agentvault_cli config set <service_id> --env` to get guidance.
3.  **Secure File (Use with Caution):**
    *   Create a file (e.g., `~/.config/agentvault/keys.env` or `~/.agentvault_keys.json`).
    *   **IMPORTANT: Secure this file! `chmod 600 ~/.config/agentvault/keys.env`**
    *   Add keys in `.env` format (`SERVICE_ID=key_value`) or JSON (`{"service_id": "key_value"}`).
    *   You can optionally run `agentvault_cli config set <service_id> --file <path_to_your_file>` to get guidance. The library needs to be initialized pointing to this file (currently requires code change or future config option).

**Checking Configuration:**

```bash
# See how the key for a specific service is being sourced
agentvault_cli config get <service_id>

# List services found via file/env methods (keyring keys only show if accessed)
agentvault_cli config list
```

## Usage (`agentvault-cli`)

### Discovering Agents

```bash
# List all agents from the default registry (paginated)
agentvault_cli discover

# Search agents mentioning "weather"
agentvault_cli discover "weather"

# Search using a specific registry URL and limit results
agentvault_cli discover --registry https://my-private-registry.com/api --limit 10 "database"
```

### Running an Agent Task

1.  **Identify the Agent:** Find the agent's ID from `discover`, or get its Agent Card URL or file path.
2.  **Ensure Keys are Configured:** Use `agentvault_cli config get <service_id>` to check if the key needed for the agent's authentication (check its Agent Card `authSchemes`) is set up locally.
3.  **Run the Task:**

    ```bash
    # Run using agent ID found via discover
    agentvault_cli run --agent <agent_card_id> --input "What is the weather in London?"

    # Run using agent card URL
    # Note: Use '--agent' for ID, URL, or File Path
    agentvault_cli run --agent https://some-agent.com/agent-card.json --input "Summarize this text: ..."

    # Run using local agent card file
    agentvault_cli run --agent ./path/to/downloaded-card.json --input "Translate to French: Hello"

    # Run with input from a file (prefix path with '@')
    agentvault_cli run --agent <agent_id> --input @./my_document.txt

    # Run with MCP context from a JSON file (Syntax TBC based on MCP implementation)
    # agentvault_cli run --agent <agent_id> --input "Analyze this data" --context-file ./context.json
    ```

The CLI will connect to the remote agent, initiate the task using the A2A protocol via the `agentvault` library, display status updates, and show the final result or artifact.

## For Agent Developers

1.  **Build Your Agent:** Create your agent logic using any language/framework.
2.  **Expose an A2A Endpoint:** Create an HTTPS web server endpoint that understands and responds to A2A protocol messages (JSON-RPC requests like `tasks/send`, `tasks/get`, etc., potentially serving SSE for `tasks/sendSubscribe`). Implement your chosen authentication mechanism(s).
3.  **Create Agent Card:** Generate a JSON file matching the A2A Agent Card schema, accurately describing your agent, its capabilities, the A2A endpoint URL, and required authentication schemes.
4.  **Publish (Phase 1):** Use the AgentVault Registry API (e.g., via `curl` or a custom script) to submit your `agent-card.json`. You will need to obtain a Developer API Key from the registry administrators first. Authenticate your API requests using the `X-Api-Key` header.

*(Reference server implementations and detailed developer guides are planned for future phases).*

## Development Setup

If you want to contribute to AgentVault itself:

1.  Clone the main repository: `git clone <repository_url>`
2.  `cd agentvault`
3.  **Crucially:** Ensure you have the correct Python version (>=3.10, <3.12) and Poetry installed.
4.  **Configure Poetry for In-Project Environment:**
    ```bash
    poetry config virtualenvs.in-project true
    ```
5.  **Create and Activate Root Environment:** Manually create the virtual environment in the project root using Python's `venv` module and activate it.
    ```bash
    # Ensure you are in the project root (e.g., D:\AgentVault)
    python -m venv .venv
    # Activate (PowerShell example)
    .\.venv\Scripts\Activate.ps1
    # Activate (Bash/Zsh example)
    # source .venv/bin/activate
    ```
6.  **Install All Components and Dependencies:** Use `pip` within the activated environment to install the local packages editably and their dependencies.
    ```bash
    # Ensure root .venv is active
    python -m pip install --upgrade pip

    # Install library editably with its extras
    pip install -e ".\agentvault_library\[os_keyring]"

    # Install registry editably
    pip install -e ".\agentvault_registry\"

    # Install CLI editably
    pip install -e ".\agentvault_cli\"

    # Install common dev dependencies manually
    pip install pytest pytest-asyncio pytest-mock httpx respx uvicorn slowapi alembic passlib[bcrypt] pydantic-settings asyncpg psycopg2-binary click rich
    ```
    *(Note: This manual installation of dev dependencies might need adjustment if specific versions are critical.)*
7.  **Set up Services:** Configure your local PostgreSQL database and create a `.env` file in `agentvault_registry/` as described in its README.
8.  **Run Migrations:**
    ```bash
    # Ensure .venv is active and you are in the project root
    cd agentvault_registry
    alembic upgrade head
    cd ..
    ```
9.  **Run Tests:**
    ```bash
    # Ensure .venv is active and you are in the project root
    pytest
    ```
10. **Run Development Server:**
    ```bash
    # Ensure .venv is active and you are in the project root
    uvicorn agentvault_registry.main:app --reload --host 0.0.0.0 --port 8000
    ```

## Contributing

We welcome contributions! Please see our [**Contributing Guidelines**](CONTRIBUTING.md) and adhere to our [**Code of Conduct**](CODE_OF_CONDUCT.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details. Dependency licenses have been reviewed and are believed to be compatible with the project's license.

## Legal

*   [Registry Policy](REGISTRY_POLICY.md)
*   [Terms of Service (Registry API)](TERMS_OF_SERVICE.md)
*   [Privacy Policy (Registry API)](PRIVACY_POLICY.md)
*   [Security Policy (Vulnerability Disclosure)](SECURITY.md)
