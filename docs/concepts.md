# Core Concepts

This page defines the key concepts within the AgentVault ecosystem.

## Agent Card

*   **Definition:** A standardized JSON document (`agent-card.json`) containing metadata about an A2A agent.
*   **Purpose:** Enables discovery and provides clients with the necessary information to interact with an agent (endpoint URL, capabilities, authentication methods, skills, etc.).
*   **Schema:** Defined by the AgentVault project (see [A2A Profile v0.2](a2a_profile_v0.2.md)).
*   **Key Fields:** `humanReadableId`, `name`, `description`, `url`, `capabilities`, `authSchemes`, `provider`.

## Agent-to-Agent (A2A) Protocol

*   **Definition:** The communication protocol used for direct interaction between an AgentVault client (or another agent) and an A2A-compliant agent server.
*   **Based On:** Aligned with concepts from the [Google A2A Protocol](https://github.com/google/A2A) specification (using JSON-RPC 2.0 over HTTP POST, Server-Sent Events for streaming).
*   **Key Methods:** `tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/sendSubscribe`.
*   **Profile:** See the [AgentVault A2A Profile v0.2](a2a_profile_v0.2.md) for specific implementation details.

## Model Context Protocol (MCP)

*   **Definition:** (Conceptual) A protocol designed for exchanging richer contextual information between agents, potentially including complex data structures, file references, and standardized metadata.
*   **Status:** Currently in the conceptual phase within AgentVault. Basic utilities exist for embedding context data within A2A message metadata.
*   **Goal:** To enable more sophisticated multi-agent collaboration beyond simple request/response.

## AgentVault Registry

*   **Definition:** A central API service where developers can register their agents (by submitting Agent Cards) and users/clients can discover agents.
*   **Component:** `agentvault_registry`
*   **Features:** Agent listing, search, detail retrieval, agent card validation, developer verification (planned). Includes a basic web UI.

## AgentVault Library (Client)

*   **Definition:** The core Python library (`agentvault`) providing client-side functionality.
*   **Component:** `agentvault_library`
*   **Features:** `AgentVaultClient` for making A2A calls (JSON-RPC, SSE), `KeyManager` for secure credential handling, Agent Card parsing/validation utilities, Pydantic models for A2A/Agent Card structures.

## AgentVault Server SDK

*   **Definition:** A Python SDK (`agentvault-server-sdk`) designed to simplify the process of building A2A-compliant agent servers.
*   **Component:** `agentvault_server_sdk`
*   **Features:** `BaseA2AAgent` class, FastAPI integration helpers (`create_a2a_router`), task state management abstractions, packaging utilities (`agentvault-sdk` CLI tool).

## Trusted Execution Environment (TEE)

*   **Definition:** A secure area within a processor, providing confidentiality and integrity guarantees for code and data running inside it.
*   **Relevance:** Agents can optionally declare TEE usage in their Agent Card (`capabilities.teeDetails`) to signal enhanced security postures. Clients can potentially verify TEE attestations.
*   **Profile:** See the [AgentVault TEE Profile](tee_profile.md) (placeholder link).
