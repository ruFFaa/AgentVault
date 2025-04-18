import pytest
import pathlib
# --- MODIFIED: Added AsyncMock ---
from unittest.mock import patch, MagicMock, ANY, call, AsyncMock
# --- END MODIFIED ---
from pytest_mock import MockerFixture
# --- MODIFIED: Import asyncclick runner and exceptions ---
import asyncclick as click # Use asyncclick alias
from asyncclick.testing import CliRunner # Use asyncclick runner
# --- END MODIFIED ---

# Import the specific command group directly
from agentvault_cli.commands.config import config_group
# Import utils for assertion
from agentvault_cli import utils

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
    # --- MODIFIED: Use asyncclick runner ---
    return CliRunner()
    # --- END MODIFIED ---

# --- Test 'config set' ---

# --- MODIFIED: Mark as async, use await runner.invoke, fix patch targets ---
@pytest.mark.asyncio
async def test_config_set_env_guidance(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --env' provides guidance."""
    # Patch utils where they are used in config.py
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    # Patch KeyManager where it's accessed in config.py
    mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager.env_prefix', "AGENTVAULT_KEY_")
    mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager.oauth_env_prefix', "AGENTVAULT_OAUTH_")

    result = await runner.invoke(config_group, ['set', 'my-service', '--env'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("Guidance: To use environment variables for 'my-service':")
    mock_display_info.assert_any_call("  For API Key: Set AGENTVAULT_KEY_MY-SERVICE=<your_api_key>")
    mock_display_info.assert_any_call("  For OAuth Client ID: Set AGENTVAULT_OAUTH_MY-SERVICE_CLIENT_ID=<your_client_id>")
    mock_display_info.assert_any_call("  For OAuth Client Secret: Set AGENTVAULT_OAUTH_MY-SERVICE_CLIENT_SECRET=<your_client_secret>")

@pytest.mark.asyncio
async def test_config_set_file_guidance(runner: CliRunner, mocker: MockerFixture, tmp_path: pathlib.Path):
    """Test 'config set --file' provides guidance."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    key_file = tmp_path / "keys.env"

    result = await runner.invoke(config_group, ['set', 'my-service', '--file', str(key_file)])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call(f"Guidance: To use a file for 'my-service':")
    mock_display_info.assert_any_call(f"  In '{key_file}' (.env format):")
    mock_display_info.assert_any_call("    my-service=<your_api_key>")
    mock_display_info.assert_any_call("    AGENTVAULT_OAUTH_my-service_CLIENT_ID=<your_client_id>")
    mock_display_info.assert_any_call(f"  Or in '{key_file}' (.json format):")
    mock_display_info.assert_any_call('    "my-service": {')

@pytest.mark.asyncio
async def test_config_set_keyring_success(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --keyring' successfully sets key."""
    mock_display_success = mocker.patch('agentvault_cli.commands.config.utils.display_success')
    # Patch KeyManager where it's imported/used in config.py
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')
    # Patch prompt where it's used in config.py
    # --- MODIFIED: Added AsyncMock ---
    mock_prompt = mocker.patch('agentvault_cli.commands.config.click.prompt', new_callable=AsyncMock, side_effect=["test-api-key", "test-api-key"])
    # --- END MODIFIED ---

    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    mock_manager_instance.set_key_in_keyring = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(
        config_group,
        ['set', 'keyring-service', '--keyring']
        # Input is handled by mocked prompt now
    )

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_success.assert_called_once_with("API key for 'keyring-service' stored successfully in keyring.")
    # --- MODIFIED: Assert await_count == 1 ---
    assert mock_prompt.await_count == 1 # Check async mock was awaited once
    # --- END MODIFIED ---
    mock_key_manager_cls.assert_called_once_with(use_keyring=True)
    mock_manager_instance.set_key_in_keyring.assert_called_once_with('keyring-service', 'test-api-key')

@pytest.mark.asyncio
async def test_config_set_keyring_error(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --keyring' handles KeyManagementError."""
    mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')
    # --- MODIFIED: Added AsyncMock ---
    mock_prompt = mocker.patch('agentvault_cli.commands.config.click.prompt', new_callable=AsyncMock, side_effect=["test-api-key", "test-api-key"])
    # --- END MODIFIED ---

    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    error_message = "Keyring access denied"
    mock_manager_instance.set_key_in_keyring.side_effect = av_exceptions.KeyManagementError(error_message)
    mock_key_manager_cls.return_value = mock_manager_instance

    # --- MODIFIED: Check exit code ---
    result = await runner.invoke(
        config_group,
        ['set', 'keyring-service', '--keyring'],
        catch_exceptions=True # Catch the exit
    )
    assert result.exit_code == 1, "Command should have failed due to KeyManagementError" # Check exit code
    # --- END MODIFIED ---
    mock_display_error.assert_any_call(f"Failed to set API key in keyring: {error_message}")
    mock_manager_instance.set_key_in_keyring.assert_called_once()

@pytest.mark.asyncio
async def test_config_set_keyring_lib_missing(runner: CliRunner, mocker: MockerFixture):
     """Test 'config set --keyring' when library import failed."""
     mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')
     # Patch the import check flag within the config module
     mocker.patch('agentvault_cli.commands.config._agentvault_lib_imported', False)

     # --- MODIFIED: Check exit code ---
     result = await runner.invoke(config_group, ['set', 'keyring-service', '--keyring'], catch_exceptions=True)
     assert result.exit_code == 1, "Command should have failed due to missing library" # Check exit code
     # --- END MODIFIED ---
     mock_display_error.assert_called_once_with("Cannot use --keyring or --oauth-configure: Failed to import the 'agentvault' library.")

# --- Tests for --oauth-configure ---
@pytest.mark.asyncio
async def test_config_set_oauth_configure_success(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --oauth-configure' successfully stores credentials."""
    mock_display_success = mocker.patch('agentvault_cli.commands.config.utils.display_success')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')
    # --- MODIFIED: Added AsyncMock ---
    mock_prompt = mocker.patch('agentvault_cli.commands.config.click.prompt', new_callable=AsyncMock, side_effect=["test-client-id", "test-secret", "test-secret"])
    # --- END MODIFIED ---

    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    mock_manager_instance.set_oauth_creds_in_keyring = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(
        config_group,
        ['set', 'oauth-service', '--oauth-configure']
    )

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    # --- MODIFIED: Assert await_count == 2 ---
    assert mock_prompt.await_count == 2 # Check async mock was awaited twice
    # --- END MODIFIED ---
    mock_display_success.assert_called_once_with("OAuth credentials for 'oauth-service' stored successfully in keyring.")
    mock_key_manager_cls.assert_called_once_with(use_keyring=True)
    mock_manager_instance.set_oauth_creds_in_keyring.assert_called_once_with('oauth-service', 'test-client-id', 'test-secret')

@pytest.mark.asyncio
async def test_config_set_oauth_configure_keyring_unavailable(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --oauth-configure' when keyring is not functional."""
    mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = False # Simulate non-functional keyring
    mock_manager_instance.set_oauth_creds_in_keyring = MagicMock()
    mock_key_manager_cls.return_value = mock_manager_instance

    # --- MODIFIED: Check exit code and error message display ---
    result = await runner.invoke(
        config_group,
        ['set', 'oauth-service', '--oauth-configure'],
        catch_exceptions=True # Catch exit
    )
    assert result.exit_code == 1, "Command should have failed due to unavailable keyring" # Check exit code
    mock_display_error.assert_called_once_with("Keyring support is not available or functional. Cannot securely store OAuth credentials.")
    # --- END MODIFIED ---
    mock_display_info.assert_any_call("Hint: Check keyring documentation for backend setup or install 'keyrings.alt'.")
    mock_manager_instance.set_oauth_creds_in_keyring.assert_not_called()

@pytest.mark.asyncio
async def test_config_set_oauth_configure_storage_error(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --oauth-configure' handles KeyManagementError during storage."""
    mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')
    # --- MODIFIED: Added AsyncMock ---
    mock_prompt = mocker.patch('agentvault_cli.commands.config.click.prompt', new_callable=AsyncMock, side_effect=["test-id", "test-secret", "test-secret"])
    # --- END MODIFIED ---

    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    error_message = "Failed to write to keyring"
    mock_manager_instance.set_oauth_creds_in_keyring.side_effect = av_exceptions.KeyManagementError(error_message)
    mock_key_manager_cls.return_value = mock_manager_instance

    # --- MODIFIED: Check exit code ---
    result = await runner.invoke(
        config_group,
        ['set', 'oauth-service', '--oauth-configure'],
        catch_exceptions=True # Catch exit
    )
    assert result.exit_code == 1, "Command should have failed due to KeyManagementError" # Check exit code
    # --- END MODIFIED ---
    mock_display_error.assert_any_call(f"Failed to set OAuth credentials in keyring: {error_message}")
    mock_manager_instance.set_oauth_creds_in_keyring.assert_called_once()

# --- MODIFIED: Split into two tests ---
@pytest.mark.asyncio
async def test_config_set_oauth_configure_empty_client_id(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --oauth-configure' handles empty client ID."""
    mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')
    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    mock_key_manager_cls.return_value = mock_manager_instance
    # --- MODIFIED: Added AsyncMock ---
    mock_prompt = mocker.patch('agentvault_cli.commands.config.click.prompt', new_callable=AsyncMock, side_effect=["", "test-secret", "test-secret"]) # Empty first prompt
    # --- END MODIFIED ---

    result = await runner.invoke(
        config_group,
        ['set', 'oauth-service', '--oauth-configure'],
        catch_exceptions=True
    )
    assert result.exit_code == 1, f"CLI Error (Empty ID): {result.output}"
    # --- MODIFIED: Use assert_any_call ---
    mock_display_error.assert_any_call("Client ID cannot be empty.")
    # --- END MODIFIED ---
    mock_manager_instance.set_oauth_creds_in_keyring.assert_not_called()
    mock_prompt.assert_awaited_once()

@pytest.mark.asyncio
async def test_config_set_oauth_configure_empty_secret(runner: CliRunner, mocker: MockerFixture):
    """Test 'config set --oauth-configure' handles empty client secret."""
    mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')
    mock_manager_instance = MagicMock()
    mock_manager_instance.use_keyring = True
    mock_key_manager_cls.return_value = mock_manager_instance
    # --- MODIFIED: Added AsyncMock ---
    mock_prompt = mocker.patch('agentvault_cli.commands.config.click.prompt', new_callable=AsyncMock, side_effect=["test-id", "", ""]) # Empty second prompt
    # --- END MODIFIED ---

    result = await runner.invoke(
        config_group,
        ['set', 'oauth-service', '--oauth-configure'],
        catch_exceptions=True
    )
    assert result.exit_code == 1, f"CLI Error (Empty Secret): {result.output}"
    # --- MODIFIED: Use assert_any_call ---
    mock_display_error.assert_any_call("Client Secret cannot be empty.")
    # --- END MODIFIED ---
    mock_manager_instance.set_oauth_creds_in_keyring.assert_not_called()
    assert mock_prompt.await_count == 2
# --- END MODIFIED ---

@pytest.mark.asyncio
async def test_config_set_mutual_exclusivity(runner: CliRunner, mocker: MockerFixture):
    """Test error when multiple source flags are provided."""
    mock_display_error = mocker.patch('agentvault_cli.commands.config.utils.display_error')

    # --- MODIFIED: Check exit code ---
    result1 = await runner.invoke(config_group, ['set', 'my-service', '--env', '--keyring'], catch_exceptions=True)
    assert result1.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")

    mock_display_error.reset_mock()
    result2 = await runner.invoke(config_group, ['set', 'my-service', '--file', 'f.txt', '--oauth-configure'], catch_exceptions=True)
    assert result2.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")

    mock_display_error.reset_mock()
    result3 = await runner.invoke(config_group, ['set', 'my-service'], catch_exceptions=True)
    assert result3.exit_code == 1
    mock_display_error.assert_called_once_with("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")
    # --- END MODIFIED ---


# --- Test 'config get' ---
@pytest.mark.asyncio
async def test_config_get_found_api_key_only(runner: CliRunner, mocker: MockerFixture):
    """Test 'config get' when only API key is found."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123"
    mock_manager_instance.get_key_source.return_value = "env"
    mock_manager_instance.get_oauth_config_status.return_value = "Not Configured"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['get', 'found-service'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("Credential status for service 'found-service':")
    mock_display_info.assert_any_call("  API Key: Found (Source: ENV)")
    mock_display_info.assert_any_call("    (Use --show-key to display a masked version)")
    mock_display_info.assert_any_call("  OAuth Credentials: Not Configured")
    mock_manager_instance.get_key.assert_called_once_with('found-service')
    mock_manager_instance.get_key_source.assert_called_once_with('found-service')
    mock_manager_instance.get_oauth_config_status.assert_called_once_with('found-service')

@pytest.mark.asyncio
async def test_config_get_found_api_key_show_key(runner: CliRunner, mocker: MockerFixture):
    """Test 'config get --show-key' when API key is found."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "found_key_123456"
    mock_manager_instance.get_key_source.return_value = "file"
    mock_manager_instance.get_oauth_config_status.return_value = "Not Configured"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['get', 'found-service', '--show-key'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("  API Key: Found (Source: FILE)")
    mock_display_info.assert_any_call("    Value (masked): foun...")

# --- Tests for OAuth in 'config get' ---
@pytest.mark.asyncio
async def test_config_get_found_oauth_only(runner: CliRunner, mocker: MockerFixture):
    """Test 'config get' when only OAuth is found."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_manager_instance.get_oauth_config_status.return_value = "Configured (Source: KEYRING)"
    mock_manager_instance.get_oauth_client_id.return_value = "oauth_client_id_abc"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['get', 'oauth-service'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("Credential status for service 'oauth-service':")
    mock_display_info.assert_any_call("  API Key: Not Found")
    mock_display_info.assert_any_call("  OAuth Credentials: Configured (Source: KEYRING)")
    mock_display_info.assert_any_call("    (Use --show-oauth-id to display Client ID)")
    mock_manager_instance.get_oauth_config_status.assert_called_once_with('oauth-service')

@pytest.mark.asyncio
async def test_config_get_found_oauth_show_id(runner: CliRunner, mocker: MockerFixture):
    """Test 'config get --show-oauth-id' when OAuth is found."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_manager_instance.get_oauth_config_status.return_value = "Configured (Source: FILE)"
    mock_manager_instance.get_oauth_client_id.return_value = "client-id-xyz"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['get', 'oauth-service', '--show-oauth-id'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("  OAuth Credentials: Configured (Source: FILE)")
    mock_display_info.assert_any_call("    Client ID: client-id-xyz")
    mock_manager_instance.get_oauth_client_id.assert_called_once_with('oauth-service')

@pytest.mark.asyncio
async def test_config_get_found_both_show_all(runner: CliRunner, mocker: MockerFixture):
    """Test 'config get' showing both API key and OAuth ID."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = "api_key_123"
    mock_manager_instance.get_key_source.return_value = "env"
    mock_manager_instance.get_oauth_config_status.return_value = "Configured (Source: FILE)"
    mock_manager_instance.get_oauth_client_id.return_value = "client-id-xyz"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['get', 'both-service', '--show-key', '--show-oauth-id'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("Credential status for service 'both-service':")
    mock_display_info.assert_any_call("  API Key: Found (Source: ENV)")
    mock_display_info.assert_any_call("    Value (masked): api_...")
    mock_display_info.assert_any_call("  OAuth Credentials: Configured (Source: FILE)")
    mock_display_info.assert_any_call("    Client ID: client-id-xyz")

@pytest.mark.asyncio
async def test_config_get_not_found(runner: CliRunner, mocker: MockerFixture):
    """Test 'config get' when credentials are not found."""
    mock_display_warning = mocker.patch('agentvault_cli.commands.config.utils.display_warning')
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance.get_key.return_value = None
    mock_manager_instance.get_key_source.return_value = None
    mock_manager_instance.get_oauth_config_status.return_value = "Not Configured"
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['get', 'missing-service'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_warning.assert_called_once_with("No API key or OAuth credentials found for service 'missing-service' in any configured source (Env, File, Keyring).")
    mock_display_info.assert_any_call("Use 'config set' to configure credentials.")

# --- Test 'config list' ---
@pytest.mark.asyncio
async def test_config_list_found(runner: CliRunner, mocker: MockerFixture):
    """Test 'config list' when keys/creds are found."""
    mock_display_table = mocker.patch('agentvault_cli.commands.config.utils.display_table')
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance._key_sources = {"service1": "env", "service_file": "file", "both_svc": "file"}
    mock_manager_instance._oauth_sources = {"both_svc": "file", "oauth_only": "env"}
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['list'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_key_manager_cls.assert_called_once_with(use_keyring=False)
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
    mock_display_info.assert_any_call("\nNote: This list shows credentials loaded from environment variables or key files.")

@pytest.mark.asyncio
async def test_config_list_empty(runner: CliRunner, mocker: MockerFixture):
    """Test 'config list' when no keys/creds are found from env/file."""
    mock_display_info = mocker.patch('agentvault_cli.commands.config.utils.display_info')
    mock_display_table = mocker.patch('agentvault_cli.commands.config.utils.display_table')
    mock_key_manager_cls = mocker.patch('agentvault_cli.commands.config.key_manager.KeyManager')

    mock_manager_instance = MagicMock()
    mock_manager_instance._key_sources = {}
    mock_manager_instance._oauth_sources = {}
    mock_key_manager_cls.return_value = mock_manager_instance

    result = await runner.invoke(config_group, ['list'])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    mock_display_info.assert_any_call("No credentials found configured via environment variables or specified key files.")
    mock_display_table.assert_not_called()
    mock_display_info.assert_any_call("(Credentials stored only in the OS keyring will not be listed here unless previously accessed.)")
# --- END MODIFIED ---
