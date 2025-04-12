# AgentVault
"Open-source toolkit (Python Library, Registry API, CLI) for secure, decentralized AI agent interoperability using A2A/MCP."
  
```markdown
# AgentVault

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) <!-- Or MIT -->
[![PyPI version](https://badge.fury.io/py/agentvault.svg)](https://badge.fury.io/py/agentvault) <!-- Placeholder - Needs actual PyPI release -->
[![Python Version](https://img.shields.io/pypi/pyversions/agentvault.svg)](https://pypi.org/project/agentvault/) <!-- Placeholder -->
<!-- Add Build Status, Coverage badges later -->

**AgentVault: Secure, Decentralized AI Agent Interoperability**

## Overview

AgentVault is an open-source ecosystem designed to empower users and developers in the evolving landscape of AI agents. Its primary goal is to enable **secure discovery and interaction with diverse, remote AI agents** while ensuring **users retain full control over their sensitive API keys**.

Built upon emerging open standards like the **Agent-to-Agent (A2A)** protocol and leveraging the **Model Context Protocol (MCP)** for standardized context exchange, AgentVault aims to be a foundational layer for a more open, secure, and interoperable agentic future.

**Core Principles:**

1.  **Local Key Management:** Your primary AI provider API keys (OpenAI, Anthropic, Google, etc.) stay securely on your local machine, managed via the `agentvault` library and CLI. They are *never* uploaded to the central registry or exposed unnecessarily.
2.  **Decentralized Execution:** Remote agents run on their providers' infrastructure. AgentVault facilitates *communication*, not execution hosting for third-party agents.
3.  **Standardized Communication:** Uses the A2A protocol for agent interaction lifecycle management and MCP for structuring contextual data payloads.
4.  **Open Discovery:** A central registry allows developers to publish metadata (Agent Cards) about their agents, making them discoverable, but the registry *only* handles metadata, not execution or keys.
5.  **Open Source:** The core library, registry backend, and reference CLI are fully open source (Apache 2.0 License).

**Phase 1 Components:**

*   **`agentvault` (Core Python Library):** The heart of the ecosystem. Implements the A2A client protocol, MCP context formatting, and secure local key management utilities. ([agentvault_library/README.md](agentvault_library/README.md))
*   **`agentvault-registry` (Backend API):** A FastAPI-based backend API providing the central discovery service. It stores and serves Agent Card metadata and handles developer submissions. ([agentvault_registry/README.md](agentvault_registry/README.md))
*   **`agentvault-cli` (CLI Client):** A command-line reference implementation demonstrating how to use the `agentvault` library to manage keys, discover agents via the registry, and interact with remote agents. ([agentvault_cli/README.md](agentvault_cli/README.md))

*(Note: Web-based user interfaces for the registry and client are planned for Phase 2).*

## Security Model: Understanding the Risks & Responsibilities

AgentVault prioritizes user control over API keys, but operating within a decentralized agent ecosystem requires understanding the trust model:

1.  **Your Keys Stay Local:** The `agentvault` library and `agentvault-cli` are designed to load and use your API keys (e.g., OpenAI, Anthropic keys needed for certain agents, OR keys provided by premium agent developers for *their* service) from your local environment (environment variables, secure files, or OS keyring). **These keys are NOT sent to the AgentVault Registry.**
2.  **Communication Requires Trust:** When you use the CLI or library to run a task with a remote agent discovered via the registry (or specified directly by URL/file):
    *   Your client establishes a **direct HTTPS connection** to the remote agent's A2A endpoint URL listed in its Agent Card.
    *   The library sends necessary **authentication credentials** (e.g., an API key *for that specific agent service*, which you configured locally via the CLI) directly to that endpoint over HTTPS.
    *   The **task input and any context** you provide are sent (over HTTPS) to the remote agent endpoint.
3.  **You Trust the Remote Agent Operator:** Just like using any third-party API, you are trusting the developer/operator hosting the remote agent endpoint to handle the data you send securely and according to their privacy policy. **AgentVault cannot enforce or guarantee the security practices of independent remote agent providers.**
4.  **Risk Mitigation:** Check the Agent Card in the registry for links to the provider's privacy policy and terms of service before interacting.
    *   **Prefer Trusted/Verifi
    *   **Review Agent Cards:**ed Agents:** Initially, prioritize using agents from known developers, open-source agents whose code you can inspect (if they link to it), or agents you host yourself.
    *   **Minimize Sensitive Data:** Be cautious about the data you include in task inputs or context files sent to unknown remote agents.
    *   **Secure Key Management:** Use the most secure method available in your environment for storing keys locally (OS Keyring > Environment Variables > Secured Files). Never commit key files to Git.

**The AgentVault Registry only stores metadata (Agent Cards) for discovery. It does not execute agents, handle A2A communication traffic, or process your API keys.**

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
*   [Poetry](https://python-poetry.org/docs/#installation)
*   [Git](https://git-scm.com/downloads)

### Installation

*(Note: Assumes `agentvault-cli` is published to PyPI. Until then, installation would be from source)*

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
    *   Requires the `keyring` library and its backends to be installed and configured on your OS. Install the extra: `pip install agentvault-library[os_keyring]`
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
        *   Replace `<SERVICE_ID_UPPERCASE>` with the service ID in uppercase (e.g., `AGENTVAULT_KEY_OPENAI`).
    *   The library will automatically pick these up if configured (default). Tell the CLI you've set it (optional guidance step):
        ```bash
        agentvault_cli config set <service_id> --env
        ```
3.  **Secure File (Use with Caution):**
    *   Create a file (e.g., `~/.config/agentvault/keys.env` or `~/.agentvault_keys.json`).
    *   **IMPORTANT: Secure this file! `chmod 600 ~/.config/agentvault/keys.env`**
    *   Add keys in `.env` format (`SERVICE_ID=key_value`) or JSON (`{"service_id": "key_value"}`).
    *   Tell the CLI where the file is (optional guidance step):
        ```bash
        agentvault_cli config set <service_id> --file ~/.config/agentvault/keys.env
        ```

**Checking Configuration:**

```bash
# See how the key for a specific service is being sourced
agentvault_cli config get <service_id>

# List services found via file/env methods
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
    agentvault_cli run --agent-url https://some-agent.com/agent-card.json --input "Summarize this text: ..."

    # Run using local agent card file
    agentvault_cli run --agent-file ./path/to/downloaded-card.json --input "Translate to French: Hello"

    # Run with input from a file
    agentvault_cli run --agent <agent_id> --input @./my_document.txt

    # Run with MCP context from a JSON file (Syntax TBC based on MCP implementation)
    # agentvault_cli run --agent <agent_id> --input "Analyze this data" --context-file ./context.json
    ```

The CLI will connect to the remote agent, initiate the task using the A2A protocol via the `agentvault` library, display status updates, and show the final result or artifact.

## For Agent Developers

1.  **Build Your Agent:** Create your agent logic using any language/framework.
2.  **Expose an A2A Endpoint:** Create an HTTPS web server endpoint that understands and responds to A2A protocol messages (JSON-RPC requests like `tasks/send`, `tasks/get`, etc., potentially serving SSE for `tasks/sendSubscribe`). Implement your chosen authentication mechanism(s).
3.  **Create Agent Card:** Generate a JSON file matching the A2A Agent Card schema, accurately describing your agent, its capabilities, the A2A endpoint URL, and required authentication schemes.
4.  **Publish (Phase 1):** Use the (future) Registry API or web UI to submit your `agent-card.json`. You'll likely need to register as a developer and get a Registry API Key first.

*(Reference server implementations and detailed developer guides are planned for future phases).*

## Development Setup

If you want to contribute to AgentVault itself:

1.  Clone the main repository: `git clone <repository_url>`
2.  `cd agentvault`
3.  Set up Poetry for in-project virtual environments: `poetry config virtualenvs.in-project true`
4.  Install all components' dependencies (including dev tools):
    ```bash
    cd agentvault_library && poetry install --sync --with dev --all-extras && cd ..
    cd agentvault_registry && poetry install --sync --with dev && cd ..
    cd agentvault_cli && poetry install --sync --with dev && cd ..
    ```
5.  Activate the environment: `. .venv/bin/activate` (Bash/Zsh) or `.\.venv\Scripts\Activate.ps1` (PowerShell)
6.  Set up necessary services for development (e.g., local PostgreSQL database for the registry).
7.  Run tests using `pytest` from the root or within component directories.

## Roadmap

*   **Phase 1 (Current):** Core Library (A2A Client, MCP Context, Key Mgmt), Registry Backend API (Discovery), CLI Client.
*   **Phase 2 (Planned):** Web UI for Registry (Discovery & Developer Portal), Reference Web Client UI. Library refinements.
*   **Phase 3+ (Ideas):** Integration with other platforms (OpenAI Assistants etc.), enhanced security features, reference server implementations, advanced A2A features.

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` (to be created) for guidelines on reporting issues, submitting pull requests, and the development process.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
```