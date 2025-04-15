import pytest
import json
from typing import Optional, Dict, Any, Union, List, Tuple, Sequence, Any
from unittest.mock import MagicMock, call as mock_call, _Call # Import _Call
import httpx
import pydantic
from pydantic_core import ValidationError

# Import the functions to test
from agentvault_testing_utils.assertions import assert_a2a_call, assert_a2a_sequence, _parse_a2a_call

# --- Helper to create mock httpx.Request ---
def create_mock_request(method: str, params: Any = None, req_id: Any = 1) -> httpx.Request:
    payload = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        payload["params"] = params
    content = json.dumps(payload).encode('utf-8')
    # Ensure URL is absolute for httpx.Request
    return httpx.Request("POST", "http://test.com/a2a", content=content, headers={"Content-Type": "application/json"})

# --- Helper to create mock unittest.mock.call ---
def create_mock_magicmock_call(method: str, params: Any = None, req_id: Any = 1) -> mock_call:
    payload = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        payload["params"] = params
    return mock_call(json=payload)

# --- Tests for _parse_a2a_call ---

def test_parse_a2a_call_httpx_request():
    req = create_mock_request("tasks/send", {"id": "t1"}, req_id="req1")
    parsed = _parse_a2a_call(req)
    assert parsed == {"method": "tasks/send", "params": {"id": "t1"}, "id": "req1"}

def test_parse_a2a_call_magicmock_call():
    mc = create_mock_magicmock_call("tasks/get", {"id": "t2"}, req_id=2)
    parsed = _parse_a2a_call(mc)
    assert parsed == {"method": "tasks/get", "params": {"id": "t2"}, "id": 2}

def test_parse_a2a_call_invalid_json():
    req = httpx.Request("POST", "http://test.com/a2a", content=b"{invalid json")
    parsed = _parse_a2a_call(req)
    assert parsed is None

def test_parse_a2a_call_not_rpc():
    req = httpx.Request("POST", "http://test.com/a2a", json={"not": "rpc"})
    parsed = _parse_a2a_call(req)
    assert parsed is None

# --- Tests for assert_a2a_call ---

@pytest.fixture
def sample_httpx_calls() -> List[httpx.Request]:
    return [
        create_mock_request("tasks/send", {"id": None, "message": {"role": "user"}}, req_id="r1"),
        create_mock_request("tasks/get", {"id": "task-abc"}, req_id="r2"),
        create_mock_request("tasks/send", {"id": "task-abc", "message": {"role": "agent"}}, req_id="r3"),
    ]

@pytest.fixture
def sample_mock_calls() -> MagicMock:
    recorder = MagicMock()
    recorder.call_args_list = [
        create_mock_magicmock_call("tasks/send", {"id": None, "message": {"role": "user"}}, req_id="r1"),
        create_mock_magicmock_call("tasks/get", {"id": "task-abc"}, req_id="r2"),
        create_mock_magicmock_call("tasks/send", {"id": "task-abc", "message": {"role": "agent"}}, req_id="r3"),
    ]
    return recorder

# Success cases for assert_a2a_call
def test_assert_a2a_call_method_match_httpx(sample_httpx_calls):
    assert_a2a_call(sample_httpx_calls, method="tasks/get")

def test_assert_a2a_call_method_match_mock(sample_mock_calls):
    assert_a2a_call(sample_mock_calls, method="tasks/get")

def test_assert_a2a_call_method_params_match_httpx(sample_httpx_calls):
    assert_a2a_call(sample_httpx_calls, method="tasks/send", params_contain={"id": "task-abc"})
    assert_a2a_call(sample_httpx_calls, method="tasks/send", params_contain={"message": {"role": "agent"}})

def test_assert_a2a_call_method_params_match_mock(sample_mock_calls):
    assert_a2a_call(sample_mock_calls, method="tasks/send", params_contain={"id": "task-abc"})
    assert_a2a_call(sample_mock_calls, method="tasks/send", params_contain={"message": {"role": "agent"}})

def test_assert_a2a_call_method_id_match_httpx(sample_httpx_calls):
    assert_a2a_call(sample_httpx_calls, method="tasks/get", req_id="r2")

def test_assert_a2a_call_method_id_match_mock(sample_mock_calls):
    assert_a2a_call(sample_mock_calls, method="tasks/get", req_id="r2")

def test_assert_a2a_call_all_match_httpx(sample_httpx_calls):
    assert_a2a_call(sample_httpx_calls, method="tasks/send", params_contain={"id": None}, req_id="r1")

def test_assert_a2a_call_all_match_mock(sample_mock_calls):
    assert_a2a_call(sample_mock_calls, method="tasks/send", params_contain={"id": None}, req_id="r1")

# Failure cases for assert_a2a_call
def test_assert_a2a_call_method_mismatch(sample_httpx_calls):
    with pytest.raises(AssertionError, match="Expected A2A call not found:\n  Method: 'tasks/cancel'"):
        assert_a2a_call(sample_httpx_calls, method="tasks/cancel")

def test_assert_a2a_call_params_mismatch(sample_httpx_calls):
    with pytest.raises(AssertionError, match=r"Params Containing: \{'id': 'task-xyz'\}"):
        assert_a2a_call(sample_httpx_calls, method="tasks/get", params_contain={"id": "task-xyz"})

def test_assert_a2a_call_params_key_missing(sample_httpx_calls):
    with pytest.raises(AssertionError, match=r"Params Containing: \{'nonexistent': True\}"):
        assert_a2a_call(sample_httpx_calls, method="tasks/get", params_contain={"nonexistent": True})

def test_assert_a2a_call_id_mismatch(sample_httpx_calls):
    with pytest.raises(AssertionError, match="ID: 'r99'"):
        assert_a2a_call(sample_httpx_calls, method="tasks/get", req_id="r99")

def test_assert_a2a_call_no_calls():
    with pytest.raises(AssertionError, match="Expected A2A call not found"):
        assert_a2a_call([], method="tasks/send")

def test_assert_a2a_call_no_parseable_calls():
    calls = [httpx.Request("POST", "http://test.com/a2a", content=b"invalid")]
    # --- MODIFIED: Check for the correct substring ---
    with pytest.raises(AssertionError) as excinfo:
        assert_a2a_call(calls, method="tasks/send")
    assert "Actual calls found, but none were parseable as JSON-RPC" in str(excinfo.value)
    # --- END MODIFIED ---


# --- Tests for assert_a2a_sequence ---

@pytest.fixture
def expected_sequence() -> List[Tuple[str, Optional[Dict]]]:
    return [
        ("tasks/send", {"id": None}),
        ("tasks/get", {"id": "task-abc"}),
        ("tasks/send", {"id": "task-abc", "message": {"role": "agent"}}),
    ]

# Success cases for assert_a2a_sequence
def test_assert_a2a_sequence_match_httpx(sample_httpx_calls, expected_sequence):
    assert_a2a_sequence(sample_httpx_calls, expected_sequence)

def test_assert_a2a_sequence_match_mock(sample_mock_calls, expected_sequence):
    assert_a2a_sequence(sample_mock_calls, expected_sequence)

def test_assert_a2a_sequence_match_no_params(sample_httpx_calls):
    expected = [("tasks/send", None), ("tasks/get", None), ("tasks/send", None)]
    assert_a2a_sequence(sample_httpx_calls, expected)

# Failure cases for assert_a2a_sequence
def test_assert_a2a_sequence_length_mismatch(sample_httpx_calls, expected_sequence):
    with pytest.raises(AssertionError, match="Expected sequence length 2, but found 3 parseable A2A calls."):
        assert_a2a_sequence(sample_httpx_calls, expected_sequence[:-1])

    with pytest.raises(AssertionError, match="Expected sequence length 4, but found 3 parseable A2A calls."):
        assert_a2a_sequence(sample_httpx_calls, expected_sequence + [("tasks/cancel", None)])

def test_assert_a2a_sequence_method_mismatch(sample_httpx_calls, expected_sequence):
    bad_sequence = [expected_sequence[0], ("tasks/cancel", {"id": "task-abc"}), expected_sequence[2]]
    with pytest.raises(AssertionError, match="Sequence mismatch at index 1:\n  Expected Method: 'tasks/cancel'\n  Actual Method:   'tasks/get'"):
        assert_a2a_sequence(sample_httpx_calls, bad_sequence)

def test_assert_a2a_sequence_params_mismatch(sample_httpx_calls, expected_sequence):
    bad_sequence = [expected_sequence[0], ("tasks/get", {"id": "task-wrong"}), expected_sequence[2]]
    with pytest.raises(AssertionError, match=r"Sequence mismatch at index 1 \(Method: 'tasks/get'\):"):
        assert_a2a_sequence(sample_httpx_calls, bad_sequence)

def test_assert_a2a_sequence_params_missing_key(sample_httpx_calls, expected_sequence):
    bad_sequence = [expected_sequence[0], ("tasks/get", {"id": "task-abc", "extra": True}), expected_sequence[2]]
    with pytest.raises(AssertionError, match=r"Missing Keys: \['extra'\]"):
        assert_a2a_sequence(sample_httpx_calls, bad_sequence)
