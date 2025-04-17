import pytest
import httpx
import json
# --- ADDED: Import pytest-httpx ---
from pytest_httpx import HTTPXMock
# --- END ADDED ---
import re
# --- REMOVED: CliRunner ---
# from click.testing import CliRunner
# --- END REMOVED ---
from typing import Optional, Dict, Any
# --- MODIFIED: Import patch from unittest.mock, keep AsyncMock/MagicMock if needed for utils ---
from unittest.mock import patch, MagicMock, ANY, AsyncMock
# --- END MODIFIED ---
import click
import logging

# Import the CLI entrypoint and command module
from agentvault_cli.main import cli
# --- MODIFIED: Import the command function directly ---
from agentvault_cli.commands import discover
# --- ADDED: Direct import of command function ---
from agentvault_cli.commands.discover import discover_command
# --- END ADDED ---

logger = logging.getLogger(__name__)


# --- Fixtures ---
# --- REMOVED: runner fixture ---

# --- Test 'discover' ---

@pytest.mark.asyncio
# Patch utils where they are imported/used in the command module
@patch('agentvault_cli.commands.discover.utils.display_table')
@patch('agentvault_cli.commands.discover.utils.display_info')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_success(mock_display_info, mock_display_table, httpx_mock: HTTPXMock): # Removed runner
    """Test successful discovery with default parameters."""
    mock_items = [{"id": "uuid-1", "name": "Agent One", "description": "Desc 1"}, {"id": "uuid-2", "name": "Agent Two", "description": "Desc 2"}]
    mock_pagination = {"total_items": 2, "limit": 25, "offset": 0, "total_pages": 1, "current_page": 1}
    mock_response_data = {"items": mock_items, "pagination": mock_pagination}

    # --- MODIFIED: Use httpx_mock ---
    expected_url = f"{discover.DEFAULT_REGISTRY_URL}/api/v1/agent-cards?limit=25&offset=0&active_only=true"
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200
    )
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    try:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED: Implicitly passed by @pass_context
                search_query=None,
                registry_url=discover.DEFAULT_REGISTRY_URL,
                limit=25,
                offset=0
                # active_only is handled internally by the command logic based on default
            )
    except click.exceptions.Exit as e:
        pytest.fail(f"Command unexpectedly exited with code {e.exit_code}")
    # --- END MODIFIED ---

    # Assertions
    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"

    expected_table_data = [['uuid-1', 'Agent One', 'Desc 1'], ['uuid-2', 'Agent Two', 'Desc 2']]
    mock_display_table.assert_called_once_with("Found Agents (Page 1)", ["ID", "Name", "Description"], expected_table_data)
    mock_display_info.assert_any_call("\nShowing 2 items (offset 0) out of 2 total. Page 1 of 1.")


@pytest.mark.asyncio
@patch('agentvault_cli.commands.discover.utils.display_table')
@patch('agentvault_cli.commands.discover.utils.display_info')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_search_and_pagination(mock_display_info, mock_display_table, httpx_mock: HTTPXMock): # Removed runner
    """Test discovery with search query and pagination."""
    search_term = "weather"
    limit = 10
    offset = 10
    mock_items = [{"id": "uuid-weather", "name": "Weather Agent", "description": "Provides weather"}]
    mock_pagination = {"total_items": 11, "limit": limit, "offset": offset, "total_pages": 2, "current_page": 2}
    mock_response_data = {"items": mock_items, "pagination": mock_pagination}

    # --- MODIFIED: Use httpx_mock with precise URL ---
    expected_url = f"{discover.DEFAULT_REGISTRY_URL}/api/v1/agent-cards?limit={limit}&offset={offset}&active_only=true&search={search_term}"
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200
    )
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    try:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED
                search_query=search_term,
                registry_url=discover.DEFAULT_REGISTRY_URL,
                limit=limit,
                offset=offset
            )
    except click.exceptions.Exit as e:
        pytest.fail(f"Command unexpectedly exited with code {e.exit_code}")
    # --- END MODIFIED ---

    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"

    expected_table_data = [['uuid-weather', 'Weather Agent', 'Provides weather']]
    mock_display_table.assert_called_once_with("Found Agents (Page 2)", ["ID", "Name", "Description"], expected_table_data)
    mock_display_info.assert_any_call(f"\nShowing 1 items (offset {offset}) out of 11 total. Page 2 of 2.")


@pytest.mark.asyncio
@patch('agentvault_cli.commands.discover.utils.display_info')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_custom_registry(mock_display_info, httpx_mock: HTTPXMock): # Removed runner
    """Test discovery using a custom registry URL."""
    custom_registry = "https://my-registry.test"
    mock_response_data = {"items": [], "pagination": {"total_items": 0, "limit": 25, "offset": 0, "total_pages": 0, "current_page": 1}}

    # --- MODIFIED: Use httpx_mock with precise URL ---
    expected_url = f"{custom_registry}/api/v1/agent-cards?limit=25&offset=0&active_only=true"
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200
    )
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    try:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED
                search_query=None,
                registry_url=custom_registry, # Pass custom registry
                limit=25,
                offset=0
            )
    except click.exceptions.Exit as e:
        pytest.fail(f"Command unexpectedly exited with code {e.exit_code}")
    # --- END MODIFIED ---

    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"
    mock_display_info.assert_any_call("No matching agents found.")


@pytest.mark.asyncio
@patch('agentvault_cli.commands.discover.utils.display_error')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_registry_error_404(mock_display_error, httpx_mock: HTTPXMock): # Removed runner
    """Test discovery when registry returns 404."""
    error_detail = "Specific Agent Not Found"

    # --- MODIFIED: Use httpx_mock ---
    expected_url = f"{discover.DEFAULT_REGISTRY_URL}/api/v1/agent-cards?limit=25&offset=0&active_only=true"
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json={"detail": error_detail},
        status_code=404
    )
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation with error check within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    with pytest.raises(click.exceptions.Exit) as excinfo:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED
                search_query=None,
                registry_url=discover.DEFAULT_REGISTRY_URL,
                limit=25,
                offset=0
            )
    assert excinfo.value.exit_code == 1
    # --- END MODIFIED ---

    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"
    mock_display_error.assert_any_call("Registry API request failed (Status 404):")
    mock_display_error.assert_any_call(f"  Detail: {error_detail}")


@pytest.mark.asyncio
@patch('agentvault_cli.commands.discover.utils.display_error')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_registry_error_500(mock_display_error, httpx_mock: HTTPXMock): # Removed runner
    """Test discovery when registry returns 500."""
    error_text = "Internal Server Error Occurred"

    # --- MODIFIED: Use httpx_mock ---
    expected_url = f"{discover.DEFAULT_REGISTRY_URL}/api/v1/agent-cards?limit=25&offset=0&active_only=true"
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        text=error_text,
        status_code=500
    )
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation with error check within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    with pytest.raises(click.exceptions.Exit) as excinfo:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED
                search_query=None,
                registry_url=discover.DEFAULT_REGISTRY_URL,
                limit=25,
                offset=0
            )
    assert excinfo.value.exit_code == 1
    # --- END MODIFIED ---

    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"
    mock_display_error.assert_any_call("Registry API request failed (Status 500):")
    mock_display_error.assert_any_call(f"  Response: {error_text}")


@pytest.mark.asyncio
@patch('agentvault_cli.commands.discover.utils.display_error')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_network_error(mock_display_error, httpx_mock: HTTPXMock): # Removed runner
    """Test discovery with a network connection error."""
    error_msg = "Connection refused"

    # --- MODIFIED: Use httpx_mock ---
    expected_url = f"{discover.DEFAULT_REGISTRY_URL}/api/v1/agent-cards?limit=25&offset=0&active_only=true"
    httpx_mock.add_exception(httpx.ConnectError(error_msg), url=expected_url, method="GET")
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation with error check within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    with pytest.raises(click.exceptions.Exit) as excinfo:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED
                search_query=None,
                registry_url=discover.DEFAULT_REGISTRY_URL,
                limit=25,
                offset=0
            )
    assert excinfo.value.exit_code == 1
    # --- END MODIFIED ---

    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"
    expected_msg = f"Network error connecting to registry at {discover.DEFAULT_REGISTRY_URL}: {error_msg}"
    mock_display_error.assert_any_call(expected_msg)


@pytest.mark.asyncio
@patch('agentvault_cli.commands.discover.utils.display_error')
# --- REMOVED @patch for httpx.AsyncClient ---
async def test_discover_invalid_json_response(mock_display_error, httpx_mock: HTTPXMock): # Removed runner
    """Test discovery when registry returns invalid JSON."""

    # --- MODIFIED: Use httpx_mock ---
    expected_url = f"{discover.DEFAULT_REGISTRY_URL}/api/v1/agent-cards?limit=25&offset=0&active_only=true"
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        text="{invalid json", # Return invalid text
        status_code=200
    )
    # --- END MODIFIED ---

    # --- MODIFIED: Direct callback invocation with error check within ctx.scope(), removed explicit ctx=ctx ---
    ctx = click.Context(discover_command)
    with pytest.raises(click.exceptions.Exit) as excinfo:
        with ctx.scope(): # Enter context scope
            await discover_command.callback(
                # ctx=ctx, # REMOVED
                search_query=None,
                registry_url=discover.DEFAULT_REGISTRY_URL,
                limit=25,
                offset=0
            )
    assert excinfo.value.exit_code == 1
    # --- END MODIFIED ---

    request = httpx_mock.get_request(url=expected_url, method="GET")
    assert request is not None, "Expected HTTP request was not made"
    # Check if *any* error call contains the expected text
    error_found = False
    for call_args, _ in mock_display_error.call_args_list:
        # Check if call_args is not None and is indexable
        if call_args and len(call_args) > 0 and isinstance(call_args[0], str):
            if "Failed to parse registry response" in call_args[0]:
                error_found = True
                break
    assert error_found, "Expected error message 'Failed to parse registry response' not found in calls."
