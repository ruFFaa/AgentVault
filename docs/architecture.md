# AgentVault Architecture

This document provides a high-level overview of the AgentVault ecosystem architecture, illustrating how the different components interact to enable secure agent discovery and communication.

## Vision

AgentVault aims to be the open-source backbone for a thriving multi-agent ecosystem. It provides the standards, tools, and infrastructure necessary for agents built by anyone, anywhere, to find each other and collaborate effectively and securely.

## Component Overview

The ecosystem consists of several distinct but interconnected Python packages and services:

1.  **`agentvault_library` (Core Client Library):** The foundation for client-side interactions. Contains the `AgentVaultClient` (handles A2A protocol logic), `KeyManager` (secure credential storage), Pydantic models (AgentCard, A2A messages), and utility functions (card parsing, MCP handling). Used by the CLI and any custom application wanting to interact with agents.
2.  **`agentvault_cli` (Command Line Interface):** The primary tool for end-users and developers to interact with the system from the terminal. Uses the `agentvault_library` to perform actions like configuring keys, discovering agents via the registry, and running tasks on agents.
3.  **`agentvault_registry` (Registry API & UI):** A central FastAPI web service acting as the discovery hub. It stores Agent Card metadata submitted by developers in a PostgreSQL database. It provides a public REST API for searching/retrieving cards and an authenticated API for developers to manage their listings. It also serves a basic web UI for discovery and developer management.
4.  **`agentvault_server_sdk` (Server SDK):** A toolkit for developers *building* A2A-compliant agents. Provides base classes (`BaseA2AAgent`), FastAPI integration helpers (`create_a2a_router`, `@a2a_method`), task state management abstractions, and packaging utilities (`agentvault-sdk package`) to simplify agent development and deployment.
5.  **`agentvault_testing_utils` (Testing Utilities):** A shared internal package containing mocks, pytest fixtures, factories, and assertion helpers used across the test suites of the other components to ensure consistency and reduce boilerplate. Not intended for direct use by end-users.

## Interaction Flow Diagram

```mermaid
graph LR
    subgraph User/Client Side
        User[User / Client App] -->|Uses| CLI(agentvault_cli)
        CLI -->|Uses| Lib(agentvault_library)
        User -->|Uses| Lib
        Lib -->|Manages Keys via KeyManager| KeyStore([Local Credential Store<br>(Env, File, Keyring)])
    end

    subgraph Developer Side
        Dev[Agent Developer] -->|Uses| SDK(agentvault_server_sdk)
        SDK -->|Builds Agent + Card| AgentServer(A2A Agent Server<br>e.g., FastAPI)
        Dev -->|Creates/Manages Registry Key| DevKeyStore([Developer API Key<br>Stored by Developer])
        Dev -->|Submits Card via API<br>(Uses DevKeyStore)| RegistryAPI(Registry API<br>/api/v1)
    end

    subgraph Central Service
        RegistryAPI -->|Reads/Writes Hashes| DB[(Registry PostgreSQL DB<br>Stores Cards & Hashed Dev Keys)]
        RegistryAPI -->|Serves UI| RegistryUI(Registry Web UI<br>/ui, /ui/developer)
        User -->|Browses| RegistryUI
    end

    subgraph Communication Paths
        Lib -- 1. Discover Agent (Public API) --> RegistryAPI
        Lib -- 2. Get Agent Card (Public API) --> RegistryAPI
        Lib -- 3. Run Task (A2A Protocol)<br>Uses KeyManager for Agent Auth --> AgentServer
        AgentServer -->|Optional: Uses Lib/SDK| ExternalService[External APIs / Services]
    end

    style Dev fill:#f9f,stroke:#333,stroke-width:2px
    style User fill:#ccf,stroke:#333,stroke-width:2px
    style KeyStore stroke-dasharray: 5 5
    style DevKeyStore stroke-dasharray: 5 5
```

**Explanation of Flows:**

1.  **Discovery:** A user or client application (using the Library or CLI) queries the Registry API's public endpoints to find agents based on criteria (search, tags, TEE support, etc.).
2.  **Card Retrieval:** The client retrieves the specific Agent Card for the desired agent from the Registry API (also a public endpoint).
3.  **Interaction (Client -> Agent):**
    *   The client application uses the information in the retrieved Agent Card (endpoint `url`, `authSchemes`).
    *   The `agentvault_library`'s `KeyManager` component attempts to load the necessary local credentials (API Key or OAuth Client ID/Secret) based on the agent's required `authSchemes` and the relevant `service_identifier`.
    *   The `AgentVaultClient` constructs and sends A2A protocol requests (JSON-RPC over POST for standard methods, potentially initiating an SSE stream via `tasks/sendSubscribe`) directly to the target Agent Server's endpoint (`url`).
    *   **Crucially, the `AgentVaultClient` automatically adds the correct authentication headers** (e.g., `X-Api-Key: <key>` or `Authorization: Bearer <token>`) based on the retrieved credentials and the scheme specified in the Agent Card. For OAuth2 Client Credentials, it handles the token fetching from the agent's `tokenUrl` automatically.
    *   The Agent Server (potentially built with the `agentvault-server-sdk`) receives the request, authenticates it based on the headers and its configuration, processes the task, and sends back JSON-RPC responses or streams SSE events.
4.  **Registration (Developer -> Registry):**
    *   The Agent Developer obtains a unique Developer API Key from the Registry administrators (process TBD, currently manual).
    *   The Developer uses this key in the `X-Api-Key` header when interacting with the authenticated endpoints of the Registry API (e.g., `POST /api/v1/agent-cards/`, `PUT /api/v1/agent-cards/{uuid}`) to submit or manage their Agent Cards.
    *   The Registry API verifies the key against stored hashes in its database.

## Key Architectural Principles

*   **Decentralized Execution:** Agents run independently wherever the developer chooses to host them. The AgentVault Registry is **only for discovery metadata**, not for agent execution or proxying A2A communication.
*   **Standardized Interface:** Client-Agent communication relies on the defined [AgentVault A2A Profile v0.2](a2a_profile_v0.2.md) (JSON-RPC/SSE) and the `AgentCard` schema defined by `agentvault.models`.
*   **Component-Based:** The ecosystem is modular, broken down into logical components (library, CLI, registry, SDK, testing utils) with distinct responsibilities.
*   **Security Focus:** Emphasis on secure credential management on the client (`KeyManager`), hashed API keys on the registry, HTTPS enforcement for all external communication, and awareness/declaration of TEE capabilities.
*   **Developer Experience:** The SDK and CLI tools aim to simplify common tasks for both agent developers (building, packaging, registering) and users (discovery, interaction, credential management).
