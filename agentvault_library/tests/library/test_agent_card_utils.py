import pytest
import httpx
# --- MODIFIED: Import respx ---
import respx
# --- END MODIFIED ---
import json
import pathlib
from unittest import mock

# Import functions and exceptions to test
from agentvault.agent_card_utils import (
    parse_agent_card_from_dict,
    load_agent_card_from_file,
    fetch_agent_card_from_url,
)
from agentvault.exceptions import (
    AgentCardError,
    AgentCardValidationError,
    AgentCardFetchError,
)
from agentvault.models import AgentCard # Assuming AgentCard is exposed via models/__init__

# --- Fixtures ---

@pytest.fixture
def valid_card_data() -> dict:
    """Provides a dictionary representing a valid Agent Card."""
    # Based on the AgentCard model structure
    return {
        "schemaVersion": "1.0",
        "humanReadableId": "test-org/test-agent",
        "agentVersion": "0.1.0",
        "name": "Test Agent",
        "description": "An agent for testing purposes.",
        "url": "https://example.com/a2a",
        "provider": {
            "name": "Test Org",
            "url": "https://example.com/provider",
            "support_contact": "support@example.com"
        },
        "capabilities": {
            "a2aVersion": "1.0",
            "mcpVersion": "0.5",
            "supportedMessageParts": ["text", "data"]
        },
        "authSchemes": [
            {
                "scheme": "apiKey",
                "description": "Use X-Api-Key header.",
                "service_identifier": "test-agent-key"
            }
        ],
        "skills": [
            {
                "id": "test-skill-1",
                "name": "Test Skill",
                "description": "Performs a test action."
            }
        ],
        "tags": ["test", "example"],
        "privacyPolicyUrl": "https://example.com/privacy",
        "termsOfServiceUrl": "https://example.com/terms",
        "iconUrl": "https://example.com/icon.png",
        "lastUpdated": "2024-01-01T12:00:00Z"
    }

# --- FIX: Request valid_card_data as argument ---
@pytest.fixture
def invalid_card_data_missing_field(valid_card_data: dict) -> dict:
    """Provides invalid card data (missing required field 'name')."""
    data = valid_card_data.copy() # Use the injected fixture data
    del data["name"]
    return data

# --- FIX: Request valid_card_data as argument ---
@pytest.fixture
def invalid_card_data_wrong_type(valid_card_data: dict) -> dict:
    """Provides invalid card data (wrong type for 'url')."""
    data = valid_card_data.copy() # Use the injected fixture data
    data["url"] = 12345 # Invalid type
    return data

# --- Tests for parse_agent_card_from_dict ---

def test_parse_agent_card_from_dict_success(valid_card_data):
    """Test successful parsing of valid dictionary data."""
    agent_card = parse_agent_card_from_dict(valid_card_data)
    assert isinstance(agent_card, AgentCard)
    assert agent_card.human_readable_id == "test-org/test-agent"
    assert agent_card.provider.name == "Test Org"
    assert len(agent_card.auth_schemes) == 1
    assert agent_card.auth_schemes[0].scheme == "apiKey"

def test_parse_agent_card_from_dict_validation_error_missing(invalid_card_data_missing_field):
    """Test raising AgentCardValidationError for missing required fields."""
    with pytest.raises(AgentCardValidationError) as excinfo:
        parse_agent_card_from_dict(invalid_card_data_missing_field)
    assert "Field required" in str(excinfo.value)
    assert "name" in str(excinfo.value) # Check if the field name is mentioned

def test_parse_agent_card_from_dict_validation_error_type(invalid_card_data_wrong_type):
    """Test raising AgentCardValidationError for incorrect field types."""
    with pytest.raises(AgentCardValidationError) as excinfo:
        parse_agent_card_from_dict(invalid_card_data_wrong_type)
    # --- FIX: Update assertion to match actual Pydantic v2 error ---
    assert "URL input should be a string or URL" in str(excinfo.value)

def test_parse_agent_card_from_dict_unexpected_error():
    """Test raising AgentCardError for unexpected errors during parsing."""
    # Mock the model_validate method to raise an unexpected error
    with mock.patch('agentvault.models.agent_card.AgentCard.model_validate', side_effect=TypeError("Unexpected parsing issue")):
        with pytest.raises(AgentCardError) as excinfo:
            parse_agent_card_from_dict({}) # Pass dummy data
        assert "An unexpected error occurred parsing the Agent Card data" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, TypeError)

# --- Tests for load_agent_card_from_file ---

# --- FIX: Mock Path object methods directly ---
@mock.patch("pathlib.Path.exists")
@mock.patch("pathlib.Path.is_file")
@mock.patch("pathlib.Path.read_text")
def test_load_agent_card_from_file_success(mock_read_text, mock_is_file, mock_exists, valid_card_data):
    """Test successful loading from a valid JSON file."""
    mock_exists.return_value = True
    mock_is_file.return_value = True
    mock_read_text.return_value = json.dumps(valid_card_data)

    file_path = pathlib.Path("dummy/path/agent.json")
    agent_card = load_agent_card_from_file(file_path)

    mock_read_text.assert_called_once_with(encoding='utf-8')
    assert isinstance(agent_card, AgentCard)
    assert agent_card.human_readable_id == "test-org/test-agent"

@mock.patch("pathlib.Path.exists")
def test_load_agent_card_from_file_not_found(mock_exists):
    """Test raising AgentCardError if file does not exist."""
    mock_exists.return_value = False
    file_path = pathlib.Path("non/existent/file.json")
    with pytest.raises(AgentCardError, match="Agent Card file not found"):
        load_agent_card_from_file(file_path)

@mock.patch("pathlib.Path.exists")
@mock.patch("pathlib.Path.is_file")
def test_load_agent_card_from_file_is_directory(mock_is_file, mock_exists):
    """Test raising AgentCardError if path is a directory."""
    mock_exists.return_value = True
    mock_is_file.return_value = False
    file_path = pathlib.Path("a/directory")
    with pytest.raises(AgentCardError, match="Path exists but is not a file"):
        load_agent_card_from_file(file_path)

# --- FIX: Mock Path object methods directly ---
@mock.patch("pathlib.Path.exists")
@mock.patch("pathlib.Path.is_file")
@mock.patch("pathlib.Path.read_text")
def test_load_agent_card_from_file_io_error(mock_read_text, mock_is_file, mock_exists):
    """Test raising AgentCardError on file read IOError."""
    mock_exists.return_value = True
    mock_is_file.return_value = True
    mock_read_text.side_effect = IOError("Permission denied") # Simulate read error

    file_path = pathlib.Path("unreadable/file.json")
    with pytest.raises(AgentCardError, match="Failed to read Agent Card file"):
        load_agent_card_from_file(file_path)

# --- FIX: Mock Path object methods directly ---
@mock.patch("pathlib.Path.exists")
@mock.patch("pathlib.Path.is_file")
@mock.patch("pathlib.Path.read_text")
def test_load_agent_card_from_file_json_decode_error(mock_read_text, mock_is_file, mock_exists):
    """Test raising AgentCardError on invalid JSON content."""
    mock_exists.return_value = True
    mock_is_file.return_value = True
    mock_read_text.return_value = "{invalid json," # Provide invalid JSON

    file_path = pathlib.Path("invalid/format.json")
    # --- FIX: Expect JSONDecodeError message ---
    with pytest.raises(AgentCardError, match="Failed to decode JSON from Agent Card file"):
        load_agent_card_from_file(file_path)

# --- FIX: Mock Path object methods directly ---
@mock.patch("pathlib.Path.exists")
@mock.patch("pathlib.Path.is_file")
@mock.patch("pathlib.Path.read_text")
def test_load_agent_card_from_file_validation_error(mock_read_text, mock_is_file, mock_exists, invalid_card_data_missing_field):
    """Test raising AgentCardValidationError for valid JSON but invalid card structure."""
    mock_exists.return_value = True
    mock_is_file.return_value = True
    # Use the corrected fixture here
    mock_read_text.return_value = json.dumps(invalid_card_data_missing_field)

    file_path = pathlib.Path("valid_json_invalid_card.json")
    with pytest.raises(AgentCardValidationError):
        load_agent_card_from_file(file_path)

# --- Tests for fetch_agent_card_from_url ---

TEST_URL = "https://test.com/agent-card.json"

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_success(valid_card_data, respx_mock):
# --- END MODIFIED ---
    """Test successful fetching and parsing from a URL."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(return_value=httpx.Response(200, json=valid_card_data))
    agent_card = await fetch_agent_card_from_url(TEST_URL)
    # --- END MODIFIED ---

    assert isinstance(agent_card, AgentCard)
    assert agent_card.human_readable_id == "test-org/test-agent"
    assert route.called # Check route was called

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_network_error(respx_mock):
# --- END MODIFIED ---
    """Test raising AgentCardFetchError for network errors."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(side_effect=httpx.ConnectError("Connection failed"))
    with pytest.raises(AgentCardFetchError, match="Network error fetching Agent Card"):
        await fetch_agent_card_from_url(TEST_URL)
    # --- END MODIFIED ---
    assert route.called

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_http_error_404(respx_mock):
# --- END MODIFIED ---
    """Test raising AgentCardFetchError for 404 status."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(return_value=httpx.Response(404, text="Not Found"))
    with pytest.raises(AgentCardFetchError) as excinfo:
        await fetch_agent_card_from_url(TEST_URL)
    # --- END MODIFIED ---
    assert route.called
    # Check exception attributes after fixing exception class
    assert "Status: 404" in str(excinfo.value)
    assert excinfo.value.status_code == 404
    assert excinfo.value.response_body == "Not Found"

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_http_error_500(respx_mock):
# --- END MODIFIED ---
    """Test raising AgentCardFetchError for 500 status."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(return_value=httpx.Response(500, text="Server Error"))
    with pytest.raises(AgentCardFetchError) as excinfo:
        await fetch_agent_card_from_url(TEST_URL)
    # --- END MODIFIED ---
    assert route.called
    # Check exception attributes after fixing exception class
    assert "Status: 500" in str(excinfo.value)
    assert excinfo.value.status_code == 500
    assert excinfo.value.response_body == "Server Error"

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_invalid_json(respx_mock):
# --- END MODIFIED ---
    """Test raising AgentCardFetchError for invalid JSON response."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(return_value=httpx.Response(200, text="{not json"))
    with pytest.raises(AgentCardFetchError, match="Failed to decode JSON response"):
        await fetch_agent_card_from_url(TEST_URL)
    # --- END MODIFIED ---
    assert route.called

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_validation_error(invalid_card_data_missing_field, respx_mock):
# --- END MODIFIED ---
    """Test raising AgentCardValidationError for valid JSON but invalid card structure."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(return_value=httpx.Response(200, json=invalid_card_data_missing_field))
    with pytest.raises(AgentCardValidationError):
        await fetch_agent_card_from_url(TEST_URL)
    # --- END MODIFIED ---
    assert route.called

@pytest.mark.asyncio
# --- MODIFIED: Add marker, use respx_mock fixture ---
@pytest.mark.respx(using="httpx")
async def test_fetch_agent_card_from_url_with_existing_client(valid_card_data, respx_mock):
# --- END MODIFIED ---
    """Test passing an existing httpx client."""
    # --- MODIFIED: Define route using respx_mock ---
    route = respx_mock.get(TEST_URL).mock(return_value=httpx.Response(200, json=valid_card_data))
    async with httpx.AsyncClient() as client:
        agent_card = await fetch_agent_card_from_url(TEST_URL, http_client=client)
    # --- END MODIFIED ---

    assert isinstance(agent_card, AgentCard)
    assert agent_card.human_readable_id == "test-org/test-agent"
    assert route.called

#
