import pytest
import httpx
import respx
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, ANY
import click  # Import click for context mocking

# Import the CLI entrypoint and the specific command FUNCTION
from agentvault_cli.main import cli
from agentvault_cli.commands.discover import DEFAULT_REGISTRY_URL, discover_command  # Import the function

# Helper function for running async Click commands with proper context
async def run_click_command(command, mock_ctx=None, **kwargs):
    """
    Run an async Click command with proper context management.
    
    Args:
        command: The Click command to run
        mock_ctx: Optional mock context to get the exit function from
        **kwargs: Arguments to pass to the command callback
    
    Returns:
        The result of the command callback
    """
    # Create a real Click context
    ctx = click.Context(command)
    
    # Create a wrapper around exit to avoid actual exiting during tests
    original_exit = ctx.exit
    def exit_wrapper(code=0):
        # Record the call, but don't actually exit
        if mock_ctx is not None:
            mock_ctx.exit(code)
        return None
    
    # Replace exit with our wrapper
    ctx.exit = exit_wrapper
    
    # Use ctx.scope to properly manage the context stack
    with ctx:
        # Call the command callback directly
        return await command.callback(**kwargs)

# --- Fixtures ---

@pytest.fixture
def runner():
    # Still needed for sync tests if any, keep mix_stderr=True
    return CliRunner(mix_stderr=True)

@pytest.fixture
def mock_ctx() -> MagicMock:
    """Provides a mock Click context with a mocked exit method."""
    ctx = MagicMock(spec=click.Context)
    # Create a fresh mock for exit before each test
    ctx.exit = MagicMock()
    return ctx

# --- Test 'discover' ---

@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_table')
@patch('agentvault_cli.commands.discover.utils.display_info')
async def test_discover_success(mock_display_info, mock_display_table, mock_ctx: MagicMock, anyio_backend):
    """Test successful discovery with default parameters."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    mock_items = [
        {"id": "uuid-1", "name": "Agent One", "description": "Desc 1"},
        {"id": "uuid-2", "name": "Agent Two", "description": "Desc 2"},
    ]
    mock_pagination = {
        "total_items": 2, "limit": 25, "offset": 0,
        "total_pages": 1, "current_page": 1
    }
    mock_response_data = {"items": mock_items, "pagination": mock_pagination}
    route = respx.get(mock_url, params={'limit': 25, 'offset': 0, 'active_only': True}).mock(
        return_value=httpx.Response(200, json=mock_response_data)
    )

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=None,
        registry_url=DEFAULT_REGISTRY_URL,
        limit=25,
        offset=0
    )

    assert route.called, "Registry API route was not called."
    expected_table_data = [
        ['uuid-1', 'Agent One', 'Desc 1'],
        ['uuid-2', 'Agent Two', 'Desc 2']
    ]
    mock_display_table.assert_called_once_with(
        "Found Agents (Page 1)",
        ["ID", "Name", "Description"],
        expected_table_data
    )
    mock_display_info.assert_any_call(
        "\nShowing 2 items (offset 0) out of 2 total. Page 1 of 1."
    )
    # Check exit wasn't called with an error code
    assert not any(args[0] != 0 for args, _ in mock_ctx.exit.call_args_list)


@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_table')
@patch('agentvault_cli.commands.discover.utils.display_info')
async def test_discover_search_and_pagination(mock_display_info, mock_display_table, mock_ctx: MagicMock, anyio_backend):
    """Test discovery with search query and pagination."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    search_term = "weather"
    limit = 10
    offset = 10
    mock_items = [{"id": "uuid-weather", "name": "Weather Agent", "description": "Provides weather"}]
    mock_pagination = {"total_items": 11, "limit": limit, "offset": offset, "total_pages": 2, "current_page": 2}
    mock_response_data = {"items": mock_items, "pagination": mock_pagination}
    route = respx.get(
        mock_url,
        params={'limit': limit, 'offset': offset, 'active_only': True, 'search': search_term}
    ).mock(return_value=httpx.Response(200, json=mock_response_data))

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=search_term,
        registry_url=DEFAULT_REGISTRY_URL,
        limit=limit,
        offset=offset
    )

    assert route.called, "API route was not called with expected parameters"
    expected_table_data = [['uuid-weather', 'Weather Agent', 'Provides weather']]
    mock_display_table.assert_called_once_with(
        "Found Agents (Page 2)",
        ["ID", "Name", "Description"],
        expected_table_data
    )
    mock_display_info.assert_any_call(
        f"\nShowing 1 items (offset {offset}) out of 11 total. Page 2 of 2."
    )
    # Check exit wasn't called with an error code
    assert not any(args[0] != 0 for args, _ in mock_ctx.exit.call_args_list)


@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_info')
async def test_discover_custom_registry(mock_display_info, mock_ctx: MagicMock, anyio_backend):
    """Test discovery using a custom registry URL."""
    custom_registry = "https://my-registry.test"
    mock_url = f"{custom_registry}/api/v1/agent-cards"
    mock_response_data = {"items": [], "pagination": {"total_items": 0, "limit": 25, "offset": 0, "total_pages": 0, "current_page": 1}}
    route = respx.get(mock_url, params={'limit': 25, 'offset': 0, 'active_only': True}).mock(
        return_value=httpx.Response(200, json=mock_response_data)
    )

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=None,
        registry_url=custom_registry,
        limit=25,
        offset=0
    )

    assert route.called, "Custom registry API route was not called."
    mock_display_info.assert_any_call("No matching agents found.")
    # Check exit wasn't called with an error code
    assert not any(args[0] != 0 for args, _ in mock_ctx.exit.call_args_list)


@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_error')
async def test_discover_registry_error_404(mock_display_error, mock_ctx: MagicMock, anyio_backend):
    """Test discovery when registry returns 404."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    error_detail = "Specific Agent Not Found"
    respx.get(mock_url, params={'limit': 25, 'offset': 0, 'active_only': True}).mock(
        return_value=httpx.Response(404, json={"detail": error_detail})
    )

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=None,
        registry_url=DEFAULT_REGISTRY_URL,
        limit=25,
        offset=0
    )

    # Check that exit was called with error code 1
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)
    mock_display_error.assert_any_call("Registry API request failed (Status 404):")
    mock_display_error.assert_any_call(f"  Detail: {error_detail}")


@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_error')
async def test_discover_registry_error_500(mock_display_error, mock_ctx: MagicMock, anyio_backend):
    """Test discovery when registry returns 500."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    error_text = "Internal Server Error Occurred"
    respx.get(mock_url, params={'limit': 25, 'offset': 0, 'active_only': True}).mock(
        return_value=httpx.Response(500, text=error_text)
    )

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=None,
        registry_url=DEFAULT_REGISTRY_URL,
        limit=25,
        offset=0
    )

    # Check that exit was called with error code 1
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)
    
    # Check for specific messages in display_error calls
    error_msg1 = "Registry API request failed (Status 500):"
    assert any(args[0] == error_msg1 for args, _ in mock_display_error.call_args_list), \
        f"Error message '{error_msg1}' not found in display_error calls"
    
    error_msg2 = f"  Response: {error_text}"
    assert any(args[0] == error_msg2 for args, _ in mock_display_error.call_args_list), \
        f"Error message '{error_msg2}' not found in display_error calls"


@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_error')
async def test_discover_network_error(mock_display_error, mock_ctx: MagicMock, anyio_backend):
    """Test discovery with a network connection error."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    error_msg = "Connection refused"
    respx.get(mock_url, params={'limit': 25, 'offset': 0, 'active_only': True}).mock(
        side_effect=httpx.ConnectError(error_msg)
    )

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=None,
        registry_url=DEFAULT_REGISTRY_URL,
        limit=25,
        offset=0
    )

    # Check that exit was called with error code 1
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)
    
    # Check for specific message in display_error calls
    expected_msg = f"Network error connecting to registry at {DEFAULT_REGISTRY_URL}: {error_msg}"
    assert any(args[0] == expected_msg for args, _ in mock_display_error.call_args_list), \
        f"Error message '{expected_msg}' not found in display_error calls"


@pytest.mark.asyncio
@respx.mock
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_error')
async def test_discover_invalid_json_response(mock_display_error, mock_ctx: MagicMock, anyio_backend):
    """Test discovery when registry returns invalid JSON."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    respx.get(mock_url, params={'limit': 25, 'offset': 0, 'active_only': True}).mock(
        return_value=httpx.Response(200, text="{invalid json")
    )

    # Use the helper function instead of directly calling the callback
    await run_click_command(
        discover_command,
        mock_ctx=mock_ctx,
        search_query=None,
        registry_url=DEFAULT_REGISTRY_URL,
        limit=25,
        offset=0
    )

    # Check that exit was called with error code 1
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)
    
    # Check that any error message contains the expected string
    any_error_contains_text = any(
        "Failed to parse registry response" in args[0] 
        for args, _ in mock_display_error.call_args_list if isinstance(args[0], str)
    )
    assert any_error_contains_text, "No error message containing 'Failed to parse registry response' found"