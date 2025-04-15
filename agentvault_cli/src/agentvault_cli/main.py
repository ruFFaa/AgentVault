import click
import logging
import asyncio # Import asyncio
import sys # Import sys

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Main CLI Group ---
# Keep cli() synchronous as Click manages async subcommands
@click.group()
@click.version_option(package_name="agentvault-cli", prog_name="agentvault_cli")
def cli():
    """
    AgentVault CLI: Interact with the AgentVault ecosystem.

    Manage local API keys, discover agents via the registry,
    and run tasks on remote agents using the A2A protocol.
    """
    pass

# --- Command Imports and Registration ---
from .commands import config
from .commands import discover
from .commands import run

cli.add_command(config.config_group)
cli.add_command(discover.discover_command) # discover_command is async
cli.add_command(run.run_command) # run_command is async


# --- Entry Point Check ---
if __name__ == "__main__":
    # --- MODIFIED: Use asyncio.run() on the result of cli() ---
    # Click's group object, when called, returns the result of the
    # invoked command. If the command is async, this result is a
    # coroutine. We pass this coroutine to asyncio.run().
    # This seems to be the most reliable way to handle async commands
    # when the script is run directly or via `python -m`.
    command_result = cli(standalone_mode=False) # Run Click, but don't let it exit
    if asyncio.iscoroutine(command_result):
        asyncio.run(command_result)
    # If the command was synchronous, command_result is likely None or some other
    # value, and we don't need to do anything further as Click already ran it.
    # --- END MODIFIED ---
