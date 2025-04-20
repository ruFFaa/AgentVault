import pytest

# Import the exceptions to test
from agentvault.exceptions import AgentCardFetchError, A2ARemoteAgentError

# --- Tests for AgentCardFetchError ---

def test_agent_card_fetch_error_str_message_only():
    """Test __str__ with only a message."""
    msg = "Failed to fetch card."
    exc = AgentCardFetchError(message=msg)
    assert str(exc) == msg

def test_agent_card_fetch_error_str_with_status_code():
    """Test __str__ with message and status code."""
    msg = "Not found."
    status_code = 404
    exc = AgentCardFetchError(message=msg, status_code=status_code)
    expected_str = f"{msg} (status_code={status_code})"
    assert str(exc) == expected_str

def test_agent_card_fetch_error_str_with_response_body_str():
    """Test __str__ with message and string response body."""
    msg = "Server error."
    response_body = "Internal Server Error Text"
    exc = AgentCardFetchError(message=msg, response_body=response_body)
    expected_str = f"{msg} (response_body='{response_body}')" # repr adds quotes
    assert str(exc) == expected_str

def test_agent_card_fetch_error_str_with_response_body_dict():
    """Test __str__ with message and dict response body."""
    msg = "Validation failed."
    response_body = {"detail": "field required", "loc": ["name"]}
    exc = AgentCardFetchError(message=msg, response_body=response_body)
    expected_str = f"{msg} (response_body={{'detail': 'field required', 'loc': ['name']}})"
    assert str(exc) == expected_str

def test_agent_card_fetch_error_str_with_all_details():
    """Test __str__ with message, status code, and response body."""
    msg = "Bad request."
    status_code = 400
    response_body = {"error": "invalid_input"}
    exc = AgentCardFetchError(message=msg, status_code=status_code, response_body=response_body)
    expected_str = f"{msg} (status_code={status_code}, response_body={{'error': 'invalid_input'}})"
    assert str(exc) == expected_str

def test_agent_card_fetch_error_str_long_response_body():
    """Test __str__ truncates long response bodies."""
    msg = "Long error response."
    long_body = "x" * 200
    exc = AgentCardFetchError(message=msg, response_body=long_body)
    str_repr = str(exc)
    assert str_repr.startswith(msg) # Check it starts with the base message
    assert "(response_body='" in str_repr # Check the body part is included
    # --- MODIFIED: Correct endswith assertion for string repr ---
    assert str_repr.endswith("...)") # Check it ends with ellipsis and closing parenthesis
    # --- END MODIFIED ---
    assert len(str_repr) < len(msg) + 150 # Check it's significantly shorter than full body

# --- Tests for A2ARemoteAgentError ---

def test_a2a_remote_agent_error_str_message_only():
    """Test __str__ with only a message."""
    msg = "Agent processing failed."
    exc = A2ARemoteAgentError(message=msg)
    assert str(exc) == msg

def test_a2a_remote_agent_error_str_with_status_code():
    """Test __str__ with message and status code."""
    msg = "Task execution error."
    status_code = -32000 # Example JSON-RPC app error code
    exc = A2ARemoteAgentError(message=msg, status_code=status_code)
    expected_str = f"{msg} (status_code={status_code})"
    assert str(exc) == expected_str

def test_a2a_remote_agent_error_str_with_response_body_str():
    """Test __str__ with message and string response body."""
    msg = "Agent side error."
    response_body = "Detailed error trace from agent"
    exc = A2ARemoteAgentError(message=msg, response_body=response_body)
    expected_str = f"{msg} (response_body='{response_body}')"
    assert str(exc) == expected_str

def test_a2a_remote_agent_error_str_with_response_body_dict():
    """Test __str__ with message and dict response body."""
    msg = "Invalid parameters received by agent."
    response_body = {"error_code": "INVALID_INPUT", "field": "prompt"}
    exc = A2ARemoteAgentError(message=msg, response_body=response_body)
    expected_str = f"{msg} (response_body={{'error_code': 'INVALID_INPUT', 'field': 'prompt'}})"
    assert str(exc) == expected_str

def test_a2a_remote_agent_error_str_with_all_details():
    """Test __str__ with message, status code, and response body."""
    msg = "Authentication failed on agent."
    status_code = 401
    response_body = {"detail": "Missing API key"}
    exc = A2ARemoteAgentError(message=msg, status_code=status_code, response_body=response_body)
    expected_str = f"{msg} (status_code={status_code}, response_body={{'detail': 'Missing API key'}})"
    assert str(exc) == expected_str

def test_a2a_remote_agent_error_str_long_response_body():
    """Test __str__ truncates long response bodies."""
    msg = "Agent returned lengthy data."
    long_body = list(range(200)) # Example long list
    exc = A2ARemoteAgentError(message=msg, response_body=long_body)
    str_repr = str(exc)
    assert str_repr.startswith(f"{msg} (response_body=[0, 1, 2,") # Check start
    assert str_repr.endswith("...)") # Check it ends with ellipsis and closing parenthesis (no bracket)
    assert len(str_repr) < len(msg) + 150 # Check it's truncated
