import pytest
import logging
from agentvault.mcp_utils import format_mcp_context, MCPContext, MCPItem

# --- Test Data ---

def valid_mcp_input_data_full():
    """Provides a dictionary representing a valid, populated MCPContext structure."""
    return {
        "items": {
            "item1": {
                "id": "id-001",
                "mediaType": "text/plain",
                "content": "This is text content.",
                "metadata": {"source": "user"}
            },
            "item2": {
                "ref": "file://path/to/data.csv",
                "mediaType": "text/csv"
            }
        }
        # Add global_metadata if defined in MCPContext model
    }

def valid_mcp_input_data_empty_items():
    """Provides a dictionary representing a valid MCPContext with an empty items dict."""
    return {"items": {}}

def invalid_mcp_input_missing_items():
    """Provides a dictionary missing the required 'items' key, but with other keys."""
    # Pydantic v2 ignores extra fields by default, so this *should* validate
    # and items should get its default value.
    return {"some_other_key": "value"}

def invalid_mcp_input_wrong_items_type():
    """Provides a dictionary where 'items' is not a dictionary."""
    return {"items": ["item1", "item2"]}

def invalid_mcp_input_item_structure():
    """Provides a dictionary where an item has an invalid structure (e.g., wrong type)."""
    return {
        "items": {
            "bad_item": {
                "mediaType": 123 # Invalid type
            }
        }
    }

# --- Test Cases for format_mcp_context ---

def test_format_mcp_context_valid_full():
    """Test formatting with a valid, populated input dictionary."""
    input_data = valid_mcp_input_data_full()
    # --- ADJUSTED EXPECTED OUTPUT ---
    # model_dump(exclude_unset=True) will not include None fields unless set
    expected_output = {
        "items": {
            "item1": {
                "id": "id-001",
                "mediaType": "text/plain",
                "content": "This is text content.",
                # ref is None, so excluded by exclude_unset=True
                "metadata": {"source": "user"}
            },
            "item2": {
                # id is None, so excluded
                "mediaType": "text/csv",
                # content is None, so excluded
                "ref": "file://path/to/data.csv",
                # metadata is None, so excluded
            }
        }
    }
    result = format_mcp_context(input_data)
    assert result == expected_output

def test_format_mcp_context_valid_empty_items():
    """Test formatting with a valid input dictionary having an empty 'items' dict."""
    input_data = valid_mcp_input_data_empty_items()
    # Since 'items' was explicitly provided (even if empty), it should be included.
    expected_output = {"items": {}}
    result = format_mcp_context(input_data)
    assert result == expected_output

def test_format_mcp_context_valid_empty_dict():
    """Test formatting with an empty input dictionary."""
    # Pydantic adds the default 'items', but exclude_unset removes it during dump
    input_data = {}
    # --- ADJUSTED EXPECTED OUTPUT ---
    expected_output = {} # items={} is default and wasn't set, so excluded
    result = format_mcp_context(input_data)
    assert result == expected_output

def test_format_mcp_context_invalid_structure_missing_items(caplog):
    """Test with input missing 'items' but having other keys (Pydantic ignores extra)."""
    # Pydantic v2 ignores extra fields by default, so validation succeeds.
    # 'items' gets its default value {}, which is then excluded by exclude_unset.
    input_data = invalid_mcp_input_missing_items()
    with caplog.at_level(logging.ERROR):
        result = format_mcp_context(input_data)
    # --- ADJUSTED ASSERTION ---
    assert result == {} # Should return empty dict as validation passes, items default excluded
    # No error should be logged in this specific case with default Pydantic settings
    assert "Failed to validate or format MCP context data" not in caplog.text


def test_format_mcp_context_invalid_structure_wrong_items_type(caplog):
    """Test with input where 'items' is not a dictionary."""
    input_data = invalid_mcp_input_wrong_items_type()
    with caplog.at_level(logging.ERROR):
        result = format_mcp_context(input_data)
    assert result is None
    assert "Failed to validate or format MCP context data" in caplog.text
    assert "Input should be a valid dictionary" in caplog.text # Check for Pydantic validation error message

def test_format_mcp_context_invalid_item_structure(caplog):
    """Test with input where an item within 'items' has an invalid structure."""
    input_data = invalid_mcp_input_item_structure()
    with caplog.at_level(logging.ERROR):
        result = format_mcp_context(input_data)
    assert result is None
    assert "Failed to validate or format MCP context data" in caplog.text
    # Check for specific Pydantic error about mediaType type
    assert "Input should be a valid string" in caplog.text or "type=string_type" in caplog.text

def test_format_mcp_context_invalid_input_type_list(caplog):
    """Test with input that is not a dictionary (list)."""
    input_data = ["item1", "item2"]
    with caplog.at_level(logging.ERROR):
        result = format_mcp_context(input_data) # type: ignore # Intentionally passing wrong type
    assert result is None
    assert "MCP context data must be a dictionary" in caplog.text

def test_format_mcp_context_invalid_input_type_string(caplog):
    """Test with input that is not a dictionary (string)."""
    input_data = "just a string"
    with caplog.at_level(logging.ERROR):
        result = format_mcp_context(input_data) # type: ignore # Intentionally passing wrong type
    assert result is None
    assert "MCP context data must be a dictionary" in caplog.text

def test_format_mcp_context_invalid_input_type_none(caplog):
    """Test with None input."""
    input_data = None
    with caplog.at_level(logging.ERROR):
        result = format_mcp_context(input_data) # type: ignore # Intentionally passing wrong type
    assert result is None
    assert "MCP context data must be a dictionary" in caplog.text
