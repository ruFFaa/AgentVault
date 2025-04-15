# Developer Guide: Testing Utilities (`agentvault-testing-utils`)

The `agentvault-testing-utils` package is an internal development tool providing shared mocks, pytest fixtures, data factories, and helper functions. Its purpose is to streamline and standardize testing across the different AgentVault components (`agentvault_library`, `agentvault_cli`, `agentvault_registry`, `agentvault_server_sdk`).

**Note:** This package is **not intended for end-users** or for distribution on PyPI. It's used within the AgentVault monorepo's development workflow.

## Installation

This package is installed as a development dependency when setting up the main project environment using Poetry:

```bash
# From the monorepo root (AgentVault/)
poetry install --with dev
```

## Provided Utilities

### 1. Mocks (`mocks.py`)

*   **`MockAgentVaultClient`**:
    *   **Purpose:** A mock implementation of `agentvault.client.AgentVaultClient`. Use this in tests for components that *use* the client library (like the CLI or potentially other agents) to simulate A2A interactions without network calls.
    *   **Features:**
        *   Configurable return values for async methods (e.g., `initiate_task_return_value`).
        *   Configurable side effects (exceptions) for async methods (e.g., `get_task_status_side_effect = A2AConnectionError(...)`).
        *   Call recording via the `call_recorder` attribute (an `unittest.mock.AsyncMock` instance).
        *   Supports async context management (`async with`).
    *   **Example:**
        ```python
        import pytest
        from agentvault_testing_utils.mocks import MockAgentVaultClient
        from agentvault.models import Task, TaskState
        from agentvault.exceptions import A2AConnectionError
        from unittest.mock import call

        @pytest.mark.asyncio
        async def test_cli_run_logic(mocker): # Assuming mocker fixture
            mock_client = MockAgentVaultClient()
            # Patch the client instantiation in the module under test
            mocker.patch('agentvault_cli.commands.run.av_client.AgentVaultClient', return_value=mock_client)

            # Configure mock behavior
            mock_client.initiate_task_return_value = "task-from-mock"
            mock_task_result = Task(...) # Create or mock a Task object
            mock_client.get_task_status_return_value = mock_task_result

            # --- Run the CLI command or function under test ---
            # result = await run_cli_command(...)

            # --- Assert interactions with the mock client ---
            mock_client.call_recorder.initiate_task.assert_awaited_once()
            mock_client.call_recorder.get_task_status.assert_awaited_with(
                 agent_card=ANY, task_id="task-from-mock", key_manager=ANY
            )
        ```

### 2. Mock Server & Fixtures (`mock_server.py`, `fixtures.py`)

*   **`mock_a2a_server` (Pytest Fixture):**
    *   **Purpose:** Provides a more realistic testing environment by mocking the HTTP endpoints of an A2A agent server and its associated OAuth token endpoint using `respx`. Useful for testing the `AgentVaultClient` itself or components that make real HTTP requests.
    *   **Features:**
        *   Sets up `respx` routes for `POST /a2a` and `POST /token`.
        *   Handles basic JSON-RPC routing (`tasks/send`, `get`, `cancel`, `sendSubscribe`).
        *   Simulates basic task state via an in-memory `task_store` dictionary accessible from the fixture.
        *   Simulates SSE streaming for `tasks/sendSubscribe` based on an `sse_event_store` dictionary accessible from the fixture.
        *   Provides the `base_url` of the mock server.
    *   **Return Type:** `MockServerInfo` (NamedTuple) with fields `base_url`, `task_store`, `sse_event_store`.
    *   **Example:**
        ```python
        import pytest
        import httpx
        from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
        from agentvault.models import TaskState, TaskStatusUpdateEvent # Example event
        import datetime

        @pytest.mark.asyncio
        async def test_client_against_mock_server(mock_a2a_server: MockServerInfo):
            # Configure the mock server's state BEFORE making the call
            task_id = "live-test-task"
            mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING}
            mock_a2a_server.sse_event_store[task_id] = [
                TaskStatusUpdateEvent(taskId=task_id, state=TaskState.COMPLETED, timestamp=datetime.datetime.now(datetime.timezone.utc))
            ]

            # Use httpx or AgentVaultClient to interact with mock_a2a_server.base_url
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{mock_a2a_server.base_url}/a2a", json={...})
                # ... assertions ...

            # Check if the mock server state was updated (e.g., after a cancel call)
            # assert mock_a2a_server.task_store[task_id]["state"] == TaskState.CANCELED
        ```
*   **`setup_mock_a2a_routes`:** The underlying function used by the fixture to configure `respx`. Can be used directly for custom setups.
*   **JSON-RPC Helpers:** `create_jsonrpc_success_response`, `create_jsonrpc_error_response`.

### 3. Factories (`factories.py`)

*   **`create_test_agent_card(**overrides)`**:
    *   **Purpose:** Generates `agentvault.models.AgentCard` Pydantic model instances with sensible default values. Simplifies creating valid test data.
    *   **Features:** Accepts keyword arguments to override any top-level or nested field in the default card structure. Performs validation using the actual `AgentCard` model.
    *   **Example:**
        ```python
        from agentvault_testing_utils.factories import create_test_agent_card

        default_card = create_test_agent_card()
        custom_card = create_test_agent_card(
            name="OAuth Agent",
            authSchemes=[{"scheme": "oauth2", "tokenUrl": "https://test.com/token"}]
        )
        ```

### 4. Test Agents (`agents.py`)

*   **`EchoAgent`**:
    *   **Purpose:** A minimal, functional implementation of `agentvault_server_sdk.BaseA2AAgent`. It stores received messages in memory, echoes the first message content back via SSE, and transitions through basic states (Submitted -> Working -> Completed).
    *   **Use Case:** Ideal for testing the Server SDK's `create_a2a_router`, basic A2A client interactions, and SSE streaming logic without needing a complex real agent.
    *   **Example:** See the Server SDK Developer Guide or the `basic_a2a_server` example.

### 5. Assertion Helpers (`assertions.py`)

*   **Purpose:** Provide convenient functions for asserting that specific A2A calls were made, simplifying tests that interact with `MockAgentVaultClient` or `respx`.
*   **Key Functions:**
    *   `assert_a2a_call(mock_calls, method, params_contain=None, req_id=None)`: Checks if *any* call in the provided list (`httpx.Request` list or `MagicMock.call_args_list`) matches the specified JSON-RPC `method`, optional `req_id`, and optionally contains the key-value pairs in `params_contain` within its `params` object.
    *   `assert_a2a_sequence(mock_calls, expected_sequence)`: Checks if the sequence of *parseable* A2A calls matches the `expected_sequence` (a list of `(method, params_contain)` tuples).
    *   **Example:**
        ```python
        from agentvault_testing_utils.assertions import assert_a2a_call, assert_a2a_sequence
        from unittest.mock import call # For sequence assertion

        # Using MockAgentVaultClient
        # await mock_client.initiate_task(...)
        # await mock_client.get_task_status(...)
        # assert_a2a_call(mock_client.call_recorder, method="tasks/get", params_contain={"id": "task-id"})
        # expected_seq = [("initiate_task", None), ("get_task_status", {"task_id": "task-id"})] # Note: Uses method name for mock recorder
        # assert_a2a_sequence(mock_client.call_recorder, expected_seq)

        # Using respx
        # with respx.mock:
        #     # setup routes...
        #     # make httpx calls...
        # assert_a2a_call(respx.calls, method="tasks/send", params_contain={"message": {"role": "user"}})
        ```
