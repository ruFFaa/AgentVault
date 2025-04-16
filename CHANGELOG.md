# Changelog

All notable changes to the AgentVault project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for its individual published packages (`agentvault`, `agentvault-cli`, `agentvault-server-sdk`).

## [Unreleased]

### Added
- *(Add new features for the next release here)*

### Changed
- *(Add changes for the next release here)*

### Fixed
- *(Add bug fixes for the next release here)*

---

## [v0.2.1] / [v0.1.1] - 2025-04-16

This release focuses primarily on major documentation improvements, adding comprehensive examples, and enhancing the usability of the registry's developer portal UI based on the established v0.2.0/v0.1.0 functionality.

### Package Versions
- `agentvault`: 0.2.1
- `agentvault-cli`: 0.1.1
- `agentvault-server-sdk`: 0.1.1

### Added
- **New Examples:**
    - OAuth2 Client Credentials agent (`examples/oauth_agent_example/`)
    - Stateful agent demonstrating multi-turn interactions (`examples/stateful_agent_example/`)
    - Direct client library usage script (`examples/library_usage_example/`)
- **New Documentation Pages:**
    - `docs/vision.md`: Articulates the project's long-term goals and potential.
    - `docs/use_cases.md`: Provides detailed scenarios illustrating AgentVault's value, including Mermaid diagrams.
    - Copied example READMEs into `docs/examples/` for inclusion in the main documentation site.
- **Developer Portal UI:**
    - Status filter dropdown structure (HTML/CSS).
    - "Cancel Edit" button in the submit/update form.
    - Clearer visual distinction for active/inactive cards.
    - Status badges (Active/Inactive) displayed prominently on cards.
    - "Verified Dev" badge displayed on cards.
    - Header explicitly identifies the "Developer Portal".
    - "Logged in as" indicator structure.
    - Implemented JavaScript logic for status filtering, status toggling (Activate/Deactivate), cancel edit, and login verification via API call.

### Changed
- **Documentation Overhaul:**
    - Consolidated documentation source into the `/docs` directory.
    - Restructured `mkdocs.yml` navigation for better organization.
    - Significantly enhanced all component developer guides (`library.md`, `server_sdk.md`, `registry.md`, `testing.md`) with more detail, clearer explanations, and improved examples.
    - Updated `ROADMAP.md` to reflect current project status (Phase 2.5) and future plans (including developer self-registration).
    - Updated `installation.md` for clarity between user/dev setup and added notes about public registry/cold starts.
    - Updated `index.md`, `architecture.md`, `registry.md`, `cli.md` to include links/mentions of the public registry instance and Web UI.
    - Updated policy documents (`PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`, `REGISTRY_POLICY.md`, `CODE_OF_CONDUCT.md`, `security_policy.md`) to use clearer placeholders for contact information.
    - Updated `a2a_profile_v0.2.md` with more implementation details and clarifications.
- **Developer Portal UI:**
    - Renamed "Edit" button to "View / Edit".
    - Replaced "Deactivate" button with a "Toggle Status" button.
    - Improved CSS styling for clarity, spacing, and responsiveness.

### Fixed
- **Documentation:**
    - Corrected numerous broken internal links after file restructuring.
    - Fixed Mermaid diagram rendering issues in `architecture.md` by enabling the theme feature, removing internal comments, and simplifying link text syntax.
    - Fixed broken links on `examples.md` overview page.
- **Developer Portal UI:**
    - Ensured inactive cards are displayed in the "My Agent Cards" list.
    - Corrected API call logic in `loadOwnedCards` to fetch necessary details for rendering status.

---

## [v0.2.0] - 2025-04-15 (Baseline for `agentvault` library)

### Added
- **Core Client Library (`agentvault`):**
    - `AgentVaultClient` for A2A communication (JSON-RPC POST, SSE).
    - Support for `apiKey`, `oauth2` (Client Credentials), and `none` authentication schemes.
    - `KeyManager` for secure local credential management (env, file, keyring).
    - Pydantic models for `AgentCard`, A2A protocol messages (`Message`, `Part`, `Task`, `TaskState`, `Artifact`), and SSE events.
    - Utilities for Agent Card parsing/validation (`agent_card_utils`).
    - Basic utilities for MCP context handling (`mcp_utils`).
    - Custom exception hierarchy (`exceptions.py`).

---

## [v0.1.0] - 2025-04-15 (Initial Baseline for CLI, SDK, Registry, Testing)

### Added
- **Command Line Interface (`agentvault-cli`):**
    - `config` command group for managing local credentials (`set`, `get`, `list`).
    - `discover` command for searching the registry API.
    - `run` command for executing tasks on agents via A2A protocol, including SSE streaming output with `rich` formatting and artifact saving.
- **Server SDK (`agentvault-server-sdk`):**
    - `BaseA2AAgent` abstract class defining the agent interface.
    - `@a2a_method` decorator for exposing custom/standard methods.
    *   `create_a2a_router` helper for FastAPI integration, handling JSON-RPC routing and SSE setup.
    *   `BaseTaskStore` interface and `InMemoryTaskStore` implementation for state management.
    *   `TaskContext` base dataclass.
    *   SDK Exception types (`AgentServerError`, `TaskNotFoundError`, etc.).
    *   `agentvault-sdk package` CLI tool for generating Docker artifacts.
- **Registry API (`agentvault_registry`):**
    *   FastAPI application serving RESTful endpoints (`/api/v1`).
    *   Endpoints for Agent Card CRUD operations (POST, GET list, GET by ID, PUT, DELETE/deactivate).
    *   Developer authentication using hashed API keys (`X-Api-Key`).
    *   Agent Card validation against the core library schema.
    *   PostgreSQL database backend with Alembic migrations.
    *   Basic rate limiting (`slowapi`) and CORS middleware.
    *   `/utils/validate-card` endpoint.
    *   Basic static file serving for Web UI (`/ui`, `/ui/developer`).
- **Testing Utilities (`agentvault-testing-utils`):**
    *   `MockAgentVaultClient` for mocking client interactions.
    *   `mock_a2a_server` pytest fixture using `respx` for mocking HTTP endpoints.
    *   `create_test_agent_card` factory function.
    *   `EchoAgent` basic test agent implementation.
    *   Assertion helpers (`assert_a2a_call`, `assert_a2a_sequence`).
- **Initial Examples:**
    - Basic A2A Server example.
    - LangChain Tool integration example.
- **Initial Documentation:** Structure using MkDocs, core concept pages, initial guides.
- **CI/CD:** Basic workflows for dependency audit and docs deployment.

---
