import click
import logging

logger = logging.getLogger(__name__)

@click.group("config")
def config_group():
    """
    Manage local API key configurations for AgentVault services.

    Allows setting key sources (environment, file, keyring) and checking
    current configurations.
    """
    pass

# Subcommands like 'set', 'get', 'list' will be added here later
# Example:
# @config_group.command("set")
# ...
# def set_key(...):
#     pass
