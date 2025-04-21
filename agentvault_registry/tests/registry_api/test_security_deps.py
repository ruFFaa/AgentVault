import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

from fastapi import HTTPException, status, Depends, Header
from fastapi.security import APIKeyHeader
# --- MODIFIED: Added AsyncSession ---
from sqlalchemy.ext.asyncio import AsyncSession
# --- END MODIFIED ---

from jose import JWTError, jwt

# Import functions/classes to test or mock
from agentvault_registry import security, models, schemas
from agentvault_registry.crud import developer as developer_crud
from agentvault_registry.config import settings
from agentvault_registry.database import get_db # Import for mocking context

# --- Fixtures ---

@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock SQLAlchemy AsyncSession."""
    # --- MODIFIED: Added spec ---
    return AsyncMock(spec=AsyncSession)
    # --- END MODIFIED ---

@pytest.fixture
def mock_developer() -> models.Developer:
    """Provides a mock Developer ORM model."""
    # Ensure all fields needed by dependencies are present
    return models.Developer(
        id=123,
        name="Security Test Dev",
        email="secure@example.com",
        hashed_password=security.hash_password("password"),
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        hashed_recovery_key=None,
        email_verification_token=None,
        verification_token_expires=None
    )

# --- Helper to create tokens ---
def create_test_token(
    dev_id: int = 123,
    purpose: Optional[str] = None,
    expires_in_minutes: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    secret: str = settings.API_KEY_SECRET, # Use correct default secret
    algorithm: str = security.ALGORITHM # Use correct default algorithm
) -> str:
    """Helper to create JWT tokens for testing."""
    expires_delta = timedelta(minutes=expires_in_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": str(dev_id), "exp": expire} # Add expiry here
    if purpose:
        to_encode["purpose"] = purpose
    # Use the provided secret and algorithm for encoding
    return jwt.encode(to_encode, secret, algorithm=algorithm)

# --- Tests for verify_access_token_required ---

@pytest.mark.asyncio
async def test_verify_required_success():
    """Test successful verification of a standard access token."""
    test_id = 456
    token = create_test_token(dev_id=test_id)
    # Call directly, simulating Depends() providing the token
    developer_id = await security.verify_access_token_required(token=token)
    assert developer_id == test_id

@pytest.mark.asyncio
async def test_verify_required_expired():
    """Test verification failure with an expired token."""
    token = create_test_token(expires_in_minutes=-5) # Expired 5 mins ago
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_access_token_required(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in excinfo.value.detail # Generic message for security

@pytest.mark.asyncio
async def test_verify_required_invalid_signature():
    """Test verification failure with wrong secret key."""
    # Create token with a DIFFERENT secret
    token = create_test_token(secret="--definitely-the-wrong-secret-key--")
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_access_token_required(token=token)
    # Assert it raises 401 because the decode should fail
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_verify_required_missing_sub():
    """Test verification failure when 'sub' claim is missing."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {"exp": expire, "other": "data"} # Missing 'sub'
    token = jwt.encode(to_encode, settings.API_KEY_SECRET, algorithm=security.ALGORITHM)
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_access_token_required(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_verify_required_sub_not_int():
    """Test verification failure when 'sub' claim is not an integer string."""
    token = create_test_token(dev_id="not-an-int") # type: ignore # Intentional type error for test
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_access_token_required(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_verify_required_wrong_purpose():
    """Test verification failure when a password-set token is used."""
    token = create_test_token(purpose="password-set")
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_access_token_required(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

# --- Tests for verify_access_token_optional ---

@pytest.mark.asyncio
async def test_verify_optional_success():
    """Test successful optional verification with valid Bearer token."""
    test_id = 789
    token = create_test_token(dev_id=test_id)
    header_value = f"Bearer {token}"
    # Call directly, simulating Header() providing the value
    developer_id = await security.verify_access_token_optional(authorization=header_value)
    assert developer_id == test_id

@pytest.mark.asyncio
async def test_verify_optional_no_header():
    """Test optional verification returns None when header is missing."""
    developer_id = await security.verify_access_token_optional(authorization=None)
    assert developer_id is None

@pytest.mark.asyncio
async def test_verify_optional_invalid_scheme():
    """Test optional verification returns None for wrong scheme."""
    token = create_test_token()
    header_value = f"Basic {token}" # Wrong scheme
    developer_id = await security.verify_access_token_optional(authorization=header_value)
    assert developer_id is None

@pytest.mark.asyncio
async def test_verify_optional_invalid_format():
    """Test optional verification returns None for invalid header format."""
    header_value = "Beareronly" # Missing space
    developer_id = await security.verify_access_token_optional(authorization=header_value)
    assert developer_id is None

@pytest.mark.asyncio
async def test_verify_optional_expired():
    """Test optional verification returns None for expired token."""
    token = create_test_token(expires_in_minutes=-5)
    header_value = f"Bearer {token}"
    developer_id = await security.verify_access_token_optional(authorization=header_value)
    assert developer_id is None

@pytest.mark.asyncio
async def test_verify_optional_invalid_signature():
    """Test optional verification returns None for invalid signature."""
    # Create token with a DIFFERENT secret
    token = create_test_token(secret="--definitely-the-wrong-secret-key--")
    header_value = f"Bearer {token}"
    developer_id = await security.verify_access_token_optional(authorization=header_value)
    # Assert it returns None because the decode should fail
    assert developer_id is None

@pytest.mark.asyncio
async def test_verify_optional_wrong_purpose():
    """Test optional verification returns None for password-set token."""
    token = create_test_token(purpose="password-set")
    header_value = f"Bearer {token}"
    developer_id = await security.verify_access_token_optional(authorization=header_value)
    assert developer_id is None

# --- Tests for verify_temp_password_token ---

@pytest.mark.asyncio
async def test_verify_temp_token_success():
    """Test successful verification of a password-set token."""
    test_id = 111
    token = create_test_token(dev_id=test_id, purpose="password-set", expires_in_minutes=5)
    developer_id = await security.verify_temp_password_token(token=token)
    assert developer_id == test_id

@pytest.mark.asyncio
async def test_verify_temp_token_expired():
    """Test failure for expired password-set token."""
    token = create_test_token(purpose="password-set", expires_in_minutes=-1)
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_temp_password_token(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or expired" in excinfo.value.detail

@pytest.mark.asyncio
async def test_verify_temp_token_wrong_purpose():
    """Test failure for token without 'password-set' purpose."""
    token = create_test_token() # Regular access token
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_temp_password_token(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_verify_temp_token_missing_sub():
    """Test failure for password-set token missing 'sub'."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    to_encode = {"exp": expire, "purpose": "password-set"} # Missing 'sub'
    token = jwt.encode(to_encode, settings.API_KEY_SECRET, algorithm=security.ALGORITHM)
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_temp_password_token(token=token)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

# --- Tests for get_current_developer ---

@pytest.mark.asyncio
@patch("agentvault_registry.security.verify_access_token_required", new_callable=AsyncMock)
@patch("agentvault_registry.security.developer_crud.get_developer_by_id", new_callable=AsyncMock)
async def test_get_current_developer_success(
    mock_crud_get: AsyncMock,
    mock_verify_token: AsyncMock,
    mock_db_session: AsyncMock, # Use the fixture
    mock_developer: models.Developer
):
    """Test successfully getting the current developer."""
    mock_verify_token.return_value = mock_developer.id
    mock_crud_get.return_value = mock_developer

    # Call the dependency function directly, providing mocks for *its* dependencies
    developer = await security.get_current_developer(db=mock_db_session, developer_id=mock_developer.id)

    assert developer is mock_developer
    # verify_access_token_required is mocked at the top level, not called here directly
    mock_crud_get.assert_awaited_once_with(db=mock_db_session, developer_id=mock_developer.id)

@pytest.mark.asyncio
@patch("agentvault_registry.security.verify_access_token_required", new_callable=AsyncMock)
@patch("agentvault_registry.security.developer_crud.get_developer_by_id", new_callable=AsyncMock)
async def test_get_current_developer_not_found_in_db(
    mock_crud_get: AsyncMock,
    mock_verify_token: AsyncMock,
    mock_db_session: AsyncMock # Use the fixture
):
    """Test failure when developer ID from token is not found in DB."""
    test_id = 999
    mock_verify_token.return_value = test_id
    mock_crud_get.return_value = None # Developer not found

    with pytest.raises(HTTPException) as excinfo:
        await security.get_current_developer(db=mock_db_session, developer_id=test_id)

    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User associated with token not found" in excinfo.value.detail
    mock_crud_get.assert_awaited_once_with(db=mock_db_session, developer_id=test_id)

# --- Tests for get_current_developer_optional ---

@pytest.mark.asyncio
@patch("agentvault_registry.security.verify_access_token_optional", new_callable=AsyncMock)
@patch("agentvault_registry.security.developer_crud.get_developer_by_id", new_callable=AsyncMock)
async def test_get_current_developer_optional_success(
    mock_crud_get: AsyncMock,
    mock_verify_token_opt: AsyncMock,
    mock_db_session: AsyncMock, # Use the fixture
    mock_developer: models.Developer
):
    """Test successfully getting optional developer when token is valid."""
    mock_verify_token_opt.return_value = mock_developer.id
    mock_crud_get.return_value = mock_developer

    developer = await security.get_current_developer_optional(db=mock_db_session, developer_id=mock_developer.id)

    assert developer is mock_developer
    mock_crud_get.assert_awaited_once_with(db=mock_db_session, developer_id=mock_developer.id)

@pytest.mark.asyncio
@patch("agentvault_registry.security.verify_access_token_optional", new_callable=AsyncMock)
@patch("agentvault_registry.security.developer_crud.get_developer_by_id", new_callable=AsyncMock)
async def test_get_current_developer_optional_no_token(
    mock_crud_get: AsyncMock,
    mock_verify_token_opt: AsyncMock,
    mock_db_session: AsyncMock # Use the fixture
):
    """Test optional developer returns None when token is missing/invalid."""
    mock_verify_token_opt.return_value = None # Simulate no valid token

    developer = await security.get_current_developer_optional(db=mock_db_session, developer_id=None)

    assert developer is None
    mock_crud_get.assert_not_awaited() # DB should not be queried

@pytest.mark.asyncio
@patch("agentvault_registry.security.verify_access_token_optional", new_callable=AsyncMock)
@patch("agentvault_registry.security.developer_crud.get_developer_by_id", new_callable=AsyncMock)
async def test_get_current_developer_optional_not_in_db(
    mock_crud_get: AsyncMock,
    mock_verify_token_opt: AsyncMock,
    mock_db_session: AsyncMock # Use the fixture
):
    """Test optional developer returns None when token ID not found in DB."""
    test_id = 998
    mock_verify_token_opt.return_value = test_id
    mock_crud_get.return_value = None # Simulate DB miss

    developer = await security.get_current_developer_optional(db=mock_db_session, developer_id=test_id)

    assert developer is None
    mock_crud_get.assert_awaited_once_with(db=mock_db_session, developer_id=test_id)

# --- Tests for verify_programmatic_api_key ---

@pytest.mark.asyncio
@patch("agentvault_registry.security.developer_crud.get_developer_by_plain_api_key", new_callable=AsyncMock)
async def test_verify_programmatic_key_success(
    mock_crud_get_key: AsyncMock,
    mock_db_session: AsyncMock, # Use the fixture
    mock_developer: models.Developer
):
    """Test successful verification of a programmatic API key."""
    test_key = "avreg_test_key_123"
    mock_crud_get_key.return_value = mock_developer

    # Call directly, simulating Depends(api_key_header_scheme) providing the key
    developer = await security.verify_programmatic_api_key(api_key=test_key, db=mock_db_session)

    assert developer is mock_developer
    mock_crud_get_key.assert_awaited_once_with(db=mock_db_session, plain_key=test_key)

@pytest.mark.asyncio
async def test_verify_programmatic_key_missing():
    """Test failure when X-Api-Key header is missing."""
    # Call directly with api_key=None
    with pytest.raises(HTTPException) as excinfo:
        await security.verify_programmatic_api_key(api_key=None, db=MagicMock(spec=AsyncSession)) # DB mock needed for signature
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
    assert "X-Api-Key header missing" in excinfo.value.detail

@pytest.mark.asyncio
@patch("agentvault_registry.security.developer_crud.get_developer_by_plain_api_key", new_callable=AsyncMock)
async def test_verify_programmatic_key_invalid(
    mock_crud_get_key: AsyncMock,
    mock_db_session: AsyncMock # Use the fixture
):
    """Test failure when the provided API key is invalid or inactive."""
    test_key = "avreg_invalid_key_456"
    mock_crud_get_key.return_value = None # Simulate key not found/verified by CRUD

    with pytest.raises(HTTPException) as excinfo:
        await security.verify_programmatic_api_key(api_key=test_key, db=mock_db_session)

    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or inactive API Key" in excinfo.value.detail
    mock_crud_get_key.assert_awaited_once_with(db=mock_db_session, plain_key=test_key)
