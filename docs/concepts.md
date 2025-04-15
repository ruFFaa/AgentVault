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

*   **Definition:** (Conceptual / Future Work) A protocol intended for exchanging richer, structured contextual information between agents beyond simple text prompts. This might include user profiles, conversation history summaries, references to external data, or task-specific parameters.
*   **Status:** Currently in the conceptual phase within AgentVault. The `agentvault_library` provides basic utilities (`mcp_utils.py`) for embedding arbitrary context data within the `metadata['mcp_context']` field of A2A `Message` objects. A formal MCP specification is planned for future development, potentially aligning with external standards if they emerge.
*   **Goal:** To enable more sophisticated, context-aware collaboration and task handoff between specialized agents.

## AgentVault Registry

*   **Definition:** A central API service (`agentvault_registry`) and web UI acting as the discovery hub for the ecosystem. Developers register their agents by submitting Agent Cards, and clients query the registry to find agents based on various criteria.
*   **Component:** `agentvault_registry`
*   **Features:** Public REST API for listing, searching (by name, description, tags, TEE support), and retrieving Agent Cards. Authenticated REST API for developers to submit, update, and deactivate their cards. Includes Agent Card validation against the core library's schema, developer verification status tracking, and a basic web UI for discovery and developer management. See the [Registry API Guide](developer_guide/registry.md).

## AgentVault Library (Client)

*   **Definition:** The core Python library (`agentvault`) providing the client-side tools needed to interact with the ecosystem.
*   **Component:** `agentvault_library`
*   **Features:** Provides the `AgentVaultClient` for making A2A calls (handling JSON-RPC, SSE, authentication), the `KeyManager` for secure local credential handling (API keys, OAuth credentials), utilities for Agent Card parsing and validation (`agent_card_utils`), basic MCP context embedding helpers (`mcp_utils`), and Pydantic models defining all necessary data structures (`agentvault.models`). See the [Library Guide](developer_guide/library.md).

## AgentVault Server SDK

*   **Definition:** A Python Software Development Kit (`agentvault-server-sdk`) designed to accelerate the development of A2A-compliant agent servers.
*   **Component:** `agentvault_server_sdk`
*   **Features:** Includes the `BaseA2AAgent` abstract class, FastAPI integration helpers (`create_a2a_router`, `@a2a_method` decorator) to automatically expose agent logic via the A2A protocol, abstractions for task state management (`BaseTaskStore`, `InMemoryTaskStore`), utilities for handling MCP context server-side, and a command-line tool (`agentvault-sdk package`) for packaging agents into Docker containers. See the [Server SDK Guide](developer_guide/server_sdk.md).

## AgentVault CLI

*   **Definition:** A command-line interface (`agentvault-cli`) providing a user-friendly way to interact with AgentVault features.
*   **Component:** `agentvault_cli`
*   **Features:** Allows users to manage local credentials (`config`), discover agents in the registry (`discover`), and execute tasks on remote agents (`run`). Built using the `agentvault` library. See the [CLI User Guide](user_guide/cli.md).

## KeyManager

*   **Definition:** A component within the `agentvault_library` responsible for securely loading, storing (optionally via OS keyring), and retrieving credentials (API keys, OAuth Client ID/Secrets) needed by the `AgentVaultClient` to authenticate with remote agents.
*   **Component:** Part of `agentvault_library` (`key_manager.py`)
*   **Sources:** Loads credentials based on a priority order: specified file (`.env` or `.json`) > environment variables > OS keyring (if enabled and available).
*   **Lookup:** Uses a [Service Identifier](#service-identifier) to find the correct credential set for a given agent.

## Service Identifier

*   **Definition:** A string used by the `KeyManager` to look up the correct local credentials (API Key or OAuth Client ID/Secret) for a specific agent or service. It acts as a local alias for a credential set.
*   **Source:** Can be explicitly defined in an agent's `AgentCard` within the `authSchemes[].service_identifier` field. If omitted in the card, clients (like the CLI) might default to using the agent's `humanReadableId` or require the user to specify an override (e.g., via `agentvault_cli run --key-service <your_local_id>`).
*   **Purpose:** Allows a single credential (like an OpenAI key) stored locally under one `service_identifier` (e.g., "openai") to be used by multiple different agents that all require OpenAI authentication, even if their `humanReadableId`s differ.

## Trusted Execution Environment (TEE)

*   **Definition:** A secure, isolated environment within a computer's processor that provides hardware-level guarantees for the confidentiality and integrity of code and data executed within it. Examples include Intel SGX, AMD SEV, AWS Nitro Enclaves.
*   **Relevance:** Agents can optionally run within a TEE to enhance security and provide verifiable guarantees about their execution environment. Agent Cards can declare TEE usage (`capabilities.teeDetails`) including the type and potentially an attestation endpoint. The registry allows filtering for TEE-enabled agents.
*   **Current Scope:** AgentVault currently supports the *declaration* and *discovery* of TEE capabilities. Automated verification of TEE attestations during A2A communication is a planned future enhancement. See the [TEE Profile](tee_profile.md).
