import pytest
# --- MODIFIED: Added datetime, timezone, timedelta ---
from unittest.mock import patch, AsyncMock, ANY, call, MagicMock
from typing import List, Optional
import datetime
from datetime import datetime, timezone, timedelta # Added imports
# --- END MODIFIED ---
from fastapi import status, Response # Added Response
from fastapi.testclient import TestClient

# Local imports
from agentvault_registry import schemas, models, security

# Fixtures are implicitly used from conftest.py

DEV_URL = "/developers" # Base prefix for developer routes

# --- Test GET /developers/me ---

def test_get_developer_me_success(
    sync_test_client: TestClient,
    mock_developer: models.Developer,
    override_get_current_developer: None # Use the fixture that provides mock_developer
):
    """Test successfully retrieving current developer info."""
    # --- Act ---
    response = sync_test_client.get(f"{DEV_URL}/me", headers={"Authorization": "Bearer fake-token"})

    # --- Assert ---
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    # Validate against the read schema
    validated = schemas.DeveloperRead.model_validate(resp_data)
    assert validated.id == mock_developer.id
    assert validated.name == mock_developer.name
    assert validated.email == mock_developer.email
    assert validated.is_verified == mock_developer.is_verified

def test_get_developer_me_unauthorized(
    sync_test_client: TestClient,
    override_get_current_developer_unauthorized: None # Use fixture that raises 401
):
    """Test GET /me when authentication fails."""
    response = sync_test_client.get(f"{DEV_URL}/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

# --- Test POST /developers/me/apikeys ---

@patch("agentvault_registry.routers.developers.security.generate_secure_api_key")
@patch("agentvault_registry.routers.developers.security.hash_api_key")
@patch("agentvault_registry.routers.developers.developer_crud.create_api_key", new_callable=AsyncMock)
def test_create_api_key_success(
    mock_crud_create_key: AsyncMock,
    mock_hash_key: MagicMock,
    mock_generate_key: MagicMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None
):
    """Test successfully creating a new API key."""
    # --- Arrange ---
    plain_key = "avreg_testplainkey123"
    hashed_key = "hashed_testplainkey123"
    prefix = "avreg_"
    description = "Test Key"
    mock_generate_key.return_value = plain_key
    mock_hash_key.return_value = hashed_key

    # Mock the DB object returned by CRUD
    mock_db_api_key = models.DeveloperApiKey(
        id=10, developer_id=mock_developer.id, key_prefix=prefix, hashed_key=hashed_key,
        description=description, is_active=True, created_at=datetime.now(timezone.utc), # Use imported datetime
        last_used_at=None
    )
    mock_crud_create_key.return_value = mock_db_api_key

    payload = {"description": description}

    # --- Act ---
    response = sync_test_client.post(f"{DEV_URL}/me/apikeys", json=payload, headers={"Authorization": "Bearer fake-token"})

    # --- Assert ---
    assert response.status_code == status.HTTP_201_CREATED
    resp_data = response.json()
    assert schemas.NewApiKeyResponse.model_validate(resp_data)
    assert resp_data["plain_api_key"] == plain_key
    assert resp_data["api_key_info"]["key_prefix"] == prefix
    assert resp_data["api_key_info"]["description"] == description
    assert resp_data["api_key_info"]["is_active"] is True
    assert resp_data["api_key_info"]["id"] == 10

    mock_generate_key.assert_called_once()
    mock_hash_key.assert_called_once_with(plain_key)
    mock_crud_create_key.assert_awaited_once_with(
        db=mock_db_session,
        developer_id=mock_developer.id,
        prefix=prefix,
        hashed_key=hashed_key,
        description=description
    )

@patch("agentvault_registry.routers.developers.security.generate_secure_api_key")
@patch("agentvault_registry.routers.developers.security.hash_api_key")
@patch("agentvault_registry.routers.developers.developer_crud.create_api_key", new_callable=AsyncMock)
def test_create_api_key_no_description(
    mock_crud_create_key: AsyncMock, mock_hash_key: MagicMock, mock_generate_key: MagicMock,
    sync_test_client: TestClient, mock_db_session: MagicMock, mock_developer: models.Developer,
    override_get_current_developer: None
):
    """Test creating an API key without providing a description."""
    plain_key = "avreg_nodesckey456"
    hashed_key = "hashed_nodesckey456"
    prefix = "avreg_"
    mock_generate_key.return_value = plain_key
    mock_hash_key.return_value = hashed_key
    mock_db_api_key = models.DeveloperApiKey(id=11, developer_id=mock_developer.id, key_prefix=prefix, hashed_key=hashed_key, description=None, is_active=True, created_at=datetime.now(timezone.utc)) # Use imported datetime
    mock_crud_create_key.return_value = mock_db_api_key

    response = sync_test_client.post(f"{DEV_URL}/me/apikeys", json={}, headers={"Authorization": "Bearer fake-token"}) # Empty JSON body

    assert response.status_code == status.HTTP_201_CREATED
    resp_data = response.json()
    assert resp_data["plain_api_key"] == plain_key
    assert resp_data["api_key_info"]["description"] is None
    mock_crud_create_key.assert_awaited_once_with(db=mock_db_session, developer_id=mock_developer.id, prefix=prefix, hashed_key=hashed_key, description=None)

@patch("agentvault_registry.routers.developers.developer_crud.create_api_key", new_callable=AsyncMock)
def test_create_api_key_db_error(mock_crud_create_key: AsyncMock, sync_test_client: TestClient, mock_developer: models.Developer, override_get_current_developer: None):
    """Test error handling when API key creation fails in CRUD."""
    mock_crud_create_key.return_value = None # Simulate DB save failure
    response = sync_test_client.post(f"{DEV_URL}/me/apikeys", json={"description": "fail key"}, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to create API key" in response.json()["detail"]

# --- Test GET /developers/me/apikeys ---

@patch("agentvault_registry.routers.developers.developer_crud.get_active_api_keys_for_developer", new_callable=AsyncMock)
def test_list_api_keys_success(
    mock_crud_get_keys: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None
):
    """Test successfully listing active API keys."""
    # --- Arrange ---
    now = datetime.now(timezone.utc) # Use imported datetime
    mock_key_1 = models.DeveloperApiKey(id=1, developer_id=mock_developer.id, key_prefix="avreg_", hashed_key="h1", description="Key 1", is_active=True, created_at=now - timedelta(days=1))
    mock_key_2 = models.DeveloperApiKey(id=2, developer_id=mock_developer.id, key_prefix="avreg_", hashed_key="h2", description=None, is_active=True, created_at=now)
    mock_crud_get_keys.return_value = [mock_key_2, mock_key_1] # Simulate DB returning ordered list

    # --- Act ---
    response = sync_test_client.get(f"{DEV_URL}/me/apikeys", headers={"Authorization": "Bearer fake-token"})

    # --- Assert ---
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert isinstance(resp_data, list)
    assert len(resp_data) == 2
    # Validate schema of first item
    validated_item = schemas.ApiKeyRead.model_validate(resp_data[0])
    assert validated_item.id == 2 # Check order returned by API
    assert validated_item.description is None
    assert validated_item.is_active is True
    assert resp_data[1]["description"] == "Key 1"

    mock_crud_get_keys.assert_awaited_once_with(db=mock_db_session, developer_id=mock_developer.id)

@patch("agentvault_registry.routers.developers.developer_crud.get_active_api_keys_for_developer", new_callable=AsyncMock)
def test_list_api_keys_none_found(
    mock_crud_get_keys: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None
):
    """Test listing API keys when none are found."""
    mock_crud_get_keys.return_value = []
    response = sync_test_client.get(f"{DEV_URL}/me/apikeys", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []
    mock_crud_get_keys.assert_awaited_once_with(db=mock_db_session, developer_id=mock_developer.id)

# --- Test DELETE /developers/me/apikeys/{key_id} ---

@patch("agentvault_registry.routers.developers.developer_crud.deactivate_api_key", new_callable=AsyncMock)
def test_delete_api_key_success(
    mock_crud_deactivate: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None
):
    """Test successfully deactivating an API key."""
    # --- Arrange ---
    key_id_to_delete = 5
    mock_crud_deactivate.return_value = True # Simulate successful deactivation

    # --- Act ---
    response = sync_test_client.delete(f"{DEV_URL}/me/apikeys/{key_id_to_delete}", headers={"Authorization": "Bearer fake-token"})

    # --- Assert ---
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_crud_deactivate.assert_awaited_once_with(
        db=mock_db_session,
        developer_id=mock_developer.id,
        api_key_id=key_id_to_delete
    )

@patch("agentvault_registry.routers.developers.developer_crud.deactivate_api_key", new_callable=AsyncMock)
def test_delete_api_key_not_found_or_not_owned(
    mock_crud_deactivate: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None
):
    """Test deleting an API key that doesn't exist or isn't owned by the user."""
    # --- Arrange ---
    key_id_to_delete = 999
    mock_crud_deactivate.return_value = False # Simulate key not found or not owned

    # --- Act ---
    response = sync_test_client.delete(f"{DEV_URL}/me/apikeys/{key_id_to_delete}", headers={"Authorization": "Bearer fake-token"})

    # --- Assert ---
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # --- MODIFIED: Check for the correct detail message ---
    assert "API Key not found or not owned by the current user" in response.json()["detail"] # Adjusted assertion
    # --- END MODIFIED ---
    mock_crud_deactivate.assert_awaited_once_with(
        db=mock_db_session,
        developer_id=mock_developer.id,
        api_key_id=key_id_to_delete
    )
