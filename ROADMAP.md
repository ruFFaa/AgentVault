# AgentVault Project Roadmap

This document outlines the planned development phases and features for the AgentVault ecosystem. Our goal is to create a secure, interoperable, and easy-to-use platform for AI agent communication based on open standards like A2A and MCP concepts.

*Disclaimer: This roadmap represents our current plans and priorities. It is subject to change based on development progress, community feedback, and the evolution of underlying standards.*

## Current Status (Conceptual - Pre Phase 2.2)

*   **`agentvault` Library:** Core client implemented for A2A JSON-RPC/SSE interactions, basic MCP embedding, API Key/None auth, and secure local KeyManager (env, file, keyring). Published on PyPI.
*   **`agentvault-registry` API:** FastAPI backend operational, supporting Agent Card submission (developer key auth), validation, list/search/get, and basic developer management (hashed keys). Uses PostgreSQL/Alembic. Basic rate limiting and CORS in place.
*   **`agentvault-cli`:** Functional CLI for local key config (`config`), registry discovery (`discover`), and basic task execution (`run`) using the library.
*   **Phase 2.1 Requirements (Foundation):** Assumes foundational Server SDK structure, initial registry UI, basic testing utils, and related documentation requirements are conceptually defined or underway.

## Planned Development Phases

### Phase 2.2: Toolkit Maturation & Ecosystem Integration

**Objective:** Enhance the core components with advanced features to significantly improve developer experience (DX), user experience (UX), and integration capabilities.

**Key Features:**

*   **Server SDK (`agentvault-server-sdk`) Enhancements:**
    *   **`@a2a_method` Decorator:** Simplify A2A method definition in agent code.
    *   **Task State Helpers:** Utilities for managing task lifecycles (in-memory store initially).
    *   **Enhanced Event Generation:** Simplified helpers for sending SSE events (Status, Message, Artifact).
    *   **Standardized Error Handling:** Map common Python exceptions to standard JSON-RPC error responses.
*   **Agent Packaging & Deployment Helpers (SDK):**
    *   **Dockerfile Generation Tool:** (`agentvault-sdk package`) Automate creation of standardized Dockerfiles for easy agent containerization.
    *   **Dependency Handling:** Manage `requirements.txt` inclusion for packaged agents.
    *   **Deployment Documentation:** Guide developers on building/deploying the generated Docker images.
*   **Registry Enhancements (API & UI):**
    *   **Web UI Search/Filtering:** Add client-side search and basic filtering to the registry discovery UI.
    *   **Badges:** Display "Verified Developer" and potentially "Open Source" badges in the UI.
    *   **API Tag Filtering:** Allow filtering agent lists by tags via the API (requires DB indexing).
    *   **Developer Portal UI:** Basic web interface for developers to log in (via API key) and manage their submitted Agent Cards (Submit, View, Update, Deactivate).
*   **Client UX Improvements (CLI):**
    *   **Improved `run` Output:** Enhanced formatting using Rich (spinners, panels, syntax highlighting).
    *   **Large Artifact Handling:** Option (`--output-artifacts`) to save large artifact content to files instead of printing.
    *   **(Documentation):** Guidance on using shell history and tools (`fzf`) for interactive agent selection.
*   **Testing Utilities (`agentvault-testing-utils`) Enhancements:**
    *   **Agent Card Factory:** Utility to generate test Agent Card data.
    *   **Test Agent Skeleton:** Provide a basic agent implementation using the SDK as a test target/example.
    *   **Stateful Mock Server:** Enhance the mock A2A server to simulate basic task state transitions.
    *   **Assertion Helpers:** Utilities for verifying A2A interaction sequences in tests.
*   **Integration Examples:**
    *   **LangChain:** Example wrapping an A2A agent as a LangChain `Tool`.
    *   **Server SDK:** Example demonstrating exposing a simple Python function/service as an A2A agent using the SDK.
*   **Documentation:** Consolidation and updates for all Phase 2.2 features.

### Phase 2.2.1: Template-Driven Workflow Automation

**Objective:** Introduce automation scripts leveraging the finalized Phase 2.2 components to streamline common developer and user workflows via simple configuration templates.

**Key Features:**

*   **New `automation_scripts/` Directory:** Central location for workflow scripts and templates.
*   **Script 1: `av_create_package_agent`:**
    *   Takes a template (YAML/TOML) defining agent basics.
    *   Generates agent boilerplate code using the SDK.
    *   Generates `agent-card.json` (placeholder URL).
    *   Runs the SDK packaging tool (`agentvault-sdk package`) to create Docker artifacts.
    *   Optionally builds the Docker image locally.
*   **Script 2: `av_deploy_register_agent`:**
    *   Takes a template defining image tag, registry details, and developer key info.
    *   Guides user through `docker push` and obtaining the public URL.
    *   Updates the local `agent-card.json` with the public URL.
    *   Uses the developer's local API key (via `KeyManager`) to submit/update the card to the AgentVault Registry API.
*   **Script 3: `av_find_run_task`:**
    *   Takes a template defining discovery terms (search/ID), task input, and required keys.
    *   Checks local key configuration using `agentvault-cli config get`.
    *   Automates discovery using `agentvault-cli discover` (handles multiple results via prompt).
    *   Invokes `agentvault-cli run` with the correct parameters, streaming output.
*   **Documentation:** Dedicated documentation explaining script usage and template formats.

### Phase 3: Advanced Multimodality (WebRTC)

**Objective:** Extend the `agentvault_library` to optionally support real-time audio/video streaming modalities via WebRTC, as suggested by the Google A2A spec overview.

**Key Features (High-Level):**

*   **Integrate `aiortc`:** Add as an optional dependency (`agentvault[webrtc]`).
*   **Signaling Implementation:** Define signaling messages (SDP/ICE) within A2A `DataPart`s; handle sending/receiving signals via the existing A2A channel in `AgentVaultClient`.
*   **Connection Management:** Manage `RTCPeerConnection` lifecycle based on signals.
*   **Media Track Handling:** Provide hooks (`add_media_track`, `on_track`) for applications to send/receive audio/video tracks.
*   **Data Channel Handling:** Provide hooks for using WebRTC data channels.
*   **Testing & Documentation:** Update tests and docs for WebRTC features.

### Future Considerations (Beyond Phase 3 / Ideas)

*   **Enhanced Registry Features:** Community reviews/ratings, usage analytics, more sophisticated developer verification, advanced search facets.
*   **Server SDK Persistent Storage:** Add more persistent storage backends for task state (e.g., Database via SQLAlchemy).
*   **Other Language SDKs/Libraries:** Develop SDKs/libraries for Node.js, Go, etc.
*   **Deeper MCP Integration:** More sophisticated handling and generation of MCP context based on spec evolution.
*   **"No-Code/Low-Code" Builder (Separate Initiative?):** Explore UI tools for non-developers to create simple agents (potentially requiring a different hosting/funding model).
*   **Visual Workflow Builder:** Graphical tool to orchestrate agents discovered via the registry.
*   **Security Audits:** Formal third-party security reviews.

## Contributing

We welcome community contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, suggesting features, and submitting pull requests. You can also join discussions on our GitHub repository.
