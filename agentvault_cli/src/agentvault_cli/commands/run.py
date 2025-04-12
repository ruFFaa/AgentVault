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
    from agentvault import key_manager # Needed now
    from agentvault import client as av_client # Needed later
    _agentvault_lib_imported = True
except ImportError as e:
    # Display error immediately if core lib is missing
    # This check might need refinement depending on how __main__ is structured
    # But it's useful for development.
    import sys
    click.secho(f"FATAL: Failed to import core 'agentvault' library: {e}", fg='red', err=True)
    click.secho("Please ensure 'agentvault_library' is installed correctly (e.g., `poetry install` in root).", err=True)
    # Set placeholders to allow CLI structure to load, but commands will fail
    agent_card_utils = None # type: ignore
    av_exceptions = None # type: ignore
    av_models = None # type: ignore
    key_manager = None # type: ignore
    av_client = None # type: ignore
    _agentvault_lib_imported = False
    # Exit here if the library is critical for the CLI to even load commands
    # sys.exit(1) # Or handle more gracefully depending on structure

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
            # Check if it's a file first, even without .json extension
            is_file = False
            try:
                if agent_path.is_file():
                    is_file = True
            except OSError: # Handle potential errors like path too long
                 pass

            if is_file:
                if agent_path.suffix.lower() == ".json":
                     utils.display_info("Reference looks like a local JSON file, loading...")
                else:
                     utils.display_warning(f"Reference is a file but not '.json'. Attempting to load anyway: {agent_ref}")
                agent_card = agent_card_utils.load_agent_card_from_file(agent_path)
            else:
                # Assume it's an ID to look up in the registry
                utils.display_info(f"Reference looks like an ID, querying registry: {registry_url}")
                # --- MODIFIED REGISTRY LOOKUP ---
                # Assume registry API has a direct lookup endpoint /api/v1/agent-cards/id/{humanReadableId}
                # Or adapt if it only supports search
                # Let's try direct lookup first, fallback to search might be complex here
                # Note: URL encoding might be needed for the ID if it contains special chars
                encoded_id = httpx.URL(path=agent_ref).path # Basic encoding for path part
                lookup_url = f"{registry_url.rstrip('/')}/api/v1/agent-cards/id/{encoded_id}"
                utils.display_info(f"Attempting direct lookup: {lookup_url}")

                async with httpx.AsyncClient() as client:
                    response = await client.get(lookup_url, timeout=15.0, follow_redirects=True)

                if response.status_code == 200:
                    card_full_data = response.json()
                    # The detail endpoint should return the full card structure including card_data
                    agent_card = agent_card_utils.parse_agent_card_from_dict(card_full_data.get("card_data", {}))
                    if not agent_card:
                         raise av_exceptions.AgentCardError("Registry returned success but card_data was missing or invalid in response.")
                elif response.status_code == 404:
                     raise av_exceptions.AgentCardError(f"Agent ID '{agent_ref}' not found in registry at {registry_url}.")
                else:
                     raise av_exceptions.AgentCardFetchError(f"Registry API error looking up agent ID '{agent_ref}' (Status {response.status_code})", status_code=response.status_code, response_body=response.text)
                # --- END MODIFIED REGISTRY LOOKUP ---

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
@click.option("--context-file", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=pathlib.Path), help="Path to a JSON file containing MCP context.")
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
        # Error already displayed during import attempt
        ctx.exit(1)

    # 1. Load Agent Card
    agent_card = await _load_agent_card(agent_ref, registry_url, ctx)
    if agent_card is None:
        ctx.exit(1)
    utils.display_success(f"Successfully loaded agent: {agent_card.name} ({agent_card.human_readable_id})")
    utils.display_info(f"Agent A2A Endpoint: {agent_card.url}")

    # 2. Process Input Data
    processed_input_text: str
    if input_data.startswith('@'):
        input_file_path_str = input_data[1:]
        input_file_path = pathlib.Path(input_file_path_str)
        if not input_file_path.is_file():
            utils.display_error(f"Input file specified via '@' not found or not a file: {input_file_path}")
            ctx.exit(1)
        try:
            processed_input_text = input_file_path.read_text(encoding='utf-8')
            utils.display_info(f"Read input from file: {input_file_path}")
        except (IOError, OSError) as e:
            utils.display_error(f"Failed to read input file {input_file_path}: {e}")
            ctx.exit(1)
        except Exception as e: # Catch other potential errors
             utils.display_error(f"An unexpected error occurred reading input file {input_file_path}: {e}")
             ctx.exit(1)
    else:
        processed_input_text = input_data

    # 3. Load MCP Context
    mcp_context_data: Optional[Dict[str, Any]] = None
    if context_file:
        utils.display_info(f"Loading MCP context from: {context_file}")
        try:
            mcp_context_data = json.loads(context_file.read_text(encoding='utf-8'))
            if not isinstance(mcp_context_data, dict):
                 utils.display_error(f"Context file {context_file} does not contain a valid JSON object.")
                 ctx.exit(1)
            utils.display_info("MCP context loaded successfully.")
        except json.JSONDecodeError as e:
            utils.display_error(f"Failed to parse JSON context file {context_file}: {e}")
            ctx.exit(1)
        except (IOError, OSError) as e:
            utils.display_error(f"Failed to read context file {context_file}: {e}")
            ctx.exit(1)
        except Exception as e:
            utils.display_error(f"An unexpected error occurred loading context file {context_file}: {e}")
            ctx.exit(1)

    # 4. Load Keys
    api_key: Optional[str] = None
    service_id: Optional[str] = None
    requires_auth = True # Assume auth needed unless 'none' scheme found

    try:
        manager = key_manager.KeyManager(use_keyring=True) # Enable all sources

        # Determine required service ID
        if key_service_override:
            service_id = key_service_override
            utils.display_info(f"Using overridden service ID for key lookup: '{service_id}'")
        else:
            # Find the first supported auth scheme (prioritize apiKey)
            api_key_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'apiKey'), None)
            none_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'none'), None)

            if api_key_scheme:
                service_id = api_key_scheme.service_identifier or agent_card.human_readable_id
                utils.display_info(f"Using service ID from agent card ('apiKey' scheme): '{service_id}'")
                requires_auth = True
            elif none_scheme:
                utils.display_info("Agent supports 'none' authentication scheme. No API key needed.")
                requires_auth = False
                service_id = None # No service ID needed if auth is none
            else:
                # Handle other schemes if added later (e.g., bearer, oauth2)
                utils.display_warning(f"Agent does not explicitly support 'apiKey' or 'none' auth schemes. Supported: {[s.scheme for s in agent_card.auth_schemes]}. Key lookup might fail.")
                # Attempt to use the first scheme's identifier as a fallback guess
                if agent_card.auth_schemes:
                     first_scheme = agent_card.auth_schemes[0]
                     service_id = first_scheme.service_identifier or agent_card.human_readable_id
                     utils.display_warning(f"Attempting key lookup using service ID from first scheme ('{first_scheme.scheme}'): '{service_id}'")
                     requires_auth = True # Assume auth needed if not 'none'
                else:
                     # Should be caught by card validation, but handle defensively
                     utils.display_error("Agent card has no authentication schemes defined.")
                     ctx.exit(1)

        # Get the API key if required and not overridden
        if requires_auth:
            if auth_key_override:
                api_key = auth_key_override
                utils.display_warning("Using API key provided directly via --auth-key (INSECURE).")
            elif service_id:
                api_key = manager.get_key(service_id)
                if api_key:
                    source = manager.get_key_source(service_id)
                    utils.display_info(f"Found API key for service '{service_id}' (Source: {source.upper() if source else 'Unknown'}).")
                else:
                    utils.display_error(f"API key required for service '{service_id}' but not found.")
                    utils.display_info("Use 'agentvault config set' to configure the key using --env, --file, or --keyring.")
                    ctx.exit(1)
            else:
                # This case should ideally be caught earlier if auth is required but no service_id found
                utils.display_error("Authentication is required, but could not determine the service ID for key lookup.")
                ctx.exit(1)
        else:
             api_key = None # Explicitly set to None if no auth required

    except Exception as e:
        utils.display_error(f"An unexpected error occurred during key loading: {e}")
        logger.exception("Unexpected error in key loading section")
        ctx.exit(1)


    # 5. Prepare Initial Message (Placeholder for REQ-CLI-RUN-003)
    # TODO: Create av_models.Message with TextPart from processed_input_text
    utils.display_info("Message preparation logic to be implemented...")
    # Example placeholder:
    # initial_message = av_models.Message(role="user", parts=[av_models.TextPart(content=processed_input_text)])


    # 6. Instantiate Client and Run Task (Placeholder for REQ-CLI-RUN-003)
    # TODO: Use async with av_client.AgentVaultClient() as client: ...
    # TODO: Call client.initiate_task(...) using agent_card, initial_message, manager (or maybe just api_key?), mcp_context_data
    # TODO: Loop through client.receive_messages(...) and display events
    # TODO: Add Ctrl+C handler to call client.terminate_task(...)
    utils.display_info("A2A client interaction logic to be implemented...")
    utils.display_warning("Run command implementation is incomplete.")

    # Simulate completion for now
    await asyncio.sleep(0.1) # Allow other tasks to run if any
