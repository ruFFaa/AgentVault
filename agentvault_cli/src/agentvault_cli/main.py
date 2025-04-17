import click
import logging
import asyncio # Keep asyncio import

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main CLI Group (Async) ---
@click.group()
@click.version_option(package_name="agentvault-cli", prog_name="agentvault_cli")
async def cli(): # <--- Keep this async
    """
    AgentVault CLI: Interact with the AgentVault ecosystem.
    """
    pass

# --- Command Imports and Registration ---
# Import commands AFTER defining the group
from .commands import config
from .commands import discover
from .commands import run

cli.add_command(config.config_group)
cli.add_command(discover.discover_command) # discover_command is async
cli.add_command(run.run_command) # run_command is async

# --- ADDED: Entry Point Check ---
# This ensures the cli() function is called when the script is run directly
# using `python -m agentvault_cli.main`. Click should handle the async nature
# of the cli group and its subcommands automatically when invoked this way
# or via the console script entry point.
if __name__ == "__main__":
    cli() # Directly call the async group function
# --- END ADDED ---
