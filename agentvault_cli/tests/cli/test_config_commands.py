import pytest
import pathlib
from unittest.mock import patch, MagicMock, ANY, call
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
    mock_key_manager_cls.oauth_env_prefix = "AGENTVAULT_OAUTH_" # Add mock for oauth prefix
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--env'])
    assert result.exit_code == 0
    assert mock_display_info.call_count >= 5 # Check at least 5 calls
    mock_display_info.assert_any_call("Guidance: To use environment variables for 'my-service':")
    mock_display_info.assert_any_call("  For API Key: Set AGENTVAULT_KEY_MY-SERVICE=<your_api_key>")
    mock_display_info.assert_any_call("  For OAuth Client ID: Set AGENTVAULT_OAUTH_MY-SERVICE_CLIENT_ID=<your_client_id>")
    mock_display_info.assert_any_call("  For OAuth Client Secret: Set AGENTVAULT_OAUTH_MY-SERVICE_CLIENT_SECRET=<your_client_secret>")
    mock_key_manager_cls.assert_not_called() # No instance should be created

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_set_file_guidance(mock_key_manager_cls, mock_display_info, runner: CliRunner, tmp_path: pathlib.Path):
    """Test 'config set --file' provides guidance."""
    key_file = tmp_path / "keys.env"
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--file', str(key_file)])
    assert result.exit_code == 0
    assert mock_display_info.call_count >= 7 # Check more calls
    mock_display_info.assert_any_call(f"Guidance: To use a file for 'my-service':")
    mock_display_info.assert_any_call(f"  In '{key_file}' (.env format):")
    mock_display_info.assert_any_call("    my-service=<your_api_key>")
    mock_display_info.assert_any_call("    AGENTVAULT_OAUTH_my-service_CLIENT_ID=<your_client_id>")
    mock_display_info.assert_any_call(f"  Or in '{key_file}' (.json format):")
    mock_display_info.assert_any_call('    "my-service": {')
    mock_key_manager_cls.assert_not_called()

@patch('agentvault_cli.commands.config.utils.display_success')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_keyring_success(mock_prompt, mock_key_manager_cls, mock_display_success, runner: CliRunner):
    """Test 'config set --keyring' successfully sets key."""
    mock_prompt.return_value = "test-api-key"
    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True # Simulate functional keyring
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
    mock_manager_instance.use_keyring = True # Assume init check passed
    error_message = "Keyring access denied"
    mock_manager_instance.set_key_in_keyring.side_effect = av_exceptions.KeyManagementError(error_message)
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])

    assert result.exit_code == 1
    mock_display_error.assert_called_once_with(f"Failed to set API key in keyring: {error_message}")
    mock_manager_instance.set_key_in_keyring.assert_called_once()

@patch('agentvault_cli.commands.config.utils.display_error')
@patch('agentvault_cli.commands.config._agentvault_lib_imported', False)
def test_config_set_keyring_lib_missing(mock_display_error, runner: CliRunner):
     """Test 'config set --keyring' when library import failed."""
     result = runner.invoke(cli, ['config', 'set', 'keyring-service', '--keyring'])
     assert result.exit_code == 1
     mock_display_error.assert_called_once_with("Cannot use --keyring or --oauth-configure: Failed to import the 'agentvault' library.")

# --- Tests for --oauth-configure ---
@patch('agentvault_cli.commands.config.utils.display_success')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_oauth_configure_success(mock_prompt, mock_key_manager_cls, mock_display_success, runner: CliRunner):
    """Test 'config set --oauth-configure' successfully stores credentials."""
    # Simulate prompt responses
    mock_prompt.side_effect = ["test-client-id", "test-secret", "test-secret"] # ID, Secret, Confirmation
    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True # Simulate functional keyring
    mock_manager_instance.set_oauth_creds_in_keyring = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'oauth-service', '--oauth-configure'])

    assert result.exit_code == 0
    assert mock_prompt.call_count == 2 # ID prompt + Secret prompt (with confirmation)
    mock_display_success.assert_called_once_with("OAuth credentials for 'oauth-service' stored successfully in keyring.")
    mock_key_manager_cls.assert_called_once_with(use_keyring=True)
    mock_manager_instance.set_oauth_creds_in_keyring.assert_called_once_with('oauth-service', 'test-client-id', 'test-secret')

@patch('agentvault_cli.commands.config.utils.display_error')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_set_oauth_configure_keyring_unavailable(mock_key_manager_cls, mock_display_error, runner: CliRunner):
    """Test 'config set --oauth-configure' when keyring is not functional."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = False # Simulate non-functional keyring
    mock_manager_instance.set_oauth_creds_in_keyring = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'oauth-service', '--oauth-configure'])

    assert result.exit_code == 1
    # --- FIX: Assert specific call (should only be called once now) ---
    mock_display_error.assert_called_once_with("Keyring support is not available or functional. Cannot securely store OAuth credentials.")
    # --- END FIX ---
    mock_manager_instance.set_oauth_creds_in_keyring.assert_not_called() # Ensure storage wasn't attempted

@patch('agentvault_cli.commands.config.utils.display_error')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
@patch('click.prompt')
def test_config_set_oauth_configure_storage_error(mock_prompt, mock_key_manager_cls, mock_display_error, runner: CliRunner):
    """Test 'config set --oauth-configure' handles KeyManagementError during storage."""
    mock_prompt.side_effect = ["test-id", "test-secret", "test-secret"]
    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    error_message = "Failed to write to keyring"
    mock_manager_instance.set_oauth_creds_in_keyring.side_effect = av_exceptions.KeyManagementError(error_message)
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'set', 'oauth-service', '--oauth-configure'])

    assert result.exit_code == 1
    mock_display_error.assert_called_once_with(f"Failed to set OAuth credentials in keyring: {error_message}")
    mock_manager_instance.set_oauth_creds_in_keyring.assert_called_once()

@patch('agentvault_cli.commands.config.utils.display_error')
@patch('click.prompt')
def test_config_set_oauth_configure_empty_input(mock_prompt, mock_display_error, runner: CliRunner):
    """Test 'config set --oauth-configure' handles empty input."""
    # Simulate empty Client ID
    mock_prompt.side_effect = ["", "test-secret", "test-secret"]
    result = runner.invoke(cli, ['config', 'set', 'oauth-service', '--oauth-configure'])
    assert result.exit_code == 1
    # --- FIX: Use assert_called_with ---
    mock_display_error.assert_called_with("Client ID cannot be empty.")
    # --- END FIX ---

    # Simulate empty Client Secret
    mock_prompt.reset_mock(side_effect=True)
    mock_display_error.reset_mock()
    mock_prompt.side_effect = ["test-id", "", ""]
    result = runner.invoke(cli, ['config', 'set', 'oauth-service', '--oauth-configure'])
    assert result.exit_code == 1
    # --- FIX: Use assert_called_with ---
    mock_display_error.assert_called_with("Client Secret cannot be empty.")
    # --- END FIX ---


@patch('agentvault_cli.commands.config.utils.display_error')
def test_config_set_mutual_exclusivity(mock_display_error, runner: CliRunner):
    """Test error when multiple source flags are provided."""
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--env', '--keyring'])
    assert result.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")

    mock_display_error.reset_mock()
    result = runner.invoke(cli, ['config', 'set', 'my-service', '--file', 'f.txt', '--oauth-configure'])
    assert result.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")

    mock_display_error.reset_mock()
    result = runner.invoke(cli, ['config', 'set', 'my-service']) # No source
    assert result.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")


# --- Test 'config get' ---

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_api_key_only(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get' when only API key is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123"
    mock_manager_instance.get_key_source.return_value = "env"
    mock_manager_instance.get_oauth_config_status.return_value = "Not Configured" # Simulate no OAuth
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'found-service'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("Credential status for service 'found-service':")
    mock_display_info.assert_any_call("  API Key: Found (Source: ENV)")
    mock_display_info.assert_any_call("    (Use --show-key to display a masked version)")
    mock_display_info.assert_any_call("  OAuth Credentials: Not Configured")
    mock_manager_instance.get_key.assert_called_once_with('found-service')
    mock_manager_instance.get_key_source.assert_called_once_with('found-service')
    mock_manager_instance.get_oauth_config_status.assert_called_once_with('found-service')

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_api_key_show_key(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get --show-key' when API key is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123456"
    mock_manager_instance.get_key_source.return_value = "file"
    mock_manager_instance.get_oauth_config_status.return_value = "Not Configured"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'found-service', '--show-key'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("  API Key: Found (Source: FILE)")
    mock_display_info.assert_any_call("    Value (masked): foun...")

# --- Tests for OAuth in 'config get' ---
@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_oauth_only(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get' when only OAuth is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_manager_instance.get_oauth_config_status.return_value = "Configured (Source: KEYRING)"
    mock_manager_instance.get_oauth_client_id.return_value = "oauth_client_id_abc" # Needed for --show-oauth-id
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'oauth-service'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("Credential status for service 'oauth-service':")
    mock_display_info.assert_any_call("  API Key: Not Found")
    mock_display_info.assert_any_call("  OAuth Credentials: Configured (Source: KEYRING)")
    mock_display_info.assert_any_call("    (Use --show-oauth-id to display Client ID)")
    mock_manager_instance.get_oauth_config_status.assert_called_once_with('oauth-service')

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_oauth_show_id(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get --show-oauth-id' when OAuth is found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_manager_instance.get_oauth_config_status.return_value = "Configured (Source: FILE)"
    mock_manager_instance.get_oauth_client_id.return_value = "client-id-xyz"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'oauth-service', '--show-oauth-id'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("  OAuth Credentials: Configured (Source: FILE)")
    mock_display_info.assert_any_call("    Client ID: client-id-xyz")
    mock_manager_instance.get_oauth_client_id.assert_called_once_with('oauth-service')

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_found_both_show_all(mock_key_manager_cls, mock_display_info, runner: CliRunner):
    """Test 'config get' showing both API key and OAuth ID."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "api_key_123"
    mock_manager_instance.get_key_source.return_value = "env"
    mock_manager_instance.get_oauth_config_status.return_value = "Configured (Source: FILE)"
    mock_manager_instance.get_oauth_client_id.return_value = "client-id-xyz"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'both-service', '--show-key', '--show-oauth-id'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("Credential status for service 'both-service':")
    mock_display_info.assert_any_call("  API Key: Found (Source: ENV)")
    mock_display_info.assert_any_call("    Value (masked): api_...")
    mock_display_info.assert_any_call("  OAuth Credentials: Configured (Source: FILE)")
    mock_display_info.assert_any_call("    Client ID: client-id-xyz")


@patch('agentvault_cli.commands.config.utils.display_warning')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_get_not_found(mock_key_manager_cls, mock_display_warning, runner: CliRunner):
    """Test 'config get' when credentials are not found."""
    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_manager_instance.get_oauth_config_status.return_value = "Not Configured"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'get', 'missing-service'])

    assert result.exit_code == 0 # Command succeeds, just warns
    mock_display_warning.assert_called_once_with("No API key or OAuth credentials found for service 'missing-service' in any configured source (Env, File, Keyring).")

# --- Test 'config list' ---

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.utils.display_table')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_list_found(mock_key_manager_cls, mock_display_table, mock_display_info, runner: CliRunner):
    """Test 'config list' when keys/creds are found."""
    mock_manager_instance = MagicMock()
    # Simulate keys/creds loaded from env/file during init
    mock_manager_instance._key_sources = {"service1": "env", "service_file": "file", "both_svc": "file"}
    mock_manager_instance._oauth_sources = {"both_svc": "file", "oauth_only": "env"}
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'list'])

    assert result.exit_code == 0
    mock_key_manager_cls.assert_called_once_with(use_keyring=False)
    # Assert display_table was called with the correct data (sorted)
    expected_data = [
        ['both_svc', "API Key: FILE, OAuth: FILE"],
        ['oauth_only', "OAuth: ENV"],
        ['service1', "API Key: ENV"],
        ['service_file', "API Key: FILE"]
    ]
    mock_display_table.assert_called_once_with(
        "Configured Credential Sources (Env/File)",
        ["Service ID", "Source(s)"],
        expected_data
    )
    # Check the notes are displayed
    mock_display_info.assert_any_call("\nNote: This list shows credentials loaded from environment variables or key files.")

@patch('agentvault_cli.commands.config.utils.display_info')
@patch('agentvault_cli.commands.config.utils.display_table')
@patch('agentvault_cli.commands.config.key_manager.KeyManager')
def test_config_list_empty(mock_key_manager_cls, mock_display_table, mock_display_info, runner: CliRunner):
    """Test 'config list' when no keys/creds are found from env/file."""
    mock_manager_instance = MagicMock()
    mock_manager_instance._key_sources = {} # No keys loaded initially
    mock_manager_instance._oauth_sources = {} # No oauth loaded initially
    mock_key_manager_cls.return_value = mock_manager_instance

    result = runner.invoke(cli, ['config', 'list'])

    assert result.exit_code == 0
    mock_display_info.assert_any_call("No credentials found configured via environment variables or specified key files.")
    mock_display_table.assert_not_called()
    mock_display_info.assert_any_call("(Credentials stored only in the OS keyring will not be listed here unless previously accessed.)")
