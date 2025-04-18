import asyncclick as click
import httpx
import pathlib
import logging
import asyncio
import json
import signal # For Ctrl+C handling
import os
import uuid # Import uuid
from typing import Optional, Dict, Any, AsyncGenerator

# Import local utilities
from .. import utils

# Import AgentVault library components
try:
    from agentvault import agent_card_utils
    from agentvault import exceptions as av_exceptions
    from agentvault import models as av_models
    from agentvault import key_manager # Import the module
    from agentvault import client as av_client # Import the module
    _agentvault_lib_imported = True
except ImportError as e:
    import logging as stdlib_logging
    stdlib_logging.critical(f"FATAL: Failed to import core 'agentvault' library: {e}")
    stdlib_logging.critical("Please ensure 'agentvault_library' is installed correctly (e.g., `poetry install` in root).")
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
    DEFAULT_REGISTRY_URL = "http://localhost:8000" # Fallback

# Rich imports
try:
    from rich.panel import Panel
    from rich.syntax import Syntax
    _RICH_AVAILABLE = True
except ImportError:
    Panel = None # type: ignore
    Syntax = None # type: ignore
    _RICH_AVAILABLE = False


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
async def _load_agent_card(
    agent_ref: str,
    registry_url: str,
    ctx: click.Context,
    # --- ADDED: Optional http client for testing ---
    _http_client: Optional[httpx.AsyncClient] = None
    # --- END ADDED ---
) -> Optional[av_models.AgentCard]:
    """Loads agent card, displaying errors and returning None on failure."""
    if not _agentvault_lib_imported or agent_card_utils is None or av_exceptions is None or av_models is None:
         utils.display_error("AgentVault library not available for loading agent card.")
         return None

    utils.display_info(f"Attempting to load agent card from reference: {agent_ref}")
    agent_card: Optional[av_models.AgentCard] = None

    # --- ADDED: Use provided client or create default ---
    client_manager = _http_client if _http_client else httpx.AsyncClient()
    # --- END ADDED ---

    try:
        if agent_ref.startswith("http://") or agent_ref.startswith("https://"):
            utils.display_info("Reference looks like a URL, fetching...")
            # --- MODIFIED: Pass client_manager ---
            agent_card = await agent_card_utils.fetch_agent_card_from_url(agent_ref, http_client=client_manager)
            # --- END MODIFIED ---
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
                     utils.display_info(f"Reference looks like a local JSON file, loading: {agent_path.resolve()}")
                else:
                     utils.display_warning(f"Reference is a file but not '.json'. Attempting to load anyway: {agent_path.resolve()}")
                agent_card = agent_card_utils.load_agent_card_from_file(agent_path)
            else:
                utils.display_info(f"Reference is not a URL or local file, assuming Agent ID. Querying registry: {registry_url}")
                lookup_url = f"{registry_url.rstrip('/')}/api/v1/agent-cards/id/{agent_ref}"
                utils.display_info(f"Attempting direct lookup: {lookup_url}")

                # --- MODIFIED: Use client_manager ---
                async with client_manager as client_cm: # Use async with on the manager
                    response = await client_cm.get(lookup_url, timeout=15.0, follow_redirects=True)
                # --- END MODIFIED ---

                if response.status_code == 200:
                    card_full_data = response.json()
                    card_data_dict = card_full_data.get("card_data")
                    if not card_data_dict or not isinstance(card_data_dict, dict):
                         raise av_exceptions.AgentCardError("Registry returned success but 'card_data' was missing or invalid in response.")
                    agent_card = agent_card_utils.parse_agent_card_from_dict(card_data_dict)
                elif response.status_code == 404:
                     raise av_exceptions.AgentCardFetchError(f"Agent ID '{agent_ref}' not found in registry at {registry_url}.", status_code=404)
                else:
                     raise av_exceptions.AgentCardFetchError(f"Registry API error looking up agent ID '{agent_ref}' (Status {response.status_code})", status_code=response.status_code, response_body=response.text)

    except av_exceptions.AgentCardValidationError as e: utils.display_error(f"Failed to load agent card: Agent Card validation failed: {e}"); return None
    except av_exceptions.AgentCardFetchError as e: utils.display_error(f"Failed to load agent card: {e}"); return None
    except av_exceptions.AgentCardError as e: utils.display_error(f"Failed to load agent card: {e}"); return None
    except httpx.RequestError as e: utils.display_error(f"Network error while loading agent card: {e}"); return None
    except Exception as e: utils.display_error(f"An unexpected error occurred loading agent card: {e}"); logger.exception("Unexpected error in _load_agent_card"); return None
    # --- ADDED: Ensure client is closed if created internally ---
    finally:
        if _http_client is None and not client_manager.is_closed: # If we created it, close it
            await client_manager.aclose()
    # --- END ADDED ---

    if agent_card is None: utils.display_error("Failed to load agent card for unknown reason."); return None
    return agent_card


# Helper for Artifact Filename (Remains unchanged)
def _get_artifact_filename(artifact: av_models.Artifact, content_is_structured: bool = False) -> str:
    base_name = artifact.id or f"artifact_{uuid.uuid4().hex[:8]}"
    ext = ".bin"
    media_type_original = artifact.media_type
    logger.info(f"[_get_artifact_filename] Artifact ID: '{base_name}', Original Media Type: '{media_type_original}', Content is structured: {content_is_structured}")
    if media_type_original:
        mime_lower = media_type_original.lower().strip()
        logger.info(f"[_get_artifact_filename] Normalized Media Type: '{mime_lower}'")
        type_map = { "application/json": ".json", "text/plain": ".txt", "text/markdown": ".md", "application/python": ".py", "text/html": ".html", "text/css": ".css", "application/yaml": ".yaml", "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/svg+xml": ".svg", "application/pdf": ".pdf", "application/zip": ".zip", "application/octet-stream": ".bin" }
        if mime_lower in type_map: ext = type_map[mime_lower]; logger.info(f"[_get_artifact_filename] Matched '{mime_lower}' in type_map. Extension set to: '{ext}'")
        else:
            logger.info(f"[_get_artifact_filename] No exact match in type_map. Trying subtype split for '{mime_lower}'.")
            parts = mime_lower.split('/')
            if len(parts) == 2 and parts[1]:
                subtype_parts = parts[1].split('+'); subtype = subtype_parts[0].strip(); suffix = subtype_parts[1].strip() if len(subtype_parts) > 1 else None
                if suffix == "json": ext = ".json"
                elif suffix == "xml": ext = ".xml"
                elif suffix == "yaml": ext = ".yaml"
                elif subtype.isalnum() and len(subtype) < 6: ext = f".{subtype}"; logger.info(f"[_get_artifact_filename] Using extension from subtype: '{ext}'")
                else: logger.info(f"[_get_artifact_filename] Could not determine simple extension from subtype: '{subtype}' or suffix: '{suffix}'")
            else: logger.info(f"[_get_artifact_filename] Could not determine simple extension from media type: {media_type_original}")
    elif content_is_structured: ext = ".json"; logger.info(f"[_get_artifact_filename] No media type provided, but content is structured. Assuming JSON. Extension set to: '{ext}'")
    else: logger.info(f"[_get_artifact_filename] No media type provided and content not structured. Using default extension: '{ext}'")
    safe_base_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in base_name); safe_base_name = safe_base_name[:100]
    final_filename = f"{safe_base_name}{ext}"; logger.info(f"[_get_artifact_filename] Final filename: '{final_filename}'")
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
# --- ADDED: Optional http client for testing ---
@click.option("--_http_client", hidden=True, default=None, help="Internal use for testing with mock client.")
# --- END ADDED ---
@click.pass_context
async def run_command(
    ctx: click.Context,
    agent_ref: str,
    input_data: str,
    context_file: Optional[pathlib.Path],
    registry_url: str,
    key_service_override: Optional[str],
    auth_key_override: Optional[str],
    output_artifacts: Optional[pathlib.Path],
    # --- ADDED: Optional http client parameter ---
    _http_client: Optional[httpx.AsyncClient] = None
    # --- END ADDED ---
) -> int:
    """
    Runs a task on a specified remote agent using the A2A protocol.
    Returns an integer exit code (0 for success, 1 for error, 2 for cancel).
    """
    global terminate_requested
    terminate_requested = False

    if not _agentvault_lib_imported: utils.display_error("Cannot run task: Core 'agentvault' library failed to import."); return 1
    if not _RICH_AVAILABLE: utils.display_warning("Optional 'rich' library not found. Output formatting will be basic.")
    if not all([agent_card_utils, av_exceptions, av_models, key_manager, av_client]): utils.display_error("Cannot run task: Core 'agentvault' library components missing."); return 1

    # --- MODIFIED: Pass http client to helper ---
    agent_card = await _load_agent_card(agent_ref, registry_url, ctx, _http_client=_http_client)
    # --- END MODIFIED ---
    if agent_card is None: return 1

    utils.display_success(f"Successfully loaded agent: {agent_card.name} ({agent_card.human_readable_id})")
    utils.display_info(f"Agent A2A Endpoint: {agent_card.url}")

    # Process Input Data (unchanged)
    processed_input_text: str;
    if input_data.startswith('@'):
        input_file_path = pathlib.Path(input_data[1:])
        if not input_file_path.is_file(): utils.display_error(f"Input file specified via '@' not found or not a file: {input_file_path}"); return 1
        try: processed_input_text = input_file_path.read_text(encoding='utf-8'); utils.display_info(f"Read input from file: {input_file_path}")
        except (IOError, OSError) as e: utils.display_error(f"Failed to read input file {input_file_path}: {e}"); return 1
        except Exception as e: utils.display_error(f"An unexpected error occurred reading input file {input_file_path}: {e}"); logger.exception(f"Unexpected error reading input file {input_file_path}"); return 1
    else: processed_input_text = input_data

    # Load MCP Context (unchanged)
    mcp_context_data: Optional[Dict[str, Any]] = None;
    if context_file:
        utils.display_info(f"Loading MCP context from: {context_file}")
        try:
            mcp_context_data = json.loads(context_file.read_text(encoding='utf-8'))
            if not isinstance(mcp_context_data, dict): utils.display_error(f"Context file {context_file} does not contain a valid JSON object."); return 1
            utils.display_info("MCP context loaded successfully.")
        except json.JSONDecodeError as e: utils.display_error(f"Failed to parse JSON context file {context_file}: {e}"); return 1
        except (IOError, OSError) as e: utils.display_error(f"Failed to read context file {context_file}: {e}"); return 1
        except Exception as e: utils.display_error(f"An unexpected error occurred loading context file {context_file}: {e}"); logger.exception(f"Unexpected error loading context file {context_file}"); return 1

    # Load Keys / Prepare KeyManager (unchanged)
    manager: Optional[key_manager.KeyManager] = None;
    try:
        manager = key_manager.KeyManager(use_keyring=True); auth_needed = True; service_id_to_use: Optional[str] = None
        if agent_card.auth_schemes:
            first_scheme = agent_card.auth_schemes[0]
            if first_scheme.scheme == 'none': auth_needed = False; utils.display_info("Agent supports 'none' authentication scheme. No credentials needed.")
            elif key_service_override: service_id_to_use = key_service_override; utils.display_info(f"Using overridden service ID for credential lookup: '{service_id_to_use}'")
            elif first_scheme.service_identifier: service_id_to_use = first_scheme.service_identifier; utils.display_info(f"Using service ID from agent card ('{first_scheme.scheme}' scheme): '{service_id_to_use}'")
            else: service_id_to_use = agent_card.human_readable_id; utils.display_warning(f"No service_identifier in agent card's '{first_scheme.scheme}' scheme. Defaulting to humanReadableId for credential lookup: '{service_id_to_use}'. Use --key-service if needed.")
        else: utils.display_warning("Agent card has no authentication schemes defined. Assuming 'none'."); auth_needed = False
        if auth_needed:
            if auth_key_override:
                 if any(s.scheme == 'apiKey' for s in agent_card.auth_schemes): utils.display_warning("Using API key provided directly via --auth-key (INSECURE).")
                 else: utils.display_error("--auth-key override is only supported for agents requiring the 'apiKey' scheme."); return 1
            elif service_id_to_use:
                key_found = manager.get_key(service_id_to_use) is not None; oauth_found = (manager.get_oauth_client_id(service_id_to_use) is not None and manager.get_oauth_client_secret(service_id_to_use) is not None)
                if not key_found and not oauth_found: utils.display_error(f"Credentials required for service '{service_id_to_use}' but none found (checked Env, File, Keyring)."); utils.display_info("Use 'agentvault config set' to configure the key/credentials using --keyring or --oauth-configure."); return 1
                else: source = manager.get_key_source(service_id_to_use) or manager._oauth_sources.get(service_id_to_use); utils.display_info(f"Found credentials for service '{service_id_to_use}' (Source: {source.upper() if source else 'Unknown'}).")
            else: utils.display_error("Authentication is required, but could not determine the service ID for credential lookup."); return 1
    except av_exceptions.KeyManagementError as e: utils.display_error(f"Key management error during setup: {e}"); return 1
    except Exception as e: utils.display_error(f"An unexpected error occurred during key/credential loading: {e}"); logger.exception("Unexpected error in key loading section"); return 1
    if manager is None: manager = key_manager.KeyManager(use_keyring=True)

    # Prepare Initial Message (unchanged)
    try: initial_message = av_models.Message(role="user", parts=[av_models.TextPart(content=processed_input_text)])
    except Exception as e: utils.display_error(f"Failed to create initial message structure: {e}"); return 1

    # Instantiate Client and Run Task
    task_id: Optional[str] = None; final_task_state: Optional[av_models.TaskState] = None
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_interrupt)
    exit_code = 1

    try:
        # --- MODIFIED: Pass injected http client to AgentVaultClient ---
        async with av_client.AgentVaultClient(http_client=_http_client) as client:
        # --- END MODIFIED ---
            try:
                utils.display_info("Initiating task with agent...")
                task_id = await client.initiate_task(
                    agent_card=agent_card, initial_message=initial_message, key_manager=manager,
                    mcp_context=mcp_context_data, webhook_url=None, auth_key_override=auth_key_override
                )
                utils.display_success(f"Task initiated successfully. Task ID: {task_id}")

                # --- MODIFIED: Use simple print if Rich unavailable ---
                status_context = utils.console.status("[bold green]Waiting for events... (Press Ctrl+C to request cancellation)", spinner="dots") if _RICH_AVAILABLE else None
                status_obj = status_context.__enter__() if status_context else None
                if not status_obj: print("Waiting for events... (Press Ctrl+C to request cancellation)", flush=True)
                # --- END MODIFIED ---

                try:
                    async for event in client.receive_messages(
                        agent_card=agent_card, task_id=task_id, key_manager=manager
                    ):
                        # ... (Event processing logic remains the same) ...
                        if terminate_requested:
                            if status_obj: status_obj.update("[bold yellow]Attempting to terminate task...")
                            else: print("Attempting to terminate task...", flush=True)
                            try: await client.terminate_task(agent_card, task_id, manager); utils.display_success(f"Termination request acknowledged for task {task_id}.")
                            except av_exceptions.A2AError as term_err: utils.display_error(f"Failed to send termination request: {term_err}")
                            final_task_state = av_models.TaskState.CANCELED; break

                        if isinstance(event, av_models.TaskStatusUpdateEvent):
                            final_task_state = event.state; status_msg = f"Task Status: {event.state.value}";
                            if event.message: status_msg += f" - {event.message}"
                            if status_obj: status_obj.update(f"[bold green]Status: {event.state.value}...")
                            utils.display_info(status_msg) # Also print info line
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
                            if _RICH_AVAILABLE: border_style = "dim";
                                if role == "assistant": border_style = "blue"
                                elif role == "tool": border_style = "yellow"
                                utils.console.print(Panel(full_content, title=title, border_style=border_style, expand=False))
                            else: utils.display_info(f"\n--- {title} ---\n{full_content}\n--- End Message ---")

                        elif isinstance(event, av_models.TaskArtifactUpdateEvent):
                            # ... (Artifact display/saving logic unchanged) ...
                            artifact = event.artifact; logger.info(f"[run_command] Processing artifact event for ID: {artifact.id}, Type: {artifact.type}, Media Type: {artifact.media_type}")
                            artifact_title = f"Artifact Update: ID={artifact.id}, Type={artifact.type}"; utils.display_info(artifact_title)
                            if artifact.url: utils.display_info(f"  URL: {artifact.url}")
                            if artifact.metadata: utils.display_info(f"  Metadata: {artifact.metadata}")
                            content_panel = None; content_bytes = None; content_str = None; save_to_file = False; file_path = None; content_is_structured_data = False
                            if artifact.content is not None:
                                try:
                                    if isinstance(artifact.content, str): content_str = artifact.content; content_bytes = content_str.encode('utf-8')
                                    elif isinstance(artifact.content, bytes): content_bytes = artifact.content; try: content_str = content_bytes.decode('utf-8'); except UnicodeDecodeError: content_str = None
                                    elif isinstance(artifact.content, (dict, list)): content_is_structured_data = True; content_str = json.dumps(artifact.content, indent=2); content_bytes = content_str.encode('utf-8')
                                    else: content_str = str(artifact.content); content_bytes = content_str.encode('utf-8')
                                except Exception as e: logger.warning(f"Could not serialize artifact content for saving/display: {e}"); content_bytes = None; content_str = f"[Error processing content: {e}]"
                                if output_artifacts and content_bytes and len(content_bytes) > ARTIFACT_SAVE_THRESHOLD_BYTES:
                                    save_to_file = True
                                    try: filename = _get_artifact_filename(artifact, content_is_structured=content_is_structured_data); file_path = output_artifacts / filename; output_artifacts.mkdir(parents=True, exist_ok=True); with open(file_path, 'wb') as f: f.write(content_bytes); utils.display_info(f"  Content saved to: {file_path}")
                                    except (IOError, OSError) as e: utils.display_error(f"  Error saving artifact content to {file_path}: {e}"); save_to_file = False
                                    except Exception as e: utils.display_error(f"  Unexpected error saving artifact {file_path}: {e}"); save_to_file = False
                            if not save_to_file:
                                if content_str is not None:
                                    display_content = content_str[:1000] + ('...' if len(content_str) > 1000 else '')
                                    if _RICH_AVAILABLE: lang = "text";
                                        if content_is_structured_data: lang = "json"
                                        elif artifact.media_type: mime_lower = artifact.media_type.lower();
                                            if "python" in mime_lower: lang = "python"; elif "javascript" in mime_lower: lang = "javascript"; elif "json" in mime_lower: lang = "json"; elif "yaml" in mime_lower: lang = "yaml"; elif "html" in mime_lower: lang = "html"; elif "css" in mime_lower: lang = "css"; elif "markdown" in mime_lower: lang = "markdown"
                                        if lang != "text": syntax = Syntax(display_content, lang, theme="default", line_numbers=True); content_panel = Panel(syntax, title=f"Artifact Content ({artifact.id})", border_style="magenta")
                                        else: content_panel = Panel(display_content, title=f"Artifact Content ({artifact.id})", border_style="magenta")
                                    else: utils.display_info(f"  Content ({artifact.media_type or 'unknown'}):\n{display_content}")
                                elif content_bytes is not None: content_panel = Panel(f"[Binary data: {len(content_bytes)} bytes]", title=f"Artifact Content ({artifact.id})", border_style="magenta") if _RICH_AVAILABLE else None;
                                    if not content_panel: utils.display_info(f"  Content: [Binary data: {len(content_bytes)} bytes]")
                                if content_panel and _RICH_AVAILABLE: utils.console.print(content_panel)
                                elif not _RICH_AVAILABLE and content_str is None and content_bytes is None: utils.display_info("  Content: [Not available or error processing]")
                        else: utils.display_warning(f"Received unknown event type: {type(event)}")
                finally:
                    if status_context: status_context.__exit__(None, None, None)

            # Catch specific A2A errors
            except av_exceptions.A2AAuthenticationError as e: utils.display_error(f"A2A Authentication Error: {e}"); logger.error(f"Auth failed: {e}", exc_info=True); exit_code = 1
            except av_exceptions.A2AConnectionError as e: utils.display_error(f"A2A Connection Error: {e}"); logger.error(f"Connection failed: {e}", exc_info=True); exit_code = 1
            except av_exceptions.A2ARemoteAgentError as e: utils.display_error(f"A2A Remote Agent Error: {e}"); logger.error(f"Remote agent error: Status={e.status_code}, Body={e.response_body}", exc_info=False); exit_code = 1
            except av_exceptions.A2AMessageError as e: utils.display_error(f"A2A Message Error: {e}"); logger.error(f"Invalid message: {e}", exc_info=True); exit_code = 1
            except av_exceptions.A2ATimeoutError as e: utils.display_error(f"A2A Timeout Error: {e}"); logger.error(f"Timeout: {e}", exc_info=True); exit_code = 1
            except Exception as e: utils.display_error(f"An unexpected error occurred during task execution: {e}"); logger.exception("Unexpected error during task execution"); exit_code = 1
            finally:
                 # Fetch final status if needed (unchanged)
                 if task_id and final_task_state not in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                     utils.display_info("-" * 20)
                     status_context_final = utils.console.status("[bold cyan]Fetching final task status...", spinner="earth") if _RICH_AVAILABLE else None
                     status_obj_final = status_context_final.__enter__() if status_context_final else None
                     if not status_obj_final: print("Fetching final task status...", flush=True)
                     try: final_task = await client.get_task_status(agent_card, task_id, manager); final_task_state = final_task.state
                     except av_exceptions.A2AError as e: utils.display_error(f"Could not fetch final task status: {e}")
                     except Exception as e: utils.display_error(f"Unexpected error fetching final status: {e}")
                     finally:
                         if status_context_final: status_context_final.__exit__(None, None, None)
                     utils.display_info(f"Final Task State: {final_task_state.value if final_task_state else 'Unknown/Fetch Failed'}")

                 # Determine final exit code (unchanged)
                 if final_task_state == av_models.TaskState.COMPLETED: utils.display_success("Task completed."); exit_code = 0
                 elif final_task_state == av_models.TaskState.FAILED: utils.display_error("Task failed."); exit_code = 1
                 elif final_task_state == av_models.TaskState.CANCELED: utils.display_warning("Task canceled."); exit_code = 2
                 elif final_task_state == av_models.TaskState.INPUT_REQUIRED: utils.display_warning("Task stopped awaiting input (not supported by CLI)."); exit_code = 2
                 else: state_str = final_task_state.value if final_task_state else "Unknown/Fetch Failed"; utils.display_warning(f"Task finished with non-terminal or unknown state: {state_str}"); exit_code = 1

    except Exception as e:
        utils.display_error(f"Failed to initialize or use A2A client: {e}")
        logger.exception("Error initializing/using AgentVaultClient")
        exit_code = 1
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)
        return exit_code
