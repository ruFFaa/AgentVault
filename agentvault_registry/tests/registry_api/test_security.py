import pytest
import secrets
import bcrypt # Import bcrypt for direct tests if needed

# Import functions to test
from agentvault_registry.security import (
    verify_password,
    hash_password,
    verify_api_key,
    hash_api_key,
    verify_recovery_key,
    hash_recovery_key,
    generate_secure_api_key,
    generate_recovery_keys,
    # Import JWT functions later when testing them
    # create_access_token,
    # verify_access_token_required,
    # verify_access_token_optional,
    # verify_temp_password_token,
)

# --- Tests for Password Hashing/Verification ---

def test_hash_password_creates_valid_hash():
    """Test that hash_password returns a string that looks like a bcrypt hash."""
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert isinstance(hashed, str)
    # Basic bcrypt hash structure check
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60 # Standard bcrypt hash length

def test_verify_password_success():
    """Test successful password verification."""
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True

def test_verify_password_failure_wrong_password():
    """Test password verification failure with incorrect password."""
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert verify_password("wrongpassword", hashed) is False

def test_verify_password_failure_invalid_hash():
    """Test password verification failure with an invalid hash format."""
    password = "mysecretpassword"
    invalid_hash = "not_a_real_hash"
    # passlib should handle invalid hash format gracefully and return False
    assert verify_password(password, invalid_hash) is False

# --- Tests for API Key Hashing/Verification (using passlib context) ---

def test_hash_api_key_creates_valid_hash():
    """Test that hash_api_key returns a bcrypt hash via passlib."""
    api_key = "avreg_some_random_key_string_123"
    hashed = hash_api_key(api_key)
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60

def test_verify_api_key_success():
    """Test successful API key verification using passlib context."""
    api_key = "avreg_another_random_key_456"
    hashed = hash_api_key(api_key)
    assert verify_api_key(api_key, hashed) is True

def test_verify_api_key_failure_wrong_key():
    """Test API key verification failure with incorrect key."""
    api_key = "avreg_secret_key_789"
    hashed = hash_api_key(api_key)
    assert verify_api_key("avreg_wrong_key_000", hashed) is False

def test_verify_api_key_failure_invalid_hash():
    """Test API key verification failure with invalid hash format."""
    api_key = "avreg_some_key"
    invalid_hash = "not_a_bcrypt_hash"
    assert verify_api_key(api_key, invalid_hash) is False

# --- Tests for Recovery Key Hashing/Verification (using bcrypt directly) ---

def test_hash_recovery_key_creates_valid_hash():
    """Test that hash_recovery_key returns a bcrypt hash."""
    recovery_key = "avrec-abcd-1234-efgh"
    hashed = hash_recovery_key(recovery_key)
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60

def test_verify_recovery_key_success():
    """Test successful recovery key verification."""
    recovery_key = "avrec-test-success-key"
    hashed = hash_recovery_key(recovery_key)
    assert verify_recovery_key(recovery_key, hashed) is True

def test_verify_recovery_key_failure_wrong_key():
    """Test recovery key verification failure with incorrect key."""
    recovery_key = "avrec-original-key-set"
    hashed = hash_recovery_key(recovery_key)
    assert verify_recovery_key("avrec-wrong-key-attempt", hashed) is False

def test_verify_recovery_key_failure_invalid_hash():
    """Test recovery key verification failure with invalid hash."""
    recovery_key = "avrec-some-key"
    invalid_hash = "invalid_hash_string"
    # bcrypt checkpw should return False for invalid hash format
    assert verify_recovery_key(recovery_key, invalid_hash) is False

def test_hash_recovery_key_non_string_input():
    """Test that hashing non-string input raises TypeError."""
    with pytest.raises(TypeError, match="Recovery key must be a string"):
        hash_recovery_key(12345) # type: ignore

def test_verify_recovery_key_non_string_input():
    """Test that verifying non-string input returns False."""
    hashed = hash_recovery_key("a-real-key")
    assert verify_recovery_key(12345, hashed) is False # type: ignore
    assert verify_recovery_key("a-real-key", None) is False # type: ignore
    assert verify_recovery_key(None, hashed) is False # type: ignore


# --- Tests for Key Generation ---

def test_generate_secure_api_key_format():
    """Test the format of the generated programmatic API key."""
    key = generate_secure_api_key()
    assert isinstance(key, str)
    assert key.startswith("avreg_")
    # Check length is roughly correct (base64 encoding adds padding/variance)
    # Default length is 32 bytes -> ~43 base64 chars + prefix
    assert len(key) > (32 * 4 // 3) # Check it's roughly the expected length or more
    # Check it's URL safe (no spaces, +, / characters typically)
    assert " " not in key
    assert "+" not in key
    assert "/" not in key

def test_generate_secure_api_key_minimum_length():
    """Test that requesting a short length uses the minimum."""
    # Capture warnings if needed, though the function logs it
    key_short = generate_secure_api_key(length=10)
    key_min = generate_secure_api_key(length=24)
    # Check length is based on the minimum enforced length (24 bytes -> ~32 base64 chars)
    assert len(key_short) >= (24 * 4 // 3)
    assert len(key_min) >= (24 * 4 // 3)

def test_generate_recovery_keys_count():
    """Test that the correct number of recovery keys are generated."""
    keys_default = generate_recovery_keys()
    assert len(keys_default) == 3

    keys_custom = generate_recovery_keys(count=5)
    assert len(keys_custom) == 5

def test_generate_recovery_keys_format():
    """Test the format of generated recovery keys."""
    keys = generate_recovery_keys(count=2)
    assert len(keys) == 2
    for key in keys:
        assert isinstance(key, str)
        assert key.startswith("avrec-")
        parts = key.split('-')
        # Expecting prefix, hex, hex, hex
        assert len(parts) == 4
        assert parts[0] == "avrec"
        assert len(parts[1]) == 8 # 4 bytes -> 8 hex chars
        assert len(parts[2]) == 8
        assert len(parts[3]) == 8
        # Check they are hex characters
        assert all(c in '0123456789abcdef' for c in parts[1])
        assert all(c in '0123456789abcdef' for c in parts[2])
        assert all(c in '0123456789abcdef' for c in parts[3])

# --- Tests for JWT functions will be added later ---
# --- Tests for FastAPI dependencies will be added later ---
