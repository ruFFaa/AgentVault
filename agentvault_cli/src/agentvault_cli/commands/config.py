import click
import logging
import pathlib
from typing import Optional # Added Optional

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
    Manage local API key configurations for AgentVault services.

    Allows setting key sources (environment, file, keyring) and checking
    current configurations.
    """
    pass

@config_group.command("set")
@click.argument("service_id", type=str)
@click.option("--env", "env_var", is_flag=True, help="Indicate key is set via environment variable (provides guidance).")
@click.option("--file", "key_file", type=click.Path(path_type=pathlib.Path), help="Indicate key is set in a file (provides guidance).")
@click.option("--keyring", "use_keyring", is_flag=True, help="Store the key securely in the OS keyring.")
@click.pass_context # Pass context for exiting on error
def set_key(
    ctx: click.Context,
    service_id: str,
    env_var: bool,
    key_file: Optional[pathlib.Path],
    use_keyring: bool
):
    """
    Configure the source or store the API key for a specific service.

    SERVICE_ID: The identifier for the service (e.g., 'openai', 'anthropic', 'agent-id').
    """
    # Ensure agentvault library is available for keyring operations
    if use_keyring and not _agentvault_lib_imported:
        utils.display_error("Cannot use --keyring: Failed to import the 'agentvault' library.")
        ctx.exit(1)
    if use_keyring and key_manager is None:
         utils.display_error("Cannot use --keyring: KeyManager component not found in 'agentvault' library.")
         ctx.exit(1)

    # --- Mutual Exclusivity Check ---
    num_sources = sum([env_var, bool(key_file), use_keyring])
    if num_sources != 1:
        utils.display_error("Please specify exactly one source method: --env, --file <path>, or --keyring.")
        ctx.exit(1)

    # --- Provide Guidance or Set Key ---
    if env_var:
        env_var_name = f"{key_manager.KeyManager.env_prefix if key_manager else 'AGENTVAULT_KEY_'}{service_id.upper()}"
        utils.display_info(f"Guidance: To use an environment variable for '{service_id}', set the following variable:")
        utils.display_info(f"  {env_var_name}=<your_api_key>")
        utils.display_info("Ensure this variable is set in your shell environment before running AgentVault commands.")

    elif key_file:
        utils.display_info(f"Guidance: To use a file for '{service_id}', add the following line to '{key_file}':")
        utils.display_info(f"  {service_id}=<your_api_key>")
        utils.display_info(f"Or in JSON format: \"{service_id}\": \"<your_api_key>\"")
        utils.display_info(f"IMPORTANT: Ensure the file '{key_file}' has secure permissions (e.g., chmod 600).")

    elif use_keyring:
        utils.display_info(f"Attempting to store key for '{service_id}' in the OS keyring.")
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
            # This ensures keyring support is checked again internally
            manager = key_manager.KeyManager(use_keyring=True) # Enable keyring usage

            # Attempt to set the key
            manager.set_key_in_keyring(service_id, api_key)
            utils.display_success(f"API key for '{service_id}' stored successfully in keyring.")

        except av_exceptions.KeyManagementError as e:
            utils.display_error(f"Failed to set key in keyring: {e}")
            if "keyring package is not installed" in str(e):
                 utils.display_info("Hint: Install keyring support via 'pip install agentvault[os_keyring]' or 'poetry install --extras os_keyring'")
            ctx.exit(1)
        except ImportError:
            # Should be caught by KeyManager, but as a fallback
            utils.display_error("Keyring support requires the 'keyring' package. Install with 'pip install agentvault[os_keyring]' or similar.")
            ctx.exit(1)
        except Exception as e:
            utils.display_error(f"An unexpected error occurred while setting key in keyring: {e}")
            logger.exception("Unexpected error in config set --keyring") # Log traceback for debug
            ctx.exit(1)
