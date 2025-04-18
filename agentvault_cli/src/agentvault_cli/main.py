# --- MODIFIED: Import standard click alongside asyncclick ---
import click # Import standard click
import asyncclick as aclick # Keep asyncclick aliased
# --- END MODIFIED ---
import logging
import asyncio # Keep asyncio import

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main CLI Group (Async) ---
# --- MODIFIED: Use asyncclick group ---
@aclick.group()
@aclick.version_option(package_name="agentvault-cli", prog_name="agentvault_cli")
async def cli(): # Keep this async
# --- END MODIFIED ---
    """
    AgentVault CLI: Interact with the AgentVault ecosystem.
    """
    pass

# --- Command Imports and Registration ---
# Import commands AFTER defining the group
from .commands import config # config now uses standard click
from .commands import discover
from .commands import run

# --- MODIFIED: Add config_group directly ---
cli.add_command(config.config_group) # Add the synchronous group
# --- END MODIFIED ---
cli.add_command(discover.discover_command) # discover_command is async
cli.add_command(run.run_command) # run_command is async

# --- ADDED: Entry Point Check ---
if __name__ == "__main__":
    # --- MODIFIED: asyncclick entry point ---
    cli.main()
    # --- END MODIFIED ---
# --- END ADDED ---
