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

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_set_env_guidance(mock_key_manager_cls, runner: CliRunner):
    """Test 'config set --env' provides guidance."""
    # Mock the class attribute directly if needed, or rely on default
    mock_key_manager_cls.env_prefix = "AGENTVAULT_KEY_"
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--env'])
    assert result.exit_code == 0
    assert "Guidance: To use an environment variable" in result.output
    assert "AGENTVAULT_KEY_MY-SERVICE" in result.output # Check variable name format
    mock_key_manager_cls.assert_not_called() # No instance should be created

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_set_file_guidance(mock_key_manager_cls, runner: CliRunner, tmp_path: pathlib.Path):
    """Test 'config set --file' provides guidance."""
    key_file = tmp_path / "keys.env"
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--file', str(key_file)])
    assert result.exit_code == 0
    assert "Guidance: To use a file" in result.output
    assert f"'{key_file}'" in result.output
    mock_key_manager_cls.assert_not_called()

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_keyring_success(mock_prompt, mock_key_manager_cls, runner: CliRunner):
    """Test 'config set --keyring' successfully sets key."""
    mock_prompt.return_value = "test-api-key"
    mock_manager_instance = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])

    assert result.exit_code == 0
    assert "SUCCESS: API key for 'keyring-service' stored successfully" in result.output
    mock_prompt.assert_called_once()
    mock_key_manager_cls.assert_called_once_with(use_keyring=True)
    mock_manager_instance.set_key_in_keyring.assert_called_once_with('keyring-service', 'test-api-key')

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_keyring_error(mock_prompt, mock_key_manager_cls, runner: CliRunner):
    """Test 'config set --keyring' handles KeyManagementError."""
    mock_prompt.return_value = "test-api-key"
    mock_manager_instance = MagicMock()
    mock_manager_instance.set_key_in_keyring.side_effect = av_exceptions.KeyManagementError("Keyring access denied")
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])

    assert result.exit_code == 1
    assert "ERROR: Failed to set key in keyring: Keyring access denied" in result.output
    mock_manager_instance.set_key_in_keyring.assert_called_once()

# Test for missing keyring package requires patching the import check flag
@patch('agentvault_cli.commands.config._agentvault_lib_imported', False)
def test_config_set_keyring_lib_missing(runner: CliRunner):
     """Test 'config set --keyring' when library import failed."""
     result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])
     assert result.exit_code == 1
     assert "ERROR: Cannot use --keyring: Failed to import the 'agentvault' library." in result.output


def test_config_set_mutual_exclusivity(runner: CliRunner):
    """Test error when multiple source flags are provided."""
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--env', '--keyring'])
    assert result.exit_code == 1
    assert "ERROR: Please specify exactly one source method" in result.output

    result = runner.invoke(cli, ['config', 'set', 'my-service']) # No source
    assert result.exit_code == 1
    assert "ERROR: Please specify exactly one source method" in result.output


# --- Test 'config get' ---

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found(mock_key_manager_cls, runner: CliRunner):
    """Test 'config get' when key is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123"
    mock_manager_instance.get_key_source.return_value = "env"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'found-service'])

    assert result.exit_code == 0
    assert "Key for service 'found-service' found." in result.output
    assert "Source: ENV" in result.output
    assert "Value (masked)" not in result.output # Default is not to show
    mock_manager_instance.get_key.assert_called_once_with('found-service')
    mock_manager_instance.get_key_source.assert_called_once_with('found-service')

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_show_key(mock_key_manager_cls, runner: CliRunner):
    """Test 'config get --show-key' when key is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123456"
    mock_manager_instance.get_key_source.return_value = "file"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'found-service', '--show-key'])

    assert result.exit_code == 0
    assert "Key for service 'found-service' found." in result.output
    assert "Source: FILE" in result.output
    assert "Value (masked): foun..." in result.output

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_not_found(mock_key_manager_cls, runner: CliRunner):
    """Test 'config get' when key is not found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'missing-service'])

    assert result.exit_code == 0 # Command succeeds, just warns
    assert "WARNING: No key found for service 'missing-service'" in result.output

# --- Test 'config list' ---

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('agentvault_cli.commands.config.utils.display_table')
def test_config_list_found(mock_display_table, mock_key_manager_cls, runner: CliRunner):
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
    assert "Note: This list shows keys loaded" in result.output

@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('agentvault_cli.commands.config.utils.display_table')
def test_config_list_empty(mock_display_table, mock_key_manager_cls, runner: CliRunner):
    """Test 'config list' when no keys are found from env/file."""
    mock_manager_instance = MagicMock()
    mock_manager_instance._key_sources = {} # No keys loaded initially
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'list'])

    assert result.exit_code == 0
    assert "No keys found configured via environment variables or specified key files." in result.output
    mock_display_table.assert_not_called()
    assert "Note: This list shows keys loaded" in result.output
