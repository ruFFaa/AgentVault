# AgentVault Testing Utilities (`agentvault-testing-utils`)

This package provides shared testing utilities, mocks, fixtures, and helper functions for testing components within the AgentVault ecosystem.

**(Placeholder - More details will be added as utilities are implemented)**

**Purpose:**

*   Reduce code duplication in tests across different AgentVault components (`agentvault_library`, `agentvault_cli`, `agentvault_server_sdk`).
*   Provide standardized ways to mock external dependencies and interactions (like A2A communication).
*   Offer helper functions for creating test data (e.g., Agent Cards).

**Key Components (Planned):**

*   `mocks.py`: Mock implementations of core classes (e.g., `MockAgentVaultClient`).
*   `mock_server.py`: Utilities for setting up mock HTTP servers (using `respx`) that simulate A2A endpoints.
*   `fixtures.py`: Reusable pytest fixtures (e.g., `mock_a2a_server`).
*   `factories.py`: Functions to generate test data (e.g., `create_test_agent_card`).
*   `assertions.py`: Custom assertion helpers for common testing patterns.

**Installation:**

This package is intended as a **development dependency** for other AgentVault components. It's typically installed via the `[dev]` group or `[test]` group of the component being tested.

```bash
# Example: Installing dev dependencies for agentvault_library
# (Run from agentvault_library directory)
# poetry install --with dev
```
