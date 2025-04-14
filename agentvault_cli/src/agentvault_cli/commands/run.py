import click
import httpx
import pathlib
import logging
import asyncio
import json
import signal # For Ctrl+C handling
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
    # Keep CLI loadable, but command will fail later if lib missing

# Import default registry URL from discover command
try:
    from .discover import DEFAULT_REGISTRY_URL
except ImportError:
    DEFAULT_REGISTRY_URL = "http://localhost:8000" # Fallback

# Rich imports for better output
from rich.panel import Panel
from rich.syntax import Syntax

logger = logging.getLogger(__name__)

# --- Flag for Ctrl+C Handling ---
terminate_requested = False

def handle_interrupt(sig, frame):
    """Signal handler to request termination."""
    global terminate_requested
    if not terminate_requested: # Prevent multiple messages if Ctrl+C pressed again
        utils.display_warning("\nTermination requested (Ctrl+C). Attempting to cancel task...")
        terminate_requested = True
    else:
        utils.display_warning("Termination already in progress...")


# --- Helper for Agent Card Loading ---
async def _load_agent_card(
    agent_ref: str, registry_url: str, ctx: click.Context
) -> Optional[av_models.AgentCard]:
    """Loads agent card from ID, URL, or file."""
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
                # Assume registry API has a direct lookup endpoint /api/v1/agent-cards/id/{humanReadableId}
                # Note: URL encoding might be needed for the ID
                encoded_id = httpx.URL(path=agent_ref).path # Basic encoding
                lookup_url = f"{registry_url.rstrip('/')}/api/v1/agent-cards/id/{encoded_id}"
                utils.display_info(f"Attempting direct lookup: {lookup_url}")

                async with httpx.AsyncClient() as client:
                    response = await client.get(lookup_url, timeout=15.0, follow_redirects=True)

                if response.status_code == 200:
                    card_full_data = response.json()
                    # The detail endpoint returns AgentCardRead schema which contains card_data
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

    Handles API Key and OAuth2 Client Credentials authentication based on the
    Agent Card. Monitors task progress via Server-Sent Events (SSE).
    Task states include: SUBMITTED, WORKING, INPUT_REQUIRED, COMPLETED, FAILED, CANCELED.
    """
    global terminate_requested # Allow modification by signal handler
    terminate_requested = False # Reset flag at start of command

    if not _agentvault_lib_imported:
        utils.display_error("Cannot run task: Core 'agentvault' library failed to import.")
        ctx.exit(1)
    # Check for essential components loaded from library
    if not all([agent_card_utils, av_exceptions, av_models, key_manager, av_client]):
        utils.display_error("Cannot run task: Core 'agentvault' library components missing.")
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
        except Exception as e:
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
    requires_auth = True
    manager: Optional[key_manager.KeyManager] = None # Define manager in broader scope

    try:
        manager = key_manager.KeyManager(use_keyring=True)

        if key_service_override:
            service_id = key_service_override
            utils.display_info(f"Using overridden service ID for key lookup: '{service_id}'")
        else:
            api_key_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'apiKey'), None)
            oauth2_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'oauth2'), None) # Check for oauth2
            none_scheme = next((s for s in agent_card.auth_schemes if s.scheme == 'none'), None)

            if api_key_scheme:
                service_id = api_key_scheme.service_identifier or agent_card.human_readable_id
                utils.display_info(f"Using service ID from agent card ('apiKey' scheme): '{service_id}'")
                requires_auth = True
            # --- ADDED: OAuth2 handling ---
            elif oauth2_scheme:
                service_id = oauth2_scheme.service_identifier or agent_card.human_readable_id
                utils.display_info(f"Using service ID from agent card ('oauth2' scheme): '{service_id}'")
                # KeyManager will handle fetching token using ID/Secret for this service_id
                requires_auth = True # Requires ID/Secret to be configured
            # --- END ADDED ---
            elif none_scheme:
                utils.display_info("Agent supports 'none' authentication scheme. No API key needed.")
                requires_auth = False
                service_id = None
            else:
                utils.display_warning(f"Agent does not explicitly support 'apiKey', 'oauth2', or 'none' auth schemes. Supported: {[s.scheme for s in agent_card.auth_schemes]}. Key/Credential lookup might fail.")
                if agent_card.auth_schemes:
                     first_scheme = agent_card.auth_schemes[0]
                     service_id = first_scheme.service_identifier or agent_card.human_readable_id
                     utils.display_warning(f"Attempting key/credential lookup using service ID from first scheme ('{first_scheme.scheme}'): '{service_id}'")
                     requires_auth = True
                else:
                     utils.display_error("Agent card has no authentication schemes defined.")
                     ctx.exit(1)

        if requires_auth:
            if auth_key_override:
                # Note: This override only works for apiKey scheme currently.
                # OAuth requires ID/Secret which aren't provided via CLI flag.
                if any(s.scheme == 'apiKey' for s in agent_card.auth_schemes) or not agent_card.auth_schemes:
                    api_key = auth_key_override
                    utils.display_warning("Using API key provided directly via --auth-key (INSECURE).")
                else:
                    utils.display_error("--auth-key override is only supported for 'apiKey' scheme.")
                    ctx.exit(1)
            elif service_id:
                # KeyManager handles both API key and OAuth cred lookup transparently
                # Check if *any* credential (key or OAuth ID/Secret) is available
                key_found = manager.get_key(service_id) is not None
                oauth_found = manager.get_oauth_client_id(service_id) is not None and \
                              manager.get_oauth_client_secret(service_id) is not None

                if key_found or oauth_found:
                    source = manager.get_key_source(service_id) or manager._oauth_sources.get(service_id) # Get source from either
                    utils.display_info(f"Found credentials for service '{service_id}' (Source: {source.upper() if source else 'Unknown'}).")
                    # No need to store api_key here, library handles it
                else:
                    utils.display_error(f"Credentials required for service '{service_id}' but not found.")
                    utils.display_info("Use 'agentvault config set' to configure the key/credentials using --env, --file, --keyring, or --oauth-configure.")
                    ctx.exit(1)
            else:
                utils.display_error("Authentication is required, but could not determine the service ID for credential lookup.")
                ctx.exit(1)
        else:
             api_key = None # Explicitly set for clarity

    except Exception as e:
        utils.display_error(f"An unexpected error occurred during key/credential loading: {e}")
        logger.exception("Unexpected error in key loading section")
        ctx.exit(1)

    # Ensure manager is instantiated if needed later
    if manager is None:
        manager = key_manager.KeyManager(use_keyring=True) # Should have been created, but safety

    # 5. Prepare Initial Message
    try:
        initial_message = av_models.Message(
            role="user",
            parts=[av_models.TextPart(content=processed_input_text)]
        )
    except Exception as e:
        utils.display_error(f"Failed to create initial message structure: {e}")
        ctx.exit(1)

    # 6. Instantiate Client and Run Task
    task_id: Optional[str] = None
    final_task_state: Optional[av_models.TaskState] = None
    original_sigint_handler = signal.getsignal(signal.SIGINT) # Store original handler
    signal.signal(signal.SIGINT, handle_interrupt) # Register custom handler

    try:
        async with av_client.AgentVaultClient() as client:
            try:
                utils.display_info("Initiating task with agent...")
                task_id = await client.initiate_task(
                    agent_card=agent_card,
                    initial_message=initial_message,
                    key_manager=manager, # Pass the instantiated manager
                    mcp_context=mcp_context_data,
                    webhook_url=None # CLI doesn't support setting this yet
                )
                utils.display_success(f"Task initiated successfully. Task ID: {task_id}")
                utils.display_info("Waiting for events... (Press Ctrl+C to request cancellation)")

                # Handle SSE stream
                async for event in client.receive_messages(
                    agent_card=agent_card, task_id=task_id, key_manager=manager
                ):
                    # --- ADDED DEBUG PRINT ---
                    # print(f"DEBUG: Processing event type: {type(event)}") # Removed for clarity
                    # --- END ADDED ---

                    if terminate_requested:
                        utils.display_info(f"Attempting to terminate task {task_id}...")
                        try:
                            await client.terminate_task(agent_card, task_id, manager)
                            utils.display_success(f"Termination request acknowledged for task {task_id}.")
                        except av_exceptions.A2AError as term_err:
                            utils.display_error(f"Failed to send termination request: {term_err}")
                        final_task_state = av_models.TaskState.CANCELED # Assume cancelled on request
                        break # Exit event loop

                    # Process different event types
                    if isinstance(event, av_models.TaskStatusUpdateEvent):
                        final_task_state = event.state
                        status_msg = f"Task Status: {event.state.value}"
                        if event.message:
                            status_msg += f" - {event.message}"
                        # --- ADDED DEBUG PRINT ---
                        # print(f"DEBUG: Displaying TaskStatusUpdateEvent: {status_msg}") # Removed for clarity
                        # --- END ADDED ---
                        utils.display_info(status_msg)
                        if event.state in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                            utils.display_info("Task reached terminal state.")
                            break # Exit event loop

                    elif isinstance(event, av_models.TaskMessageEvent):
                        role = event.message.role
                        content_parts = []
                        for part in event.message.parts:
                            if isinstance(part, av_models.TextPart):
                                content_parts.append(part.content)
                            elif isinstance(part, av_models.FilePart):
                                content_parts.append(f"[File: {part.filename or part.url} ({part.media_type or 'unknown'})]")
                            elif isinstance(part, av_models.DataPart):
                                # Pretty print JSON data part
                                try:
                                     content_parts.append(f"[Data ({part.media_type}):\n{json.dumps(part.content, indent=2)}]")
                                except Exception:
                                     content_parts.append(f"[Data ({part.media_type}): {part.content}]")
                            else:
                                 content_parts.append("[Unknown message part type]")

                        full_content = "\n".join(content_parts)
                        title = f"Message from {role.capitalize()}"
                        if role == "assistant":
                            utils.console.print(Panel(full_content, title=title, border_style="blue"))
                        elif role == "tool":
                             utils.console.print(Panel(full_content, title=title, border_style="yellow"))
                        else: # user, system
                             utils.console.print(Panel(full_content, title=title, border_style="dim"))


                    elif isinstance(event, av_models.TaskArtifactUpdateEvent):
                        artifact = event.artifact
                        utils.display_info(f"Artifact Update: ID={artifact.id}, Type={artifact.type}")
                        if artifact.url:
                            utils.display_info(f"  URL: {artifact.url}")
                        if artifact.content:
                             # Display content nicely if possible (e.g., syntax highlight code)
                             content_str = str(artifact.content)
                             if isinstance(artifact.content, (dict, list)):
                                 try: content_str = json.dumps(artifact.content, indent=2)
                                 except Exception: pass # Keep original string if dump fails
                             # Basic check for code-like content
                             lang = artifact.media_type.split('/')[-1] if artifact.media_type and '/' in artifact.media_type else "text"
                             if lang in ["python", "json", "yaml", "javascript", "html", "css", "markdown"]:
                                  syntax = Syntax(content_str, lang, theme="default", line_numbers=True)
                                  utils.console.print(Panel(syntax, title=f"Artifact Content ({artifact.id})"))
                             else:
                                  utils.display_info(f"  Content: {content_str[:200]}{'...' if len(content_str) > 200 else ''}")
                        if artifact.metadata:
                             utils.display_info(f"  Metadata: {artifact.metadata}")

                    else:
                        utils.display_warning(f"Received unknown event type: {type(event)}")

                # End of event loop

            except av_exceptions.A2AError as e:
                # --- ADDED DEBUG PRINT ---
                # print(f"DEBUG: Caught A2AError: {e}") # Removed for clarity
                # --- END ADDED ---
                utils.display_error(f"A2A communication error: {e}")
                logger.exception("A2AError during task execution")
                ctx.exit(1)
            except Exception as e:
                 utils.display_error(f"An unexpected error occurred during task execution: {e}")
                 logger.exception("Unexpected error during task execution")
                 ctx.exit(1)
            finally:
                 # Fetch final status if task ID was obtained and loop finished/broke
                 if task_id and final_task_state not in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                     utils.display_info("-" * 20)
                     utils.display_info("Fetching final task status...")
                     try:
                         final_task = await client.get_task_status(agent_card, task_id, manager)
                         final_task_state = final_task.state
                         utils.display_info(f"Final Task State: {final_task.state.value}")
                         # Optionally display final messages/artifacts here if needed
                     except av_exceptions.A2AError as e:
                         utils.display_error(f"Could not fetch final task status: {e}")
                     except Exception as e:
                          utils.display_error(f"Unexpected error fetching final status: {e}")

                 # Restore original signal handler
                 signal.signal(signal.SIGINT, original_sigint_handler)

                 # Determine final exit code based on state
                 if final_task_state == av_models.TaskState.COMPLETED:
                     utils.display_success("Task completed.")
                     ctx.exit(0)
                 elif final_task_state == av_models.TaskState.FAILED:
                     utils.display_error("Task failed.")
                     ctx.exit(1)
                 elif final_task_state == av_models.TaskState.CANCELED:
                     utils.display_warning("Task canceled.")
                     ctx.exit(2) # Use different exit code for cancellation
                 elif final_task_state == av_models.TaskState.INPUT_REQUIRED:
                     utils.display_warning("Task stopped awaiting input (not supported by CLI).")
                     ctx.exit(2) # Treat as non-success
                 else:
                     # Includes SUBMITTED, WORKING, or None if status fetch failed
                     state_str = final_task_state.value if final_task_state else "Unknown/Fetch Failed"
                     utils.display_warning(f"Task finished with non-terminal state: {state_str}")
                     ctx.exit(1) # Treat unexpected non-terminal state as error


    except Exception as e: # Catch errors during client instantiation
        utils.display_error(f"Failed to initialize A2A client: {e}")
        logger.exception("Error initializing AgentVaultClient")
        ctx.exit(1)
