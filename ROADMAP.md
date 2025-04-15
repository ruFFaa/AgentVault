# AgentVault Project Roadmap

This document outlines the planned development phases and features for the AgentVault ecosystem. Our goal is to create a secure, interoperable, and easy-to-use platform for AI agent communication based on open standards like A2A and MCP concepts.

*Disclaimer: This roadmap represents our current plans and priorities. It is subject to change based on development progress, community feedback, and the evolution of underlying standards.*

## Current Status (Post Phase 2.5 Plan Definition)

*   **`agentvault` Library:** Core client implemented for A2A JSON-RPC/SSE interactions, API Key/None/OAuth2 (Client Creds) auth, secure local KeyManager (env, file, keyring), Agent Card parsing/validation, basic MCP utilities. Published on PyPI.
*   **`agentvault_registry` API:** FastAPI backend operational, supporting Agent Card submission/management (developer key auth), validation, list/search/get (including basic TEE/tag filtering), developer verification status. Uses PostgreSQL/Alembic. Basic rate limiting and CORS in place. Basic Web UI for discovery and developer portal implemented.
*   **`agentvault_cli`:** Functional CLI for local key config (`config`), registry discovery (`discover`), and task execution (`run`) using the library. Includes `rich` output formatting and artifact saving.
*   **`agentvault_server_sdk`:** Foundational SDK available with `BaseA2AAgent`, FastAPI integration (`create_a2a_router`, `@a2a_method`), `InMemoryTaskStore` with listener/notification support, and packaging tool (`agentvault-sdk package`). Published on PyPI.
*   **`agentvault_testing_utils`:** Shared utilities including `MockAgentVaultClient`, `mock_a2a_server` fixture, `create_test_agent_card` factory, `EchoAgent`, and assertion helpers.
*   **Documentation:** Initial documentation structure created with MkDocs, core concepts/architecture/security outlined, basic guides drafted, A2A profile documented. Deployed via GitHub Pages.
*   **CI/CD:** Workflows for dependency audit and documentation deployment are functional.

## Next Steps (Consolidated Phase 2.5 Implementation)

**Objective:** Execute the tasks outlined in the **"Phase 2.5: Ecosystem Enablement & Refinement"** plan. This involves significantly enhancing documentation, creating diverse examples, refining the registry UI/UX, polishing the SDK and testing utilities, and ensuring TEE discovery features are fully implemented and tested.

*(Refer to the detailed Phase 2.5 plan for specific task breakdowns)*

## Future Considerations (Beyond Phase 2.5 / Ideas)

*   **Phase 2.6: Automation & Robustness:**
    *   Implement the `automation_scripts/` (`av_create_package_agent`, `av_deploy_register_agent`, `av_find_run_task`).
    *   Address scalability concerns (e.g., registry developer key lookup).
    *   Enhance Server SDK state management (persistent stores like DB/Redis).
    *   Improve error handling depth and test coverage across all components.
*   **Phase 3: Advanced Multimodality (WebRTC):**
    *   Integrate `aiortc` for optional real-time audio/video streaming support within the A2A protocol.
    *   Define signaling mechanisms via A2A.
    *   Provide SDK hooks for media track and data channel handling.
*   **Registry Enhancements:** Community reviews/ratings, usage analytics (opt-in), more advanced search/filtering, improved developer portal features.
*   **Deeper MCP Integration:** Align with finalized MCP specifications, provide SDK helpers for context manipulation.
*   **TEE Attestation Verification:** Implement client-side verification of TEE attestations based on `attestationEndpoint` in Agent Cards.
*   **Other Language SDKs/Libraries:** Explore SDKs for Node.js, Go, etc.
*   **Security Audits:** Formal third-party security reviews.
*   **"No-Code/Low-Code" Builder:** (Potential separate initiative) UI tools for creating simple agents.
*   **Visual Workflow Builder:** Graphical tool for orchestrating discovered agents.

## Contributing

We welcome community contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, suggesting features, and submitting pull requests. You can also join discussions on our GitHub repository.
