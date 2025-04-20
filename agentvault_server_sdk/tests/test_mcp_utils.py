import pytest
from unittest.mock import MagicMock, patch # Added patch
import logging # Added logging
import importlib # Added importlib
import sys # Added sys

# Import the function to test
# Need to import the module itself to reload it after patching
from agentvault_server_sdk import mcp_utils

# Import or mock the Message model
try:
    from agentvault.models import Message, TextPart
    _MODELS_AVAILABLE = True
except ImportError:
    # Create a mock class that mimics the structure needed for the tests
    class MockTextPart:
        def __init__(self, content):
            self.type = "text"
            self.content = content
    class MockMessage:
        def __init__(self, role="user", parts=None, metadata=None):
            self.role = role
            self.parts = parts if parts is not None else [MockTextPart(content="test")]
            self.metadata = metadata
    Message = MockMessage # type: ignore
    TextPart = MockTextPart # type: ignore
    _MODELS_AVAILABLE = False


# --- Helper to create a valid Message instance ---
def create_test_message(**kwargs):
    """Creates a Message instance with default required fields."""
    # Provide defaults for required fields if not overridden
    defaults = {
        "role": "user",
        "parts": [TextPart(content="test content")]
    }
    # Merge defaults with provided kwargs
    final_kwargs = {**defaults, **kwargs}
    # Only use real model if available, otherwise use mock
    if _MODELS_AVAILABLE:
        return Message(**final_kwargs)
    else:
        # If using mock, directly assign attributes
        mock_msg = Message()
        for k, v in final_kwargs.items():
            setattr(mock_msg, k, v)
        return mock_msg


# --- Test Cases ---

def test_get_mcp_context_success():
    """Test extracting valid MCP context."""
    mcp_data = {"user_id": "123", "session_info": {"theme": "dark"}}
    # Use the helper to create a valid message
    message = create_test_message(metadata={"other_key": "value", "mcp_context": mcp_data})
    result = mcp_utils.get_mcp_context(message)
    assert result == mcp_data

def test_get_mcp_context_no_metadata():
    """Test message with no metadata attribute."""
    # Mock a message object that doesn't even have the attribute
    message_no_meta = MagicMock(spec=Message)
    # Ensure the spec includes required fields if needed by other parts of the code
    message_no_meta.role = "user"
    message_no_meta.parts = [TextPart(content="test")]
    # Remove metadata specifically for this test
    # Use try-except in case the attribute doesn't exist on the mock spec
    try:
        del message_no_meta.metadata
    except AttributeError:
        pass
    # Also set it to None just in case del didn't work as expected on the mock
    message_no_meta.metadata = None

    result = mcp_utils.get_mcp_context(message_no_meta)
    assert result is None

def test_get_mcp_context_metadata_is_none():
    """Test message where metadata attribute exists but is None."""
    # Use the helper
    message = create_test_message(metadata=None)
    result = mcp_utils.get_mcp_context(message)
    assert result is None

def test_get_mcp_context_metadata_not_dict():
    """Test message where metadata is not a dictionary."""
    # --- MODIFIED: Use MagicMock to bypass Message validation ---
    # Create a mock object that *looks* like a Message but allows invalid metadata type
    message_mock = MagicMock(spec=Message)
    message_mock.role = "user"
    message_mock.parts = [TextPart(content="test")]
    message_mock.metadata = ["list", "is", "not", "dict"] # Assign the invalid type
    # --- END MODIFIED ---
    result = mcp_utils.get_mcp_context(message_mock) # Pass the mock object
    assert result is None

def test_get_mcp_context_key_missing():
    """Test message with metadata dictionary but missing 'mcp_context' key."""
    # Use the helper
    message = create_test_message(metadata={"other_key": "value", "another": 123})
    result = mcp_utils.get_mcp_context(message)
    assert result is None

def test_get_mcp_context_value_not_dict():
    """Test message where 'mcp_context' value is not a dictionary."""
    # Use the helper
    message = create_test_message(metadata={"mcp_context": "this is a string, not a dict"})
    result = mcp_utils.get_mcp_context(message)
    assert result is None

def test_get_mcp_context_empty_dict_value():
    """Test message where 'mcp_context' value is an empty dictionary."""
    # Use the helper
    message = create_test_message(metadata={"mcp_context": {}})
    result = mcp_utils.get_mcp_context(message)
    assert result == {}

# --- ADDED: Test for import fallback ---
def test_get_mcp_context_import_error(monkeypatch, caplog):
    """Test get_mcp_context when core models cannot be imported."""
    # Simulate ImportError by temporarily removing the module
    # Use monkeypatch for cleaner sys.modules manipulation
    monkeypatch.setitem(sys.modules, 'agentvault.models', None)

    # Reload the module under test to trigger the import error handling
    importlib.reload(mcp_utils)

    # Create a dummy message (doesn't need real structure as import failed,
    # but needs the 'metadata' attribute for the function logic)
    mcp_payload = {"data": 1}
    dummy_message = MagicMock()
    dummy_message.metadata = {"mcp_context": mcp_payload}

    with caplog.at_level(logging.ERROR):
        result = mcp_utils.get_mcp_context(dummy_message) # Call the reloaded function

    # --- MODIFIED: Assert result is extracted correctly despite import error ---
    assert result == mcp_payload # Function should still work via duck typing
    # --- END MODIFIED ---
    assert "Failed to import Message model from 'agentvault'" in caplog.text

    # Clean up - restore the module if it was originally present
    # This might be needed if other tests in the same session rely on it
    monkeypatch.delitem(sys.modules, 'agentvault.models', raising=False)
    # Force reload again to restore normal state for subsequent tests
    importlib.reload(mcp_utils)
# --- END ADDED ---
