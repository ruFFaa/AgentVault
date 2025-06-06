import pytest
import os
import json
import pathlib
import logging
import io
from unittest.mock import MagicMock, call, patch, ANY # Keep ANY if used

# Import the class and exception to test
# Use absolute import based on src being in pythonpath
from agentvault.key_manager import KeyManager, KeyManagementError
from dotenv import dotenv_values

# --- Fixtures ---

# Mock the keyring module *before* KeyManager is potentially imported by tests
# This ensures that any check within KeyManager sees the mock from the start.
@pytest.fixture(autouse=True)
def mock_keyring_module(mocker):
    # Mock the module itself where it's imported within key_manager.py
    mock_keyring = MagicMock()
    # Use a dictionary to simulate keyring storage for get_password
    keyring_store = {}

    def mock_get_password(service, username):
        # Simulate potential backend errors if needed in specific tests
        if service == "agentvault:oauth:kr_error" and username == "clientId":
            raise Exception("Simulated keyring read error")
        return keyring_store.get((service, username))

    def mock_set_password(service, username, password):
         # Simulate potential backend errors if needed in specific tests
        if service == "agentvault:oauth:kr_write_error":
            raise Exception("Simulated keyring write error")
        keyring_store[(service, username)] = password

    mock_keyring.get_password = MagicMock(side_effect=mock_get_password)
    mock_keyring.set_password = MagicMock(side_effect=mock_set_password)
    mock_keyring.get_keyring = MagicMock() # Mock the functional check call
    mocker.patch('agentvault.key_manager.keyring', mock_keyring, create=True) # Use create=True if module might not exist yet
    # Also mock the import check flag if tests rely on it
    mocker.patch('agentvault.key_manager._keyring_imported', True, create=True)
    # Return the mock and the simulated store for manipulation in tests
    return mock_keyring, keyring_store

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
    assert km.oauth_env_prefix == "AGENTVAULT_OAUTH_" # Check default OAuth prefix
    assert km._keys == {}
    assert km._key_sources == {}
    assert km._oauth_creds == {} # Check OAuth dict init
    assert km._oauth_sources == {} # Check OAuth source dict init
    # Check methods were called during init
    spy_load_file.assert_not_called()
    spy_load_env.assert_called_once_with(km) # Env loading should happen by default

def test_key_manager_init_custom_params(tmp_path, mocker):
    spy_load_file = mocker.spy(KeyManager, "_load_from_file")
    spy_load_env = mocker.spy(KeyManager, "_load_from_env")
    mock_functional_check = mocker.patch('agentvault.key_manager.keyring.get_keyring') # Mock check

    key_file = tmp_path / "keys.json"
    km = KeyManager(
        key_file_path=key_file,
        use_env_vars=False,
        use_keyring=True,
        env_prefix="MYAPP_KEY_",
        oauth_env_prefix="MYAPP_OAUTH_" # Test custom OAuth prefix
    )

    assert km.key_file_path == key_file.resolve()
    assert km.use_env_vars is False
    assert km.use_keyring is True # Should be true now as mock check passes
    assert km.env_prefix == "MYAPP_KEY_"
    assert km.oauth_env_prefix == "MYAPP_OAUTH_" # Check custom OAuth prefix
    spy_load_file.assert_called_once_with(km)
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
def test_load_from_env_api_keys_success(mocker):
    # Prevent file loading from interfering
    mocker.patch.object(KeyManager, "_load_from_file")
    km = KeyManager(use_env_vars=True, key_file_path=None) # Ensure no file path
    assert km._keys == {"service1": "key1_value", "service2_upper": "key2_value"}
    assert km._key_sources == {"service1": "env", "service2_upper": "env"}
    assert not km._oauth_creds # Ensure OAuth is empty

@patch.dict(os.environ, {"AGENTVAULT_KEY_SERVICE1": "env_key"}, clear=True)
def test_load_from_env_api_key_priority(mocker):
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

@patch.dict(os.environ, {
    "AGENTVAULT_OAUTH_OASVC1_CLIENT_ID": "oa1_id",
    "AGENTVAULT_OAUTH_OASVC1_CLIENT_SECRET": "oa1_secret",
    "AGENTVAULT_OAUTH_oasvc2_lower_CLIENT_ID": "oa2_id", # Test lowercase service id part
    "AGENTVAULT_OAUTH_OASVC3_CLIENT_ID": "oa3_id_only",
    "AGENTVAULT_OAUTH_OASVC4_CLIENT_SECRET": "oa4_secret_only",
    "AGENTVAULT_OAUTH_EMPTYVAL_CLIENT_ID": "",
    "AGENTVAULT_OAUTH_MALFORMED": "bad",
    "AGENTVAULT_OAUTH_": "empty_id",
    "AGENTVAULT_KEY_OASVC1": "api_key_for_oa1" # Test coexistence
}, clear=True)
def test_load_from_env_oauth_success(mocker):
    mocker.patch.object(KeyManager, "_load_from_file")
    km = KeyManager(use_env_vars=True, key_file_path=None)

    # Check API Key loaded
    assert km._keys.get("oasvc1") == "api_key_for_oa1"
    assert km._key_sources.get("oasvc1") == "env"

    # Check OAuth Creds loaded correctly
    assert "oasvc1" in km._oauth_creds
    assert km._oauth_creds["oasvc1"].get("clientId") == "oa1_id"
    assert km._oauth_creds["oasvc1"].get("clientSecret") == "oa1_secret"
    assert km._oauth_sources.get("oasvc1") == "env"

    assert "oasvc2_lower" in km._oauth_creds
    assert km._oauth_creds["oasvc2_lower"].get("clientId") == "oa2_id"
    assert "clientSecret" not in km._oauth_creds["oasvc2_lower"] # Secret not provided
    assert km._oauth_sources.get("oasvc2_lower") == "env"

    assert "oasvc3" in km._oauth_creds
    assert km._oauth_creds["oasvc3"].get("clientId") == "oa3_id_only"
    assert "clientSecret" not in km._oauth_creds["oasvc3"]
    assert km._oauth_sources.get("oasvc3") == "env"

    assert "oasvc4" in km._oauth_creds
    assert "clientId" not in km._oauth_creds["oasvc4"]
    assert km._oauth_creds["oasvc4"].get("clientSecret") == "oa4_secret_only"
    assert km._oauth_sources.get("oasvc4") == "env"

    # Check ignored vars
    assert "emptyval" not in km._oauth_creds
    assert "" not in km._oauth_creds # Malformed/empty IDs

@patch.dict(os.environ, {
    "AGENTVAULT_OAUTH_PRIORITY_CLIENT_ID": "env_id",
    "AGENTVAULT_OAUTH_PRIORITY_CLIENT_SECRET": "env_secret"
}, clear=True)
def test_load_from_env_oauth_priority(mocker):
    mocker.patch.object(KeyManager, "_load_from_file")
    # Simulate file load setting OAuth creds first
    km = KeyManager(use_env_vars=False)
    km._oauth_creds["priority"] = {"clientId": "file_id", "clientSecret": "file_secret"}
    km._oauth_sources["priority"] = "file"

    # Now enable env loading and call the method
    km.use_env_vars = True
    km._load_from_env()

    # Assert file creds were not overwritten
    assert km._oauth_creds["priority"]["clientId"] == "file_id"
    assert km._oauth_creds["priority"]["clientSecret"] == "file_secret"
    assert km._oauth_sources["priority"] == "file"


# --- Test _load_from_file ---

# Use patch from unittest.mock for Path methods
@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.read_text")
def test_load_from_file_env_api_keys_success(mock_read_text, mock_is_file, mock_exists, tmp_path, mocker):
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
def test_load_from_file_json_api_keys_success(mock_read_text, mock_is_file, mock_exists, tmp_path, mocker):
    key_file = tmp_path / "keys.json"
    json_content = {"service_c": "key_c_json", "SERVICE_D_UPPER": "key_d_json", "not_a_string": 123, "empty_string": ""}
    mock_read_text.return_value = json.dumps(json_content)

    km = KeyManager(key_file_path=key_file, use_env_vars=False)

    mock_read_text.assert_called_once_with(encoding='utf-8')
    assert km._keys == {"service_c": "key_c_json", "service_d_upper": "key_d_json"}
    assert km._key_sources == {"service_c": "file", "service_d_upper": "file"}

@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.is_file", return_value=True)
def test_load_from_file_env_oauth_success(mock_is_file, mock_exists, tmp_path, mocker):
    key_file = tmp_path / "oauth.env"
    env_content = """
AGENTVAULT_OAUTH_SVC1_CLIENT_ID=env_id1
AGENTVAULT_OAUTH_SVC1_CLIENT_SECRET=env_secret1
# Comment
AGENTVAULT_OAUTH_svc2_CLIENT_ID=env_id2
AGENTVAULT_OAUTH_SVC3_CLIENT_SECRET=env_secret3_only
EMPTY_OAUTH=
AGENTVAULT_OAUTH_SVC4_CLIENT_ID=
    """
    key_file.write_text(env_content)
    # Mock dotenv_values to return parsed content
    mock_dotenv = mocker.patch(
        "agentvault.key_manager.dotenv_values",
        return_value=dotenv_values(stream=io.StringIO(env_content))
    )

    km = KeyManager(key_file_path=key_file, use_env_vars=False)

    assert "svc1" in km._oauth_creds
    assert km._oauth_creds["svc1"]["clientId"] == "env_id1"
    assert km._oauth_creds["svc1"]["clientSecret"] == "env_secret1"
    assert km._oauth_sources["svc1"] == "file"

    assert "svc2" in km._oauth_creds
    assert km._oauth_creds["svc2"]["clientId"] == "env_id2"
    assert "clientSecret" not in km._oauth_creds["svc2"]
    assert km._oauth_sources["svc2"] == "file"

    assert "svc3" in km._oauth_creds
    assert "clientId" not in km._oauth_creds["svc3"]
    assert km._oauth_creds["svc3"]["clientSecret"] == "env_secret3_only"
    assert km._oauth_sources["svc3"] == "file"

    assert "svc4" not in km._oauth_creds # Value was empty

@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.read_text")
def test_load_from_file_json_oauth_success(mock_read_text, mock_is_file, mock_exists, tmp_path):
    key_file = tmp_path / "oauth.json"
    json_content = {
        "service1": {
            "apiKey": "api1",
            "oauth": {
                "clientId": "json_id1",
                "clientSecret": "json_secret1"
            }
        },
        "SERVICE2_UPPER": { # Test case insensitivity for service ID
            "oauth": {
                "clientId": "json_id2"
                # Secret missing
            }
        },
        "service3": {
            "oauth": {
                "clientSecret": "json_secret3"
                # ID missing
            }
        },
        "service4": {
            "oauth": {} # Empty oauth block
        },
        "service5": {
            "oauth": "not_a_dict" # Invalid oauth block type
        },
        "service6": {
            "oauth": {
                "clientId": 123, # Invalid type
                "clientSecret": True # Invalid type
            }
        },
        "service7_api_only": "api7"
    }
    mock_read_text.return_value = json.dumps(json_content)

    km = KeyManager(key_file_path=key_file, use_env_vars=False)

    # Service 1: Both API Key and OAuth
    assert km._keys.get("service1") == "api1"
    assert km._key_sources.get("service1") == "file"
    assert "service1" in km._oauth_creds
    assert km._oauth_creds["service1"]["clientId"] == "json_id1"
    assert km._oauth_creds["service1"]["clientSecret"] == "json_secret1"
    assert km._oauth_sources["service1"] == "file"

    # Service 2: Only OAuth ID (case insensitive key)
    assert "service2_upper" not in km._keys
    assert "service2_upper" in km._oauth_creds
    assert km._oauth_creds["service2_upper"]["clientId"] == "json_id2"
    assert "clientSecret" not in km._oauth_creds["service2_upper"]
    assert km._oauth_sources["service2_upper"] == "file"

    # Service 3: Only OAuth Secret
    assert "service3" not in km._keys
    assert "service3" in km._oauth_creds
    assert "clientId" not in km._oauth_creds["service3"]
    assert km._oauth_creds["service3"]["clientSecret"] == "json_secret3"
    assert km._oauth_sources["service3"] == "file"

    # Service 4, 5, 6: Invalid OAuth structures
    assert "service4" not in km._oauth_creds
    assert "service5" not in km._oauth_creds
    assert "service6" not in km._oauth_creds

    # Service 7: API Key only
    assert km._keys.get("service7_api_only") == "api7"
    assert km._key_sources.get("service7_api_only") == "file"
    assert "service7_api_only" not in km._oauth_creds


# --- Test Keyring Methods (using the autouse mock_keyring_module fixture) ---

def test_load_from_keyring_disabled(mock_keyring_module):
    mock_kr, _ = mock_keyring_module # Unpack fixture
    km = KeyManager(use_keyring=False)
    assert km.use_keyring is False
    assert km._load_from_keyring("service1") is None
    mock_kr.get_password.assert_not_called() # Should not attempt access

def test_load_from_keyring_not_installed(mock_keyring_not_installed):
    km = KeyManager(use_keyring=True) # Request keyring
    assert km.use_keyring is False # Init should detect it's not available
    assert km._load_from_keyring("service1") is None

def test_load_from_keyring_success(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    keyring_store[("agentvault:service_kr", "service_kr")] = "keyring_secret"
    km = KeyManager(use_keyring=True)
    assert km.use_keyring is True # Init check should pass with mock
    key = km._load_from_keyring("service_kr") # Call internal method
    assert key == "keyring_secret"
    mock_kr.get_password.assert_called_once_with("agentvault:service_kr", "service_kr")
    assert "service_kr" not in km._keys

def test_load_from_keyring_not_found(mock_keyring_module):
    mock_kr, _ = mock_keyring_module
    # Ensure the key is not in the mock store
    mock_kr.get_password.return_value = None # Explicitly ensure it returns None
    km = KeyManager(use_keyring=True)
    key = km._load_from_keyring("service_missing")
    assert key is None
    mock_kr.get_password.assert_called_once_with("agentvault:service_missing", "service_missing")

def test_load_from_keyring_exception(mock_keyring_module, caplog):
    mock_kr, _ = mock_keyring_module
    mock_kr.get_password.side_effect = Exception("Keyring backend error")
    km = KeyManager(use_keyring=True)
    with caplog.at_level(logging.ERROR):
        key = km._load_from_keyring("service_err")
    assert key is None
    assert "Failed to get API key for service 'service_err' from keyring: Keyring backend error" in caplog.text

def test_set_key_in_keyring_success(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    km = KeyManager(use_keyring=True)
    km.set_key_in_keyring("SetMe", "new_value")
    mock_kr.set_password.assert_called_once_with("agentvault:setme", "setme", "new_value")
    assert keyring_store[("agentvault:setme", "setme")] == "new_value"

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
    mock_kr, _ = mock_keyring_module
    mock_kr.set_password.side_effect = Exception("Keyring backend error")
    km = KeyManager(use_keyring=True)
    with pytest.raises(KeyManagementError, match="Failed to set API key in keyring"):
        km.set_key_in_keyring("SetErr", "value")

# --- Tests for OAuth Keyring ---
def test_load_oauth_from_keyring_success(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    keyring_store[("agentvault:oauth:oasvc_kr", "clientId")] = "kr_id"
    keyring_store[("agentvault:oauth:oasvc_kr", "clientSecret")] = "kr_secret"

    km = KeyManager(use_keyring=True)
    creds = km._load_oauth_from_keyring("oasvc_kr")

    assert creds == {"clientId": "kr_id", "clientSecret": "kr_secret"}
    assert mock_kr.get_password.call_count == 2
    mock_kr.get_password.assert_any_call("agentvault:oauth:oasvc_kr", "clientId")
    mock_kr.get_password.assert_any_call("agentvault:oauth:oasvc_kr", "clientSecret")

def test_load_oauth_from_keyring_partial_fail(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    keyring_store[("agentvault:oauth:oasvc_partial", "clientId")] = "kr_id_partial"
    # Secret is missing

    km = KeyManager(use_keyring=True)
    creds = km._load_oauth_from_keyring("oasvc_partial")

    assert creds is None # Should return None if incomplete
    assert mock_kr.get_password.call_count == 2

def test_load_oauth_from_keyring_exception(mock_keyring_module, caplog):
    mock_kr, _ = mock_keyring_module
    mock_kr.get_password.side_effect = [Exception("Keyring backend error"), "dummy_secret"]
    km = KeyManager(use_keyring=True)
    with caplog.at_level(logging.ERROR):
        creds = km._load_oauth_from_keyring("kr_error") # Use different service name
    assert creds is None
    assert "Failed to get OAuth credentials for service 'kr_error' from keyring" in caplog.text

def test_set_oauth_creds_in_keyring_success(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    km = KeyManager(use_keyring=True)
    km.set_oauth_creds_in_keyring("SetOAuth", "id_to_set", "secret_to_set")

    assert mock_kr.set_password.call_count == 2
    mock_kr.set_password.assert_any_call("agentvault:oauth:setoauth", "clientId", "id_to_set")
    mock_kr.set_password.assert_any_call("agentvault:oauth:setoauth", "clientSecret", "secret_to_set")
    # Check if values were actually stored in our mock store
    assert keyring_store[("agentvault:oauth:setoauth", "clientId")] == "id_to_set"
    assert keyring_store[("agentvault:oauth:setoauth", "clientSecret")] == "secret_to_set"

def test_set_oauth_creds_in_keyring_exception(mock_keyring_module):
    mock_kr, _ = mock_keyring_module
    mock_kr.set_password.side_effect = lambda service, username, password: (_ for _ in ()).throw(Exception("Cannot write to keyring")) if service == "agentvault:oauth:kr_write_error" else None
    km = KeyManager(use_keyring=True)
    with pytest.raises(KeyManagementError, match="Failed to set OAuth creds in keyring"):
        km.set_oauth_creds_in_keyring("kr_write_error", "id", "secret") # Use specific service name

def test_get_oauth_creds_triggers_keyring_load(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    keyring_store[("agentvault:oauth:kr_load", "clientId")] = "loaded_id"
    keyring_store[("agentvault:oauth:kr_load", "clientSecret")] = "loaded_secret"

    km = KeyManager(use_keyring=True)
    # Ensure not in cache initially
    assert "kr_load" not in km._oauth_creds

    # Call getter - should trigger keyring load
    client_id = km.get_oauth_client_id("kr_load")
    client_secret = km.get_oauth_client_secret("kr_load")

    assert client_id == "loaded_id"
    assert client_secret == "loaded_secret"
    # Check if cached
    assert "kr_load" in km._oauth_creds
    assert km._oauth_creds["kr_load"]["clientId"] == "loaded_id"
    assert km._oauth_creds["kr_load"]["clientSecret"] == "loaded_secret"
    assert km._oauth_sources["kr_load"] == "keyring"
    # Check keyring was called
    assert mock_kr.get_password.call_count == 2

def test_get_oauth_config_status_keyring(mock_keyring_module):
    mock_kr, keyring_store = mock_keyring_module
    keyring_store[("agentvault:oauth:kr_status", "clientId")] = "status_id"
    keyring_store[("agentvault:oauth:kr_status", "clientSecret")] = "status_secret"

    km = KeyManager(use_keyring=True)
    status = km.get_oauth_config_status("kr_status")
    assert status == "Configured (Source: KEYRING)"


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
        mock_kr, keyring_store = mock_keyring_module # Unpack store

        # Determine the key to request (normalize from inputs)
        service_id = "missing" # Default if no key expected
        if file_content: service_id = file_content.split("=")[0].lower()
        elif env_vars: service_id = list(env_vars.keys())[0][len(KeyManager.env_prefix):].lower()
        elif keyring_return: service_id = "keyring_key" # Use a consistent key for keyring tests

        # Populate mock keyring store if needed for API key
        if expected_source == 'keyring' and keyring_return is not None:
             keyring_store[(f"agentvault:{service_id}", service_id)] = keyring_return
        # Reset mock call count before instantiation for this specific test case
        mock_kr.get_password.reset_mock()


        # Instantiate KeyManager
        # Determine if keyring should be considered enabled for this test run
        keyring_enabled_for_test = (keyring_return is not None) or (expected_source == 'keyring') or (expected_key is None and not file_content and not env_vars)
        km = KeyManager(key_file_path=key_file, use_env_vars=bool(env_vars), use_keyring=keyring_enabled_for_test)


        # Call get_key
        actual_key = km.get_key(service_id)
        actual_source = km.get_key_source(service_id)

        # Assertions
        assert actual_key == expected_key
        assert actual_source == expected_source

        # Check if keyring was called appropriately
        if expected_source == 'keyring':
            mock_kr.get_password.assert_called_once_with(f"agentvault:{service_id}", service_id)
        elif expected_source in ['file', 'env']:
            mock_kr.get_password.assert_not_called()
        elif expected_key is None and km.use_keyring: # Not found, but keyring was enabled and checked
             # Check if keyring was called for the specific service ID
             keyring_call_args = [call(f"agentvault:{service_id}", service_id)]
             assert keyring_call_args[0] in mock_kr.get_password.call_args_list
        else: # Not found, keyring disabled or not needed
            mock_kr.get_password.assert_not_called()

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

# --- Tests for OAuth Getters (using file loaded data) ---

@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.read_text")
def test_get_oauth_creds_from_json_file(mock_read_text, mock_is_file, mock_exists, tmp_path):
    key_file = tmp_path / "oauth_get.json"
    json_content = {
        "svc1": { "oauth": { "clientId": "id1", "clientSecret": "secret1" } },
        "svc2": { "oauth": { "clientId": "id2" } }, # Secret missing
        "svc3": { "oauth": { "clientSecret": "secret3" } }, # ID missing
        "svc4_api": "apikey" # No oauth block
    }
    mock_read_text.return_value = json.dumps(json_content)

    km = KeyManager(key_file_path=key_file, use_env_vars=False, use_keyring=False)

    # Service 1: Both present
    assert km.get_oauth_client_id("svc1") == "id1"
    assert km.get_oauth_client_secret("svc1") == "secret1"
    assert km.get_oauth_config_status("svc1") == "Configured (Source: FILE)"

    # Service 2: Only ID present
    assert km.get_oauth_client_id("svc2") == "id2"
    assert km.get_oauth_client_secret("svc2") is None
    assert km.get_oauth_config_status("svc2") == "Partially Configured (Source: FILE)"

    # Service 3: Only Secret present
    assert km.get_oauth_client_id("svc3") is None
    assert km.get_oauth_client_secret("svc3") == "secret3"
    assert km.get_oauth_config_status("svc3") == "Partially Configured (Source: FILE)"

    # Service 4: Neither present
    assert km.get_oauth_client_id("svc4_api") is None
    assert km.get_oauth_client_secret("svc4_api") is None
    assert km.get_oauth_config_status("svc4_api") == "Not Configured"
    # Check API key is still loaded
    assert km.get_key("svc4_api") == "apikey"
    assert km.get_key_source("svc4_api") == "file"


# (Add back other specific file/env tests if desired)
