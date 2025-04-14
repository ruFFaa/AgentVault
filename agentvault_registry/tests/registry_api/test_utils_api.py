import pytest
from unittest.mock import patch, MagicMock
import pydantic

from fastapi import status
from fastapi.testclient import TestClient

# Import schemas used by the endpoint
from agentvault_registry import schemas

# Define the API endpoint path
UTILS_API_BASE_URL = "/api/v1/utils"

# Sample valid card data structure for requests
SAMPLE_VALID_CARD_DATA = {
    "schemaVersion": "1.0",
    "humanReadableId": "test-org/validation-agent",
    "agentVersion": "1.0.0",
    "name": "Validation Test Agent",
    "description": "Agent for testing validation.",
    "url": "https://validation.example.com/a2a",
    "provider": {"name": "Test Suite Inc."},
    "capabilities": {"a2aVersion": "1.0"},
    "authSchemes": [{"scheme": "none"}]
}

# Use the sync_test_client fixture implicitly defined in conftest.py

@patch("agentvault_registry.routers.utils.AgentCardModel") # Mock the imported model class
def test_validate_card_success(mock_agent_card_model_cls, sync_test_client: TestClient):
    """Test successful validation of valid card data."""
    # Configure the mock model_validate method
    mock_validated_card = MagicMock()
    # Make model_dump return the original data for simplicity in this test
    mock_validated_card.model_dump.return_value = SAMPLE_VALID_CARD_DATA
    mock_agent_card_model_cls.model_validate.return_value = mock_validated_card

    request_payload = {"card_data": SAMPLE_VALID_CARD_DATA}
    response = sync_test_client.post(f"{UTILS_API_BASE_URL}/validate-card", json=request_payload)

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert schemas.AgentCardValidationResponse.model_validate(resp_data)
    assert resp_data["is_valid"] is True
    assert resp_data["detail"] is None
    assert resp_data["validated_card_data"] == SAMPLE_VALID_CARD_DATA
    mock_agent_card_model_cls.model_validate.assert_called_once_with(SAMPLE_VALID_CARD_DATA)

@patch("agentvault_registry.routers.utils.AgentCardModel")
def test_validate_card_pydantic_error(mock_agent_card_model_cls, sync_test_client: TestClient):
    """Test validation failure due to Pydantic error."""
    error_message = "Validation Failed: Field required [type=missing, loc=('name',)]"
    # Configure mock to raise ValidationError
    # Need to simulate the structure Pydantic uses for errors if the detail matters
    mock_pydantic_error = pydantic.ValidationError.from_exception_data(
        title="AgentCard", line_errors=[{"type": "missing", "loc": ("name",), "msg": "Field required"}]
    )
    mock_agent_card_model_cls.model_validate.side_effect = mock_pydantic_error

    request_payload = {"card_data": {"description": "missing name"}} # Data causing the mock error
    response = sync_test_client.post(f"{UTILS_API_BASE_URL}/validate-card", json=request_payload)

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert schemas.AgentCardValidationResponse.model_validate(resp_data)
    assert resp_data["is_valid"] is False
    assert resp_data["validated_card_data"] is None
    assert "Field required" in resp_data["detail"] # Check if Pydantic error string is included
    assert "name" in resp_data["detail"]
    mock_agent_card_model_cls.model_validate.assert_called_once_with({"description": "missing name"})

def test_validate_card_invalid_request_body(sync_test_client: TestClient):
    """Test sending a request body missing the 'card_data' field."""
    invalid_payload = {"some_other_field": "value"}
    response = sync_test_client.post(f"{UTILS_API_BASE_URL}/validate-card", json=invalid_payload)

    # FastAPI should return 422 for request body validation errors
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    resp_data = response.json()
    assert "detail" in resp_data
    # Check that the detail mentions the missing field
    assert any("card_data" in detail["loc"] for detail in resp_data["detail"] if "loc" in detail)

@patch("agentvault_registry.routers.utils.AgentCardModel")
def test_validate_card_unexpected_exception(mock_agent_card_model_cls, sync_test_client: TestClient):
    """Test validation failure due to an unexpected exception during validation."""
    error_message = "Something unexpected broke"
    mock_agent_card_model_cls.model_validate.side_effect = Exception(error_message)

    request_payload = {"card_data": SAMPLE_VALID_CARD_DATA}
    response = sync_test_client.post(f"{UTILS_API_BASE_URL}/validate-card", json=request_payload)

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert schemas.AgentCardValidationResponse.model_validate(resp_data)
    assert resp_data["is_valid"] is False
    assert resp_data["validated_card_data"] is None
    assert "An unexpected error occurred during validation: Exception" in resp_data["detail"]
    mock_agent_card_model_cls.model_validate.assert_called_once_with(SAMPLE_VALID_CARD_DATA)

# --- MODIFIED: Removed mock arguments from function signature ---
@patch("agentvault_registry.routers.utils._agentvault_lib_available", False)
@patch("agentvault_registry.routers.utils.AgentCardModel", None) # Ensure model is None too
def test_validate_card_library_unavailable(sync_test_client: TestClient):
# --- END MODIFIED ---
    """Test validation endpoint when the core library is unavailable."""
    request_payload = {"card_data": SAMPLE_VALID_CARD_DATA}
    response = sync_test_client.post(f"{UTILS_API_BASE_URL}/validate-card", json=request_payload)

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert schemas.AgentCardValidationResponse.model_validate(resp_data)
    assert resp_data["is_valid"] is True # Treats as valid because check is skipped
    assert resp_data["detail"] == "Validation skipped: Core library not available."
    assert resp_data["validated_card_data"] == SAMPLE_VALID_CARD_DATA
