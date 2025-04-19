import asyncclick as click
import asyncio
import uuid
import json
import pathlib
import datetime
import logging
import signal
import sys
import re
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List

# Import core library components
from agentvault.models import (
    AgentCard, Message, TextPart, Task, TaskState, TaskStatus,
    TaskStatusUpdateEvent, TaskMessageEvent, TaskArtifactUpdateEvent, Artifact
)
from agentvault.exceptions import (
    AgentCardValidationError, AgentCardFetchError, A2AConnectionError, A2AMessageError,
    A2AAuthenticationError, A2ARemoteAgentError, A2ATimeoutError, KeyManagementError, A2AError
)
from agentvault import agent_card_utils, key_manager, client as av_client

# Import CLI utilities
from .. import utils
from ..config import AgentVaultConfig

# --- ADDED: Import _RICH_AVAILABLE ---
try:
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False
# --- END ADDED ---

logger = logging.getLogger(__name__)

# --- Global variable to track interruption ---
_interrupted = False

def _signal_handler(sig, frame):
    global _interrupted
    if not _interrupted:
        _interrupted = True
        utils.display_warning("\n🛑 Interrupt received. Attempting graceful shutdown...")
        # Suppress further signals of the same type to avoid multiple messages
        signal.signal(sig, signal.SIG_IGN)
    else:
        utils.display_warning("\n🛑 Second interrupt received. Forcing exit.")
        sys.exit(1) # Force exit on second interrupt


async def _load_agent_card(
    agent_ref: str, registry_url: Optional[str], config: AgentVaultConfig
) -> Optional[AgentCard]:
    """Helper to load agent card, handling errors and displaying messages."""
    utils.display_info(f"Attempting to load agent card for: {agent_ref}")
    try:
        card = await agent_card_utils.load_agent_card(agent_ref, registry_url, config.registry_path)
        if not card:
            utils.display_error(f"Agent card not found for reference: {agent_ref}")
            return None
        utils.display_success(f"Successfully loaded agent: {card.name} ({card.human_readable_id})")
        utils.display_info(f"  Agent A2A Endpoint: {card.url}")
        return card
    except AgentCardValidationError as e:
        utils.display_error(f"Agent card validation failed for {agent_ref}: {e}")
        logger.error(f"Validation error details: {e.errors()}", exc_info=True)
        return None
    except AgentCardFetchError as e:
        utils.display_error(f"Failed to fetch agent card for {agent_ref}: {e}")
        logger.error(f"Fetch error details", exc_info=True)
        return None
    except Exception as e:
        utils.display_error(f"An unexpected error occurred while loading agent card {agent_ref}: {e}")
        logger.error(f"Unexpected agent load error", exc_info=True)
        return None

def _get_auth_details(
    card: AgentCard, mgr: key_manager.KeyManager, service_override: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Gets authentication scheme, key, and source, handling errors."""
    scheme = card.preferred_auth_scheme
    key = None
    key_source = None
    service_id = service_override or card.preferred_auth_service_identifier

    if not scheme:
        utils.display_error("Agent card does not specify any supported authentication schemes.")
        return None, None, None
    if scheme == "none":
        utils.display_info("Agent supports 'none' authentication scheme. No credentials needed.")
        return scheme, None, None

    if not service_id:
        utils.display_error(f"Agent requires '{scheme}' authentication, but no service identifier was found in the agent card.")
        utils.display_info("You can try specifying one with the --auth-service-id option.")
        return None, None, None

    utils.display_info(f"Agent requires '{scheme}' authentication for service '{service_id}'. Looking up credentials...")

    try:
        if scheme == "apiKey":
            key = mgr.get_key(service_id)
            key_source = mgr.get_key_source(service_id)
        elif scheme == "oauth2":
            # For OAuth2, we might need client_id and client_secret for client_credentials flow
            # Or just rely on stored refresh tokens etc. for authorization_code flow (handled by client)
            # Let's assume for now the client handles the flow if tokens exist, but check for config
            client_id = mgr.get_oauth_client_id(service_id)
            client_secret = mgr.get_oauth_client_secret(service_id) # May be None
            key = client_id # Use client_id as the primary identifier for OAuth presence check
            key_source = mgr.get_oauth_source(service_id)
            if not key:
                 utils.display_error(f"OAuth2 configuration required for service '{service_id}' but none found (checked Env, File, Keyring).")
                 utils.display_info("Use 'agentvault config set --oauth-configure' to set up OAuth2 credentials.")
                 return scheme, None, None # Indicate scheme but missing key
            # Store both for potential use by the client
            key = f"client_id={client_id}" # Pack for potential client use, may need refinement
            if client_secret:
                key += f";client_secret={client_secret}"

        else:
            utils.display_error(f"Unsupported authentication scheme specified by agent: {scheme}")
            return None, None, None

        if not key:
            utils.display_error(f"Credentials required for service '{service_id}' but none found (checked Env, File, Keyring).")
            if scheme == "apiKey":
                 utils.display_info("Use 'agentvault config set' to configure the key using --key or --keyring.")
            # OAuth guidance already given if key (client_id) was missing
            return scheme, None, None # Indicate scheme but missing key
        else:
            utils.display_success(f"Credentials found for service '{service_id}' (Source: {key_source}).")
            return scheme, key, key_source

    except KeyManagementError as e:
        utils.display_error(f"Error accessing credentials for service '{service_id}': {e}")
        logger.error("Key management error", exc_info=True)
        return scheme, None, None
    except Exception as e:
        utils.display_error(f"An unexpected error occurred during credential lookup for '{service_id}': {e}")
        logger.error("Unexpected credential lookup error", exc_info=True)
        return scheme, None, None


def _determine_artifact_filename(artifact: Artifact, output_dir: pathlib.Path, task_id: str) -> pathlib.Path:
    """Determines a safe filename for an artifact."""
    # Sanitize artifact ID for use as part of filename
    safe_base_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in artifact.id)[:100]

    # Determine extension based on media type or artifact type
    ext = ".bin" # Default extension
    if artifact.media_type:
        # Basic mapping, can be expanded
        mime_map = {
            "text/plain": ".txt",
            "text/markdown": ".md",
            "application/json": ".json",
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "application/octet-stream": ".bin",
        }
        ext = mime_map.get(artifact.media_type.lower(), ".bin")
    elif artifact.type:
        # Fallback to artifact type if media_type is missing
        type_map = {
            "log": ".log",
            "file": ".dat",
            "code": ".txt", # Default code to text
        }
        ext = type_map.get(artifact.type.lower(), ".bin")

    # Ensure directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Construct filename: {output_dir}/{sanitized_artifact_id}{.ext}
    filename = output_dir / f"{safe_base_name}{ext}"

    # Handle potential filename collisions (though unlikely with UUIDs/unique IDs)
    counter = 1
    base_filename = filename.stem
    while filename.exists():
        filename = output_dir / f"{base_filename}_{counter}{ext}"
        counter += 1
        if counter > 100: # Safety break
             logger.error(f"Could not find unique filename for artifact {artifact.id} after 100 attempts.")
             # Fallback to a more unique name
             filename = output_dir / f"{safe_base_name}_{uuid.uuid4().hex[:8]}{ext}"
             break

    return filename

async def _save_artifact(artifact: Artifact, output_dir: pathlib.Path, task_id: str):
    """Saves artifact content to a file."""
    if artifact.content is None:
        utils.display_warning(f"Artifact '{artifact.id}' has no content to save.")
        return

    filename = _determine_artifact_filename(artifact, output_dir, task_id)
    utils.display_info(f"  Saving artifact: {artifact.id} (Type: {artifact.type}, Media Type: {artifact.media_type or 'N/A'})")
    try:
        # Assume content is string, needs encoding for binary write
        # TODO: Handle potentially pre-encoded binary content if model changes
        content_bytes = artifact.content.encode('utf-8')
        with open(filename, "wb") as f:
            f.write(content_bytes)
        utils.display_info(f"  Content saved to: {filename}")
    except IOError as e:
        utils.display_error(f"  Error saving artifact {artifact.id} to {filename}: {e}")
        logger.error(f"IOError saving artifact {artifact.id}", exc_info=True)
    except Exception as e:
        utils.display_error(f"  Unexpected error saving artifact {artifact.id}: {e}")
        logger.error(f"Unexpected error saving artifact {artifact.id}", exc_info=True)


async def _handle_sse_events(
    client: av_client.AgentVaultClient,
    task_id: str,
    output_artifacts_dir: Optional[pathlib.Path] = None,
    timeout: Optional[float] = None
) -> TaskState:
    """Processes SSE events from the agent, updating display and saving artifacts."""
    global _interrupted
    last_state = TaskState.PENDING
    processed_messages = set()
    processed_artifacts = set()
    start_time = asyncio.get_event_loop().time()

    # --- Rich Live Display Setup ---
    live_display = None
    status_spinner = None
    message_panel = None
    artifact_text = None
    if _RICH_AVAILABLE:
        status_spinner = Spinner("dots", text=Text("Waiting for task updates...", style="blue"))
        message_panel = Panel("", title="Agent Messages", border_style="green", expand=False)
        artifact_text = Text("", style="dim")
        display_group = click.Group(status_spinner, message_panel, artifact_text)
        live_display = Live(display_group, refresh_per_second=4, transient=False) # Keep final state

    async def update_display(state: TaskState, message: Optional[str] = None, artifact_info: Optional[str] = None):
        if live_display:
            nonlocal status_spinner, message_panel, artifact_text
            status_text = f"Task Status: {state.value.upper()}"
            if message:
                status_text += f" - {message}"
            status_spinner.text = Text(status_text, style="blue" if state in [TaskState.PENDING, TaskState.WORKING] else "green" if state == TaskState.COMPLETED else "red")

            if message and message not in processed_messages:
                 # Append new message content to the panel
                 current_content = message_panel.renderable if isinstance(message_panel.renderable, str) else ""
                 # Basic check for markdown, render accordingly
                 if any(c in message for c in ['*', '_', '`', '#']):
                     new_content = Markdown(message)
                 else:
                     new_content = Text(message)
                 # Combine (if needed, adjust formatting)
                 if current_content:
                     message_panel.renderable = click.Group(current_content, new_content)
                 else:
                     message_panel.renderable = new_content
                 processed_messages.add(message) # Avoid duplication in panel

            if artifact_info and artifact_info not in processed_artifacts:
                current_artifacts = artifact_text.plain
                new_artifact_line = f"- Artifact Updated: {artifact_info}"
                artifact_text.plain = f"{current_artifacts}\n{new_artifact_line}" if current_artifacts else new_artifact_line
                processed_artifacts.add(artifact_info) # Avoid duplication

            # Update the live display group
            live_display.update(click.Group(status_spinner, message_panel, artifact_text))
        else:
            # Fallback to simple printing if Rich is not available
            status_text = f"Task Status: {state.value.upper()}"
            if message:
                status_text += f" - {message}"
            utils.display_info(status_text)
            if message and message not in processed_messages:
                 utils.console.print(f"Assistant: {message}")
                 processed_messages.add(message)
            if artifact_info and artifact_info not in processed_artifacts:
                 utils.display_info(f"Artifact Updated: {artifact_info}")
                 processed_artifacts.add(artifact_info)

    try:
        if live_display:
            with live_display:
                await update_display(TaskState.PENDING) # Initial status
                async for event in client.receive_messages(task_id):
                    if _interrupted:
                        utils.display_warning("Stopping event processing due to interrupt.")
                        break # Exit the loop gracefully

                    # Timeout check
                    if timeout and (asyncio.get_event_loop().time() - start_time > timeout):
                        utils.display_error(f"Timeout reached ({timeout}s) waiting for task completion.")
                        # Consider attempting to cancel the task on the agent side if API supports it
                        raise asyncio.TimeoutError("Task execution timed out.")

                    if isinstance(event, TaskStatusUpdateEvent):
                        last_state = event.state
                        await update_display(event.state, event.message)
                        if event.state.is_terminal():
                            break # Stop listening if task is completed or failed

                    elif isinstance(event, TaskMessageEvent):
                        # Display message content
                        msg_content = " ".join([part.content for part in event.message.parts if isinstance(part, TextPart)])
                        if msg_content:
                            await update_display(last_state, message=msg_content) # Update with message, keep last known state

                    elif isinstance(event, TaskArtifactUpdateEvent):
                        artifact_info = f"{event.artifact.id} (Type: {event.artifact.type})"
                        await update_display(last_state, artifact_info=artifact_info)
                        if output_artifacts_dir and event.artifact.content is not None:
                            await _save_artifact(event.artifact, output_artifacts_dir, task_id)

                    # Add a small sleep to prevent tight loop if stream is very fast or empty
                    await asyncio.sleep(0.05)

        else: # No Rich available
            await update_display(TaskState.PENDING) # Initial status
            async for event in client.receive_messages(task_id):
                if _interrupted:
                    utils.display_warning("Stopping event processing due to interrupt.")
                    break

                # Timeout check
                if timeout and (asyncio.get_event_loop().time() - start_time > timeout):
                    utils.display_error(f"Timeout reached ({timeout}s) waiting for task completion.")
                    raise asyncio.TimeoutError("Task execution timed out.")

                if isinstance(event, TaskStatusUpdateEvent):
                    last_state = event.state
                    await update_display(event.state, event.message)
                    if event.state.is_terminal():
                        break
                elif isinstance(event, TaskMessageEvent):
                    msg_content = " ".join([part.content for part in event.message.parts if isinstance(part, TextPart)])
                    if msg_content:
                         await update_display(last_state, message=msg_content)
                elif isinstance(event, TaskArtifactUpdateEvent):
                    artifact_info = f"{event.artifact.id} (Type: {event.artifact.type})"
                    await update_display(last_state, artifact_info=artifact_info)
                    if output_artifacts_dir and event.artifact.content is not None:
                        await _save_artifact(event.artifact, output_artifacts_dir, task_id)
                await asyncio.sleep(0.05)

    except asyncio.TimeoutError:
        # Error already displayed
        return TaskState.FAILED # Or a specific timeout state if available
    except A2AConnectionError as e:
        logger.error(f"Connection failed during event stream: {e}", exc_info=True)
        utils.display_error(f"Connection lost while waiting for task updates: {e}")
        # Fallback to fetching final status might be needed
        return TaskState.UNKNOWN # Indicate connection was lost
    except A2AError as e:
        logger.error(f"A2A error during event stream: {e}", exc_info=True)
        utils.display_error(f"An error occurred while receiving task updates: {e}")
        return TaskState.UNKNOWN
    except Exception as e:
        logger.error(f"Unexpected error processing SSE events: {e}", exc_info=True)
        utils.display_error(f"An unexpected error occurred: {e}")
        return TaskState.UNKNOWN
    finally:
        # Ensure live display is stopped if it was started
        # This might not be strictly necessary if using `with live_display:`
        # but added for robustness.
        # if live_display and live_display.is_started:
        #     live_display.stop()
        pass # 'with' statement handles stopping

    if _interrupted:
         utils.display_warning("Task processing was interrupted.")
         # Attempt to get final status if possible, but mark as interrupted
         return TaskState.CANCELLED # Or UNKNOWN depending on desired state

    return last_state


async def _get_final_task_status(client: av_client.AgentVaultClient, task_id: str) -> Task:
    """Fetches the final task status."""
    utils.display_info("Fetching final task details...")
    try:
        final_task = await client.get_task_status(task_id)
        utils.display_success(f"Final task state: {final_task.state.value.upper()}")
        # Optionally display final messages/artifacts here if needed
        return final_task
    except A2AError as e:
        utils.display_error(f"Failed to retrieve final task status: {e}")
        logger.error(f"Failed to get final task status for {task_id}", exc_info=True)
        # Create a dummy Task object to indicate failure but allow type consistency
        return Task(
            id=task_id,
            state=TaskState.UNKNOWN, # Indicate fetch failed
            createdAt=datetime.datetime.now(datetime.timezone.utc), # Placeholder
            updatedAt=datetime.datetime.now(datetime.timezone.utc), # Placeholder
            messages=[],
            artifacts=[]
        )

# --- MODIFIED: Add @click.pass_context and ctx parameter ---
@click.command()
@click.option('--agent', '-a', 'agent_ref', required=True, help='Agent reference (human-readable ID, URL, or local file path).')
@click.option('--input', '-i', 'input_content', required=True, help='Initial input/prompt for the agent. Prefix with "@" to read from a file (e.g., @prompt.txt).')
@click.option('--context', '-c', 'context_content', multiple=True, help='Additional context for the agent. Prefix with "@" to read from a file. Can be used multiple times.')
@click.option('--output-artifacts', '-o', type=click.Path(file_okay=False, dir_okay=True, writable=True, path_type=pathlib.Path), help='Directory to save any artifacts generated by the agent.')
@click.option('--registry', '-r', 'registry_url', help='URL of the agent registry to use for resolving agent IDs.')
@click.option('--timeout', '-t', type=float, default=300.0, help='Timeout in seconds to wait for the task to complete (default: 300).')
@click.option('--auth-service-id', help='Override the service identifier used for looking up authentication credentials.')
@click.option('--use-keyring/--no-use-keyring', default=True, help='Enable/disable using the system keyring for credentials.')
@click.pass_context
async def run(
    ctx: click.Context, # Added ctx parameter
    agent_ref: str,
    input_content: str,
    context_content: Tuple[str],
    output_artifacts: Optional[pathlib.Path],
    registry_url: Optional[str],
    timeout: float,
    auth_service_id: Optional[str],
    use_keyring: bool
):
# --- END MODIFIED ---
    """
    Run a task with a specified agent.

    Loads the agent card, prepares the initial message and context,
    initiates a task with the agent via A2A protocol, streams status
    updates and messages, and optionally saves artifacts.
    """
    global _interrupted
    _interrupted = False # Reset interrupt flag for this run
    # Set up signal handling for graceful shutdown
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except ValueError:
        # Cannot set signal handlers in non-main thread (e.g. during tests)
        logger.warning("Could not set signal handlers. Graceful interruption might not work.")
        pass


    config = AgentVaultConfig()
    config.load() # Load default config

    # 1. Load Agent Card
    card = await _load_agent_card(agent_ref, registry_url, config)
    if not card:
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---

    # 2. Handle Authentication
    utils.display_info("Initializing KeyManager...")
    try:
        mgr = key_manager.KeyManager(use_keyring=use_keyring)
        utils.display_success("KeyManager initialized.")
    except Exception as e:
        utils.display_error(f"Failed to initialize KeyManager: {e}")
        logger.error("KeyManager initialization failed", exc_info=True)
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---

    auth_scheme, auth_key, _ = _get_auth_details(card, mgr, auth_service_id)

    if auth_scheme is None: # Error occurred and was displayed in helper
         # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
         ctx.exit(1)
         # --- END MODIFIED ---
    if auth_scheme != "none" and auth_key is None: # Scheme requires key, but none found
         # Error message already displayed by _get_auth_details
         # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
         ctx.exit(1)
         # --- END MODIFIED ---

    # 3. Prepare Initial Message and Context
    initial_message_parts = []
    # Handle input (file or direct string)
    if input_content.startswith('@'):
        input_file = pathlib.Path(input_content[1:])
        try:
            input_text = input_file.read_text(encoding='utf-8')
            utils.display_info(f"Read input from file: {input_file}")
            initial_message_parts.append(TextPart(content=input_text))
        except FileNotFoundError:
            utils.display_error(f"Input file not found: {input_file}")
            # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
            ctx.exit(1)
            # --- END MODIFIED ---
        except IOError as e:
            utils.display_error(f"Error reading input file {input_file}: {e}")
            # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
            ctx.exit(1)
            # --- END MODIFIED ---
    else:
        initial_message_parts.append(TextPart(content=input_content))

    # Handle context files/strings
    for ctx_item in context_content:
        if ctx_item.startswith('@'):
            ctx_file = pathlib.Path(ctx_item[1:])
            try:
                ctx_text = ctx_file.read_text(encoding='utf-8')
                utils.display_info(f"Read context from file: {ctx_file}")
                # Decide how to structure context parts - separate TextPart for now
                initial_message_parts.append(TextPart(content=ctx_text, role="context")) # Assuming role="context" is valid or handled
            except FileNotFoundError:
                utils.display_error(f"Context file not found: {ctx_file}")
                # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
                ctx.exit(1)
                # --- END MODIFIED ---
            except IOError as e:
                utils.display_error(f"Error reading context file {ctx_file}: {e}")
                # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
                ctx.exit(1)
                # --- END MODIFIED ---
        else:
             initial_message_parts.append(TextPart(content=ctx_item, role="context"))

    initial_message = Message(role="user", parts=initial_message_parts)

    # 4. Initialize A2A Client
    try:
        # Pass necessary auth details based on scheme
        client_auth_params = {}
        if auth_scheme == "apiKey":
            client_auth_params['api_key'] = auth_key
        elif auth_scheme == "oauth2":
            # The client needs to handle parsing the packed key or use stored tokens
            # This might require refinement in the client library
            # For now, just pass the packed string, assuming client knows what to do
             client_auth_params['oauth_config'] = auth_key # Placeholder name
        # Add other schemes as needed

        client = av_client.AgentVaultClient(
            agent_url=card.url,
            auth_scheme=auth_scheme,
            **client_auth_params
        )
        utils.display_info("A2A Client initialized.")
    except Exception as e:
        utils.display_error(f"Failed to initialize A2A client: {e}")
        logger.error("A2A client initialization failed", exc_info=True)
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---


    # 5. Run Task and Process Events
    task_id = None
    final_state = TaskState.UNKNOWN
    try:
        utils.display_info("Initiating task with agent...")
        task_id = await client.initiate_task(initial_message=initial_message)
        utils.display_success(f"Task initiated successfully. Task ID: {task_id}")

        # Process SSE stream
        final_state = await _handle_sse_events(client, task_id, output_artifacts, timeout)

        # If stream finished without terminal state or was interrupted/lost connection, get final status
        if not final_state.is_terminal() or final_state == TaskState.UNKNOWN:
             if _interrupted and final_state != TaskState.CANCELLED:
                 final_state = TaskState.CANCELLED # Mark as cancelled if interrupted
             else:
                 utils.display_warning(f"Event stream ended with non-terminal state ({final_state.value}). Fetching final status.")
                 final_task_obj = await _get_final_task_status(client, task_id)
                 final_state = final_task_obj.state # Update with fetched state

    except A2AAuthenticationError as e:
        utils.display_error(f"A2A Authentication Error: {e}")
        logger.error("A2A Authentication Error", exc_info=True)
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---
    except A2AConnectionError as e:
        utils.display_error(f"A2A Connection Error: {e}")
        logger.error("A2A Connection Error", exc_info=True)
        # Attempt to get final status if task_id was obtained
        if task_id:
            utils.display_warning("Attempting to fetch final task status despite connection error...")
            final_task_obj = await _get_final_task_status(client, task_id)
            final_state = final_task_obj.state
        else:
            final_state = TaskState.FAILED # Failed before getting task_id
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1) # Exit even if final status was fetched, as connection failed initially
        # --- END MODIFIED ---
    except A2ARemoteAgentError as e:
        utils.display_error(f"Remote Agent Error: {e}")
        logger.error("Remote Agent Error", exc_info=True)
        final_state = TaskState.FAILED # Assume failed if agent reported error
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---
    except A2ATimeoutError as e:
        utils.display_error(f"A2A Timeout Error: {e}")
        logger.error("A2A Timeout Error", exc_info=True)
        final_state = TaskState.FAILED # Assume failed on timeout
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---
    except A2AError as e:
        utils.display_error(f"A2A Error: {e}")
        logger.error("A2A Error", exc_info=True)
        final_state = TaskState.FAILED # Assume general A2A failure
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---
    except asyncio.CancelledError:
         utils.display_warning("Task run was cancelled.")
         final_state = TaskState.CANCELLED
         # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
         ctx.exit(1) # Exit with error code on cancellation
         # --- END MODIFIED ---
    except Exception as e:
        utils.display_error(f"An unexpected error occurred during task execution: {e}")
        logger.error("Unexpected error during run", exc_info=True)
        final_state = TaskState.FAILED
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---
    finally:
        # Restore default signal handlers
        try:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except ValueError:
            pass # Ignore if they couldn't be set initially
        except Exception as e:
             logger.warning(f"Could not restore default signal handlers: {e}")

        utils.console.print("----") # Separator
        utils.console.print(f"Final Task State: {final_state.value.upper()}")
        if not final_state.is_successful():
             utils.display_warning(f"Task finished with non-terminal or unknown state: {final_state.value.upper()}")


    # Final exit based on terminal state
    if final_state.is_successful():
        utils.display_success("Task completed successfully.")
        # Implicit ctx.exit(0)
    else:
        utils.display_error("Task did not complete successfully.")
        # --- MODIFIED: Use ctx.exit(1) instead of return 1 ---
        ctx.exit(1)
        # --- END MODIFIED ---
