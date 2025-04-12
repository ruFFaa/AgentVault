import pytest
import pathlib
from unittest.mock import patch, MagicMock, ANY
from click.testing import CliRunner

# Import the CLI entrypoint and the specific command group
from agentvault_cli.main import cli
# Import KeyManager and exceptions for mocking side effects
try:
    from agentvault import key_manager, exceptions as av_exceptions
    _AGENTVAULT_AVAILABLE = True
except ImportError:
    key_manager = None
    av_exceptions = None
    _AGENTVAULT_AVAILABLE = False

# Skip tests if library not available
pytestmark = pytest.mark.skipif(not _AGENTVAULT_AVAILABLE, reason="agentvault library not found")

# --- Fixtures ---

@pytest.fixture
def runner():
    return CliRunner()

# --- Test 'config set' ---

# Patch the utils used by the command
@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_set_env_guidance(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config set --env' provides guidance."""
    # Mock the class attribute directly if needed, or rely on default
    mock_key_manager_cls.env_prefix = "AGENTVAULT_KEY_"
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--env'])
    assert result.exit_code == 0
    # Assert that display_info was called with the expected guidance parts
    assert mock_display_info.call_count >= 3 # Check at least 3 calls
    mock_display_info.assert_any_call("Guidance: To use an environment variable for 'my-service', set the following variable:")
    mock_display_info.assert_any_call("  AGENTVAULT_KEY_MY-SERVICE=<your_api_key>")
    mock_key_manager_cls.assert_not_called() # No instance should be created

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_set_file_guidance(mock_key_manager_cls, mock_display_info, runner: CliRunner, tmp_path: pathlib.Path):
    """Test 'config set --file' provides guidance."""
    key_file = tmp_path / "keys.env"
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--file', str(key_file)])
    assert result.exit_code == 0
    assert mock_display_info.call_count >= 4 # Check at least 4 calls
    mock_display_info.assert_any_call(f"Guidance: To use a file for 'my-service', add the following line to '{key_file}':")
    mock_display_info.assert_any_call("  my-service=<your_api_key>")
    mock_key_manager_cls.assert_not_called()

@patch('agentvault_cli.commands.config.utils.display_success')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_keyring_success(mock_prompt, mock_key_manager_cls, mock_display_success, runner: CliRunner):
    """Test 'config set --keyring' successfully sets key."""
    mock_prompt.return_value = "test-api-key"
    mock_manager_instance = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])

    assert result.exit_code == 0
    mock_display_success.assert_called_once_with("API key for 'keyring-service' stored successfully in keyring.")
    mock_prompt.assert_called_once()
    mock_key_manager_cls.assert_called_once_with(use_keyring=True)
    mock_manager_instance.set_key_in_keyring.assert_called_once_with('keyring-service', 'test-api-key')

@patch('agentvault_cli.commands.config.utils.display_error')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_keyring_error(mock_prompt, mock_key_manager_cls, mock_display_error, runner: CliRunner):
    """Test 'config set --keyring' handles KeyManagementError."""
    mock_prompt.return_value = "test-api-key"
    mock_manager_instance = MagicMock()
    error_message = "Keyring access denied"
    mock_manager_instance.set_key_in_keyring.side_effect = av_exceptions.KeyManagementError(error_message)
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])

    assert result.exit_code == 1
    mock_display_error.assert_called_once_with(f"Failed to set key in keyring: {error_message}")
    mock_manager_instance.set_key_in_keyring.assert_called_once()

@patch('agentvault_cli.commands.config.utils.display_error')
@patch('agentvault_cli.commands.config._agentvault_lib_imported', False)
def test_config_set_keyring_lib_missing(mock_display_error, runner: CliRunner):
     """Test 'config set --keyring' when library import failed."""
     result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])
     assert result.exit_code == 1
     mock_display_error.assert_called_once_with("Cannot use --keyring: Failed to import the 'agentvault' library.")

@patch('agentvault_cli.commands.config.utils.display_error')
def test_config_set_mutual_exclusivity(mock_display_error, runner: CliRunner):
    """Test error when multiple source flags are provided."""
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--env', '--keyring'])
    assert result.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one source method: --env, --file <path>, or --keyring.")

    mock_display_error.reset_mock()
    result = runner.invoke(cli, ['config', 'set', 'my-service']) # No source
    assert result.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one source method: --env, --file <path>, or --keyring.")


# --- Test 'config get' ---

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get' when key is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123"
    mock_manager_instance.get_key_source.return_value = "env"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'found-service'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("Key for service 'found-service' found.")
    mock_display_info.assert_any_call("  Source: ENV")
    mock_display_info.assert_any_call("  (Use --show-key to display a masked version of the key)")
    mock_manager_instance.get_key.assert_called_once_with('found-service')
    mock_manager_instance.get_key_source.assert_called_once_with('found-service')

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_show_key(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get --show-key' when key is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123456"
    mock_manager_instance.get_key_source.return_value = "file"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'found-service', '--show-key'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("Key for service 'found-service' found.")
    mock_display_info.assert_any_call("  Source: FILE")
    mock_display_info.assert_any_call("  Value (masked): foun...")

@patch('agentvault_cli.commands.config.utils.display_warning')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_not_found(mock_key_manager_cls, mock_display_warning, runner: CliRunner):
    """Test 'config get' when key is not found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'missing-service'])

    assert result.exit_code == 0 # Command succeeds, just warns
    mock_display_warning.assert_called_once_with("No key found for service 'missing-service' in any configured source (Env, File, Keyring).")

# --- Test 'config list' ---

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.utils.display_table')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_list_found(mock_key_manager_cls, mock_display_table, mock_display_info, runner: CliRunner):
    """Test 'config list' when keys are found."""
    mock_manager_instance = MagicMock()
    # Simulate keys loaded from env/file during init
    mock_manager_instance._key_sources = {"service1": "env", "service_file": "file"}
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'list'])

    assert result.exit_code == 0
    mock_key_manager_cls.assert_called_once_with(use_keyring=False)
    # Assert display_table was called with the correct data (sorted)
    expected_data = [['service1', 'ENV'], ['service_file', 'FILE']]
    mock_display_table.assert_called_once_with(
        "Configured Key Sources (Env/File)",
        ["Service ID", "Source"],
        expected_data
    )
    # Check the notes are displayed
    mock_display_info.assert_any_call("\nNote: This list shows keys loaded from environment variables or key files.")

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.utils.display_table')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_list_empty(mock_key_manager_cls, mock_display_table, mock_display_info, runner: CliRunner):
    """Test 'config list' when no keys are found from env/file."""
    mock_manager_instance = MagicMock()
    mock_manager_instance._key_sources = {} # No keys loaded initially
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'list'])

    assert result.exit_code == 0
    # --- FIX: Assert display_info called instead of checking output ---
    mock_display_info.assert_any_call("No keys found configured via environment variables or specified key files.")
    mock_display_table.assert_not_called()
    # --- FIX: Assert the note call specifically ---
    mock_display_info.assert_any_call("(Keys stored only in the OS keyring will not be listed here unless previously accessed.)")
