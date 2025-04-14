"""
Pytest fixtures for AgentVault testing.
"""

import pytest
import respx
# --- MODIFIED: Import NamedTuple, List, Dict, Any ---
from typing import Dict, Any, List, NamedTuple
# --- END MODIFIED ---


# Import the setup function from the mock server module
from .mock_server import setup_mock_a2a_routes

# Import core types for type hints with fallback
try:
    from agentvault.models import A2AEvent
    _MODELS_AVAILABLE = True
except ImportError:
    A2AEvent = Any # type: ignore
    _MODELS_AVAILABLE = False


# --- MODIFIED: Define NamedTuple ---
class MockServerInfo(NamedTuple):
    """Information returned by the mock_a2a_server fixture."""
    base_url: str
    task_store: Dict[str, Dict] # task_id -> dict representing task state
    sse_event_store: Dict[str, List[A2AEvent]] # task_id -> list of events to yield
# --- END MODIFIED ---


@pytest.fixture
def mock_a2a_server(respx_mock: respx.mock) -> MockServerInfo:
    """
    Pytest fixture that sets up mock A2A and OAuth token endpoints using respx.
    Provides access to in-memory stores for task state and SSE events.

    Yields:
        MockServerInfo: An object containing the base_url, task_store,
                        and sse_event_store used by the mock server, allowing
                        tests to inspect or modify mock state.
    """
    base_url = "https://mock-a2a-agent.test" # Default base URL for the mock
    # --- MODIFIED: Create stores locally ---
    task_store: Dict[str, Dict] = {} # In-memory store for basic task state
    sse_event_store: Dict[str, List[A2AEvent]] = {} # Store events to be streamed
    # --- END MODIFIED ---

    # Setup the default routes using the imported function
    # --- MODIFIED: Pass stores to setup function ---
    setup_mock_a2a_routes(
        mock_router=respx_mock,
        base_url=base_url,
        task_store=task_store,
        sse_event_store=sse_event_store
    )
    # --- END MODIFIED ---

    # Yield the necessary info for tests to interact with the mock setup
    yield MockServerInfo(
        base_url=base_url,
        task_store=task_store,
        sse_event_store=sse_event_store
    )

    # Teardown is handled automatically by respx_mock fixture scope
