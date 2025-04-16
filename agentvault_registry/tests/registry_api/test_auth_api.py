import pytest
# --- MODIFIED: Added MagicMock ---
from unittest.mock import patch, MagicMock, ANY, AsyncMock, call
# --- END MODIFIED ---
from typing import List, Optional
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from pydantic import EmailStr

# Local imports
from agentvault_registry import schemas, models, security
from agentvault_registry.config import settings # Import settings for expiry calc if needed

# Fixtures are implicitly used from conftest.py

AUTH_URL = "/auth" # Base prefix for auth routes

# --- Test /auth/register ---

@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.developer_crud.create_developer_with_hashed_details", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.send_verification_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.security.hash_password")
@patch("agentvault_registry.routers.auth.security.generate_recovery_keys")
@patch("agentvault_registry.routers.auth.security.hash_recovery_key")
@patch("agentvault_registry.routers.auth.secrets.token_urlsafe")
def test_register_developer_success(
    mock_token_urlsafe: MagicMock,
    mock_hash_recovery: MagicMock,
    mock_gen_recovery: MagicMock,
    mock_hash_pass: MagicMock,
    mock_send_email: AsyncMock,
    mock_crud_create: AsyncMock,
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock # Needed for dependency resolution
):
    """Test successful developer registration."""
    # --- Arrange ---
    mock_crud_get_email.return_value = None # No existing developer
    mock_hash_pass.return_value = "hashed_password_abc"
    mock_gen_recovery.return_value = ["rec-key-1", "rec-key-2", "rec-key-3"]
    mock_hash_recovery.return_value = "hashed_recovery_key_xyz"
    mock_token_urlsafe.return_value = "test_verification_token"

    # Mock the developer object returned by CRUD create
    mock_created_dev = models.Developer(
        id=1, name="New Dev", email="new@example.com", hashed_password="hashed_password_abc",
        is_verified=False, email_verification_token="test_verification_token",
        verification_token_expires=datetime.now(timezone.utc) + timedelta(hours=1), # Use settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS if defined
        hashed_recovery_key="hashed_recovery_key_xyz",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    mock_crud_create.return_value = mock_created_dev

    register_payload = {
        "name": "New Dev",
        "email": "new@example.com",
        "password": "password123"
    }

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/register", json=register_payload)

    # --- Assert ---
    assert response.status_code == status.HTTP_201_CREATED
    resp_data = response.json()
    assert resp_data["message"] == "Registration successful. Please check your email to verify your account."
    assert resp_data["recovery_keys"] == ["rec-key-1", "rec-key-2", "rec-key-3"]

    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email="new@example.com")
    mock_hash_pass.assert_called_once_with("password123")
    mock_gen_recovery.assert_called_once()
    mock_hash_recovery.assert_called_once_with("rec-key-1") # Assuming first key is hashed
    mock_token_urlsafe.assert_called_once_with(32)
    mock_crud_create.assert_awaited_once()
    # Check the developer data passed to CRUD create
    call_args, call_kwargs = mock_crud_create.call_args
    created_dev_arg = call_kwargs.get('developer_data')
    assert isinstance(created_dev_arg, models.Developer)
    assert created_dev_arg.name == "New Dev"
    assert created_dev_arg.email == "new@example.com"
    assert created_dev_arg.hashed_password == "hashed_password_abc"
    assert created_dev_arg.hashed_recovery_key == "hashed_recovery_key_xyz"
    assert created_dev_arg.email_verification_token == "test_verification_token"
    assert created_dev_arg.is_verified is False
    mock_send_email.assert_awaited_once_with(
        to_email="new@example.com",
        username="New Dev",
        token="test_verification_token"
    )


@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
def test_register_developer_email_exists(
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer # Use existing fixture
):
    """Test registration failure when email already exists."""
    # --- Arrange ---
    mock_crud_get_email.return_value = mock_developer # Simulate developer found

    register_payload = {
        "name": "Another Dev",
        "email": mock_developer.email, # Use existing email
        "password": "password123"
    }

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/register", json=register_payload)

    # --- Assert ---
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in response.json()["detail"]
    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email=mock_developer.email)


@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.developer_crud.create_developer_with_hashed_details", new_callable=AsyncMock)
def test_register_developer_name_conflict(
    mock_crud_create: AsyncMock,
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock
):
    """Test registration failure due to name conflict (IntegrityError)."""
    # --- Arrange ---
    mock_crud_get_email.return_value = None # Email is unique
    mock_crud_create.side_effect = IntegrityError("Mock integrity error", params={}, orig=Exception()) # Simulate DB conflict

    register_payload = {
        "name": "Conflicting Name",
        "email": "unique.email@example.com",
        "password": "password123"
    }

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/register", json=register_payload)

    # --- Assert ---
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "Username or email already exists" in response.json()["detail"]
    mock_crud_get_email.assert_awaited_once()
    mock_crud_create.assert_awaited_once()


# --- Test /auth/login ---

@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.security.verify_password")
@patch("agentvault_registry.routers.auth.security.create_access_token")
def test_login_success(
    mock_create_token: MagicMock,
    mock_verify_pass: MagicMock,
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer # Use existing fixture
):
    """Test successful login with correct credentials."""
    # --- Arrange ---
    mock_developer.is_verified = True # Ensure developer is verified
    mock_crud_get_email.return_value = mock_developer
    mock_verify_pass.return_value = True
    mock_create_token.return_value = "test_jwt_token"

    login_data = {"username": mock_developer.email, "password": "testpassword"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/login", data=login_data)

    # --- Assert ---
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["access_token"] == "test_jwt_token"
    assert resp_data["token_type"] == "bearer"

    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email=mock_developer.email)
    mock_verify_pass.assert_called_once_with("testpassword", mock_developer.hashed_password)
    mock_create_token.assert_called_once_with(data={"sub": str(mock_developer.id)}, expires_delta=ANY)


@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
def test_login_developer_not_found(
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock
):
    """Test login failure when email does not exist."""
    # --- Arrange ---
    mock_crud_get_email.return_value = None
    login_data = {"username": "notfound@example.com", "password": "password123"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/login", data=login_data)

    # --- Assert ---
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect email or password" in response.json()["detail"]
    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email="notfound@example.com")


@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
def test_login_developer_not_verified(
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer
):
    """Test login failure when developer email is not verified."""
    # --- Arrange ---
    mock_developer.is_verified = False # Ensure developer is NOT verified
    mock_crud_get_email.return_value = mock_developer
    login_data = {"username": mock_developer.email, "password": "testpassword"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/login", data=login_data)

    # --- Assert ---
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Email address not verified" in response.json()["detail"]
    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email=mock_developer.email)


@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.security.verify_password")
def test_login_incorrect_password(
    mock_verify_pass: MagicMock,
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer
):
    """Test login failure with incorrect password."""
    # --- Arrange ---
    mock_developer.is_verified = True # Developer is verified
    mock_crud_get_email.return_value = mock_developer
    mock_verify_pass.return_value = False # Simulate password mismatch
    login_data = {"username": mock_developer.email, "password": "wrongpassword"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/login", data=login_data)

    # --- Assert ---
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect email or password" in response.json()["detail"]
    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email=mock_developer.email)
    mock_verify_pass.assert_called_once_with("wrongpassword", mock_developer.hashed_password)

# TODO: Add tests for /verify-email, /recover-account, /set-new-password later
