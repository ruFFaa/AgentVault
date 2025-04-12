# AgentVault

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE) <!-- Updated link -->
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

*(Content of Getting Started section remains the same)*

### Prerequisites
...
### Installation
...
### Configuration: Setting Up Your Local API Keys
...
## Usage (`agentvault-cli`)
...
### Discovering Agents
...
### Running an Agent Task
...

## For Agent Developers

*(Content remains the same)*

## Development Setup

*(Content remains the same, ensure it mentions the manual venv setup + pip install -e as the current reliable method)*

## Contributing

We welcome contributions! Please see our [**Contributing Guidelines**](CONTRIBUTING.md) and adhere to our [**Code of Conduct**](CODE_OF_CONDUCT.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details. Dependency licenses have been reviewed for compatibility.

## Legal

*   [Registry Policy](REGISTRY_POLICY.md)
*   [Terms of Service (Registry API)](TERMS_OF_SERVICE.md)
*   [Privacy Policy (Registry API)](PRIVACY_POLICY.md)
*   [Security Policy (Vulnerability Disclosure)](SECURITY.md)
