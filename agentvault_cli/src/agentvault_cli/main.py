import click
import logging

# --- Basic Logging Setup ---
# Configure logging early, can be refined later
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Main CLI Group ---
@click.group()
@click.version_option(package_name="agentvault-cli", prog_name="agentvault_cli")
def cli():
    """
    AgentVault CLI: Interact with the AgentVault ecosystem.

    Manage local API keys, discover agents via the registry,
    and run tasks on remote agents using the A2A protocol.
    """
    # This main group function can be used for global setup if needed later
    # e.g., setting up global context objects, configuring logging based on flags
    pass

# --- Command Imports and Registration ---
# Import command groups/commands from other modules here
from .commands import config
# Placeholder imports - uncomment and adjust as commands are implemented
# from .commands import discover
# from .commands import run

# Add the imported commands/groups to the main CLI group
cli.add_command(config.config_group) # Register the config group
# Placeholder command additions - uncomment and adjust later
# cli.add_command(discover.discover_command, name="discover")
# cli.add_command(run.run_command, name="run")


# --- Entry Point Check ---
# Allows running the script directly for development/testing
if __name__ == "__main__":
    # In a packaged installation, the entry point defined in pyproject.toml
    # (`agentvault_cli = "agentvault_cli.main:cli"`) calls cli() directly.
    cli()
