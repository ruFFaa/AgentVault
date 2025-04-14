import click
import httpx
import pathlib
import logging
import asyncio
import json
import signal # For Ctrl+C handling
import os
import uuid # Import uuid
from typing import Optional, Dict, Any

# Import local utilities
from .. import utils

# Import AgentVault library components
try:
    from agentvault import agent_card_utils
    from agentvault import exceptions as av_exceptions
    from agentvault import models as av_models
    from agentvault import key_manager
    from agentvault import client as av_client # Import the client class
    _agentvault_lib_imported = True
except ImportError as e:
    import sys
    click.secho(f"FATAL: Failed to import core 'agentvault' library: {e}", fg='red', err=True)
    click.secho("Please ensure 'agentvault_library' is installed correctly (e.g., `poetry install` in root).", err=True)
    agent_card_utils = None
    av_exceptions = None
    av_models = None
    key_manager = None
    av_client = None
    _agentvault_lib_imported = False

# Import default registry URL from discover command
try:
    from .discover import DEFAULT_REGISTRY_URL
except ImportError:
    DEFAULT_REGISTRY_URL = "http://localhost:8000" # Fallback

# Rich imports
from rich.panel import Panel
from rich.syntax import Syntax

logger = logging.getLogger(__name__)

# Artifact Saving Threshold
ARTIFACT_SAVE_THRESHOLD_BYTES = 1024

# Flag for Ctrl+C Handling
terminate_requested = False

def handle_interrupt(sig, frame):
    """Signal handler to request termination."""
    global terminate_requested
    if not terminate_requested:
        utils.display_warning("\nTermination requested (Ctrl+C). Attempting to cancel task...")
        terminate_requested = True
    else:
        utils.display_warning("Termination already in progress...")


# Helper for Agent Card Loading
# (Remains unchanged)
async def _load_agent_card(
    agent_ref: str, registry_url: str, ctx: click.Context
) -> Optional[av_models.AgentCard]:
    # ... (implementation omitted for brevity) ...
    if not _agentvault_lib_imported or agent_card_utils is None:
         utils.display_error("AgentVault library not available for loading agent card.")
         return None

    utils.display_info(f"Attempting to load agent card from reference: {agent_ref}")
    agent_card: Optional[av_models.AgentCard] = None

    try:
        if agent_ref.startswith("http://") or agent_ref.startswith("https://"):
            utils.display_info("Reference looks like a URL, fetching...")
            agent_card = await agent_card_utils.fetch_agent_card_from_url(agent_ref)
        else:
            agent_path = pathlib.Path(agent_ref)
            is_file = False
            try:
                if agent_path.is_file():
                    is_file = True
            except OSError:
                 pass

            if is_file:
                if agent_path.suffix.lower() == ".json":
                     utils.display_info("Reference looks like a local JSON file, loading...")
                else:
                     utils.display_warning(f"Reference is a file but not '.json'. Attempting to load anyway: {agent_ref}")
                agent_card = agent_card_utils.load_agent_card_from_file(agent_path)
            else:
                utils.display_info(f"Reference looks like an ID, querying registry: {registry_url}")
                encoded_id = httpx.URL(path=agent_ref).path
                lookup_url = f"{registry_url.rstrip('/')}/api/v1/agent-cards/id/{encoded_id}"
                utils.display_info(f"Attempting direct lookup: {lookup_url}")

                async with httpx.AsyncClient() as client:
                    response = await client.get(lookup_url, timeout=15.0, follow_redirects=True)

                if response.status_code == 200:
                    card_full_data = response.json()
                    agent_card = agent_card_utils.parse_agent_card_from_dict(card_full_data.get("card_data", {}))
                    if not agent_card:
                         raise av_exceptions.AgentCardError("Registry returned success but card_data was missing or invalid in response.")
                elif response.status_code == 404:
                     raise av_exceptions.AgentCardError(f"Agent ID '{agent_ref}' not found in registry at {registry_url}.")
                else:
                     raise av_exceptions.AgentCardFetchError(f"Registry API error looking up agent ID '{agent_ref}' (Status {response.status_code})", status_code=response.status_code, response_body=response.text)

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


# Helper for Artifact Filename
# --- MODIFIED: Added content_is_structured parameter ---
def _get_artifact_filename(artifact: av_models.Artifact, content_is_structured: bool = False) -> str:
    """Determines a suitable filename for saving an artifact."""
    base_name = artifact.id or f"artifact_{uuid.uuid4().hex[:8]}"
    ext = ".bin" # Default extension
    media_type_original = artifact.media_type
    logger.info(f"[_get_artifact_filename] Artifact ID: '{base_name}', Original Media Type: '{media_type_original}', Content is structured: {content_is_structured}")

    if media_type_original:
        mime_lower = media_type_original.lower().strip()
        logger.info(f"[_get_artifact_filename] Normalized Media Type: '{mime_lower}'")

        if mime_lower == "application/json":
            ext = ".json"
            logger.info(f"[_get_artifact_filename] Matched 'application/json'. Extension set to: '{ext}'")
        else:
            type_map = {
                "text/plain": ".txt", "text/markdown": ".md", "application/python": ".py",
                "text/html": ".html", "text/css": ".css", "application/yaml": ".yaml",
                "image/png": ".png", "image/jpeg": ".jpg", "application/pdf": ".pdf",
                "application/octet-stream": ".bin"
            }
            found_match = False
            for mime, file_ext in type_map.items():
                logger.debug(f"  Checking against map key: '{mime}'")
                if mime_lower == mime:
                    ext = file_ext
                    found_match = True
                    logger.info(f"[_get_artifact_filename] Matched '{mime}' in type_map. Extension set to: '{ext}'")
                    break

            if not found_match:
                logger.info(f"[_get_artifact_filename] No exact match in type_map. Trying subtype split for '{mime_lower}'.")
                parts = mime_lower.split('/')
                if len(parts) == 2 and parts[1]:
                    subtype = parts[1].split('+')[0]
                    if subtype.isalnum() and len(subtype) < 6:
                        ext = f".{subtype}"
                        logger.info(f"[_get_artifact_filename] Using extension from subtype: '{ext}'")
                    else:
                        logger.info(f"[_get_artifact_filename] Could not determine simple extension from subtype: '{subtype}'")
                else:
                    logger.info(f"[_get_artifact_filename] Could not determine simple extension from media type: {media_type_original}")
    # --- MODIFIED: Check content structure if media_type was None ---
    elif content_is_structured:
        ext = ".json"
        logger.info(f"[_get_artifact_filename] No media type provided, but content is structured. Assuming JSON. Extension set to: '{ext}'")
    # --- END MODIFICATION ---
    else:
        logger.info(f"[_get_artifact_filename] No media type provided and content not structured. Using default extension: '{ext}'")

    safe_base_name = base_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    final_filename = f"{safe_base_name}{ext}"
    logger.info(f"[_get_artifact_filename] Final filename: '{final_filename}'")
    return final_filename


# Main Run Command
@click.command("run")
@click.option("--agent", "-a", "agent_ref", required=True, help="Agent identifier: ID (e.g., 'org/agent'), URL (https://...), or local file path.")
@click.option("--input", "-i", "input_data", required=True, help="Input text for the agent, or '@filepath' to read from a file.")
@click.option("--context-file", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=pathlib.Path), help="Path to a JSON file containing MCP context.")
@click.option("--registry", "registry_url", default=DEFAULT_REGISTRY_URL, help="URL of the AgentVault Registry API (used if agent ID is provided).", show_default=True, envvar="AGENTVAULT_REGISTRY_URL")
@click.option("--key-service", "key_service_override", help="Override the service ID used for key lookup (if agent card doesn't specify or is ambiguous).")
@click.option("--auth-key", "auth_key_override", help="Directly provide the API key (INSECURE - for testing only).")
@click.option(
    "--output-artifacts",
    type=click.Path(file_okay=False, dir_okay=True, writable=True, resolve_path=True, path_type=pathlib.Path),
    default=None,
    help="Directory to save artifact content larger than 1KB."
)
@click.pass_context
async def run_command(
    ctx: click.Context,
    agent_ref: str,
    input_data: str,
    context_file: Optional[pathlib.Path],
    registry_url: str,
    key_service_override: Optional[str],
    auth_key_override: Optional[str],
    output_artifacts: Optional[pathlib.Path]
):
    """ Runs a task on a specified remote agent... """
    global terminate_requested
    terminate_requested = False

    if not _agentvault_lib_imported:
        utils.display_error("Cannot run task: Core 'agentvault' library failed to import.")
        ctx.exit(1)
    if not all([agent_card_utils, av_exceptions, av_models, key_manager, av_client]):
        utils.display_error("Cannot run task: Core 'agentvault' library components missing.")
        ctx.exit(1)

    # 1. Load Agent Card
    agent_card = await _load_agent_card(agent_ref, registry_url, ctx)
    if agent_card is None: ctx.exit(1)
    utils.display_success(f"Successfully loaded agent: {agent_card.name} ({agent_card.human_readable_id})")
    utils.display_info(f"Agent A2A Endpoint: {agent_card.url}")

    # 2. Process Input Data
    processed_input_text: str
    if input_data.startswith('@'):
        input_file_path_str = input_data[1:]
        input_file_path = pathlib.Path(input_file_path_str)
        if not input_file_path.is_file(): utils.display_error(f"Input file specified via '@' not found or not a file: {input_file_path}"); ctx.exit(1)
        try: processed_input_text = input_file_path.read_text(encoding='utf-8'); utils.display_info(f"Read input from file: {input_file_path}")
        except (IOError, OSError) as e: utils.display_error(f"Failed to read input file {input_file_path}: {e}"); ctx.exit(1)
        except Exception as e: utils.display_error(f"An unexpected error occurred reading input file {input_file_path}: {e}"); ctx.exit(1)
    else: processed_input_text = input_data

    # 3. Load MCP Context
    mcp_context_data: Optional[Dict[str, Any]] = None
    if context_file:
        utils.display_info(f"Loading MCP context from: {context_file}")
        try:
            mcp_context_data = json.loads(context_file.read_text(encoding='utf-8'))
            if not isinstance(mcp_context_data, dict): utils.display_error(f"Context file {context_file} does not contain a valid JSON object."); ctx.exit(1)
            utils.display_info("MCP context loaded successfully.")
        except json.JSONDecodeError as e: utils.display_error(f"Failed to parse JSON context file {context_file}: {e}"); ctx.exit(1)
        except (IOError, OSError) as e: utils.display_error(f"Failed to read context file {context_file}: {e}"); ctx.exit(1)
        except Exception as e: utils.display_error(f"An unexpected error occurred loading context file {context_file}: {e}"); ctx.exit(1)

    # 4. Load Keys
    api_key: Optional[str] = None; service_id: Optional[str] = None; requires_auth = True
    manager: Optional[key_manager.KeyManager] = None
    try:
        manager = key_manager.KeyManager(use_keyring=True)
        if key_service_override: service_id = key_service_override; utils.display_info(f"Using overridden service ID for key lookup: '{service_id}'")
        else:
            api_key_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'apiKey'), None)
            oauth2_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'oauth2'), None)
            none_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'none'), None)
            if api_key_scheme: service_id = api_key_scheme.service_identifier or agent_card.human_readable_id; utils.display_info(f"Using service ID from agent card ('apiKey' scheme): '{service_id}'"); requires_auth = True
            elif oauth2_scheme: service_id = oauth2_scheme.service_identifier or agent_card.human_readable_id; utils.display_info(f"Using service ID from agent card ('oauth2' scheme): '{service_id}'"); requires_auth = True
            elif none_scheme: utils.display_info("Agent supports 'none' authentication scheme. No API key needed."); requires_auth = False; service_id = None
            else:
                utils.display_warning(f"Agent does not explicitly support 'apiKey', 'oauth2', or 'none' auth schemes. Supported: {[s.scheme for s in agent_card.auth_schemes]}. Key/Credential lookup might fail.")
                if agent_card.auth_schemes: first_scheme = agent_card.auth_schemes[0]; service_id = first_scheme.service_identifier or agent_card.human_readable_id; utils.display_warning(f"Attempting key/credential lookup using service ID from first scheme ('{first_scheme.scheme}'): '{service_id}'"); requires_auth = True
                else: utils.display_error("Agent card has no authentication schemes defined."); ctx.exit(1)
        if requires_auth:
            if auth_key_override:
                if any(s.scheme == 'apiKey' for s in agent_card.auth_schemes) or not agent_card.auth_schemes: api_key = auth_key_override; utils.display_warning("Using API key provided directly via --auth-key (INSECURE).")
                else: utils.display_error("--auth-key override is only supported for 'apiKey' scheme."); ctx.exit(1)
            elif service_id:
                key_found = manager.get_key(service_id) is not None
                oauth_found = manager.get_oauth_client_id(service_id) is not None and manager.get_oauth_client_secret(service_id) is not None
                if key_found or oauth_found: source = manager.get_key_source(service_id) or manager._oauth_sources.get(service_id); utils.display_info(f"Found credentials for service '{service_id}' (Source: {source.upper() if source else 'Unknown'}).")
                else: utils.display_error(f"Credentials required for service '{service_id}' but not found."); utils.display_info("Use 'agentvault config set' to configure the key/credentials using --env, --file, --keyring, or --oauth-configure."); ctx.exit(1)
            else: utils.display_error("Authentication is required, but could not determine the service ID for credential lookup."); ctx.exit(1)
        else: api_key = None
    except Exception as e: utils.display_error(f"An unexpected error occurred during key/credential loading: {e}"); logger.exception("Unexpected error in key loading section"); ctx.exit(1)
    if manager is None: manager = key_manager.KeyManager(use_keyring=True)

    # 5. Prepare Initial Message
    try: initial_message = av_models.Message(role="user", parts=[av_models.TextPart(content=processed_input_text)])
    except Exception as e: utils.display_error(f"Failed to create initial message structure: {e}"); ctx.exit(1)

    # 6. Instantiate Client and Run Task
    task_id: Optional[str] = None
    final_task_state: Optional[av_models.TaskState] = None
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_interrupt)

    try:
        async with av_client.AgentVaultClient() as client:
            try:
                utils.display_info("Initiating task with agent...")
                task_id = await client.initiate_task(
                    agent_card=agent_card, initial_message=initial_message, key_manager=manager,
                    mcp_context=mcp_context_data, webhook_url=None
                )
                utils.display_success(f"Task initiated successfully. Task ID: {task_id}")

                with utils.console.status("[bold green]Waiting for events... (Press Ctrl+C to request cancellation)", spinner="dots") as status:
                    async for event in client.receive_messages(
                        agent_card=agent_card, task_id=task_id, key_manager=manager
                    ):
                        if terminate_requested:
                            status.update("[bold yellow]Attempting to terminate task...")
                            try: await client.terminate_task(agent_card, task_id, manager); utils.display_success(f"Termination request acknowledged for task {task_id}.")
                            except av_exceptions.A2AError as term_err: utils.display_error(f"Failed to send termination request: {term_err}")
                            final_task_state = av_models.TaskState.CANCELED; break

                        if isinstance(event, av_models.TaskStatusUpdateEvent):
                            final_task_state = event.state; status_msg = f"Task Status: {event.state.value}"
                            if event.message: status_msg += f" - {event.message}"
                            status.update(f"[bold green]Status: {event.state.value}..."); utils.display_info(status_msg)
                            if event.state in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]: utils.display_info("Task reached terminal state."); break

                        elif isinstance(event, av_models.TaskMessageEvent):
                            role = event.message.role; content_parts = []
                            for part in event.message.parts:
                                if isinstance(part, av_models.TextPart): content_parts.append(part.content)
                                elif isinstance(part, av_models.FilePart): content_parts.append(f"[File: {part.filename or part.url} ({part.media_type or 'unknown'})]")
                                elif isinstance(part, av_models.DataPart):
                                    try: content_parts.append(f"[Data ({part.media_type}):\n{json.dumps(part.content, indent=2)}]")
                                    except Exception: content_parts.append(f"[Data ({part.media_type}): {part.content}]")
                                else: content_parts.append("[Unknown message part type]")
                            full_content = "\n".join(content_parts); title = f"Message from {role.capitalize()}"
                            border_style = "dim";
                            if role == "assistant": border_style = "blue"
                            elif role == "tool": border_style = "yellow"
                            utils.console.print(Panel(full_content, title=title, border_style=border_style, expand=False))

                        elif isinstance(event, av_models.TaskArtifactUpdateEvent):
                            artifact = event.artifact
                            # --- ADDED Debug Log ---
                            logger.info(f"[run_command] Processing artifact event for ID: {artifact.id}, Type: {artifact.type}, Media Type: {artifact.media_type}")
                            # --- END Debug Log ---
                            artifact_title = f"Artifact Update: ID={artifact.id}, Type={artifact.type}"
                            utils.display_info(artifact_title)
                            if artifact.url: utils.display_info(f"  URL: {artifact.url}")
                            if artifact.metadata: utils.display_info(f"  Metadata: {artifact.metadata}")

                            content_panel = None; content_bytes = None; content_str = None
                            save_to_file = False; file_path = None
                            content_is_structured_data = False # Flag for JSON inference

                            if artifact.content is not None:
                                try:
                                    if isinstance(artifact.content, str): content_str = artifact.content; content_bytes = content_str.encode('utf-8')
                                    elif isinstance(artifact.content, bytes):
                                        content_bytes = artifact.content
                                        try: content_str = content_bytes.decode('utf-8')
                                        except UnicodeDecodeError: content_str = None
                                    elif isinstance(artifact.content, (dict, list)):
                                        content_is_structured_data = True # Mark as structured
                                        content_str = json.dumps(artifact.content, indent=2); content_bytes = content_str.encode('utf-8')
                                    else: content_str = str(artifact.content); content_bytes = content_str.encode('utf-8')
                                except Exception as e: logger.warning(f"Could not serialize artifact content for saving/display: {e}"); content_bytes = None; content_str = f"[Error processing content: {e}]"

                                if output_artifacts and content_bytes and len(content_bytes) > ARTIFACT_SAVE_THRESHOLD_BYTES:
                                    save_to_file = True
                                    try:
                                        # --- Pass content structure hint to filename helper ---
                                        filename = _get_artifact_filename(artifact, content_is_structured=content_is_structured_data)
                                        # --- End Pass ---
                                        file_path = output_artifacts / filename
                                        output_artifacts.mkdir(parents=True, exist_ok=True)
                                        with open(file_path, 'wb') as f: f.write(content_bytes)
                                        utils.display_info(f"  Content saved to: {file_path}")
                                    except (IOError, OSError) as e: utils.display_error(f"  Error saving artifact content to {file_path}: {e}"); save_to_file = False
                                    except Exception as e: utils.display_error(f"  Unexpected error saving artifact {file_path}: {e}"); save_to_file = False

                            if not save_to_file and content_str is not None:
                                lang = "text"
                                # --- Infer JSON language if needed ---
                                if content_is_structured_data:
                                     lang = "json"
                                # --- End Infer ---
                                elif artifact.media_type:
                                    mime_lower = artifact.media_type.lower()
                                    if "python" in mime_lower: lang = "python"
                                    elif "javascript" in mime_lower: lang = "javascript"
                                    elif "json" in mime_lower: lang = "json"
                                    elif "yaml" in mime_lower: lang = "yaml"
                                    elif "html" in mime_lower: lang = "html"
                                    elif "css" in mime_lower: lang = "css"
                                    elif "markdown" in mime_lower: lang = "markdown"

                                if lang != "text": syntax = Syntax(content_str, lang, theme="default", line_numbers=True); content_panel = Panel(syntax, title=f"Artifact Content ({artifact.id})", border_style="magenta")
                                else: content_panel = Panel(content_str[:500] + ('...' if len(content_str) > 500 else ''), title=f"Artifact Content ({artifact.id})", border_style="magenta")
                            elif not save_to_file and content_bytes is not None: content_panel = Panel(f"[Binary data: {len(content_bytes)} bytes]", title=f"Artifact Content ({artifact.id})", border_style="magenta")

                            if content_panel: utils.console.print(content_panel)
                            elif not save_to_file: utils.display_info("  Content: [Not available or error processing]")

                        else: utils.display_warning(f"Received unknown event type: {type(event)}")

            except av_exceptions.A2AError as e: utils.display_error(f"A2A communication error: {e}"); logger.exception("A2AError during task execution"); ctx.exit(1)
            except Exception as e: utils.display_error(f"An unexpected error occurred during task execution: {e}"); logger.exception("Unexpected error during task execution"); ctx.exit(1)
            finally:
                 if task_id and final_task_state not in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                     utils.display_info("-" * 20)
                     with utils.console.status("[bold cyan]Fetching final task status...", spinner="earth"):
                         try: final_task = await client.get_task_status(agent_card, task_id, manager); final_task_state = final_task.state
                         except av_exceptions.A2AError as e: utils.display_error(f"Could not fetch final task status: {e}")
                         except Exception as e: utils.display_error(f"Unexpected error fetching final status: {e}")
                     utils.display_info(f"Final Task State: {final_task_state.value if final_task_state else 'Unknown/Fetch Failed'}")
                 signal.signal(signal.SIGINT, original_sigint_handler)
                 if final_task_state == av_models.TaskState.COMPLETED: utils.display_success("Task completed."); ctx.exit(0)
                 elif final_task_state == av_models.TaskState.FAILED: utils.display_error("Task failed."); ctx.exit(1)
                 elif final_task_state == av_models.TaskState.CANCELED: utils.display_warning("Task canceled."); ctx.exit(2)
                 elif final_task_state == av_models.TaskState.INPUT_REQUIRED: utils.display_warning("Task stopped awaiting input (not supported by CLI)."); ctx.exit(2)
                 else: state_str = final_task_state.value if final_task_state else "Unknown/Fetch Failed"; utils.display_warning(f"Task finished with non-terminal state: {state_str}"); ctx.exit(1)

    except Exception as e:
        utils.display_error(f"Failed to initialize A2A client: {e}")
        logger.exception("Error initializing AgentVaultClient")
        ctx.exit(1)
