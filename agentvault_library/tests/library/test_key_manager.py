import pytest
import os
import json
import pathlib
import logging
from unittest.mock import MagicMock, call, patch, ANY # Keep ANY if used

# Import the class and exception to test
# Use absolute import based on src being in pythonpath
from agentvault.key_manager import KeyManager, KeyManagementError
# Import dotenv specifically for mocking if needed for complex file tests
# import dotenv # Not strictly needed if just mocking read_text

# --- Fixtures ---

# Mock the keyring module *before* KeyManager is potentially imported by tests
# This ensures that any check within KeyManager sees the mock from the start.
@pytest.fixture(autouse=True)
def mock_keyring_module(mocker):
    # Mock the module itself where it's imported within key_manager.py
    mock_keyring = MagicMock()
    mock_keyring.get_password = MagicMock(return_value=None)
    mock_keyring.set_password = MagicMock()
    mock_keyring.get_keyring = MagicMock() # Mock the functional check call
    mocker.patch('agentvault.key_manager.keyring', mock_keyring, create=True) # Use create=True if module might not exist yet
    # Also mock the import check flag if tests rely on it
    mocker.patch('agentvault.key_manager._keyring_imported', True, create=True)
    return mock_keyring

@pytest.fixture
def mock_keyring_not_installed(mocker):
    # Simulate import failure
    mocker.patch('agentvault.key_manager.keyring', None)
    mocker.patch('agentvault.key_manager._keyring_imported', False)
    # No need to mock get_keyring here as the import fails first

# --- Test __init__ ---

# Use mocker fixture directly instead of patch decorator for spies if issues persist
def test_key_manager_init_defaults(mocker):
    # Spy on the methods *after* ensuring the class can be instantiated
    spy_load_file = mocker.spy(KeyManager, "_load_from_file")
    spy_load_env = mocker.spy(KeyManager, "_load_from_env")

    # Instantiate the class with default arguments
    km = KeyManager() # key_file_path is None by default

    # Assertions
    assert km.key_file_path is None
    assert km.use_env_vars is True
    assert km.use_keyring is False # Should be false by default, even if lib installed
    assert km.env_prefix == "AGENTVAULT_KEY_"
    assert km._keys == {}
    assert km._key_sources == {}
    # Check methods were called during init
    # --- MODIFIED: Assert _load_from_file is NOT called by default ---
    spy_load_file.assert_not_called()
    # --- END MODIFIED ---
    spy_load_env.assert_called_once_with(km) # Env loading should happen by default

def test_key_manager_init_custom_params(tmp_path, mocker):
    spy_load_file = mocker.spy(KeyManager, "_load_from_file")
    spy_load_env = mocker.spy(KeyManager, "_load_from_env")
    mock_functional_check = mocker.patch('agentvault.key_manager.keyring.get_keyring') # Mock check

    key_file = tmp_path / "keys.json"
    km = KeyManager(key_file_path=key_file, use_env_vars=False, use_keyring=True, env_prefix="MYAPP_")

    assert km.key_file_path == key_file.resolve()
    assert km.use_env_vars is False
    assert km.use_keyring is True # Should be true now as mock check passes
    assert km.env_prefix == "MYAPP_"
    # --- MODIFIED: Assert _load_from_file IS called when path provided ---
    spy_load_file.assert_called_once_with(km)
    # --- END MODIFIED ---
    spy_load_env.assert_not_called() # use_env_vars is False
    mock_functional_check.assert_called_once() # Check that the functional check was attempted

def test_key_manager_init_keyring_warning(mock_keyring_not_installed, caplog):
    # Test the warning when keyring package isn't installed
    with caplog.at_level(logging.WARNING):
        km = KeyManager(use_keyring=True)
    assert km.use_keyring is False
    assert "Keyring usage requested, but 'keyring' package is not installed" in caplog.text

def test_key_manager_init_keyring_backend_fail(mocker, caplog):
    # Test the warning when keyring import works but backend fails
    mock_keyring = MagicMock()
    mock_keyring.get_keyring = MagicMock(side_effect=Exception("Backend unavailable"))
    mocker.patch('agentvault.key_manager.keyring', mock_keyring, create=True)
    mocker.patch('agentvault.key_manager._keyring_imported', True, create=True)

    with caplog.at_level(logging.WARNING):
        km = KeyManager(use_keyring=True)

    assert km.use_keyring is False
    assert "Keyring library imported but backend failed to initialize" in caplog.text
    assert "Backend unavailable" in caplog.text


# --- Test _load_from_env ---

# Patch os.environ directly for env var tests
@patch.dict(os.environ, {
    "AGENTVAULT_KEY_SERVICE1": "key1_value",
    "AGENTVAULT_KEY_SERVICE2_UPPER": "key2_value",
    "OTHER_VAR": "not_a_key",
    "AGENTVAULT_KEY_": "empty_id_key",
    "AGENTVAULT_KEY_EMPTYVAL": ""
}, clear=True) # clear=True ensures only these vars exist for the test
def test_load_from_env_success(mocker):
    # Prevent file loading from interfering
    mocker.patch.object(KeyManager, "_load_from_file")
    km = KeyManager(use_env_vars=True, key_file_path=None) # Ensure no file path
    assert km._keys == {"service1": "key1_value", "service2_upper": "key2_value"}
    assert km._key_sources == {"service1": "env", "service2_upper": "env"}

@patch.dict(os.environ, {"AGENTVAULT_KEY_SERVICE1": "env_key"}, clear=True)
def test_load_from_env_priority(mocker):
    # Prevent file loading
    mocker.patch.object(KeyManager, "_load_from_file")
    # Manually set a pre-existing key as if loaded from file
    km = KeyManager(use_env_vars=False) # Init without env loading first
    km._keys["service1"] = "file_key"
    km._key_sources["service1"] = "file"
    # Now enable env loading and call the method
    km.use_env_vars = True
    km._load_from_env()
    # Assert the file key was not overwritten
    assert km._keys["service1"] == "file_key"
    assert km._key_sources["service1"] == "file"


# --- Test _load_from_file ---

# Use patch from unittest.mock for Path methods
@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.read_text")
def test_load_from_file_env_success(mock_read_text, mock_is_file, mock_exists, tmp_path, mocker):
    key_file = tmp_path / "keys.env"
    # Mock dotenv_values directly where it's used
    mock_dotenv = mocker.patch(
        "agentvault.key_manager.dotenv_values",
        return_value={'SERVICE_A': 'key_a_file', 'service_b_lower': 'key_b_file', 'EMPTY_KEY': '', 'NO_VALUE_KEY': None}
    )

    km = KeyManager(key_file_path=key_file, use_env_vars=False) # Disable env loading

    mock_dotenv.assert_called_once_with(key_file.resolve(), stream=None, verbose=False)
    assert km._keys == {"service_a": "key_a_file", "service_b_lower": "key_b_file"}
    assert km._key_sources == {"service_a": "file", "service_b_lower": "file"}

@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.read_text")
def test_load_from_file_json_success(mock_read_text, mock_is_file, mock_exists, tmp_path, mocker):
    key_file = tmp_path / "keys.json"
    json_content = {"service_c": "key_c_json", "SERVICE_D_UPPER": "key_d_json", "not_a_string": 123, "empty_string": ""}
    mock_read_text.return_value = json.dumps(json_content)

    km = KeyManager(key_file_path=key_file, use_env_vars=False)

    mock_read_text.assert_called_once_with(encoding='utf-8')
    assert km._keys == {"service_c": "key_c_json", "service_d_upper": "key_d_json"}
    assert km._key_sources == {"service_c": "file", "service_d_upper": "file"}

# --- Test Keyring Methods (using the autouse mock_keyring_module fixture) ---

def test_load_from_keyring_disabled(mock_keyring_module):
    # Keyring module is mocked, but we instantiate KM with use_keyring=False
    km = KeyManager(use_keyring=False)
    assert km.use_keyring is False
    # Call the internal method directly for testing isolation
    assert km._load_from_keyring("service1") is None
    mock_keyring_module.get_password.assert_not_called() # Should not attempt access

def test_load_from_keyring_not_installed(mock_keyring_not_installed):
    # Fixture simulates import failure
    km = KeyManager(use_keyring=True) # Request keyring
    assert km.use_keyring is False # Init should detect it's not available
    assert km._load_from_keyring("service1") is None

def test_load_from_keyring_success(mock_keyring_module):
    mock_keyring_module.get_password.return_value = "keyring_secret"
    km = KeyManager(use_keyring=True)
    assert km.use_keyring is True # Init check should pass with mock
    key = km._load_from_keyring("service_kr") # Call internal method
    assert key == "keyring_secret"
    mock_keyring_module.get_password.assert_called_once_with("agentvault:service_kr", "service_kr")
    # Check internal state NOT updated by _load_from_keyring itself
    assert "service_kr" not in km._keys

def test_load_from_keyring_not_found(mock_keyring_module):
    mock_keyring_module.get_password.return_value = None
    km = KeyManager(use_keyring=True)
    key = km._load_from_keyring("service_missing")
    assert key is None
    mock_keyring_module.get_password.assert_called_once_with("agentvault:service_missing", "service_missing")

def test_load_from_keyring_exception(mock_keyring_module, caplog):
    mock_keyring_module.get_password.side_effect = Exception("Keyring backend error")
    km = KeyManager(use_keyring=True)
    with caplog.at_level(logging.ERROR):
        key = km._load_from_keyring("service_err")
    assert key is None
    assert "Failed to get key for service 'service_err' from keyring: Keyring backend error" in caplog.text

def test_set_key_in_keyring_success(mock_keyring_module):
    km = KeyManager(use_keyring=True)
    km.set_key_in_keyring("SetMe", "new_value")
    mock_keyring_module.set_password.assert_called_once_with("agentvault:setme", "setme", "new_value")

def test_set_key_in_keyring_disabled():
    km = KeyManager(use_keyring=False)
    with pytest.raises(KeyManagementError, match="Keyring support is not enabled or non-functional"):
        km.set_key_in_keyring("SetMe", "new_value")

def test_set_key_in_keyring_not_installed(mock_keyring_not_installed):
    km = KeyManager(use_keyring=True) # Request it
    assert km.use_keyring is False # But init disables it
    with pytest.raises(KeyManagementError, match="Keyring support is not enabled or non-functional"):
        km.set_key_in_keyring("SetMe", "new_value")

def test_set_key_in_keyring_exception(mock_keyring_module):
    mock_keyring_module.set_password.side_effect = Exception("Keyring backend error")
    km = KeyManager(use_keyring=True)
    with pytest.raises(KeyManagementError, match="Failed to set key in keyring"):
        km.set_key_in_keyring("SetErr", "value")

# --- Test get_key (Combined Logic) ---

# Use parametrize to test different sources
@pytest.mark.parametrize("file_content, env_vars, keyring_return, expected_key, expected_source", [
    # Only file
    ("FILE_KEY=file_val", {}, None, "file_val", "file"),
    # Only env
    (None, {"AGENTVAULT_KEY_ENV_KEY": "env_val"}, None, "env_val", "env"),
    # Only keyring
    (None, {}, "keyring_val", "keyring_val", "keyring"),
    # File overrides Env
    ("FILE_KEY=file_val", {"AGENTVAULT_KEY_FILE_KEY": "env_val"}, None, "file_val", "file"),
    # File overrides Keyring (Keyring not checked if file found)
    ("FILE_KEY=file_val", {}, "keyring_val", "file_val", "file"),
    # Env overrides Keyring (Keyring not checked if env found)
    (None, {"AGENTVAULT_KEY_ENV_KEY": "env_val"}, "keyring_val", "env_val", "env"),
    # Keyring used when others missing
    (None, {}, "keyring_val", "keyring_val", "keyring"),
    # Not found anywhere
    (None, {}, None, None, None),
    # Case insensitivity
    ("UPPER_KEY=file_val", {}, None, "file_val", "file"),
])
def test_get_key_priority_and_sources(
    tmp_path, monkeypatch, mocker, mock_keyring_module,
    file_content, env_vars, keyring_return, expected_key, expected_source
):
    # Setup file if needed
    key_file = None
    if file_content:
        key_file = tmp_path / "test_get.env"
        key_file.write_text(file_content)

    # Setup environment variables using patch.dict for isolation
    with patch.dict(os.environ, env_vars, clear=True):
        # Setup keyring mock
        mock_keyring_module.get_password.return_value = keyring_return

        # Instantiate KeyManager
        # Determine if keyring should be considered enabled for this test run
        keyring_enabled_for_test = (keyring_return is not None) or (expected_source == 'keyring') or (expected_key is None and not file_content and not env_vars)
        km = KeyManager(key_file_path=key_file, use_env_vars=bool(env_vars), use_keyring=keyring_enabled_for_test)

        # Determine the key to request (normalize from inputs)
        service_id = "missing" # Default if no key expected
        if file_content: service_id = file_content.split("=")[0].lower()
        elif env_vars: service_id = list(env_vars.keys())[0][len(KeyManager.env_prefix):].lower()
        elif keyring_return: service_id = "keyring_key" # Use a consistent key for keyring tests

        # Call get_key
        actual_key = km.get_key(service_id)
        actual_source = km.get_key_source(service_id)

        # Assertions
        assert actual_key == expected_key
        assert actual_source == expected_source

        # Check if keyring was called appropriately
        if expected_source == 'keyring':
            mock_keyring_module.get_password.assert_called_once_with(f"agentvault:{service_id}", service_id)
        elif expected_source in ['file', 'env']:
            mock_keyring_module.get_password.assert_not_called()
        elif expected_key is None and km.use_keyring: # Not found, but keyring was enabled and checked
             mock_keyring_module.get_password.assert_called_once_with(f"agentvault:{service_id}", service_id)
        else: # Not found, keyring disabled or not needed
            mock_keyring_module.get_password.assert_not_called()

# --- Test get_key_source (Simpler test focusing only on source retrieval) ---

def test_get_key_source_direct(mocker):
    km = KeyManager(use_env_vars=False, use_keyring=False) # Disable auto-loading
    # Manually populate internal state
    km._keys['service_a'] = 'val_a'
    km._key_sources['service_a'] = 'file'
    km._keys['service_b'] = 'val_b'
    km._key_sources['service_b'] = 'env'
    km._keys['service_c'] = 'val_c'
    km._key_sources['service_c'] = 'keyring'

    assert km.get_key_source('service_a') == 'file'
    assert km.get_key_source('SERVICE_A') == 'file'
    assert km.get_key_source('service_b') == 'env'
    assert km.get_key_source('service_c') == 'keyring'
    assert km.get_key_source('missing') is None

# --- Restore original test structure for file/env loading if needed ---

# Example: Restore individual test for file not found
@patch("pathlib.Path.exists", return_value=False)
def test_load_from_file_not_exists_restored(mock_exists, tmp_path, mocker, caplog):
    key_file = tmp_path / "nonexistent.json"
    mocker.patch.object(KeyManager, "_load_from_env") # Prevent env loading
    with caplog.at_level(logging.WARNING):
        km = KeyManager(key_file_path=key_file, use_env_vars=False)
    assert not km._keys
    assert f"Key file specified but not found: {key_file.resolve()}" in caplog.text

# (Add back other specific file/env tests if desired)
