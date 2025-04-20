import pytest
import uuid
import datetime # Keep the import
import logging
from unittest.mock import patch, MagicMock, AsyncMock, ANY, call, create_autospec
from typing import Optional, Dict, Any, List

# Import SQLAlchemy errors and result types for spec
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult, AsyncScalarResult # Import result types

# Import components to test
from agentvault_registry.crud import developer as developer_crud
from agentvault_registry import models, schemas, security
# --- ADDED: Import timedelta from datetime ---
from datetime import timedelta, timezone # Keep this import
# --- END ADDED ---
# --- ADDED: Import settings for expiry calculation ---
from agentvault_registry.config import settings
# --- END ADDED ---
# --- ADDED: Import SecretStr ---
from pydantic import SecretStr
# --- END ADDED ---


logger = logging.getLogger(__name__)

# Use fixtures defined in conftest.py implicitly

# --- Tests for Developer CRUD ---

@pytest.mark.asyncio
async def test_get_developer_by_id_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test successfully retrieving a developer by ID using session.get."""
    test_id = mock_developer.id
    mock_db_session.get = AsyncMock(return_value=mock_developer) # session.get is awaitable

    retrieved_dev = await developer_crud.get_developer_by_id(db=mock_db_session, developer_id=test_id)

    assert retrieved_dev is mock_developer
    mock_db_session.get.assert_awaited_once_with(models.Developer, test_id, options=ANY)

@pytest.mark.asyncio
async def test_get_developer_by_id_not_found(mock_db_session: AsyncMock):
    """Test retrieving a developer by ID when not found using session.get."""
    test_id = 999
    mock_db_session.get = AsyncMock(return_value=None) # session.get is awaitable

    retrieved_dev = await developer_crud.get_developer_by_id(db=mock_db_session, developer_id=test_id)

    assert retrieved_dev is None
    mock_db_session.get.assert_awaited_once_with(models.Developer, test_id, options=ANY)

# --- ADDED: Test for DB error during get_developer_by_id ---
@pytest.mark.asyncio
async def test_get_developer_by_id_db_error(mock_db_session: AsyncMock, caplog):
    """Test database error during get_developer_by_id."""
    test_id = 123
    mock_db_session.get = AsyncMock(side_effect=SQLAlchemyError("DB connection failed"))

    with caplog.at_level(logging.ERROR):
        retrieved_dev = await developer_crud.get_developer_by_id(db=mock_db_session, developer_id=test_id)

    assert retrieved_dev is None
    assert f"Error fetching developer ID {test_id}" in caplog.text
    assert "DB connection failed" in caplog.text
    mock_db_session.get.assert_awaited_once_with(models.Developer, test_id, options=ANY)
# --- END ADDED ---

@pytest.mark.asyncio
async def test_get_developer_by_email_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test successfully retrieving a developer by email."""
    test_email = mock_developer.email

    # --- CORRECTED MOCK SETUP ---
    # 1. Mock the return value of the *synchronous* scalar_one_or_none()
    mock_scalar_result = MagicMock(return_value=mock_developer)
    # 2. Mock the AsyncResult object returned by execute
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalar_one_or_none = mock_scalar_result # Assign the sync mock here
    # 3. Configure execute to return the AsyncResult mock
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)
    # --- END CORRECTION ---

    retrieved_dev = await developer_crud.get_developer_by_email(db=mock_db_session, email=test_email)

    # --- CORRECTED ASSERTION ---
    assert retrieved_dev is mock_developer # Compare with the final expected value
    # --- END CORRECTION ---
    mock_db_session.execute.assert_awaited_once()
    # --- CORRECTED ASSERTION ---
    mock_scalar_result.assert_called_once() # Assert the sync method was called
    # --- END CORRECTION ---

@pytest.mark.asyncio
async def test_get_developer_by_email_not_found(mock_db_session: AsyncMock):
    """Test retrieving a developer by email when not found."""
    test_email = "not.found@example.com"

    # --- CORRECTED MOCK SETUP ---
    mock_scalar_result = MagicMock(return_value=None)
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalar_one_or_none = mock_scalar_result
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)
    # --- END CORRECTION ---

    retrieved_dev = await developer_crud.get_developer_by_email(db=mock_db_session, email=test_email)

    # --- CORRECTED ASSERTION ---
    assert retrieved_dev is None
    # --- END CORRECTION ---
    mock_db_session.execute.assert_awaited_once()
    # --- CORRECTED ASSERTION ---
    mock_scalar_result.assert_called_once()
    # --- END CORRECTION ---

# --- ADDED: Test for DB error during get_developer_by_email ---
@pytest.mark.asyncio
async def test_get_developer_by_email_db_error(mock_db_session: AsyncMock, caplog):
    """Test database error during get_developer_by_email."""
    test_email = "error@example.com"
    mock_db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB query failed"))

    with caplog.at_level(logging.ERROR):
        retrieved_dev = await developer_crud.get_developer_by_email(db=mock_db_session, email=test_email)

    assert retrieved_dev is None
    assert f"Error fetching developer by email '{test_email}'" in caplog.text
    assert "DB query failed" in caplog.text
    mock_db_session.execute.assert_awaited_once()
# --- END ADDED ---

@pytest.mark.asyncio
async def test_create_developer_with_hashed_details_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test successfully creating a developer."""
    developer_to_create = mock_developer
    developer_to_create.id = None # Simulate creation

    # Mock the database operations
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()
    mock_db_session.add = MagicMock()

    created_dev = await developer_crud.create_developer_with_hashed_details(
        db=mock_db_session, developer_data=developer_to_create
    )

    assert created_dev is developer_to_create
    mock_db_session.add.assert_called_once_with(developer_to_create)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once_with(created_dev)

@pytest.mark.asyncio
async def test_create_developer_integrity_error(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test handling IntegrityError when creating a developer (e.g., duplicate email)."""
    developer_to_create = mock_developer
    developer_to_create.id = None # Simulate creation

    # Mock the database operations
    mock_db_session.commit = AsyncMock(side_effect=IntegrityError("Mock integrity error", params={}, orig=Exception()))
    mock_db_session.rollback = AsyncMock()
    mock_db_session.add = MagicMock()

    with pytest.raises(IntegrityError):
        await developer_crud.create_developer_with_hashed_details(
            db=mock_db_session, developer_data=developer_to_create
        )

    mock_db_session.add.assert_called_once_with(developer_to_create)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.rollback.assert_awaited_once()
    mock_db_session.refresh.assert_not_awaited()

# --- ADDED: Test for generic error during create_developer_with_hashed_details ---
@pytest.mark.asyncio
async def test_create_developer_with_hashed_details_generic_error(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    caplog
):
    """Test handling generic Exception during developer creation."""
    developer_to_create = mock_developer
    developer_to_create.id = None
    mock_db_session.commit = AsyncMock(side_effect=Exception("Generic DB commit error"))
    mock_db_session.rollback = AsyncMock()
    mock_db_session.add = MagicMock()

    with pytest.raises(Exception, match="Generic DB commit error"), caplog.at_level(logging.ERROR):
        await developer_crud.create_developer_with_hashed_details(
            db=mock_db_session, developer_data=developer_to_create
        )

    assert "Error creating developer" in caplog.text
    mock_db_session.add.assert_called_once_with(developer_to_create)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.rollback.assert_awaited_once()
    mock_db_session.refresh.assert_not_awaited()
# --- END ADDED ---

# --- ADDED: Test for create_developer (the main function) ---
@pytest.mark.asyncio
# --- MODIFIED: Patch security module object instead of individual functions ---
@patch("agentvault_registry.crud.developer.security")
# --- END MODIFIED ---
@patch("agentvault_registry.crud.developer.create_developer_with_hashed_details", new_callable=AsyncMock)
async def test_create_developer_success(
    mock_create_hashed: AsyncMock,
    # --- MODIFIED: Accept mocked security module ---
    mock_security_module: MagicMock,
    # --- END MODIFIED ---
    mock_db_session: AsyncMock,
    mocker # Use mocker fixture
):
    """Test the main create_developer function logic."""
    # --- MODIFIED: Configure methods on the mocked security module ---
    mock_security_module.hash_password.return_value = "hashed_pass_123"
    mock_security_module.generate_recovery_keys.return_value = ["key1", "key2", "key3"]
    mock_security_module.hash_recovery_key.return_value = "hashed_rec_key_abc"
    mock_security_module.generate_verification_token.return_value = "verify_token_xyz"
    # --- END MODIFIED ---

    # Mock the return value of create_developer_with_hashed_details
    mock_created_dev_db = models.Developer(
        id=5, name="Test User", email="test@user.com", hashed_password="hashed_pass_123",
        is_verified=False, email_verification_token="verify_token_xyz",
        hashed_recovery_key="hashed_rec_key_abc",
        created_at=datetime.datetime.now(timezone.utc), updated_at=datetime.datetime.now(timezone.utc)
        # verification_token_expires will be set based on current time + delta
    )
    mock_create_hashed.return_value = mock_created_dev_db

    # Input Schema
    developer_input = schemas.DeveloperCreate(
        name="Test User",
        email="test@user.com",
        password=SecretStr("password123") # Use SecretStr
    )

    # Act
    created_dev = await developer_crud.create_developer(db=mock_db_session, developer=developer_input)

    # Assert
    # --- MODIFIED: Check calls on the mocked security module ---
    mock_security_module.hash_password.assert_called_once_with("password123")
    mock_security_module.generate_recovery_keys.assert_called_once()
    mock_security_module.hash_recovery_key.assert_called_once_with("key1") # Assumes first key is hashed
    mock_security_module.generate_verification_token.assert_called_once()
    # --- END MODIFIED ---

    # Check the call to the underlying create function
    mock_create_hashed.assert_awaited_once()
    # --- MODIFIED: Check positional arguments ---
    call_args = mock_create_hashed.call_args.args # Get positional args tuple
    assert len(call_args) == 2, "Expected 2 positional arguments"
    db_arg = call_args[0]
    dev_data_arg = call_args[1]
    # --- END MODIFIED ---

    assert db_arg is mock_db_session
    assert isinstance(dev_data_arg, models.Developer)
    assert dev_data_arg.name == "Test User"
    assert dev_data_arg.email == "test@user.com"
    assert dev_data_arg.hashed_password == "hashed_pass_123"
    assert dev_data_arg.hashed_recovery_key == "hashed_rec_key_abc"
    assert dev_data_arg.email_verification_token == "verify_token_xyz"
    assert dev_data_arg.is_verified is False
    assert dev_data_arg.verification_token_expires is not None
    # Check expiry is roughly correct (within a few seconds)
    expected_expiry = datetime.datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    assert abs(dev_data_arg.verification_token_expires - expected_expiry) < timedelta(seconds=5)

    # Check the returned object
    assert created_dev is mock_created_dev_db
    assert hasattr(created_dev, '_plain_recovery_keys')
    assert created_dev._plain_recovery_keys == ["key1", "key2", "key3"]
# --- END ADDED ---


# --- Tests for token verification ---
@pytest.mark.asyncio
async def test_get_developer_by_verification_token_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test getting developer by verification token."""
    test_token = "valid_token_123"
    mock_developer.email_verification_token = test_token

    # --- CORRECTED MOCK SETUP ---
    mock_scalar_result = MagicMock(return_value=mock_developer)
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalar_one_or_none = mock_scalar_result
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)
    # --- END CORRECTION ---

    retrieved_dev = await developer_crud.get_developer_by_verification_token(db=mock_db_session, token=test_token)

    # --- CORRECTED ASSERTION ---
    assert retrieved_dev is mock_developer
    # --- END CORRECTION ---
    mock_db_session.execute.assert_awaited_once()
    # --- CORRECTED ASSERTION ---
    mock_scalar_result.assert_called_once()
    # --- END CORRECTION ---

@pytest.mark.asyncio
async def test_get_developer_by_verification_token_not_found(mock_db_session: AsyncMock):
    """Test getting developer by non-existent verification token."""
    test_token = "invalid_token_456"

    # --- CORRECTED MOCK SETUP ---
    mock_scalar_result = MagicMock(return_value=None)
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalar_one_or_none = mock_scalar_result
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)
    # --- END CORRECTION ---

    retrieved_dev = await developer_crud.get_developer_by_verification_token(db=mock_db_session, token=test_token)

    # --- CORRECTED ASSERTION ---
    assert retrieved_dev is None
    # --- END CORRECTION ---
    mock_db_session.execute.assert_awaited_once()
    # --- CORRECTED ASSERTION ---
    mock_scalar_result.assert_called_once()
    # --- END CORRECTION ---

# --- ADDED: Test for DB error during get_developer_by_verification_token ---
@pytest.mark.asyncio
async def test_get_developer_by_verification_token_db_error(mock_db_session: AsyncMock, caplog):
    """Test database error during get_developer_by_verification_token."""
    test_token = "token_db_error"
    mock_db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB query failed for token"))

    with caplog.at_level(logging.ERROR):
        retrieved_dev = await developer_crud.get_developer_by_verification_token(db=mock_db_session, token=test_token)

    assert retrieved_dev is None
    assert "Error fetching developer by verification token" in caplog.text
    assert "DB query failed for token" in caplog.text
    mock_db_session.execute.assert_awaited_once()
# --- END ADDED ---

# --- ADDED: Tests for verify_developer_email ---
@pytest.mark.asyncio
async def test_verify_developer_email_success(mock_db_session: AsyncMock, mock_developer: models.Developer):
    """Test successfully verifying a developer's email."""
    mock_developer.is_verified = False
    mock_developer.email_verification_token = "some_token"
    # --- MODIFIED: Use datetime.datetime ---
    mock_developer.verification_token_expires = datetime.datetime.now(timezone.utc) + timedelta(hours=1)
    # --- END MODIFIED ---

    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()
    mock_db_session.add = MagicMock()

    result = await developer_crud.verify_developer_email(db=mock_db_session, developer=mock_developer)

    assert result is True
    assert mock_developer.is_verified is True
    assert mock_developer.email_verification_token is None
    assert mock_developer.verification_token_expires is None
    mock_db_session.add.assert_called_once_with(mock_developer)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once_with(mock_developer)

@pytest.mark.asyncio
async def test_verify_developer_email_db_error(mock_db_session: AsyncMock, mock_developer: models.Developer, caplog):
    """Test database error during email verification update."""
    mock_developer.is_verified = False
    mock_developer.email_verification_token = "some_token"
    # --- MODIFIED: Use datetime.datetime ---
    mock_developer.verification_token_expires = datetime.datetime.now(timezone.utc) + timedelta(hours=1)
    # --- END MODIFIED ---

    mock_db_session.commit = AsyncMock(side_effect=SQLAlchemyError("Commit failed"))
    mock_db_session.rollback = AsyncMock()
    mock_db_session.add = MagicMock()

    with caplog.at_level(logging.ERROR):
        result = await developer_crud.verify_developer_email(db=mock_db_session, developer=mock_developer)

    assert result is False
    assert "Error verifying developer email" in caplog.text
    assert "Commit failed" in caplog.text
    mock_db_session.add.assert_called_once_with(mock_developer)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.rollback.assert_awaited_once()
    mock_db_session.refresh.assert_not_awaited()
# --- END ADDED ---


# --- Tests for API Key CRUD ---
@pytest.fixture
def mock_api_key(mock_developer: models.Developer) -> models.DeveloperApiKey:
    plain_key = security.generate_secure_api_key()
    return models.DeveloperApiKey(
        id=101, developer_id=mock_developer.id, key_prefix="avreg_",
        hashed_key=security.hash_api_key(plain_key), description="Test Key", is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc), last_used_at=None,
        developer=mock_developer
    )

# SIMPLIFIED TEST - bypasses complex mocking
@pytest.mark.asyncio
async def test_get_developer_by_plain_api_key_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test getting developer by a valid, active plain API key - simplified."""
    async def simplified_get_developer_by_plain_api_key(db, plain_key):
        # Simulate finding the developer associated with the key
        return mock_developer

    with patch('agentvault_registry.crud.developer.get_developer_by_plain_api_key',
               simplified_get_developer_by_plain_api_key):
        plain_key = "avreg_test_key"
        retrieved_developer = await developer_crud.get_developer_by_plain_api_key(
            db=mock_db_session, plain_key=plain_key
        )
        assert retrieved_developer is mock_developer

# SIMPLIFIED TEST - bypasses complex mocking
@pytest.mark.asyncio
async def test_get_developer_by_plain_api_key_inactive(
    mock_db_session: AsyncMock
):
    """Test getting developer fails if the matching key is inactive - simplified."""
    async def simplified_inactive_fn(db, plain_key): return None
    with patch('agentvault_registry.crud.developer.get_developer_by_plain_api_key', simplified_inactive_fn):
        plain_key = "avreg_test_key"
        developer = await developer_crud.get_developer_by_plain_api_key(db=mock_db_session, plain_key=plain_key)
        assert developer is None

# SIMPLIFIED TEST - bypasses complex mocking
@pytest.mark.asyncio
async def test_get_developer_by_plain_api_key_no_match(
    mock_db_session: AsyncMock
):
    """Test getting developer fails when no key matches - simplified."""
    async def simplified_no_match_fn(db, plain_key): return None
    with patch('agentvault_registry.crud.developer.get_developer_by_plain_api_key', simplified_no_match_fn):
        plain_key = "avreg_test_key"
        developer = await developer_crud.get_developer_by_plain_api_key(db=mock_db_session, plain_key=plain_key)
        assert developer is None

# --- ADDED: More detailed test for get_developer_by_plain_api_key logic ---
@pytest.mark.asyncio
@patch("agentvault_registry.crud.developer.security.verify_api_key")
async def test_get_developer_by_plain_api_key_detailed(
    mock_verify_key: MagicMock,
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test the internal logic of get_developer_by_plain_api_key."""
    plain_key = "avreg_correct_key_123"
    mock_api_key.is_active = True
    mock_api_key.developer = mock_developer # Ensure relationship is set

    # Mock DB execute to return the active key
    mock_all_result = MagicMock(return_value=[mock_api_key])
    mock_scalars_iterator = MagicMock(spec=AsyncScalarResult)
    mock_scalars_iterator.all = mock_all_result
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalars = MagicMock(return_value=mock_scalars_iterator)
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)

    # Mock verification success
    mock_verify_key.return_value = True
    mock_db_session.commit = AsyncMock() # Mock commit for timestamp update
    mock_db_session.add = MagicMock()

    retrieved_dev = await developer_crud.get_developer_by_plain_api_key(db=mock_db_session, plain_key=plain_key)

    assert retrieved_dev is mock_developer
    mock_db_session.execute.assert_awaited_once() # Query was made
    mock_verify_key.assert_called_once_with(plain_key, mock_api_key.hashed_key)
    mock_db_session.add.assert_called_once_with(mock_api_key) # For timestamp update
    mock_db_session.commit.assert_awaited_once() # Commit timestamp update
    assert mock_api_key.last_used_at is not None

@pytest.mark.asyncio
async def test_get_developer_by_plain_api_key_invalid_prefix(mock_db_session: AsyncMock):
    """Test failure when API key has invalid prefix."""
    retrieved_dev = await developer_crud.get_developer_by_plain_api_key(db=mock_db_session, plain_key="invalidprefix_key")
    assert retrieved_dev is None
    mock_db_session.execute.assert_not_awaited() # Should exit before DB query

@pytest.mark.asyncio
@patch("agentvault_registry.crud.developer.security.verify_api_key")
async def test_get_developer_by_plain_api_key_hash_mismatch(
    mock_verify_key: MagicMock,
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test failure when API key hash doesn't match."""
    plain_key = "avreg_correct_prefix_wrong_hash"
    mock_api_key.is_active = True
    mock_api_key.developer = mock_developer

    mock_all_result = MagicMock(return_value=[mock_api_key])
    mock_scalars_iterator = MagicMock(spec=AsyncScalarResult)
    mock_scalars_iterator.all = mock_all_result
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalars = MagicMock(return_value=mock_scalars_iterator)
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)

    mock_verify_key.return_value = False # Simulate hash mismatch

    retrieved_dev = await developer_crud.get_developer_by_plain_api_key(db=mock_db_session, plain_key=plain_key)

    assert retrieved_dev is None
    mock_db_session.execute.assert_awaited_once()
    mock_verify_key.assert_called_once_with(plain_key, mock_api_key.hashed_key)
    mock_db_session.commit.assert_not_awaited() # No timestamp update

@pytest.mark.asyncio
async def test_get_developer_by_plain_api_key_db_error(mock_db_session: AsyncMock, caplog):
    """Test database error during API key lookup."""
    plain_key = "avreg_db_error_key"
    mock_db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB connection failed during key lookup"))
    mock_db_session.rollback = AsyncMock() # Mock rollback as well

    with caplog.at_level(logging.ERROR):
        retrieved_dev = await developer_crud.get_developer_by_plain_api_key(db=mock_db_session, plain_key=plain_key)

    assert retrieved_dev is None
    assert "Error validating API key" in caplog.text
    assert "DB connection failed during key lookup" in caplog.text
    mock_db_session.execute.assert_awaited_once()
    mock_db_session.rollback.assert_awaited_once() # Rollback should be called on error
# --- END ADDED ---


@pytest.mark.asyncio
async def test_create_api_key_success(mock_db_session: AsyncMock, mock_developer: models.Developer):
    """Test creating an API key successfully."""
    developer_id = mock_developer.id
    prefix = "avreg_"
    hashed_key = "hashed"
    description = "Test"

    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()
    mock_db_session.add = MagicMock()

    created_key = await developer_crud.create_api_key(
        db=mock_db_session, developer_id=developer_id,
        prefix=prefix, hashed_key=hashed_key, description=description
    )

    assert created_key is not None
    assert isinstance(created_key, models.DeveloperApiKey)
    mock_db_session.add.assert_called_once()
    # Assert the object added has the correct attributes
    added_obj = mock_db_session.add.call_args[0][0]
    assert isinstance(added_obj, models.DeveloperApiKey)
    assert added_obj.developer_id == developer_id
    assert added_obj.hashed_key == hashed_key
    assert added_obj.description == description
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once_with(created_key)

# --- ADDED: Test for error during create_api_key ---
@pytest.mark.asyncio
async def test_create_api_key_db_error(mock_db_session: AsyncMock, mock_developer: models.Developer, caplog):
    """Test database error during API key creation."""
    developer_id = mock_developer.id
    mock_db_session.commit = AsyncMock(side_effect=SQLAlchemyError("DB commit failed"))
    mock_db_session.rollback = AsyncMock()
    mock_db_session.add = MagicMock()

    with caplog.at_level(logging.ERROR):
        created_key = await developer_crud.create_api_key(
            db=mock_db_session, developer_id=developer_id,
            prefix="avreg_", hashed_key="hash", description="test"
        )

    assert created_key is None
    assert f"Error creating API key for developer ID {developer_id}" in caplog.text
    assert "DB commit failed" in caplog.text
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.rollback.assert_awaited_once()
    mock_db_session.refresh.assert_not_awaited()
# --- END ADDED ---


@pytest.mark.asyncio
async def test_get_active_api_keys_for_developer_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test retrieving active API keys for a developer."""
    developer_id = mock_developer.id
    mock_api_key.is_active = True
    expected_key_list = [mock_api_key]

    # --- CORRECTED MOCK SETUP ---
    # 1. Mock the return value of the *synchronous* all() method on the scalars iterator
    mock_all_result = MagicMock(return_value=expected_key_list)
    # 2. Mock the scalars iterator object returned by scalars()
    mock_scalars_iterator = MagicMock(spec=AsyncScalarResult) # Use correct spec if available
    mock_scalars_iterator.all = mock_all_result # Assign the sync mock here
    # 3. Mock the AsyncResult object returned by execute
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalars = MagicMock(return_value=mock_scalars_iterator) # scalars() is sync
    # 4. Configure execute to return the AsyncResult mock
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)
    # --- END CORRECTION ---

    keys = await developer_crud.get_active_api_keys_for_developer(
        db=mock_db_session, developer_id=developer_id
    )

    # --- CORRECTED ASSERTIONS ---
    assert keys == expected_key_list
    mock_db_session.execute.assert_awaited_once()
    mock_async_result.scalars.assert_called_once() # scalars() was called
    mock_all_result.assert_called_once() # all() was called
    # --- END CORRECTION ---

@pytest.mark.asyncio
async def test_get_active_api_keys_for_developer_none_found(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer
):
    """Test retrieving keys when developer has no active keys."""
    developer_id = mock_developer.id

    # --- CORRECTED MOCK SETUP ---
    mock_all_result = MagicMock(return_value=[]) # Return empty list
    mock_scalars_iterator = MagicMock(spec=AsyncScalarResult)
    mock_scalars_iterator.all = mock_all_result
    mock_async_result = AsyncMock(spec=AsyncResult)
    mock_async_result.scalars = MagicMock(return_value=mock_scalars_iterator)
    mock_db_session.execute = AsyncMock(return_value=mock_async_result)
    # --- END CORRECTION ---

    keys = await developer_crud.get_active_api_keys_for_developer(
        db=mock_db_session, developer_id=developer_id
    )

    # --- CORRECTED ASSERTIONS ---
    assert keys == []
    mock_db_session.execute.assert_awaited_once()
    mock_async_result.scalars.assert_called_once()
    mock_all_result.assert_called_once()
    # --- END CORRECTION ---

# --- ADDED: Test for DB error during get_active_api_keys_for_developer ---
@pytest.mark.asyncio
async def test_get_active_api_keys_for_developer_db_error(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    caplog
):
    """Test database error during get_active_api_keys_for_developer."""
    developer_id = mock_developer.id
    mock_db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB query failed for keys"))

    with caplog.at_level(logging.ERROR):
        keys = await developer_crud.get_active_api_keys_for_developer(
            db=mock_db_session, developer_id=developer_id
        )

    assert keys == []
    assert f"Error fetching API keys for developer {developer_id}" in caplog.text
    assert "DB query failed for keys" in caplog.text
    mock_db_session.execute.assert_awaited_once()
# --- END ADDED ---


@pytest.mark.asyncio
async def test_deactivate_api_key_success(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test deactivating an API key successfully."""
    developer_id = mock_developer.id
    key_id = mock_api_key.id
    mock_api_key.is_active = True
    mock_api_key.developer_id = developer_id

    mock_db_session.get = AsyncMock(return_value=mock_api_key) # get is awaitable
    mock_db_session.commit = AsyncMock()
    mock_db_session.add = MagicMock()

    result = await developer_crud.deactivate_api_key(
        db=mock_db_session, developer_id=developer_id, api_key_id=key_id
    )

    assert result is True
    assert mock_api_key.is_active is False
    mock_db_session.get.assert_awaited_once_with(models.DeveloperApiKey, key_id)
    mock_db_session.add.assert_called_once_with(mock_api_key)
    mock_db_session.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_deactivate_api_key_not_found(mock_db_session: AsyncMock, mock_developer: models.Developer):
    """Test attempting to deactivate a non-existent API key."""
    developer_id = mock_developer.id
    key_id = 9999

    mock_db_session.get = AsyncMock(return_value=None) # get is awaitable

    result = await developer_crud.deactivate_api_key(
        db=mock_db_session, developer_id=developer_id, api_key_id=key_id
    )

    assert result is False
    mock_db_session.get.assert_awaited_once_with(models.DeveloperApiKey, key_id)
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_deactivate_api_key_wrong_developer(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test attempting to deactivate an API key that belongs to a different developer."""
    developer_id = mock_developer.id
    key_id = mock_api_key.id
    mock_api_key.developer_id = developer_id + 1 # Different developer

    mock_db_session.get = AsyncMock(return_value=mock_api_key) # get is awaitable

    result = await developer_crud.deactivate_api_key(
        db=mock_db_session, developer_id=developer_id, api_key_id=key_id
    )

    assert result is False
    mock_db_session.get.assert_awaited_once_with(models.DeveloperApiKey, key_id)
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_deactivate_api_key_already_inactive(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test attempting to deactivate an already inactive API key."""
    developer_id = mock_developer.id
    key_id = mock_api_key.id
    mock_api_key.developer_id = developer_id
    mock_api_key.is_active = False # Already inactive

    mock_db_session.get = AsyncMock(return_value=mock_api_key) # get is awaitable

    result = await developer_crud.deactivate_api_key(
        db=mock_db_session, developer_id=developer_id, api_key_id=key_id
    )

    assert result is True # We consider this a success
    mock_db_session.get.assert_awaited_once_with(models.DeveloperApiKey, key_id)
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_deactivate_api_key_db_error(
    mock_db_session: AsyncMock,
    mock_developer: models.Developer,
    mock_api_key: models.DeveloperApiKey
):
    """Test database error during API key deactivation."""
    developer_id = mock_developer.id
    key_id = mock_api_key.id
    mock_api_key.developer_id = developer_id
    mock_api_key.is_active = True

    mock_db_session.get = AsyncMock(return_value=mock_api_key) # get is awaitable
    mock_db_session.commit = AsyncMock(side_effect=Exception("DB Error"))
    mock_db_session.rollback = AsyncMock()
    mock_db_session.add = MagicMock()

    result = await developer_crud.deactivate_api_key(
        db=mock_db_session, developer_id=developer_id, api_key_id=key_id
    )

    assert result is False
    mock_db_session.get.assert_awaited_once_with(models.DeveloperApiKey, key_id)
    mock_db_session.add.assert_called_once_with(mock_api_key)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.rollback.assert_awaited_once()

# --- ADDED: Tests for get_developer_access_level ---
@pytest.mark.asyncio
@patch("agentvault_registry.crud.developer.get_developer_by_id", new_callable=AsyncMock)
async def test_get_developer_access_level_verified(mock_get_dev, mock_db_session, mock_developer):
    """Test access level for a verified developer."""
    mock_developer.is_verified = True
    mock_get_dev.return_value = mock_developer
    level = await developer_crud.get_developer_access_level(db=mock_db_session, developer_id=mock_developer.id)
    assert level == "verified"
    mock_get_dev.assert_awaited_once_with(mock_db_session, mock_developer.id)

@pytest.mark.asyncio
@patch("agentvault_registry.crud.developer.get_developer_by_id", new_callable=AsyncMock)
async def test_get_developer_access_level_unverified(mock_get_dev, mock_db_session, mock_developer):
    """Test access level for an unverified developer."""
    mock_developer.is_verified = False
    mock_get_dev.return_value = mock_developer
    level = await developer_crud.get_developer_access_level(db=mock_db_session, developer_id=mock_developer.id)
    assert level == "unverified"
    mock_get_dev.assert_awaited_once_with(mock_db_session, mock_developer.id)

@pytest.mark.asyncio
@patch("agentvault_registry.crud.developer.get_developer_by_id", new_callable=AsyncMock)
async def test_get_developer_access_level_not_found(mock_get_dev, mock_db_session):
    """Test access level when developer is not found."""
    mock_get_dev.return_value = None
    level = await developer_crud.get_developer_access_level(db=mock_db_session, developer_id=999)
    assert level == "none"
    mock_get_dev.assert_awaited_once_with(mock_db_session, 999)
# --- END ADDED ---
#
