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
        Lib -->|Manages Keys| KeyStore([Local Credential Store<br>(Env, File, Keyring)])
    end

    subgraph Developer Side
        Dev[Agent Developer] -->|Uses| SDK(agentvault_server_sdk)
        SDK -->|Builds Agent + Card| AgentServer(A2A Agent Server)
        Dev -->|Creates/Manages Keys| DevKeyStore([Developer API Key])
        Dev -->|Submits Card via API| RegistryAPI(Registry API<br>/api/v1)
    end

    subgraph Central Service
        RegistryAPI -->|Reads/Writes| DB[(Registry PostgreSQL DB)]
        RegistryAPI -->|Serves UI| RegistryUI(Registry Web UI<br>/ui, /ui/developer)
        User -->|Browses| RegistryUI
    end

    subgraph Communication Paths
        Lib -- 1. Discover Agent --> RegistryAPI
        Lib -- 2. Get Agent Card --> RegistryAPI
        Lib -- 3. Authenticate & Run Task (A2A Protocol) --> AgentServer
        AgentServer -->|Optional: Uses Lib/SDK| ExternalService[External APIs / Services]
    end

    style Dev fill:#f9f,stroke:#333,stroke-width:2px
    style User fill:#ccf,stroke:#333,stroke-width:2px
    style KeyStore stroke-dasharray: 5 5
    style DevKeyStore stroke-dasharray: 5 5
```

**Explanation of Flows:**

1.  **Discovery:** A user or client application (using the Library or CLI) queries the Registry API to find agents based on criteria (search, tags, etc.).
2.  **Card Retrieval:** The client retrieves the specific Agent Card for the desired agent from the Registry API.
3.  **Interaction:**
    *   The client uses the information in the Agent Card (endpoint `url`, `authSchemes`).
    *   The `agentvault_library` uses the `KeyManager` to retrieve the necessary local credentials based on the agent's required `authSchemes` and `service_identifier`.
    *   The library constructs and sends A2A protocol requests (JSON-RPC over POST/SSE) directly to the target Agent Server's endpoint (`url`).
    *   Authentication headers (`X-Api-Key` or `Authorization: Bearer`) are added automatically by the library based on the retrieved credentials and scheme.
    *   The Agent Server (potentially built with the `agentvault-server-sdk`) receives the request, authenticates it, processes the task, and sends back responses or streams events.
4.  **Registration (Developer):** The developer uses their unique Developer API Key to interact with the authenticated endpoints of the Registry API to submit or manage their Agent Cards.

## Key Architectural Principles

*   **Decentralized Execution:** Agents run independently. The registry is only for discovery, not execution or proxying.
*   **Standardized Interface:** Communication relies on the defined A2A profile (JSON-RPC/SSE) and Agent Card schema.
*   **Component-Based:** The ecosystem is broken down into logical components (library, CLI, registry, SDK) with distinct responsibilities.
*   **Security Focus:** Secure key management on the client, hashed keys on the registry, HTTPS enforcement (recommended), and TEE awareness are integrated.
*   **Developer Experience:** SDK and CLI tools aim to simplify common tasks for both agent developers and users.
