# AgentVault

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI version](https://badge.fury.io/py/agentvault.svg)](https://pypi.org/project/agentvault/)
[![Python Version](https://img.shields.io/pypi/pyversions/agentvault.svg)](https://pypi.org/project/agentvault/)
<!-- Add Build Status, Coverage badges later -->

**AgentVault: Secure, Decentralized AI Agent Interoperability**

## Overview

AgentVault is an open-source ecosystem designed to empower users and developers in the evolving landscape of AI agents. Its primary goal is to enable **secure discovery and interaction with diverse, remote AI agents** while ensuring **users retain full control over their sensitive API keys**.

Built upon emerging open standards like the **Agent-to-Agent (A2A)** protocol (specifically the AgentVault A2A Profile, aligned with Google's A2A JSON-RPC/SSE approach) and leveraging the **Model Context Protocol (MCP)** for structuring context exchange, AgentVault aims to be a foundational layer for a more open, secure, and interoperable agentic future.

**Core Principles:**

1.  **Local Key Management:** Your primary AI provider API keys stay securely on your local machine.
2.  **Decentralized Execution:** Remote agents run on their providers' infrastructure.
3.  **Standardized Communication:** Uses the AgentVault A2A Profile and MCP concepts.
4.  **Open Discovery:** Central registry for Agent Card metadata only.
5.  **Open Source:** Core components are Apache 2.0 licensed.

**Core Components:**

*   **`agentvault` (Core Python Library):** A2A client, MCP context helpers, secure local key management. ([agentvault_library/README.md](agentvault_library/README.md)) - **Available on PyPI!**
*   **`agentvault-registry` (Backend API & Basic UI):** FastAPI backend and simple Web UI for Agent Card discovery and developer submissions. ([agentvault_registry/README.md](agentvault_registry/README.md)) - **Live Dev Instance Available!**
*   **`agentvault-cli` (CLI Client):** Reference client using the library for configuration, discovery, and task execution. ([agentvault_cli/README.md](agentvault_cli/README.md)) - *(Planned for PyPI)*

## Security Model & Trust

AgentVault prioritizes user control over API keys, but operating within a decentralized agent ecosystem requires understanding the trust model:

1.  **Your Keys Stay Local:** The `agentvault` library and `agentvault-cli` load and use your API keys from your local environment (environment variables, secure files, or OS keyring). **These keys are NOT sent to the AgentVault Registry.**
2.  **Communication Requires Trust:** When you interact with a remote agent:
    *   Your client connects **directly** to the agent's A2A endpoint (HTTPS).
    *   Authentication credentials *for that specific agent service* (configured locally using API Key or OAuth2) are sent directly to the agent.
    *   Task input and context are sent directly to the agent.
3.  **Trusting Remote Agents:** You are trusting the developer/operator hosting the remote agent endpoint. **AgentVault cannot enforce or guarantee the security or privacy practices of independent remote agent providers.**
4.  **Risk Mitigation:**
    *   **Review Agent Cards:** Check the card in the registry (via API or Web UI) for provider info, links to their privacy policy ([`PRIVACY_POLICY.md`](PRIVACY_POLICY.md)) and terms of service ([`TERMS_OF_SERVICE.md`](TERMS_OF_SERVICE.md)) before interacting. Also review the [AgentVault Registry Policy](REGISTRY_POLICY.md). Look for verified developer badges.
    *   **Prefer Trusted Agents:** Prioritize agents from known developers or open-source projects.
    *   **Minimize Sensitive Data:** Be cautious about the data sent to unknown agents.
    *   **Secure Key Management:** Use the most secure local method available (OS Keyring recommended via `agentvault-cli config set ... --keyring` or `--oauth-configure`).

**The AgentVault Registry only stores metadata (Agent Cards) for discovery. It does not execute agents, handle A2A communication traffic, or process your primary API keys.** For details on reporting security issues with AgentVault itself, see our [Security Policy](SECURITY.md).

## Architecture (Conceptual)

```
+-------------------+      (Registry API Call)      +-------------------------+
| User via          |<~-~-~-~-~-~-~-~-~-~-~-~-~-~-~>| AgentVault Registry     |
| `agentvault-cli`  | (GET/POST /api/v1/...) + (UI) | (FastAPI + DB + Web UI) |
| (Runs Locally)    |                               | (Hosted Service)        |
+-------------------+                               +-------------------------+
      |     ^                                                 | (Metadata Only)
      |     | (Uses Library)                                  |
      v     |                                                 |
+-------------------+ (A2A Protocol: JSON-RPC over HTTPS + SSE) +--------------------+
| `agentvault`      |----------------------------------------->| Remote Agent Host  |
| (Python Library)  |<-----------------------------------------| (Developer's Infra)|
| (Runs Locally,    |    (Handles Auth Locally:               | (AgentVault SDK? + |
|  Manages Keys)    |     APIKey / OAuth2 Client Creds)       |  Agent Logic)      |
+-------------------+                                         +--------------------+
      |
      v
(OS Keyring / .env / File on User Machine)
```*(Diagram shows conceptual flow after Phase 2.2.1)*

## Project Status & Roadmap

AgentVault is currently under active development. The core library (`agentvault`), registry API (`agentvault-registry`), and CLI (`agentvault-cli`) provide foundational A2A interaction capabilities based on JSON-RPC and SSE, with robust local key management.

We are currently focused on **Phase 2.2 and 2.2.1**, which involve maturing the ecosystem toolkit to significantly enhance developer experience and usability. Key upcoming features include:

*   **`agentvault-server-sdk`:** A Python library to drastically simplify building A2A-compliant agents.
*   **Enhanced Registry:** Improved UI, search, and trust features (like developer verification).
*   **Dockerfile Generation:** Tools within the SDK to easily package agents for deployment.
*   **Workflow Automation Scripts:** Tools to automate common tasks like creating, deploying, and running agents.
*   **OAuth 2.0 Client Support:** Adding support for OAuth Client Credentials in the library and CLI.

**See our [Project Roadmap](ROADMAP.md) for details on upcoming features and planned phases.**

## Getting Started (Using the CLI)

*(Keep existing Installation, Configuration, Live Registry, and Usage sections as they are in the current README.md, ensuring they reflect Phase 2.1/2.2 state once reached, especially regarding OAuth config)*

*(Example Snippet - ensure this section is up-to-date)*
### Installation
```bash
# Install core library (includes client functionality)
pip install agentvault
# Install optional OS Keyring support
# pip install agentvault[os_keyring]

# Install CLI (assuming published to PyPI after REQ-CLI-DIST-001)
pip install agentvault-cli

# Verify
agentvault_cli --version
```*(Update configuration section to include `--oauth-configure`)*

## For Agent Developers

*(Keep existing section, but update point 4)*

4.  **Package & Deploy:** Use the `agentvault-server-sdk` packaging tool (`agentvault-sdk package`) to generate a Dockerfile and related artifacts. Build the Docker image and deploy it to your preferred hosting platform. Get the public HTTPS URL.
5.  **Publish to Registry:** Update your `agent-card.json` with the final public URL. Submit or update the card on the AgentVault Registry using the Developer Portal UI or the API (requires a Developer API Key).

## Development Setup

*(Keep existing section, potentially simplifying the manual pip install steps if Poetry workspaces or monorepo tools become more reliable, but the editable install principle remains)*

## Contributing

We welcome contributions! Please see our [**Contributing Guidelines**](CONTRIBUTING.md) and adhere to our [**Code of Conduct**](CODE_OF_CONDUCT.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details. Dependency licenses have been reviewed and are believed to be compatible. See [DEPENDENCY_LICENSES.md](DEPENDENCY_LICENSES.md).

## Legal

*   [Registry Policy](REGISTRY_POLICY.md)
*   [Terms of Service (Registry API)](TERMS_OF_SERVICE.md)
*   [Privacy Policy (Registry API)](PRIVACY_POLICY.md)
*   [Security Policy (Vulnerability Disclosure)](SECURITY.md)
