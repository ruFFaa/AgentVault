# AgentVault Project Roadmap

This document outlines the planned development phases and features for the AgentVault ecosystem. Our goal is to create a secure, interoperable, and easy-to-use platform for AI agent communication based on open standards like A2A and MCP concepts.

*Disclaimer: This roadmap represents our current plans and priorities. It is subject to change based on development progress, community feedback, and the evolution of underlying standards.*

## Current Status (April 2025 - Phase 2.5 Underway)

The AgentVault project has established a functional baseline across its core components and is actively refining the ecosystem based on initial implementation and usability testing.

*   **`agentvault` Library:** Core client implemented (A2A JSON-RPC/SSE, Auth Schemes, KeyManager, Models, Utils). Published.
*   **`agentvault_registry` API & UI:** Operational API (Card CRUD, Validation, Discovery Filters incl. TEE/Tags). **New:** Developer authentication via email/password (JWT), email verification, recovery keys, programmatic API key management (`/developers/me/apikeys`), Agent Builder endpoint (`/agent-builder/generate`). Web UI for public discovery (`/ui`) and developer portal (`/ui/developer`) with login/register/recovery flows implemented. Uses PostgreSQL/Alembic. Rate limiting/CORS active. *(Note: Email sending depends on deployment configuration).*
*   **`agentvault_cli`:** Functional CLI (`config`, `discover`, `run`). Supports KeyManager (keyring, oauth config), SSE streaming, artifact saving.
*   **`agentvault_server_sdk`:** Foundational SDK (`BaseA2AAgent`, FastAPI integration, `@a2a_method`, `InMemoryTaskStore` with notifications), packaging tool (`agentvault-sdk package`). Published.
*   **`agentvault_testing_utils`:** Shared utilities (`MockAgentVaultClient`, `mock_a2a_server` fixture, factory, `EchoAgent`, assertions).
*   **Examples:** Basic Server, LangChain Tool, OAuth Agent, Stateful Agent, Library Usage examples available.
*   **Documentation:** Structure established, core concepts/architecture/security documented, component guides drafted, A2A/TEE profiles documented, examples included. Deployed via GitHub Pages.
*   **CI/CD:** Dependency audit and docs deployment workflows functional.

## Next Steps: Phase 2.6 - Automation, Robustness & Polish

**Objective:** Complete automation scripts, improve robustness (testing, error handling, scalability), and polish the developer/user experience.

**Key Tasks:**

1.  **Automation Scripts:**
    *   **TODO:** Finalize and test `automation_scripts/` (`av_create_package_agent`, `av_deploy_register_agent`, `av_find_run_task`). Ensure they work reliably with the latest components.
    *   **TODO:** Refine agent template generation (e.g., better `.env` setup based on selected options).
2.  **Testing & Coverage:**
    *   **TODO:** Implement CI workflow for running `pytest` across all components.
    *   **TODO:** Integrate `pytest-cov` and add coverage reporting/thresholds to CI.
    *   **TODO:** Increase test coverage, focusing on complex logic (client state machine, registry auth flows, SDK router edge cases, CLI interactions).
    *   **TODO:** Add basic end-to-end tests (e.g., CLI -> Registry -> Mock Agent).
3.  **Registry Enhancements:**
    *   **TODO:** Investigate and potentially optimize developer programmatic API key lookup performance if needed for scale.
    *   **TODO:** Implement email-based password reset flow (currently placeholder).
    *   **TODO:** Further UI/UX improvements for the Developer Portal (e.g., easier card editing interface, clearer API key management).
4.  **SDK & Error Handling:**
    *   **TODO:** Provide examples or interfaces for persistent `BaseTaskStore` implementations (e.g., Redis, SQL).
    *   **TODO:** Review and standardize error handling and logging across all components for consistency.
5.  **Documentation Polish:**
    *   **TODO:** Fill in remaining placeholders in policy documents (Contact emails).
    *   **TODO:** Add more diagrams where helpful (e.g., auth flows).
    *   **TODO:** Review all guides for clarity and accuracy against latest code.

## Future Considerations (Phase 3 & Beyond)

*   **Multimodality (WebRTC):** Integrate `aiortc` for optional real-time audio/video streaming.
*   **Deeper MCP Integration:** Align with finalized MCP specifications, provide SDK helpers.
*   **TEE Attestation Verification:** Implement client-side verification of TEE attestations.
*   **Registry Features:** Community reviews/ratings, usage analytics (opt-in), advanced search, key rotation.
*   **Other Language SDKs/Libraries:** Explore SDKs for Node.js, Go, etc.
*   **Security Audits:** Formal third-party security reviews.

## Contributing

We welcome community contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
