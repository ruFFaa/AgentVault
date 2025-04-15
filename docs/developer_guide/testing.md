# Developer Guide: Testing Utilities (`agentvault-testing-utils`)

The `agentvault-testing-utils` package provides shared mocks, fixtures, factories, and helper functions designed to facilitate the testing of AgentVault components like the core library, CLI, registry, and server SDK implementations.

## Installation

This package is intended for development use only. Install it as a development dependency within the component you are testing using Poetry:

```bash
# From the component's directory (e.g., agentvault_library)
poetry add --group dev agentvault-testing-utils --path ../agentvault_testing_utils
```

Or ensure it's included in the main `poetry install --with dev` when run from the monorepo root.

## Provided Utilities

### Mocks (`MockAgentVaultClient`)

*   **Path:** `agentvault_testing_utils.mocks.MockAgentVaultClient`
*   **Purpose:** A mock implementation of the core `agentvault.client.AgentVaultClient`. It allows you to simulate A2A interactions without making real network calls, configure return values or exceptions for client methods, and record calls made to the client for assertion purposes.
*   **Usage Example:**
    ```python
    import pytest
    from agentvault_testing_utils.mocks import MockAgentVaultClient
    from agentvault.models import Task, TaskState
    from agentvault.exceptions import A2AConnectionError

    @pytest.mark.asyncio
    async def test_client_logic():
        mock_client = MockAgentVaultClient()

        # Configure return value for get_task_status
        mock_task = Task(...) # Assume Task object is created or mocked
        mock_client.get_task_status_return_value = mock_task

        # Configure initiate_task to raise an error
        mock_client.initiate_task_side_effect = A2AConnectionError("Mock connection failed")

        # --- Use the mock client in your test ---
        # Example: Test error handling
        with pytest.raises(A2AConnectionError):
            await mock_client.initiate_task(...)

        # Example: Test successful call
        status = await mock_client.get_task_status(...)
        assert status == mock_task

        # Example: Assert calls were made
        mock_client.call_recorder.get_task_status.assert_awaited_once()
    ```

### Mock Server (`mock_a2a_server` fixture)

*   **Path:** `agentvault_testing_utils.fixtures.mock_a2a_server`
*   **Purpose:** A pytest fixture that utilizes `respx` to set up mock HTTP endpoints simulating an A2A agent server and an OAuth token endpoint. It provides basic stateful handling for tasks and SSE events.
*   **Features:**
    *   Mocks `POST /a2a` endpoint, routing based on JSON-RPC `method`.
    *   Mocks `POST /token` endpoint for OAuth Client Credentials flow.
    *   Provides in-memory `task_store` (dict) and `sse_event_store` (dict) accessible via the fixture's return value, allowing tests to configure mock state and expected SSE events.
    *   Handles basic JSON-RPC request/response formatting and errors.
*   **Usage Example:**
    ```python
    import httpx
    import pytest
    from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
    from agentvault.models import TaskState, TaskStatusUpdateEvent # Example event

    @pytest.mark.asyncio
    async def test_api_interaction(mock_a2a_server: MockServerInfo):
        # Configure mock state before making the call
        task_id = "test-task-123"
        mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING}
        mock_a2a_server.sse_event_store[task_id] = [
            TaskStatusUpdateEvent(...) # Create event instances
        ]

        # Make calls using httpx or AgentVaultClient to mock_a2a_server.base_url
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_a2a_server.base_url}/a2a",
                json={
                    "jsonrpc": "2.0",
                    "method": "tasks/get",
                    "params": {"id": task_id},
                    "id": "req-1"
                }
            )
            assert response.status_code == 200
            assert response.json()["result"]["state"] == "WORKING"

        # Assertions on task_store or further interactions...
    ```

### Factories (`create_test_agent_card`)

*   **Path:** `agentvault_testing_utils.factories.create_test_agent_card`
*   **Purpose:** Creates `agentvault.models.AgentCard` Pydantic model instances with sensible default values, making it easy to generate valid test data. Allows overriding specific fields via keyword arguments.
*   **Usage Example:**
    ```python
    from agentvault_testing_utils.factories import create_test_agent_card

    # Default card
    card1 = create_test_agent_card()

    # Card with specific overrides
    card2 = create_test_agent_card(
        name="Specific Test Agent",
        humanReadableId="my-org/specific-agent",
        authSchemes=[{"scheme": "apiKey", "service_identifier": "specific-key"}]
    )
    ```

### Test Agents (`EchoAgent`)

*   **Path:** `agentvault_testing_utils.agents.EchoAgent`
*   **Purpose:** A simple implementation of `agentvault_server_sdk.BaseA2AAgent` that performs basic actions like echoing the input message via SSE and setting task states. Useful for testing the Server SDK's router (`create_a2a_router`) and basic A2A flows without needing a complex agent implementation.
*   **Usage Example:** See [Server SDK Example](../../examples/basic_a2a_server/README.md).

### Assertion Helpers (`assertions.py`)

*   **Path:** `agentvault_testing_utils.assertions`
*   **Purpose:** Provides helper functions to simplify assertions about A2A calls made during tests, whether using `respx` or `MockAgentVaultClient`.
*   **Key Functions:**
    *   `assert_a2a_call(mock_calls, method, params_contain=None, req_id=None)`: Asserts that at least one call matching the criteria exists in the `mock_calls` (list of `httpx.Request` or `MagicMock.call_args_list`). `params_contain` performs a subset check on the call's parameters.
    *   `assert_a2a_sequence(mock_calls, expected_sequence)`: Asserts that the sequence of parseable A2A calls matches the `expected_sequence` list of `(method, params_contain)` tuples.
