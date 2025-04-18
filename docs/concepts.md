# Core Concepts

This page defines the key concepts and terminology used throughout the AgentVault ecosystem. Understanding these concepts is crucial for effectively using the tools and contributing to the project.

## Agent Card

*   **Definition:** A standardized JSON document (typically named `agent-card.json`) containing metadata that describes an A2A-compliant agent. It's the agent's "business card" for the digital world.
*   **Purpose:** Enables discovery via the [AgentVault Registry](#agentvault-registry) and provides essential information for clients (other agents or applications) to connect, authenticate, and interact with the agent.
*   **Schema:** The structure and required fields are defined by the `agentvault.models.AgentCard` Pydantic model, aligning with emerging A2A standards. See the [A2A Profile v0.2](a2a_profile_v0.2.md) for protocol details derived from the card.
*   **Key Fields:** Includes the agent's unique `humanReadableId`, display `name`, `description`, the A2A endpoint `url`, technical `capabilities` (like supported protocol versions, TEE usage), required `authSchemes`, and details about the `provider`.

## Agent-to-Agent (A2A) Protocol

*   **Definition:** The standardized communication protocol enabling direct interaction between AgentVault clients and A2A-compliant agent servers. It defines the methods, message formats, and interaction patterns.
*   **Based On:** Inspired by and aligned with concepts from the [Google A2A Protocol](https://github.com/google/A2A) specification, utilizing JSON-RPC 2.0 over HTTP POST for requests and Server-Sent Events (SSE) over HTTP for asynchronous streaming updates.
*   **Key Methods:** Defines standard operations like initiating tasks (`tasks/send`), retrieving task status (`tasks/get`), requesting cancellation (`tasks/cancel`), and subscribing to real-time updates (`tasks/sendSubscribe`).
*   **Profile:** The specific implementation details, method signatures, payload structures, and state transitions used within AgentVault are documented in the [AgentVault A2A Profile v0.2](a2a_profile_v0.2.md).

## Model Context Protocol (MCP)

*   **Definition:** (Conceptual / Future Work) A protocol intended for exchanging richer, structured contextual information between agents beyond simple text prompts.
*   **Status:** Currently conceptual within AgentVault. Basic embedding in message metadata is supported. A formal specification is planned.
*   **Goal:** Enable more sophisticated, context-aware collaboration.

## AgentVault Registry

*   **Definition:** A central API service (`agentvault_registry`) and web UI acting as the discovery hub. Developers register agents by submitting Agent Cards. Clients query the registry to find agents.
*   **Component:** `agentvault_registry`
*   **Features:** Public REST API for discovery (list, search, get). Authenticated REST API and **Developer Portal UI (`/ui/developer`)** for developers to manage cards (submit, update, deactivate) and **programmatic API keys**. Includes Agent Card validation, developer account management (email/password login, JWT sessions, recovery keys), and a public discovery UI (`/ui`). See the [Registry API Guide](developer_guide/registry.md).

## AgentVault Library (Client)

*   **Definition:** The core Python library (`agentvault`) providing client-side tools.
*   **Component:** `agentvault_library`
*   **Features:** `AgentVaultClient` (A2A calls, SSE, auth handling), `KeyManager` (secure local credential storage), Agent Card utilities, MCP helpers, Pydantic models. See the [Library Guide](developer_guide/library.md).

## AgentVault Server SDK

*   **Definition:** Python SDK (`agentvault-server-sdk`) to accelerate building A2A-compliant agent servers.
*   **Component:** `agentvault_server_sdk`
*   **Features:** `BaseA2AAgent` class, FastAPI integration (`create_a2a_router`, `@a2a_method`), task state abstractions, packaging tool (`agentvault-sdk package`). See the [Server SDK Guide](developer_guide/server_sdk.md).

## AgentVault CLI

*   **Definition:** Command-line interface (`agentvault-cli`) for users/developers.
*   **Component:** `agentvault_cli`
*   **Features:** Manage local credentials (`config`), discover agents (`discover`), execute tasks (`run`). See the [CLI User Guide](user_guide/cli.md).

## KeyManager

*   **Definition:** Component in `agentvault_library` for secure local credential management (API keys, OAuth Client ID/Secrets).
*   **Component:** Part of `agentvault_library` (`key_manager.py`)
*   **Sources:** Loads from file (`.env` or `.json`), environment variables, or OS Keyring (recommended).
*   **Lookup:** Uses a [Service Identifier](#service-identifier) to find the correct credential set.

## Service Identifier

*   **Definition:** A string used by `KeyManager` to look up local credentials. Acts as a local alias.
*   **Source:** Defined in `AgentCard` (`authSchemes[].service_identifier`) or specified by the user/client (e.g., `agentvault_cli run --key-service <your_local_id>`).
*   **Purpose:** Allows reusing a single local credential (e.g., "openai" key) for multiple agents requiring the same authentication.

## Trusted Execution Environment (TEE)

*   **Definition:** Secure, isolated hardware environment (e.g., Intel SGX, AWS Nitro Enclaves).
*   **Relevance:** Agents can declare TEE usage in their Agent Card (`capabilities.teeDetails`). Registry allows filtering by TEE support.
*   **Current Scope:** Declarative only. Automated attestation verification is future work. See the [TEE Profile](tee_profile.md).

## Developer Authentication (Registry)

*   **Login:** Developers authenticate to the registry API and Developer Portal UI using **email and password**, receiving a **JWT** session token.
*   **Programmatic Access:** Developers can generate separate, long-lived **API Keys** (prefixed `avreg_`) via the Developer Portal for use in scripts or CI/CD to manage their agent cards. These are sent via the `X-Api-Key` header.
*   **Recovery:** Account access can be recovered using **Recovery Keys** generated during registration if the password is lost.
