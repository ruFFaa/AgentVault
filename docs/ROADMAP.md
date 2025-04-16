# AgentVault Project Roadmap

This document outlines the planned development phases and features for the AgentVault ecosystem. Our goal is to create a secure, interoperable, and easy-to-use platform for AI agent communication based on open standards like A2A and MCP concepts.

*Disclaimer: This roadmap represents our current plans and priorities. It is subject to change based on development progress, community feedback, and the evolution of underlying standards.*

## Current Status (April 2025)

The AgentVault project has established a functional baseline across its core components:

*   **`agentvault` Library:** Core client implemented for A2A JSON-RPC/SSE interactions, API Key/None/OAuth2 (Client Creds) auth, secure local KeyManager (env, file, keyring), Agent Card parsing/validation, basic MCP utilities. Published on PyPI.
*   **`agentvault_registry` API:** FastAPI backend operational, supporting Agent Card submission/management (developer key auth), validation, list/search/get (including basic TEE/tag filtering), developer verification status. Uses PostgreSQL/Alembic. Basic rate limiting and CORS in place. Basic Web UI for discovery and developer portal implemented. *(Note: Developer registration is currently manual/admin-driven).*
*   **`agentvault_cli`:** Functional CLI for local key config (`config`), registry discovery (`discover`), and task execution (`run`) using the library. Includes `rich` output formatting and artifact saving.
*   **`agentvault_server_sdk`:** Foundational SDK available with `BaseA2AAgent`, FastAPI integration (`create_a2a_router`, `@a2a_method`), `InMemoryTaskStore` with listener/notification support, and packaging tool (`agentvault-sdk package`). Published on PyPI.
*   **`agentvault_testing_utils`:** Shared utilities including `MockAgentVaultClient`, `mock_a2a_server` fixture, `create_test_agent_card` factory, `EchoAgent`, and assertion helpers.
*   **Documentation:** Foundational documentation structure created with MkDocs, core concepts/architecture/security outlined, component guides drafted, A2A profile documented, examples added. Deployed via GitHub Pages.
*   **CI/CD:** Workflows for dependency audit and documentation deployment are functional.

## Next Steps: Phase 2.5 - Ecosystem Enablement & Refinement

**Objective:** Solidify the existing components, improve developer/user experience through better documentation and examples, and prepare for broader adoption.

**Key Tasks:**

1.  **Documentation Overhaul (Largely Complete - Minor Polish Remaining):**
    *   Enhance Component Guides (Done).
    *   Improve Core Concepts (Done).
    *   Finalize Policies (Placeholders updated).
    *   Installation Guide (Enhanced).
    *   Examples Overview (Updated).
    *   Vision Document (Added).
    *   Use Cases Document (Added).
2.  **Example Implementations (Complete):**
    *   Basic A2A Server (Done).
    *   LangChain Integration (Done).
    *   OAuth Agent Example (Done).
    *   Stateful Agent Example (Done).
    *   Direct Library Usage Example (Done).
3.  **Registry UI/UX Improvements:**
    *   **TODO:** Enhance the developer portal UI (`/ui/developer`) for easier card management (editing, viewing status).
    *   **TODO:** Improve filtering/search capabilities on the public UI (`/ui`).
    *   **TODO:** Display developer verification status clearly.
4.  **SDK & Testing Refinements:**
    *   **TODO:** Improve Server SDK state management abstractions (consider adding basic persistent store examples or interfaces).
    *   **TODO:** Expand `agentvault-testing-utils` with more assertion helpers or complex mocks as needed.
    *   **TODO:** Increase test coverage across all components.
5.  **TEE Feature Polish:**
    *   **TODO:** Test and verify TEE filtering in the registry API and UI works reliably.
    *   **TODO:** Ensure TEE support limitations (declarative only) are clearly documented (`tee_profile.md`).

## Future Considerations (Beyond Phase 2.5 / Ideas)

*   **Phase 2.6: Automation & Robustness:**
    *   Implement the `automation_scripts/` (`av_create_package_agent`, `av_deploy_register_agent`, `av_find_run_task`).
    *   Address scalability concerns (e.g., registry developer key lookup).
    *   Enhance Server SDK state management (persistent stores like DB/Redis).
    *   Improve error handling depth across all components.
*   **Phase 3: Advanced Features & Ecosystem Growth:**
    *   **Developer Self-Registration:** Implement a secure self-service workflow for developers to register and obtain API keys via the Registry API/UI (including email verification).
    *   **Multimodality (WebRTC):** Integrate `aiortc` for optional real-time audio/video streaming support within the A2A protocol.
    *   **Deeper MCP Integration:** Align with finalized MCP specifications, provide SDK helpers for context manipulation.
    *   **TEE Attestation Verification:** Implement client-side verification of TEE attestations based on `attestationEndpoint` in Agent Cards.
    *   **Registry Enhancements:** Community reviews/ratings, usage analytics (opt-in), more advanced search/filtering, improved developer portal features (key rotation, etc.).
    *   **Other Language SDKs/Libraries:** Explore SDKs for Node.js, Go, etc.
    *   **Security Audits:** Formal third-party security reviews.

## Contributing

We welcome community contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, suggesting features, and submitting pull requests. You can also join discussions on our GitHub repository.
