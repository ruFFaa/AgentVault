# AgentVault Testing Utilities

This package provides shared mocks, fixtures, factories, and helpers for testing AgentVault components (`agentvault_library`, `agentvault_cli`, `agentvault_registry`, `agentvault_server_sdk`).

## Installation

This package is intended for development use and is typically installed as part of the monorepo setup using Poetry:

```bash
# From the monorepo root
poetry install --with dev
```

## Components

### Mocks

*   **`MockAgentVaultClient`**: A mock implementation of `agentvault.client.AgentVaultClient`. Allows configuring return values and side effects for testing client-side logic without making real network calls.

    ```python
    from agentvault_testing_utils.mocks import MockAgentVaultClient
    from agentvault.models import Task, TaskState

    mock_client = MockAgentVaultClient()

    # Configure return value
    mock_task = Task(...) # Create a mock Task object
    mock_client.get_task_status_return_value = mock_task

    # Configure side effect (exception)
    mock_client.initiate_task_side_effect = A2AConnectionError("Mock connection failed")

    # Use in tests
    async def test_something():
        # ... setup ...
        status = await mock_client.get_task_status(...)
        assert status == mock_task
        # ... assertions ...
        mock_client.call_recorder.get_task_status.assert_awaited_once()
    ```

### Mock Server & Fixtures

*   **`mock_a2a_server` (Pytest Fixture)**: Sets up mock A2A JSON-RPC and OAuth token endpoints using `respx`. Provides basic request handling and allows tests to inspect/modify mock state (task store, SSE events).

    ```python
    # In your conftest.py or test file:
    from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo

    # In your test function:
    def test_api_call(mock_a2a_server: MockServerInfo):
        # mock_a2a_server.base_url gives the mock server URL
        # mock_a2a_server.task_store allows checking mock task state
        # mock_a2a_server.sse_event_store allows configuring events for SSE
        # ... make calls using httpx or AgentVaultClient ...
    ```

*   **`setup_mock_a2a_routes`**: Helper function used by the fixture to configure `respx` routes. Can be used directly for more complex mock server setups.

### Factories

*   **`create_test_agent_card`**: Creates an `AgentCard` Pydantic model instance with default values, allowing overrides for specific fields. Useful for generating test data.

    ```python
    from agentvault_testing_utils.factories import create_test_agent_card

    # Create a default card
    default_card = create_test_agent_card()

    # Create a card with overrides
    custom_card = create_test_agent_card(
        name="My Custom Test Agent",
        humanReadableId="my-org/custom",
        provider={"name": "My Test Org"}
    )
    ```

### Test Agents

*   **`EchoAgent`**: A basic implementation of `BaseA2AAgent` that simply echoes back the first message received in a task and completes. Useful for testing the Server SDK's router integration and basic A2A flows.

    ```python
    # Example usage with FastAPI test client
    from agentvault_testing_utils.agents import EchoAgent
    from agentvault_server_sdk.fastapi_integration import create_a2a_router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    echo_agent = EchoAgent()
    a2a_router = create_a2a_router(agent=echo_agent)
    app = FastAPI()
    app.include_router(a2a_router, prefix="/a2a")
    client = TestClient(app)

    # Now make requests to client.post("/a2a/", ...)
    ```

### Assertions

*(To be added - e.g., helpers for asserting specific A2A calls were made)*
