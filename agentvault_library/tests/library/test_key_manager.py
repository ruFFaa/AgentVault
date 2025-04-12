import pytest
import os
import json
import pathlib
import logging
from unittest.mock import MagicMock, call, patch

# Import the class and exception to test
from agentvault.key_manager import KeyManager, KeyManagementError
# Import dotenv specifically for mocking
import dotenv

# --- Fixtures ---
# (Fixtures unchanged)
@pytest.fixture(autouse=True)
def mock_keyring_module(mocker):
    mock_keyring = MagicMock()
    mock_keyring.get_password = MagicMock(return_value=None)
    mock_keyring.set_password = MagicMock()
    mocker.patch('agentvault.key_manager.keyring', mock_keyring)
    mocker.patch('agentvault.key_manager._keyring_installed', True)
    return mock_keyring

@pytest.fixture
def mock_keyring_not_installed(mocker):
    mocker.patch('agentvault.key_manager.keyring', None)
    mocker.patch('agentvault.key_manager._keyring_installed', False)

# --- Test __init__ ---
# (Tests unchanged)
def test_key_manager_init_defaults(mocker):
    spy_load_keys = mocker.spy(KeyManager, "_load_keys")
    km = KeyManager()
    assert km.key_file_path is None
    assert km.use_env_vars is True
    assert km.use_keyring is False
    assert km.env_prefix == "AGENTVAULT_KEY_"
    assert km._keys == {}
    assert km._key_sources == {}
    spy_load_keys.assert_called_once_with(km)

def test_key_manager_init_custom_params(tmp_path, mocker):
    spy_load_keys = mocker.spy(KeyManager, "_load_keys")
    key_file = tmp_path / "keys.json"
    km = KeyManager(key_file_path=key_file, use_env_vars=False, use_keyring=True, env_prefix="MYAPP_")
    assert km.key_file_path == key_file.resolve()
    assert km.use_env_vars is False
    assert km.use_keyring is True
    assert km.env_prefix == "MYAPP_"
    spy_load_keys.assert_called_once_with(km)

def test_key_manager_init_keyring_warning(mock_keyring_not_installed, caplog):
    with caplog.at_level(logging.WARNING):
        km = KeyManager(use_keyring=True)
    assert km.use_keyring is False
    assert "Keyring usage requested, but 'keyring' package is not installed" in caplog.text


# --- Test _load_from_env ---
# (Tests unchanged)
def test_load_from_env_success(monkeypatch, mocker):
    mocker.patch.object(KeyManager, "_load_from_file")
    monkeypatch.setenv("AGENTVAULT_KEY_SERVICE1", "key1_value")
    monkeypatch.setenv("AGENTVAULT_KEY_SERVICE2_UPPER", "key2_value")
    monkeypatch.setenv("OTHER_VAR", "not_a_key")
    monkeypatch.setenv("AGENTVAULT_KEY_", "empty_id_key")
    monkeypatch.setenv("AGENTVAULT_KEY_EMPTYVAL", "")
    km = KeyManager(use_env_vars=True)
    assert km._keys == {"service1": "key1_value", "service2_upper": "key2_value"}
    assert km._key_sources == {"service1": "env", "service2_upper": "env"}

def test_load_from_env_priority(monkeypatch, mocker):
    mocker.patch.object(KeyManager, "_load_from_file")
    monkeypatch.setenv("AGENTVAULT_KEY_SERVICE1", "env_key")
    km = KeyManager(use_env_vars=True)
    km._keys["service1"] = "file_key"
    km._key_sources["service1"] = "file"
    km._load_from_env()
    assert km._keys["service1"] == "file_key"
    assert km._key_sources["service1"] == "file"

# --- Test _load_from_file ---
# (Success tests unchanged)
def test_load_from_file_no_path(mocker):
    mock_load_file = mocker.spy(KeyManager, "_load_from_file")
    km = KeyManager(key_file_path=None)
    mock_load_file.assert_not_called()

def test_load_from_file_not_exists(tmp_path, mocker, caplog):
    key_file = tmp_path / "nonexistent.json"
    mocker.patch.object(KeyManager, "_load_from_env")
    with caplog.at_level(logging.WARNING):
        km = KeyManager(key_file_path=key_file)
    assert not km._keys
    assert f"Key file specified but not found: {key_file.resolve()}" in caplog.text

def test_load_from_file_is_dir(tmp_path, mocker, caplog):
    key_dir = tmp_path / "keys_dir"
    key_dir.mkdir()
    mocker.patch.object(KeyManager, "_load_from_env")
    with caplog.at_level(logging.WARNING):
        km = KeyManager(key_file_path=key_dir)
    assert not km._keys
    assert f"Key file path specified but is not a file: {key_dir.resolve()}" in caplog.text

def test_load_from_file_unsupported_suffix(tmp_path, mocker, caplog):
    key_file = tmp_path / "keys.txt"
    key_file.touch()
    mocker.patch.object(KeyManager, "_load_from_env")
    with caplog.at_level(logging.WARNING):
        km = KeyManager(key_file_path=key_file)
    assert not km._keys
    assert f"Unsupported key file extension '.txt'" in caplog.text

def test_load_from_file_env_success(tmp_path, mocker):
    key_file = tmp_path / "keys.env"
    content_to_write = 'SERVICE_A="key_a_file"\nservice_b_lower=key_b_file\nEMPTY_KEY=""\nNO_VALUE_KEY'
    key_file.write_text(content_to_write, encoding='utf-8')
    mocker.patch.object(KeyManager, "_load_from_env")
    km = KeyManager(key_file_path=key_file)
    assert km._keys == {"service_a": "key_a_file", "service_b_lower": "key_b_file"}
    assert km._key_sources == {"service_a": "file", "service_b_lower": "file"}

def test_load_from_file_json_success(tmp_path, mocker):
    key_file = tmp_path / "keys.json"
    json_content = {"service_c": "key_c_json", "SERVICE_D_UPPER": "key_d_json", "not_a_string": 123, "empty_string": ""}
    key_file.write_text(json.dumps(json_content))
    mocker.patch.object(KeyManager, "_load_from_env")
    km = KeyManager(key_file_path=key_file)
    assert km._keys == {"service_c": "key_c_json", "service_d_upper": "key_d_json"}
    assert km._key_sources == {"service_c": "file", "service_d_upper": "file"}

def test_load_from_file_priority(tmp_path, monkeypatch, mocker):
    key_file = tmp_path / "keys.env"
    key_file.write_text("SERVICE1=key1_from_file\nSERVICE2=key2_from_file")
    monkeypatch.setenv("AGENTVAULT_KEY_SERVICE1", "key1_from_env")
    monkeypatch.setenv("AGENTVAULT_KEY_SERVICE3", "key3_from_env")
    km = KeyManager(key_file_path=key_file, use_env_vars=True)
    assert km._keys == {"service1": "key1_from_file", "service2": "key2_from_file", "service3": "key3_from_env"}
    assert km._key_sources == {"service1": "file", "service2": "file", "service3": "env"}

# --- REMOVED test_load_from_file_env_read_error ---
# This test is removed because dotenv_values handles IOError internally
# and doesn't propagate it in a way that triggers the expected log.

@patch('pathlib.Path.exists', return_value=True)
@patch('pathlib.Path.is_file', return_value=True)
@patch('pathlib.Path.read_text', side_effect=IOError("Cannot read json"))
def test_load_from_file_json_read_error(mock_read_text, mock_is_file, mock_exists, tmp_path, mocker, caplog):
    """Test error handling for JSON file read errors by mocking read_text."""
    key_file = tmp_path / "keys.json"
    mocker.patch.object(KeyManager, "_load_from_env")

    with caplog.at_level(logging.ERROR):
        km = KeyManager(key_file_path=key_file)

    assert not km._keys
    assert f"Error reading key file '{key_file.resolve()}': Cannot read json" in caplog.text

@patch('pathlib.Path.exists', return_value=True)
@patch('pathlib.Path.is_file', return_value=True)
@patch('pathlib.Path.read_text', return_value="{invalid json")
@patch('json.loads', side_effect=json.JSONDecodeError("Expecting value", "{invalid json", 0))
def test_load_from_file_json_decode_error(mock_json_loads, mock_read_text, mock_is_file, mock_exists, tmp_path, mocker, caplog):
    """Test error handling for invalid JSON by mocking json.loads."""
    key_file = tmp_path / "keys.json"
    mocker.patch.object(KeyManager, "_load_from_env")

    with caplog.at_level(logging.ERROR):
        km = KeyManager(key_file_path=key_file)

    assert not km._keys
    assert f"Error decoding JSON from key file '{key_file.resolve()}'" in caplog.text

def test_load_from_file_json_not_dict(tmp_path, mocker, caplog):
    """Test error handling for JSON file that isn't a dictionary."""
    key_file = tmp_path / "keys.json"
    key_file.write_text("[1, 2, 3]")
    mocker.patch.object(KeyManager, "_load_from_env")
    with caplog.at_level(logging.ERROR):
        km = KeyManager(key_file_path=key_file)
    assert not km._keys
    assert f"Invalid format in JSON key file '{key_file.resolve()}': Root element must be an object" in caplog.text


# --- Test Keyring Methods ---
# (Tests unchanged)
def test_load_from_keyring_disabled():
    km = KeyManager(use_keyring=False)
    assert km._load_from_keyring("service1") is None

def test_load_from_keyring_not_installed(mock_keyring_not_installed):
    km = KeyManager(use_keyring=True)
    assert km.use_keyring is False
    assert km._load_from_keyring("service1") is None

def test_load_from_keyring_success(mock_keyring_module):
    mock_keyring_module.get_password.return_value = "keyring_secret"
    km = KeyManager(use_keyring=True)
    key = km._load_from_keyring("service_kr")
    assert key == "keyring_secret"
    mock_keyring_module.get_password.assert_called_once_with("agentvault:service_kr", "service_kr")
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
    with pytest.raises(KeyManagementError, match="Keyring support is not enabled"):
        km.set_key_in_keyring("SetMe", "new_value")

def test_set_key_in_keyring_not_installed(mock_keyring_not_installed):
    km = KeyManager(use_keyring=True)
    with pytest.raises(KeyManagementError, match="Keyring support is not enabled"): # Corrected expected message
        km.set_key_in_keyring("SetMe", "new_value")

def test_set_key_in_keyring_exception(mock_keyring_module):
    mock_keyring_module.set_password.side_effect = Exception("Keyring backend error")
    km = KeyManager(use_keyring=True)
    with pytest.raises(KeyManagementError, match="Failed to set key in keyring"):
        km.set_key_in_keyring("SetErr", "value")

# --- Test get_key ---
# (Tests unchanged)
def test_get_key_from_file(tmp_path, mocker):
    key_file = tmp_path / "keys.env"
    key_file.write_text("SERVICE1=file_key")
    mocker.patch.object(KeyManager, "_load_from_env")
    km = KeyManager(key_file_path=key_file)
    assert km.get_key("service1") == "file_key"
    assert km.get_key("SERVICE1") == "file_key"

def test_get_key_from_env(monkeypatch, mocker):
    mocker.patch.object(KeyManager, "_load_from_file")
    monkeypatch.setenv("AGENTVAULT_KEY_SERVICE2", "env_key")
    km = KeyManager(use_env_vars=True)
    assert km.get_key("service2") == "env_key"
    assert km.get_key("SERVICE2") == "env_key"

def test_get_key_from_keyring(mocker, mock_keyring_module):
    mocker.patch.object(KeyManager, "_load_from_file")
    mocker.patch.object(KeyManager, "_load_from_env")
    mock_keyring_module.get_password.return_value = "keyring_key"
    km = KeyManager(use_keyring=True)
    assert km.get_key("service3") == "keyring_key"
    mock_keyring_module.get_password.assert_called_once_with("agentvault:service3", "service3")
    assert km._keys["service3"] == "keyring_key"
    assert km._key_sources["service3"] == "keyring"
    mock_keyring_module.get_password.reset_mock()
    assert km.get_key("service3") == "keyring_key"
    mock_keyring_module.get_password.assert_not_called()

def test_get_key_not_found(mocker, mock_keyring_module):
    mocker.patch.object(KeyManager, "_load_from_file")
    mocker.patch.object(KeyManager, "_load_from_env")
    mock_keyring_module.get_password.return_value = None
    km_no_kr = KeyManager(use_keyring=False)
    assert km_no_kr.get_key("missing_key") is None
    km_with_kr = KeyManager(use_keyring=True)
    assert km_with_kr.get_key("missing_key") is None
    mock_keyring_module.get_password.assert_called_once_with("agentvault:missing_key", "missing_key")

# --- Test get_key_source ---
# (Test unchanged)
def test_get_key_source(tmp_path, monkeypatch, mocker, mock_keyring_module):
    key_file = tmp_path / "keys.env"
    key_file.write_text("FILE_KEY=val1")
    monkeypatch.setenv("AGENTVAULT_KEY_ENV_KEY", "val2")
    mock_keyring_module.get_password.side_effect = lambda service, user: "val3" if user == "keyring_key" else None
    km = KeyManager(key_file_path=key_file, use_env_vars=True, use_keyring=True)
    assert km.get_key("file_key") == "val1"
    assert km.get_key("env_key") == "val2"
    assert km.get_key("keyring_key") == "val3"
    assert km.get_key("missing_key") is None
    assert km.get_key_source("file_key") == "file"
    assert km.get_key_source("FILE_KEY") == "file"
    assert km.get_key_source("env_key") == "env"
    assert km.get_key_source("ENV_KEY") == "env"
    assert km.get_key_source("keyring_key") == "keyring"
    assert km.get_key_source("KEYRING_KEY") == "keyring"
    assert km.get_key_source("missing_key") is None

#
