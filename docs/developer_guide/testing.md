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
    *   **Purpose:** A mock implementation of `agentvault.client.AgentVaultClient`. Use this in tests for components that *use* the client library (like the CLI or potentially other agents) to simulate A2A interactions without making real network calls.
    *   **Features:**
        *   Configurable return values for async methods (e.g., `mock_client.initiate_task_return_value = "task-abc"`).
        *   Configurable side effects (exceptions) for async methods (e.g., `mock_client.get_task_status_side_effect = A2AConnectionError("Mock connection failed")`).
        *   Call recording via the `mock_client.call_recorder` attribute (an `unittest.mock.AsyncMock` instance). Use standard `assert_awaited_once_with`, `assert_has_calls`, etc. on this recorder.
        *   Supports async context management (`async with mock_client:`).
    *   **Example:**
        ```python
        import pytest
        from unittest.mock import call, ANY # Import ANY for flexible matching
        from agentvault_testing_utils.mocks import MockAgentVaultClient
        from agentvault.models import Task, TaskState # Assuming Task model exists
        from agentvault.exceptions import A2AConnectionError

        @pytest.mark.asyncio
        async def test_cli_run_logic(mocker): # Assuming pytest-mock 'mocker' fixture
            # --- Setup ---
            mock_client = MockAgentVaultClient()
            # Patch the location where AgentVaultClient is instantiated in the code under test
            mocker.patch('agentvault_cli.commands.run.AgentVaultClient', return_value=mock_client)

            # Configure mock behavior
            mock_client.initiate_task_return_value = "task-from-mock"
            # Create a mock Task object or use a real one if needed
            mock_task_result = MagicMock(spec=Task)
            mock_task_result.state = TaskState.COMPLETED
            mock_client.get_task_status_return_value = mock_task_result

            # --- Action ---
            # Execute the function or command that uses the AgentVaultClient
            # e.g., await run_cli_command_logic(...)

            # --- Assertions ---
            # Check initiate_task was called correctly
            mock_client.call_recorder.initiate_task.assert_awaited_once_with(
                agent_card=ANY, initial_message=ANY, key_manager=ANY,
                mcp_context=None, webhook_url=None # Check default args if needed
            )
            # Check get_task_status was called with the ID returned by initiate_task
            mock_client.call_recorder.get_task_status.assert_awaited_with(
                 agent_card=ANY, task_id="task-from-mock", key_manager=ANY
            )
        ```

### 2. Mock Server & Fixtures (`mock_server.py`, `fixtures.py`)

*   **`mock_a2a_server` (Pytest Fixture):**
    *   **Purpose:** Provides a more realistic testing environment by mocking the HTTP endpoints of an A2A agent server (`/a2a`) and its associated OAuth token endpoint (`/token`) using `respx`. Useful for testing the `AgentVaultClient` itself or components that make real HTTP requests to agents.
    *   **Features:**
        *   Sets up `respx` routes for `POST /a2a` and `POST /token` at a test URL.
        *   Handles basic JSON-RPC routing for standard A2A methods (`tasks/send`, `get`, `cancel`, `sendSubscribe`).
        *   Simulates basic task state via an in-memory `task_store` dictionary accessible from the fixture. You can pre-populate this store in your test.
        *   Simulates SSE streaming for `tasks/sendSubscribe` based on an `sse_event_store` list accessible from the fixture. You pre-populate this list with the `A2AEvent` objects you want the mock server to stream back.
        *   Provides the `base_url` of the mock server.
    *   **Return Type:** `MockServerInfo` (NamedTuple) with fields:
        *   `base_url` (str): The base URL of the mock server (e.g., `https://mock-a2a-agent.test`).
        *   `task_store` (Dict[str, Dict]): Dictionary mapping task IDs to their simple state dict (e.g., `{'state': TaskState.WORKING}`).
        *   `sse_event_store` (Dict[str, List[A2AEvent]]): Dictionary mapping task IDs to a list of `A2AEvent` objects to be yielded by the mock SSE stream.
    *   **Example:**
        ```python
        import pytest
        import httpx
        from agentvault_testing_utils.fixtures import mock_a2a_server, MockServerInfo
        # Import necessary models
        from agentvault.models import TaskState, TaskStatusUpdateEvent, Message, TextPart
        from agentvault.client import AgentVaultClient # Import the real client
        import datetime

        @pytest.mark.asyncio
        async def test_client_get_status_against_mock_server(mock_a2a_server: MockServerInfo, mocker):
            # --- Setup Mock Server State ---
            task_id = "live-test-task-get"
            # Pre-populate the task store the mock server will use
            mock_a2a_server.task_store[task_id] = {"state": TaskState.WORKING}

            # --- Action ---
            # Use the real AgentVaultClient against the mock server's URL
            mock_card = mocker.MagicMock() # Mock the card
            mock_card.url = f"{mock_a2a_server.base_url}/a2a"
            mock_card.auth_schemes = [] # Assume no auth for simplicity

            async with AgentVaultClient() as client:
                 # This call will hit the respx route set up by the fixture
                 task_details = await client.get_task_status(
                     agent_card=mock_card,
                     task_id=task_id,
                     key_manager=mocker.MagicMock() # Mock key manager
                 )

            # --- Assertions ---
            assert task_details.id == task_id
            assert task_details.state == TaskState.WORKING # Check state returned by mock
        ```

*   **`setup_mock_a2a_routes`:** The underlying function used by the `mock_a2a_server` fixture to configure `respx` routes. Can be used directly for more complex or custom mock server setups outside the fixture.
*   **JSON-RPC Helpers:** `create_jsonrpc_success_response`, `create_jsonrpc_error_response` for constructing standard JSON-RPC response dictionaries in custom mock handlers.

### 3. Factories (`factories.py`)

*   **`create_test_agent_card(**overrides)`**:
    *   **Purpose:** Generates `agentvault.models.AgentCard` Pydantic model instances with sensible default values. Simplifies creating valid test data for agent cards.
    *   **Features:** Accepts keyword arguments to override any top-level or nested field in the default card structure (uses deep merging for nested dicts). Performs validation using the actual `AgentCard` model.
    *   **Example:**
        ```python
        from agentvault_testing_utils.factories import create_test_agent_card

        # Create a card with default values
        default_card = create_test_agent_card()

        # Create a card overriding name and adding an OAuth scheme
        custom_card = create_test_agent_card(
            name="My Custom OAuth Agent",
            authSchemes=[ # Overwrites the default 'none' scheme
                {"scheme": "oauth2", "tokenUrl": "https://my-agent.test/token"}
            ],
            tags=["custom", "oauth"] # Overwrites default tags
        )
        ```

### 4. Test Agents (`agents.py`)

*   **`EchoAgent`**:
    *   **Purpose:** A minimal, functional implementation of `agentvault_server_sdk.BaseA2AAgent`. It uses an `InMemoryTaskStore` to manage state, echoes the first message content back via SSE notification, and transitions through basic states (Submitted -> Working -> Completed).
    *   **Use Case:** Ideal for testing the Server SDK's `create_a2a_router`, basic A2A client interactions, and SSE streaming logic without needing a complex real agent implementation. Useful for end-to-end tests of the client library or CLI against a basic functional agent.
    *   **Example (Testing SDK Router):** See the [Server SDK Developer Guide](server_sdk.md) or the [Basic A2A Server Example](../examples.md).

### 5. Assertion Helpers (`assertions.py`)

*   **Purpose:** Provide convenient functions for asserting that specific A2A JSON-RPC calls were made, simplifying tests that interact with `MockAgentVaultClient` or `respx`.
*   **Key Functions:**
    *   **`assert_a2a_call(mock_calls, method, params_contain=None, req_id=None)`**: Checks if *any* call in the provided list (`httpx.Request` list from `respx.calls` or `MagicMock.call_args_list` from `MockAgentVaultClient.call_recorder`) matches the specified JSON-RPC `method`, optional `req_id`, and optionally contains the key-value pairs in `params_contain` within its `params` object (performs a subset check).
    *   **`assert_a2a_sequence(mock_calls, expected_sequence)`**: Checks if the sequence of *parseable* A2A calls matches the `expected_sequence` (a list of `(method, params_contain)` tuples). Ignores non-JSON-RPC calls in the list.
    *   **Example:**
        ```python
        from agentvault_testing_utils.assertions import assert_a2a_call, assert_a2a_sequence
        from unittest.mock import call # For sequence assertion with MagicMock

        # --- Using MockAgentVaultClient ---
        # await mock_client.initiate_task(...)
        # await mock_client.get_task_status(task_id="task-123", ...)

        # Assert a specific call was made (anywhere in the list)
        assert_a2a_call(
            mock_client.call_recorder.call_args_list, # Pass the call list
            method="tasks/get",
            params_contain={"id": "task-123"}
        )

        # Assert the exact sequence of calls
        expected_seq = [
            ("initiate_task", None), # Use the Python method name for MagicMock recorder
            ("get_task_status", {"task_id": "task-123"}) # Use Python param names
        ]
        # Note: assert_a2a_sequence expects JSON-RPC method names in the sequence definition
        # Adjust if using MagicMock recorder directly vs parsing httpx requests.
        # Example below assumes parsing logic handles method name mapping if needed.
        expected_rpc_seq = [
             ("tasks/send", None), # Assuming initiate_task maps to tasks/send
             ("tasks/get", {"id": "task-123"})
        ]
        # assert_a2a_sequence(mock_client.call_recorder.call_args_list, expected_rpc_seq)


        # --- Using respx ---
        # with respx.mock:
        #     # setup routes...
        #     # await http_client.post(url, json=payload1)
        #     # await http_client.post(url, json=payload2)

        # Assert a specific call was made
        assert_a2a_call(
            respx.calls, # Pass the list of httpx.Request objects
            method="tasks/send",
            params_contain={"message": {"role": "user"}}
        )

        # Assert the sequence
        expected_respx_seq = [
            ("tasks/send", {"id": None}),
            ("tasks/get", {"id": "task-abc"})
        ]
        assert_a2a_sequence(respx.calls, expected_respx_seq)
        ```
