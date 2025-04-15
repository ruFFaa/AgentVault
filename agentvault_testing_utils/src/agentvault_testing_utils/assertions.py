"""
Assertion helper functions for testing AgentVault A2A interactions.
"""

import json
import logging
from typing import Optional, Dict, Any, Union, List, Tuple, Sequence, Any
from unittest.mock import MagicMock, _Call

import httpx

logger = logging.getLogger(__name__)

def _parse_a2a_call(call_obj: Union[httpx.Request, Any]) -> Optional[Dict[str, Any]]:
    """
    Attempts to parse an httpx.Request or mock.call (_Call) into a JSON-RPC structure.

    Returns a dictionary with 'method', 'params', 'id' keys if successful,
    otherwise None.
    """
    payload = None
    try:
        if isinstance(call_obj, httpx.Request):
            if call_obj.content:
                payload = json.loads(call_obj.content)
        elif isinstance(call_obj, _Call):
            if 'json' in call_obj.kwargs and isinstance(call_obj.kwargs['json'], dict):
                 payload = call_obj.kwargs['json']
            elif 'json_payload' in call_obj.kwargs and isinstance(call_obj.kwargs['json_payload'], dict):
                 payload = call_obj.kwargs['json_payload']
            elif len(call_obj.args) > 0 and isinstance(call_obj.args[-1], dict):
                 payload = call_obj.args[-1]
            else:
                 logger.debug(f"Could not easily extract JSON-RPC payload from mock call object: {call_obj}")
                 return None
        else:
             logger.debug(f"Input to _parse_a2a_call is not httpx.Request or mock._Call: {type(call_obj)}")
             return None

        if payload and isinstance(payload, dict) and payload.get("jsonrpc") == "2.0":
            return {
                "method": payload.get("method"),
                "params": payload.get("params"),
                "id": payload.get("id"),
            }
        else:
            logger.debug(f"Payload is not a valid JSON-RPC 2.0 request: {payload}")
            return None
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to parse call object as JSON-RPC: {e} - Call: {call_obj!r}")
        return None

def assert_a2a_call(
    mock_calls: Union[Sequence[httpx.Request], MagicMock],
    method: str,
    params_contain: Optional[Dict] = None,
    req_id: Optional[Union[str, int]] = None,
    msg: Optional[str] = None
):
    """
    Asserts that at least one call in the list/mock matches the A2A criteria.
    # ... (rest of docstring unchanged) ...
    """
    found_match = False
    call_list: Sequence[Union[httpx.Request, Any]]

    if isinstance(mock_calls, MagicMock):
        call_list = mock_calls.call_args_list
    elif isinstance(mock_calls, (list, tuple)):
        call_list = mock_calls
    else:
        raise TypeError("mock_calls must be a list/tuple of httpx.Request or a MagicMock")

    parsed_calls_details = []
    has_parseable_calls = False # Track if *any* call could be parsed

    for i, call_obj in enumerate(call_list):
        parsed = _parse_a2a_call(call_obj)
        if not parsed:
            parsed_calls_details.append(f"  Call {i}: Could not parse as JSON-RPC. Object: {call_obj!r}")
            continue

        # If we reach here, at least one call was parseable
        has_parseable_calls = True
        parsed_calls_details.append(f"  Call {i}: method='{parsed['method']}', id='{parsed['id']}', params={str(parsed['params'])[:100]}...")

        # Check method
        if parsed.get("method") != method:
            continue
        # Check request ID if specified
        if req_id is not None and parsed.get("id") != req_id:
            continue
        # Check params if specified (subset check)
        if params_contain is not None:
            actual_params = parsed.get("params")
            if not isinstance(actual_params, dict): continue
            match = True
            for key, expected_value in params_contain.items():
                if key not in actual_params or actual_params[key] != expected_value:
                    match = False
                    break
            if not match: continue

        found_match = True
        break

    if not found_match:
        error_msg = msg or ""
        error_msg += (
            f"\nExpected A2A call not found:"
            f"\n  Method: '{method}'"
        )
        if req_id is not None: error_msg += f"\n  ID: '{req_id}'"
        if params_contain is not None: error_msg += f"\n  Params Containing: {params_contain}"

        # --- MODIFIED: Improve error message when no calls were parseable ---
        if not has_parseable_calls and call_list:
             error_msg += "\nActual calls found, but none were parseable as JSON-RPC:"
        elif parsed_calls_details:
             error_msg += "\nActual calls parsed:"
        else: # No calls provided at all
             error_msg += "\n(No calls provided in mock_calls)"

        if parsed_calls_details:
             error_msg += "\n" + "\n".join(parsed_calls_details)
        # --- END MODIFIED ---

        raise AssertionError(error_msg)


def assert_a2a_sequence(
    mock_calls: Union[Sequence[httpx.Request], MagicMock],
    expected_sequence: List[Tuple[str, Optional[Dict]]],
    msg: Optional[str] = None
):
    """
    Asserts that the sequence of A2A calls matches the expected sequence.
    # ... (rest of docstring unchanged) ...
    """
    call_list: Sequence[Union[httpx.Request, Any]]

    if isinstance(mock_calls, MagicMock):
        call_list = mock_calls.call_args_list
    elif isinstance(mock_calls, (list, tuple)):
        call_list = mock_calls
    else:
        raise TypeError("mock_calls must be a list/tuple of httpx.Request or a MagicMock")

    parseable_calls = []
    for call_obj in call_list:
        parsed = _parse_a2a_call(call_obj)
        if parsed:
            parseable_calls.append(parsed)

    if len(parseable_calls) != len(expected_sequence):
        error_msg = msg or ""
        error_msg += (
            f"\nExpected sequence length {len(expected_sequence)}, but found {len(parseable_calls)} parseable A2A calls."
            f"\nExpected sequence: {expected_sequence}"
            f"\nActual parsed calls: {parseable_calls}"
        )
        raise AssertionError(error_msg)

    for i, (actual_parsed, expected_tuple) in enumerate(zip(parseable_calls, expected_sequence)):
        expected_method, expected_params_contain = expected_tuple

        actual_method = actual_parsed.get("method")
        if actual_method != expected_method:
            error_msg = msg or ""
            error_msg += (
                f"\nSequence mismatch at index {i}:"
                f"\n  Expected Method: '{expected_method}'"
                f"\n  Actual Method:   '{actual_method}'"
                f"\nFull Actual Call: {actual_parsed}"
            )
            raise AssertionError(error_msg)

        if expected_params_contain is not None:
            actual_params = actual_parsed.get("params")
            if not isinstance(actual_params, dict):
                 error_msg = msg or ""
                 error_msg += (
                     f"\nSequence mismatch at index {i} (Method: '{actual_method}'):"
                     f"\n  Expected Params Contain: {expected_params_contain}"
                     f"\n  Actual Params are not a dictionary: {actual_params!r}"
                 )
                 raise AssertionError(error_msg)

            match = True
            missing_keys = []
            mismatched_values = []
            for key, expected_value in expected_params_contain.items():
                if key not in actual_params:
                    match = False
                    missing_keys.append(key)
                elif actual_params[key] != expected_value:
                    match = False
                    mismatched_values.append((key, expected_value, actual_params[key]))

            if not match:
                error_msg = msg or ""
                error_msg += (
                    f"\nSequence mismatch at index {i} (Method: '{actual_method}'):"
                    f"\n  Expected Params Contain: {expected_params_contain}"
                    f"\n  Actual Params: {actual_params}"
                )
                if missing_keys: error_msg += f"\n  Missing Keys: {missing_keys}"
                if mismatched_values: error_msg += f"\n  Mismatched Values: {mismatched_values}"
                raise AssertionError(error_msg)
