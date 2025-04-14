import click
import logging
import pathlib
from typing import Optional

# Import AgentVault library components
try:
    from agentvault import key_manager
    from agentvault import exceptions as av_exceptions
    _agentvault_lib_imported = True
except ImportError:
    key_manager = None # type: ignore
    av_exceptions = None # type: ignore
    _agentvault_lib_imported = False

# Import local utilities
from .. import utils

logger = logging.getLogger(__name__)

@click.group("config")
def config_group():
    """
    Manage local API key and OAuth credential configurations for AgentVault services.

    Allows setting key sources (environment, file, keyring) and checking
    current configurations. Includes secure storage for OAuth credentials.
    """
    pass

@config_group.command("set")
@click.argument("service_id", type=str)
@click.option("--env", "env_var", is_flag=True, help="Indicate key is set via environment variable (provides guidance).")
@click.option("--file", "key_file", type=click.Path(path_type=pathlib.Path), help="Indicate key is set in a file (provides guidance).")
@click.option("--keyring", "use_keyring", is_flag=True, help="Store the API key securely in the OS keyring.")
@click.option("--oauth-configure", "oauth_configure", is_flag=True, help="Configure and store OAuth Client ID/Secret securely (prefers keyring).")
@click.pass_context # Pass context for exiting on error
def set_key(
    ctx: click.Context,
    service_id: str,
    env_var: bool,
    key_file: Optional[pathlib.Path],
    use_keyring: bool,
    oauth_configure: bool
):
    """
    Configure the source or store credentials for a specific service.

    Use --env or --file to provide guidance on setting credentials externally.

    Use --keyring to securely store an API key in the OS keyring.

    Use --oauth-configure to securely store OAuth2 Client ID and Secret
    in the OS keyring (required for agents using the 'oauth2' scheme).

    SERVICE_ID: The identifier for the service (e.g., 'openai', 'anthropic', 'agent-id').
    """
    # Ensure agentvault library is available for keyring/oauth operations
    if (use_keyring or oauth_configure) and not _agentvault_lib_imported:
        utils.display_error("Cannot use --keyring or --oauth-configure: Failed to import the 'agentvault' library.")
        ctx.exit(1)
    if (use_keyring or oauth_configure) and key_manager is None:
         utils.display_error("Cannot use --keyring or --oauth-configure: KeyManager component not found in 'agentvault' library.")
         ctx.exit(1)

    # Mutual Exclusivity Check
    num_sources = sum([env_var, bool(key_file), use_keyring, oauth_configure])
    if num_sources != 1:
        utils.display_error("Please specify exactly one configuration method: --env, --file <path>, --keyring, or --oauth-configure.")
        ctx.exit(1)

    # Provide Guidance or Set Key/Creds
    if env_var:
        # Use the default prefix from KeyManager if available, otherwise fallback
        api_key_prefix = key_manager.KeyManager.env_prefix if key_manager else 'AGENTVAULT_KEY_'
        oauth_prefix = key_manager.KeyManager.oauth_env_prefix if key_manager else 'AGENTVAULT_OAUTH_'
        service_upper = service_id.upper()

        utils.display_info(f"Guidance: To use environment variables for '{service_id}':")
        utils.display_info(f"  For API Key: Set {api_key_prefix}{service_upper}=<your_api_key>")
        utils.display_info(f"  For OAuth Client ID: Set {oauth_prefix}{service_upper}_CLIENT_ID=<your_client_id>")
        utils.display_info(f"  For OAuth Client Secret: Set {oauth_prefix}{service_upper}_CLIENT_SECRET=<your_client_secret>")
        utils.display_info("Ensure these variables are set in your shell environment before running AgentVault commands.")

    elif key_file:
        utils.display_info(f"Guidance: To use a file for '{service_id}':")
        utils.display_info(f"  In '{key_file}' (.env format):")
        utils.display_info(f"    {service_id.lower()}=<your_api_key>")
        utils.display_info(f"    AGENTVAULT_OAUTH_{service_id.lower()}_CLIENT_ID=<your_client_id>")
        utils.display_info(f"    AGENTVAULT_OAUTH_{service_id.lower()}_CLIENT_SECRET=<your_client_secret>")
        utils.display_info(f"  Or in '{key_file}' (.json format):")
        utils.display_info(f'    "{service_id.lower()}": {{')
        utils.display_info(f'      "apiKey": "<your_api_key>",')
        utils.display_info(f'      "oauth": {{ "clientId": "<your_client_id>", "clientSecret": "<your_client_secret>" }}')
        utils.display_info(f'    }}')
        utils.display_info(f"IMPORTANT: Ensure the file '{key_file}' has secure permissions (e.g., chmod 600).")

    elif use_keyring:
        utils.display_info(f"Attempting to store API key for '{service_id}' in the OS keyring.")
        try:
            # Prompt securely for the API key
            api_key = click.prompt(
                f"Enter API key for '{service_id}'",
                hide_input=True,
                confirmation_prompt=True # Ask user to enter it twice
            )
            if not api_key:
                 utils.display_error("API key cannot be empty.")
                 ctx.exit(1)

            # Instantiate KeyManager specifically for this operation
            manager = key_manager.KeyManager(use_keyring=True) # Enable keyring usage
            if not manager.use_keyring: # Check if keyring is actually functional
                 utils.display_error("Keyring support is enabled but the backend is not functional. Cannot store key.")
                 utils.display_info("Hint: Check keyring documentation for backend setup or install 'keyrings.alt'.")
                 ctx.exit(1)

            # Attempt to set the key
            manager.set_key_in_keyring(service_id, api_key)
            utils.display_success(f"API key for '{service_id}' stored successfully in keyring.")

        except av_exceptions.KeyManagementError as e:
            utils.display_error(f"Failed to set API key in keyring: {e}")
            if "keyring package is not installed" in str(e):
                 utils.display_info("Hint: Install keyring support via 'pip install agentvault[os_keyring]' or 'poetry install --extras os_keyring'")
            ctx.exit(1)
        except ImportError:
            # Should be caught by KeyManager, but as a fallback
            utils.display_error("Keyring support requires the 'keyring' package. Install with 'pip install agentvault[os_keyring]' or similar.")
            ctx.exit(1)
        except click.exceptions.Exit: # Catch click's exit exception
            raise # Re-raise to let click handle it
        except Exception as e:
            utils.display_error(f"An unexpected error occurred while setting API key in keyring: {e}")
            logger.exception("Unexpected error in config set --keyring") # Log traceback for debug
            ctx.exit(1)

    elif oauth_configure:
        utils.display_info(f"Configuring OAuth 2.0 Client Credentials for '{service_id}' (will store in OS keyring if available).")
        try:
            # Instantiate KeyManager, prioritizing keyring
            manager = key_manager.KeyManager(use_keyring=True)
            if not manager.use_keyring:
                 utils.display_error("Keyring support is not available or functional. Cannot securely store OAuth credentials.")
                 utils.display_info("Hint: Check keyring documentation for backend setup or install 'keyrings.alt'.")
                 ctx.exit(1)
                 # return # Explicit return after exit (already added, keep)

            # Prompt for Client ID
            client_id = click.prompt(f"Enter OAuth Client ID for '{service_id}'", hide_input=False)
            if not client_id:
                utils.display_error("Client ID cannot be empty.")
                ctx.exit(1)

            # Prompt securely for Client Secret
            client_secret = click.prompt(
                f"Enter OAuth Client Secret for '{service_id}'",
                hide_input=True,
                confirmation_prompt=True
            )
            if not client_secret:
                 utils.display_error("Client Secret cannot be empty.")
                 ctx.exit(1)

            # Attempt to store credentials in keyring
            manager.set_oauth_creds_in_keyring(service_id, client_id, client_secret)
            utils.display_success(f"OAuth credentials for '{service_id}' stored successfully in keyring.")

        except av_exceptions.KeyManagementError as e:
            utils.display_error(f"Failed to set OAuth credentials in keyring: {e}")
            ctx.exit(1)
        except NotImplementedError: # Catch if set_oauth_creds_in_keyring is still a stub
             utils.display_error("Storing OAuth credentials is not fully implemented in the library yet.")
             ctx.exit(1)
        # --- ADDED: Catch Exit before generic Exception ---
        except click.exceptions.Exit:
            raise # Re-raise to let click handle it
        # --- END ADDED ---
        except Exception as e:
            utils.display_error(f"An unexpected error occurred while setting OAuth credentials: {e}")
            logger.exception("Unexpected error in config set --oauth-configure")
            ctx.exit(1)


@config_group.command("get")
@click.argument("service_id", type=str)
@click.option("--show-key", is_flag=True, help="Display the first few characters of the API key (use with caution).")
@click.option("--show-oauth-id", is_flag=True, help="Display the configured OAuth Client ID.")
@click.pass_context
def get_key(ctx: click.Context, service_id: str, show_key: bool, show_oauth_id: bool):
    """
    Check how credentials (API key, OAuth) for a service are being sourced.

    Checks environment variables, configured key files, and the OS keyring (if enabled).
    Use --show-oauth-id to display the Client ID if OAuth is configured.

    SERVICE_ID: The identifier for the service (e.g., 'openai', 'anthropic', 'agent-id').
    """
    if not _agentvault_lib_imported or key_manager is None:
        utils.display_error("Cannot get credential source: Failed to import the 'agentvault' library or KeyManager.")
        ctx.exit(1)

    try:
        # Instantiate KeyManager, enabling keyring to check all potential sources
        manager = key_manager.KeyManager(use_keyring=True)

        # Check API Key
        key_value = manager.get_key(service_id)
        key_source = manager.get_key_source(service_id)

        # Check OAuth Config Status
        oauth_status = manager.get_oauth_config_status(service_id)

        found_anything = bool(key_value) or (oauth_status != "Not Configured")

        if not found_anything:
            utils.display_warning(f"No API key or OAuth credentials found for service '{service_id}' in any configured source (Env, File, Keyring).")
            utils.display_info("Use 'config set' to configure credentials.")
        else:
            utils.display_info(f"Credential status for service '{service_id}':")
            if key_value:
                utils.display_info(f"  API Key: Found (Source: {key_source.upper() if key_source else 'Unknown'})")
                if show_key:
                    masked_key = key_value[:4] + '...' * (len(key_value) > 4)
                    utils.display_info(f"    Value (masked): {masked_key}")
                else:
                     utils.display_info("    (Use --show-key to display a masked version)")
            else:
                utils.display_info("  API Key: Not Found")

            utils.display_info(f"  OAuth Credentials: {oauth_status}")
            if show_oauth_id and oauth_status != "Not Configured":
                client_id = manager.get_oauth_client_id(service_id)
                if client_id:
                    utils.display_info(f"    Client ID: {client_id}")
                else:
                     # This case might happen if only secret is found, or error during get
                     utils.display_info("    Client ID: Not Found (Status indicates partial config or error)")
            elif oauth_status != "Not Configured":
                 utils.display_info("    (Use --show-oauth-id to display Client ID)")
            # Note: Never display client secret here

    except Exception as e:
        utils.display_error(f"An unexpected error occurred while getting credential source: {e}")
        logger.exception(f"Unexpected error in config get for service '{service_id}'")
        ctx.exit(1)


@config_group.command("list")
@click.pass_context
def list_keys(ctx: click.Context):
    """
    List services with credentials found via environment variables or key files.

    This command shows keys/creds loaded during the KeyManager initialization.
    It does not actively scan the OS keyring unless previously accessed.
    """
    if not _agentvault_lib_imported or key_manager is None:
        utils.display_error("Cannot list credentials: Failed to import the 'agentvault' library or KeyManager.")
        ctx.exit(1)

    try:
        # Instantiate KeyManager without enabling keyring for this list command
        manager = key_manager.KeyManager(use_keyring=False)

        # Access the sources identified during initialization
        api_key_sources = manager._key_sources
        oauth_sources = manager._oauth_sources # Get OAuth sources as well

        # Combine sources for display
        all_services = set(api_key_sources.keys()) | set(oauth_sources.keys())

        if not all_services:
            utils.display_info("No credentials found configured via environment variables or specified key files.")
            utils.display_info("(Credentials stored only in the OS keyring will not be listed here unless previously accessed.)")
            return

        # Prepare data for the table
        data = []
        for service_id in sorted(list(all_services)):
            api_source = api_key_sources.get(service_id)
            oauth_source = oauth_sources.get(service_id)
            source_str = ""
            if api_source and oauth_source:
                source_str = f"API Key: {api_source.upper()}, OAuth: {oauth_source.upper()}"
            elif api_source:
                source_str = f"API Key: {api_source.upper()}"
            elif oauth_source:
                 source_str = f"OAuth: {oauth_source.upper()}"
            data.append([service_id, source_str])

        utils.display_table("Configured Credential Sources (Env/File)", ["Service ID", "Source(s)"], data)
        utils.display_info("\nNote: This list shows credentials loaded from environment variables or key files.")
        utils.display_info("Credentials stored only in the OS keyring are typically loaded on demand and")
        utils.display_info("may not appear here unless accessed by 'config get' or an agent run.")

    except Exception as e:
        utils.display_error(f"An unexpected error occurred while listing credential sources: {e}")
        logger.exception("Unexpected error in config list")
        ctx.exit(1)
