import pytest
# --- MODIFIED: Added datetime, timezone, timedelta ---
from unittest.mock import patch, MagicMock, ANY, AsyncMock, call
from typing import List, Optional
import secrets
from datetime import datetime, timezone, timedelta # Added imports
# --- MODIFIED: Added logging ---
import logging
# --- END MODIFIED ---
# --- END MODIFIED ---


# --- MODIFIED: Added HTTPException, Depends ---
from fastapi import status, HTTPException, Depends, Body, Query, Response # Added Response
from fastapi.responses import RedirectResponse, JSONResponse # Added JSONResponse
# --- END MODIFIED ---
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
# --- MODIFIED: Added SecretStr ---
from pydantic import EmailStr, SecretStr # Added SecretStr
# --- END MODIFIED ---
# --- ADDED: Import jose ---
from jose import jwt, JWTError
# --- END ADDED ---
# --- ADDED: Import Annotated and OAuth2PasswordRequestForm ---
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm
# --- END ADDED ---


# Local imports
from agentvault_registry import schemas, models, security
from agentvault_registry.database import get_db
from agentvault_registry.crud import developer as developer_crud # Use alias
# --- MODIFIED: Import both email functions ---
from agentvault_registry.email_utils import send_verification_email, send_password_reset_email # Added send_password_reset_email
# --- END MODIFIED ---
# --- ADDED: Import settings ---
from agentvault_registry.config import settings
# --- END ADDED ---


logger = logging.getLogger(__name__)

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
        # Use settings for expiry calculation consistency
        verification_token_expires=datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
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

# --- Tests for /auth/verify-email ---
@patch("agentvault_registry.crud.developer.get_developer_by_verification_token", new_callable=AsyncMock)
def test_verify_email_success(
    mock_crud_get_token: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer
):
    """Test successful email verification."""
    # --- Arrange ---
    test_token = "valid_verify_token"
    mock_developer.is_verified = False
    mock_developer.email_verification_token = test_token
    mock_developer.verification_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_crud_get_token.return_value = mock_developer

    # --- Act ---
    response = sync_test_client.get(f"{AUTH_URL}/verify-email", params={"token": test_token})

    # --- Assert ---
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "verified"}
    mock_crud_get_token.assert_awaited_once_with(mock_db_session, token=test_token)
    mock_db_session.add.assert_called_once_with(mock_developer)
    mock_db_session.commit.assert_awaited_once()
    assert mock_developer.is_verified is True
    assert mock_developer.email_verification_token is None
    assert mock_developer.verification_token_expires is None

@patch("agentvault_registry.crud.developer.get_developer_by_verification_token", new_callable=AsyncMock)
def test_verify_email_invalid_token(mock_crud_get_token: AsyncMock, sync_test_client: TestClient, mock_db_session: MagicMock):
    """Test verification with an invalid/unknown token."""
    mock_crud_get_token.return_value = None
    response = sync_test_client.get(f"{AUTH_URL}/verify-email", params={"token": "invalid_token"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired verification token" in response.json()["detail"]

@patch("agentvault_registry.crud.developer.get_developer_by_verification_token", new_callable=AsyncMock)
def test_verify_email_expired_token(mock_crud_get_token: AsyncMock, sync_test_client: TestClient, mock_db_session: MagicMock, mock_developer: models.Developer):
    """Test verification with an expired token."""
    test_token = "expired_token"
    mock_developer.is_verified = False
    mock_developer.email_verification_token = test_token
    mock_developer.verification_token_expires = datetime.now(timezone.utc) - timedelta(hours=1) # Expired
    mock_crud_get_token.return_value = mock_developer

    response = sync_test_client.get(f"{AUTH_URL}/verify-email", params={"token": test_token})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired verification token" in response.json()["detail"]

@patch("agentvault_registry.crud.developer.get_developer_by_verification_token", new_callable=AsyncMock)
def test_verify_email_already_verified(mock_crud_get_token: AsyncMock, sync_test_client: TestClient, mock_db_session: MagicMock, mock_developer: models.Developer):
    """Test verification when the developer is already verified."""
    test_token = "valid_token_but_verified"
    mock_developer.is_verified = True # Already verified
    mock_developer.email_verification_token = test_token
    mock_developer.verification_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_crud_get_token.return_value = mock_developer

    response = sync_test_client.get(f"{AUTH_URL}/verify-email", params={"token": test_token})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "already_verified"}
    mock_db_session.commit.assert_not_awaited() # Should not commit changes

# --- Tests for Recovery Key Flow ---
@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.security.verify_recovery_key")
@patch("agentvault_registry.routers.auth.security.create_access_token")
def test_recover_account_success(
    mock_create_token: MagicMock,
    mock_verify_recovery: MagicMock,
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer
):
    """Test successful account recovery initiation using a recovery key."""
    # --- Arrange ---
    mock_developer.is_verified = True
    mock_developer.hashed_recovery_key = security.hash_password("key-hash-placeholder") # Needs a stored hash
    mock_crud_get_email.return_value = mock_developer
    mock_verify_recovery.return_value = True # Simulate key matches hash
    mock_create_token.return_value = "temp_password_set_token"

    recover_payload = {"email": mock_developer.email, "recovery_key": "plain-rec-key-1"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/recover-account", json=recover_payload)

    # --- Assert ---
    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["access_token"] == "temp_password_set_token"
    assert resp_data["token_type"] == "bearer"

    mock_crud_get_email.assert_awaited_once_with(mock_db_session, email=mock_developer.email)
    mock_verify_recovery.assert_called_once_with("plain-rec-key-1", mock_developer.hashed_recovery_key)
    mock_create_token.assert_called_once()
    # Check that the token has the correct purpose and a short expiry
    call_args, call_kwargs = mock_create_token.call_args
    assert call_kwargs['data'] == {"sub": str(mock_developer.id), "purpose": "password-set"}
    assert isinstance(call_kwargs['expires_delta'], timedelta)
    assert call_kwargs['expires_delta'] <= timedelta(minutes=10) # Check for reasonably short expiry

@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
def test_recover_account_dev_not_found(mock_crud_get_email: AsyncMock, sync_test_client: TestClient, mock_db_session: MagicMock):
    """Test recovery failure if email not found."""
    mock_crud_get_email.return_value = None
    recover_payload = {"email": "not.found@example.com", "recovery_key": "plain-rec-key-1"}
    response = sync_test_client.post(f"{AUTH_URL}/recover-account", json=recover_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid email or recovery key" in response.json()["detail"]

@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
def test_recover_account_dev_not_verified(mock_crud_get_email: AsyncMock, sync_test_client: TestClient, mock_db_session: MagicMock, mock_developer: models.Developer):
    """Test recovery failure if developer is not verified."""
    mock_developer.is_verified = False
    mock_crud_get_email.return_value = mock_developer
    recover_payload = {"email": mock_developer.email, "recovery_key": "plain-rec-key-1"}
    response = sync_test_client.post(f"{AUTH_URL}/recover-account", json=recover_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid email or recovery key" in response.json()["detail"]

@patch("agentvault_registry.routers.auth.developer_crud.get_developer_by_email", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.security.verify_recovery_key")
def test_recover_account_invalid_key(
    mock_verify_recovery: MagicMock,
    mock_crud_get_email: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer
):
    """Test recovery failure with an invalid recovery key."""
    mock_developer.is_verified = True
    mock_developer.hashed_recovery_key = security.hash_password("key-hash-placeholder")
    mock_crud_get_email.return_value = mock_developer
    mock_verify_recovery.return_value = False # Simulate key mismatch

    recover_payload = {"email": mock_developer.email, "recovery_key": "wrong-key"}
    response = sync_test_client.post(f"{AUTH_URL}/recover-account", json=recover_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid email or recovery key" in response.json()["detail"]

# --- Test /auth/set-new-password ---
@patch("agentvault_registry.crud.developer.get_developer_by_id", new_callable=AsyncMock)
@patch("agentvault_registry.routers.auth.security.hash_password")
def test_set_new_password_success(
    mock_hash_pass: MagicMock,
    mock_crud_get_id: AsyncMock,
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    mocker
):
    """Test successfully setting a new password using the temporary token."""
    # --- Arrange ---
    temp_token_dev_id = mock_developer.id
    new_password = "newSecurePassword123"
    new_hashed_password = "new_hashed_password_xyz"

    # Mock the dependency using app override
    async def mock_verify_temp_success(token: str = Depends(security.oauth2_scheme_required)): # Add Depends back
        # Simulate successful verification by returning the ID
        # In a real scenario, this would decode the token passed in the header
        return temp_token_dev_id

    original_override = sync_test_client.app.dependency_overrides.get(security.verify_temp_password_token)
    sync_test_client.app.dependency_overrides[security.verify_temp_password_token] = mock_verify_temp_success

    mock_developer.hashed_recovery_key = "some_hash" # Ensure it exists before being cleared
    mock_crud_get_id.return_value = mock_developer
    mock_hash_pass.return_value = new_hashed_password

    # --- CORRECTED PAYLOAD (Based on user research) ---
    set_payload = {"new_password": new_password}
    # --- END CORRECTION ---

    temp_token = security.create_access_token(
        data={"sub": str(temp_token_dev_id), "purpose": "password-set"},
        expires_delta=timedelta(minutes=5)
    )
    headers = {"Authorization": f"Bearer {temp_token}"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/set-new-password", json=set_payload, headers=headers)

    # --- Assert ---
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Password updated successfully."}

    mock_crud_get_id.assert_awaited_once_with(mock_db_session, developer_id=temp_token_dev_id)
    # --- REVISED ASSERTION for mock_hash_pass ---
    mock_hash_pass.assert_called_once_with(new_password) # Check it was called with the plain string
    # --- END REVISED ASSERTION ---
    mock_db_session.add.assert_called_once_with(mock_developer)
    mock_db_session.commit.assert_awaited_once()
    assert mock_developer.hashed_password == new_hashed_password # Check the *mocked* return value was assigned
    assert mock_developer.hashed_recovery_key is None # Check recovery key was invalidated

    # Clean up override
    if original_override: sync_test_client.app.dependency_overrides[security.verify_temp_password_token] = original_override
    else: del sync_test_client.app.dependency_overrides[security.verify_temp_password_token]


def test_set_new_password_invalid_token(
    sync_test_client: TestClient,
    mocker
):
    """Test setting password fails with invalid/expired temp token."""
    # --- Arrange ---
    # Mock the dependency using app override to raise 401
    async def mock_verify_temp_fail(token: str = Depends(security.oauth2_scheme_required)): # Add Depends back
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password recovery token"
        )

    original_override = sync_test_client.app.dependency_overrides.get(security.verify_temp_password_token)
    sync_test_client.app.dependency_overrides[security.verify_temp_password_token] = mock_verify_temp_fail

    # --- CORRECTED PAYLOAD (Based on user research) ---
    set_payload = {"new_password": "newpassword"}
    # --- END CORRECTION ---
    headers = {"Authorization": "Bearer invalid-or-expired-token"}

    # --- Act ---
    response = sync_test_client.post(f"{AUTH_URL}/set-new-password", json=set_payload, headers=headers)

    # --- Assert ---
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or expired password recovery token" in response.json()["detail"]

    # Clean up override
    if original_override: sync_test_client.app.dependency_overrides[security.verify_temp_password_token] = original_override
    else: del sync_test_client.app.dependency_overrides[security.verify_temp_password_token]


# TODO: Add tests for email-based password reset endpoints when implemented
