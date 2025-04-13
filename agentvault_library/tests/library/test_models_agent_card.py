import pytest
from pydantic import ValidationError, HttpUrl

# Import models to test
from agentvault.models.agent_card import (
    AgentProvider,
    AgentSkill,
    AgentAuthentication,
    AgentCapabilities,
    TeeDetails,
    AgentCard
)

# --- Test AgentAuthentication ---

def test_agent_auth_apikey_valid():
    """Test valid apiKey scheme."""
    auth = AgentAuthentication(scheme="apiKey", service_identifier="test-service")
    assert auth.scheme == "apiKey"
    assert auth.service_identifier == "test-service"
    assert auth.token_url is None
    assert auth.scopes is None

def test_agent_auth_none_valid():
    """Test valid none scheme."""
    auth = AgentAuthentication(scheme="none")
    assert auth.scheme == "none"
    assert auth.service_identifier is None

def test_agent_auth_oauth2_valid():
    """Test valid oauth2 scheme with required fields."""
    token_url_str = "https://auth.example.com/token"
    scopes = ["read:tasks", "write:tasks"]
    auth_data = {
        "scheme": "oauth2",
        "tokenUrl": token_url_str,
        "scopes": scopes,
        "service_identifier": "oauth-service"
    }
    auth = AgentAuthentication.model_validate(auth_data)
    assert auth.scheme == "oauth2"
    assert isinstance(auth.token_url, HttpUrl)
    assert str(auth.token_url).rstrip('/') == token_url_str # Compare string representation, ignore trailing slash
    assert auth.scopes == scopes
    assert auth.service_identifier == "oauth-service"

def test_agent_auth_oauth2_missing_token_url():
    """Test oauth2 scheme validation failure when tokenUrl is missing."""
    with pytest.raises(ValidationError) as excinfo:
        # --- FIX: Use model_validate to trigger alias and validator ---
        AgentAuthentication.model_validate({"scheme": "oauth2", "scopes": ["read"]})
        # --- END FIX ---
    assert "'tokenUrl' is required when scheme is 'oauth2'" in str(excinfo.value)

def test_agent_auth_invalid_scheme():
    """Test validation failure for an unknown scheme."""
    with pytest.raises(ValidationError) as excinfo:
        AgentAuthentication(scheme="invalidScheme")
    assert "Input should be 'apiKey', 'bearer', 'oauth2' or 'none'" in str(excinfo.value)


def test_agent_auth_invalid_token_url_type():
    """Test validation failure for invalid tokenUrl type."""
    with pytest.raises(ValidationError) as excinfo:
        AgentAuthentication.model_validate({"scheme": "oauth2", "tokenUrl": 123})
    assert "URL input should be a string or URL" in str(excinfo.value)

# --- Test AgentCapabilities ---

def test_agent_capabilities_minimal():
    """Test minimal valid AgentCapabilities."""
    caps = AgentCapabilities(a2aVersion="1.0")
    assert caps.a2a_version == "1.0"
    assert caps.mcp_version is None
    assert caps.supported_message_parts is None
    assert caps.tee_details is None
    assert caps.supports_push_notifications is None

def test_agent_capabilities_full():
    """Test AgentCapabilities with all optional fields."""
    tee_data = {"type": "TestTEE", "attestationEndpoint": "https://attest.example.com"}
    caps_data = {
        "a2aVersion": "1.1",
        "mcpVersion": "0.6",
        "supportedMessageParts": ["text", "file"],
        "teeDetails": tee_data,
        "supportsPushNotifications": True
    }
    caps = AgentCapabilities.model_validate(caps_data)
    assert caps.a2a_version == "1.1"
    assert caps.mcp_version == "0.6"
    assert caps.supported_message_parts == ["text", "file"]
    assert isinstance(caps.tee_details, TeeDetails)
    assert caps.tee_details.type == "TestTEE"
    assert caps.supports_push_notifications is True

# --- Test TeeDetails ---

def test_tee_details_minimal():
    """Test minimal valid TeeDetails."""
    tee = TeeDetails(type="TestTEE")
    assert tee.type == "TestTEE"
    assert tee.attestation_endpoint is None
    assert tee.public_key is None
    assert tee.description is None

def test_tee_details_full():
    """Test TeeDetails with all optional fields."""
    att_url_str = "https://attest.example.com"
    tee_data = {
        "type": "TestTEE",
        "attestationEndpoint": att_url_str,
        "publicKey": "mypublickeydata",
        "description": "Test TEE environment"
    }
    tee = TeeDetails.model_validate(tee_data)
    assert tee.type == "TestTEE"
    assert isinstance(tee.attestation_endpoint, HttpUrl)
    # --- FIX: Compare string representations ignoring trailing slash ---
    assert str(tee.attestation_endpoint).rstrip('/') == att_url_str.rstrip('/')
    # --- END FIX ---
    assert tee.public_key == "mypublickeydata"
    assert tee.description == "Test TEE environment"

# --- Test AgentCard (Basic Instantiation) ---
# More comprehensive tests might involve valid_card_data fixtures similar to test_agent_card_utils.py

def test_agent_card_basic_instantiation():
    """Test basic AgentCard instantiation with nested models."""
    card = AgentCard(
        schemaVersion="1.0",
        humanReadableId="test/basic-card",
        agentVersion="0.1",
        name="Basic Agent",
        description="A basic test card",
        url="https://basic.example.com/a2a",
        provider=AgentProvider(name="Basic Provider"),
        capabilities=AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[AgentAuthentication(scheme="none")]
    )
    assert card.name == "Basic Agent"
    assert card.provider.name == "Basic Provider"
    assert card.capabilities.a2a_version == "1.0"
    assert card.auth_schemes[0].scheme == "none"

def test_agent_card_validation_error_missing_auth():
    """Test AgentCard validation fails if authSchemes is empty."""
    with pytest.raises(ValidationError) as excinfo:
        AgentCard(
            schemaVersion="1.0", humanReadableId="test/no-auth", agentVersion="0.1",
            name="No Auth Agent", description="...", url="https://no-auth.example.com",
            provider=AgentProvider(name="Prov"), capabilities=AgentCapabilities(a2aVersion="1.0"),
            authSchemes=[] # Empty list
        )
    assert "List should have at least 1 item after validation, not 0" in str(excinfo.value)
    assert "authSchemes" in str(excinfo.value)
