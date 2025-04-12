import click
import httpx
import pathlib
import logging
import asyncio
import json # For parsing context file
from typing import Optional, Dict, Any

# Import local utilities
from .. import utils

# Import AgentVault library components
try:
    from agentvault import agent_card_utils
    from agentvault import exceptions as av_exceptions
    from agentvault import models as av_models
    from agentvault import key_manager # Needed later
    from agentvault import client as av_client # Needed later
    _agentvault_lib_imported = True
except ImportError as e:
    utils.display_error(f"Fatal: Failed to import core 'agentvault' library: {e}")
    utils.display_error("Please ensure 'agentvault_library' is installed correctly (e.g., `poetry install` in root).")
    # Set placeholders to allow CLI structure to load, but commands will fail
    agent_card_utils = None # type: ignore
    av_exceptions = None # type: ignore
    av_models = None # type: ignore
    key_manager = None # type: ignore
    av_client = None # type: ignore
    _agentvault_lib_imported = False

# Import default registry URL from discover command
try:
    from .discover import DEFAULT_REGISTRY_URL
except ImportError:
    # Fallback if discover isn't created yet (shouldn't happen in sequence)
    DEFAULT_REGISTRY_URL = "http://localhost:8000"

logger = logging.getLogger(__name__)

# --- Helper for Agent Card Loading ---

async def _load_agent_card(
    agent_ref: str, registry_url: str, ctx: click.Context
) -> Optional[av_models.AgentCard]:
    """Loads agent card from ID, URL, or file."""
    if not _agentvault_lib_imported or agent_card_utils is None:
         utils.display_error("AgentVault library not available for loading agent card.")
         return None # Cannot proceed

    utils.display_info(f"Attempting to load agent card from reference: {agent_ref}")
    agent_card: Optional[av_models.AgentCard] = None

    try:
        if agent_ref.startswith("http://") or agent_ref.startswith("https://"):
            utils.display_info("Reference looks like a URL, fetching...")
            agent_card = await agent_card_utils.fetch_agent_card_from_url(agent_ref)
        else:
            agent_path = pathlib.Path(agent_ref)
            if agent_path.is_file() and agent_path.suffix.lower() == ".json":
                utils.display_info("Reference looks like a local JSON file, loading...")
                agent_card = agent_card_utils.load_agent_card_from_file(agent_path)
            elif agent_path.is_file(): # Allow non-.json files if they are valid cards
                 utils.display_warning(f"Reference is a file but not '.json'. Attempting to load anyway: {agent_ref}")
                 agent_card = agent_card_utils.load_agent_card_from_file(agent_path)
            else:
                # Assume it's an ID to look up in the registry
                utils.display_info(f"Reference looks like an ID, querying registry: {registry_url}")
                api_endpoint = f"{registry_url.rstrip('/')}/api/v1/agent-cards"
                # Use 'search' param to find by ID (assuming registry supports exact match or filtering)
                params = {"search": agent_ref, "limit": 2, "active_only": True}
                async with httpx.AsyncClient() as client:
                    response = await client.get(api_endpoint, params=params, timeout=15.0)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    if len(items) == 1:
                        # Found unique match by ID via search
                        # The registry returns summaries, need to fetch full card
                        card_summary = items[0]
                        card_id = card_summary.get("id")
                        if not card_id:
                             raise av_exceptions.AgentCardError("Registry search result missing agent ID.")
                        utils.display_info(f"Found agent ID {card_id} via search, fetching full card...")
                        full_card_url = f"{registry_url.rstrip('/')}/api/v1/agent-cards/{card_id}"
                        async with httpx.AsyncClient() as client_detail:
                             response_detail = await client_detail.get(full_card_url, timeout=15.0)
                        if response_detail.status_code == 200:
                             card_full_data = response_detail.json()
                             # Parse the full card data received from the detail endpoint
                             agent_card = agent_card_utils.parse_agent_card_from_dict(card_full_data.get("card_data", {}))
                        else:
                             raise av_exceptions.AgentCardFetchError(f"Failed to fetch full agent card details for ID {card_id} (Status {response_detail.status_code})", status_code=response_detail.status_code, response_body=response_detail.text)

                    elif len(items) > 1:
                        raise av_exceptions.AgentCardError(f"Ambiguous agent ID '{agent_ref}': Multiple agents found via search.")
                    else:
                        raise av_exceptions.AgentCardError(f"Agent ID '{agent_ref}' not found in registry via search.")
                else:
                    raise av_exceptions.AgentCardFetchError(f"Registry API error searching for agent ID '{agent_ref}' (Status {response.status_code})", status_code=response.status_code, response_body=response.text)

    except av_exceptions.AgentCardError as e:
        utils.display_error(f"Failed to load agent card: {e}")
        return None
    except httpx.RequestError as e:
        utils.display_error(f"Network error while loading agent card: {e}")
        return None
    except Exception as e:
        utils.display_error(f"An unexpected error occurred loading agent card: {e}")
        logger.exception("Unexpected error in _load_agent_card")
        return None

    return agent_card


# --- Main Run Command ---

@click.command("run")
@click.option("--agent", "-a", "agent_ref", required=True, help="Agent identifier: ID (e.g., 'org/agent'), URL (https://...), or local file path.")
@click.option("--input", "-i", "input_data", required=True, help="Input text for the agent, or '@filepath' to read from a file.")
@click.option("--context-file", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path), help="Path to a JSON file containing MCP context.")
@click.option("--registry", "registry_url", default=DEFAULT_REGISTRY_URL, help="URL of the AgentVault Registry API (used if agent ID is provided).", show_default=True, envvar="AGENTVAULT_REGISTRY_URL")
@click.option("--key-service", "key_service_override", help="Override the service ID used for key lookup (if agent card doesn't specify or is ambiguous).")
@click.option("--auth-key", "auth_key_override", help="Directly provide the API key (INSECURE - for testing only).")
@click.pass_context
async def run_command(
    ctx: click.Context,
    agent_ref: str,
    input_data: str,
    context_file: Optional[pathlib.Path],
    registry_url: str,
    key_service_override: Optional[str],
    auth_key_override: Optional[str]
):
    """
    Run a task on a specified remote agent using the A2A protocol.
    """
    if not _agentvault_lib_imported:
        utils.display_error("Cannot run task: Core 'agentvault' library failed to import.")
        ctx.exit(1)

    # 1. Load Agent Card
    agent_card = await _load_agent_card(agent_ref, registry_url, ctx)
    if agent_card is None:
        # Error message already displayed by _load_agent_card
        ctx.exit(1)
    utils.display_success(f"Successfully loaded agent: {agent_card.name} ({agent_card.human_readable_id})")
    utils.display_info(f"Agent A2A Endpoint: {agent_card.url}")

    # 2. Process Input Data (Placeholder for REQ-CLI-RUN-002)
    # TODO: Handle reading input from file if input_data starts with '@'
    processed_input_text = input_data
    if input_data.startswith('@'):
        input_file_path = pathlib.Path(input_data[1:])
        if not input_file_path.is_file():
            utils.display_error(f"Input file not found: {input_file_path}")
            ctx.exit(1)
        try:
            processed_input_text = input_file_path.read_text(encoding='utf-8')
            utils.display_info(f"Read input from file: {input_file_path}")
        except Exception as e:
            utils.display_error(f"Failed to read input file {input_file_path}: {e}")
            ctx.exit(1)


    # 3. Load MCP Context (Placeholder for REQ-CLI-RUN-002)
    mcp_context_data: Optional[Dict[str, Any]] = None
    if context_file:
        # TODO: Implement context file loading
        utils.display_info(f"Loading MCP context from: {context_file}")
        try:
            mcp_context_data = json.loads(context_file.read_text(encoding='utf-8'))
        except Exception as e:
             utils.display_error(f"Failed to load or parse context file {context_file}: {e}")
             ctx.exit(1)


    # 4. Load Keys (Placeholder for REQ-CLI-RUN-002)
    # TODO: Instantiate KeyManager, determine service_id, handle overrides
    utils.display_info("Key loading logic to be implemented...")
    # Example placeholder:
    # manager = key_manager.KeyManager(use_keyring=True)
    # service_id = key_service_override or agent_card.auth_schemes[0].service_identifier # Needs better logic
    # api_key = auth_key_override or manager.get_key(service_id)
    # if not api_key and agent_card.auth_schemes[0].scheme != 'none': # Needs better logic
    #     utils.display_error(f"Missing API key for service '{service_id}'")
    #     ctx.exit(1)


    # 5. Prepare Initial Message (Placeholder for REQ-CLI-RUN-003)
    # TODO: Create av_models.Message with TextPart from processed_input_text
    utils.display_info("Message preparation logic to be implemented...")
    # Example placeholder:
    # initial_message = av_models.Message(role="user", parts=[av_models.TextPart(content=processed_input_text)])


    # 6. Instantiate Client and Run Task (Placeholder for REQ-CLI-RUN-003)
    # TODO: Use async with av_client.AgentVaultClient() as client: ...
    # TODO: Call client.initiate_task(...)
    # TODO: Loop through client.receive_messages(...) and display events
    # TODO: Add Ctrl+C handler to call client.terminate_task(...)
    utils.display_info("A2A client interaction logic to be implemented...")
    utils.display_warning("Run command implementation is incomplete.")

    # Simulate completion for now
    await asyncio.sleep(0.1) # Allow other tasks to run if any
