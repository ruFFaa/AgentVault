import pytest
import httpx
import respx
from click.testing import CliRunner

# Import the CLI entrypoint and the specific command
from agentvault_cli.main import cli
from agentvault_cli.commands.discover import DEFAULT_REGISTRY_URL

# --- Fixtures ---

@pytest.fixture
def runner():
    return CliRunner()

# --- Test 'discover' ---

@pytest.mark.asyncio
@respx.mock
async def test_discover_success(runner: CliRunner):
    """Test successful discovery with default parameters."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    mock_response_data = {
        "items": [
            {"id": "uuid-1", "name": "Agent One", "description": "Desc 1"},
            {"id": "uuid-2", "name": "Agent Two", "description": "Desc 2"},
        ],
        "pagination": {
            "total_items": 2, "limit": 25, "offset": 0,
            "total_pages": 1, "current_page": 1
        }
    }
    respx.get(mock_url).mock(return_value=httpx.Response(200, json=mock_response_data))

    result = await runner.invoke_async(cli, ['discover']) # Use invoke_async

    assert result.exit_code == 0
    assert "Found Agents" in result.output
    assert "uuid-1" in result.output
    assert "Agent One" in result.output
    assert "Desc 1" in result.output
    assert "uuid-2" in result.output
    assert "Agent Two" in result.output
    assert "Desc 2" in result.output
    assert "Showing 2 items" in result.output
    assert "Page 1 of 1" in result.output

@pytest.mark.asyncio
@respx.mock
async def test_discover_search_and_pagination(runner: CliRunner):
    """Test discovery with search query and pagination."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    search_term = "weather"
    limit = 10
    offset = 10
    mock_response_data = {
        "items": [{"id": "uuid-weather", "name": "Weather Agent", "description": "Provides weather"}],
        "pagination": {"total_items": 11, "limit": limit, "offset": offset, "total_pages": 2, "current_page": 2}
    }
    # Mock the specific URL with expected query parameters
    route = respx.get(
        mock_url,
        params={'limit': limit, 'offset': offset, 'active_only': True, 'search': search_term}
    ).mock(return_value=httpx.Response(200, json=mock_response_data))

    result = await runner.invoke_async(cli, [
        'discover', search_term, '--limit', str(limit), '--offset', str(offset)
    ])

    assert result.exit_code == 0
    assert route.called, "API route was not called with expected parameters"
    assert "Weather Agent" in result.output
    assert "Showing 1 items" in result.output
    assert f"offset {offset}" in result.output
    assert f"Page 2 of 2" in result.output
    assert "Hint: Use '--offset 20'" not in result.output # Should not show hint on last page

@pytest.mark.asyncio
@respx.mock
async def test_discover_custom_registry(runner: CliRunner):
    """Test discovery using a custom registry URL."""
    custom_registry = "https://my-registry.test"
    mock_url = f"{custom_registry}/api/v1/agent-cards"
    mock_response_data = {"items": [], "pagination": {"total_items": 0, "limit": 25, "offset": 0, "total_pages": 0, "current_page": 1}}
    route = respx.get(mock_url).mock(return_value=httpx.Response(200, json=mock_response_data))

    result = await runner.invoke_async(cli, ['discover', '--registry', custom_registry])

    assert result.exit_code == 0
    assert route.called
    assert "No matching agents found." in result.output

@pytest.mark.asyncio
@respx.mock
async def test_discover_registry_error_404(runner: CliRunner):
    """Test discovery when registry returns 404."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    respx.get(mock_url).mock(return_value=httpx.Response(404, json={"detail": "Not Found"}))

    result = await runner.invoke_async(cli, ['discover'])

    assert result.exit_code == 1
    assert "ERROR: Registry API request failed (Status 404)" in result.output
    assert "Detail: Not Found" in result.output

@pytest.mark.asyncio
@respx.mock
async def test_discover_registry_error_500(runner: CliRunner):
    """Test discovery when registry returns 500."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    respx.get(mock_url).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    result = await runner.invoke_async(cli, ['discover'])

    assert result.exit_code == 1
    assert "ERROR: Registry API request failed (Status 500)" in result.output
    assert "Response: Internal Server Error" in result.output # Shows raw text on non-JSON

@pytest.mark.asyncio
@respx.mock
async def test_discover_network_error(runner: CliRunner):
    """Test discovery with a network connection error."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    respx.get(mock_url).mock(side_effect=httpx.ConnectError("Connection refused"))

    result = await runner.invoke_async(cli, ['discover'])

    assert result.exit_code == 1
    assert "ERROR: Network error connecting to registry" in result.output
    assert "Connection refused" in result.output

@pytest.mark.asyncio
@respx.mock
async def test_discover_invalid_json_response(runner: CliRunner):
    """Test discovery when registry returns invalid JSON."""
    mock_url = f"{DEFAULT_REGISTRY_URL}/api/v1/agent-cards"
    respx.get(mock_url).mock(return_value=httpx.Response(200, text="{invalid json"))

    result = await runner.invoke_async(cli, ['discover'])

    assert result.exit_code == 1
    assert "ERROR: Failed to parse registry response" in result.output
