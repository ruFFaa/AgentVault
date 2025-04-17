import asyncio
import logging
import pathlib
import click # Still needed for Context object if used internally
import signal # Import signal
import os # Import os

# Configure logging same as CLI for visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Imports from the CLI command (ensure paths are correct) ---
# Assuming this script is run from D:\AgentVault with venv active
try:
    from agentvault_cli.commands.run import _load_agent_card, _get_artifact_filename, handle_interrupt, terminate_requested, ARTIFACT_SAVE_THRESHOLD_BYTES # Import helpers too
    from agentvault_cli import utils
    from agentvault import agent_card_utils # Import from core lib
    from agentvault import exceptions as av_exceptions
    from agentvault import models as av_models
    from agentvault import key_manager
    from agentvault import client as av_client
    _agentvault_lib_imported = True
except ImportError as e:
    print(f"FATAL: Failed to import necessary modules: {e}")
    print("Ensure the main virtual environment is activated and you are running from the project root.")
    exit(1)

# --- Mock Context (if needed by internal functions) ---
# Create a dummy context object if any internal helpers rely on ctx.exit or ctx.obj
class DummyContext:
    def exit(self, code=0):
        print(f"INFO: DummyContext exit called with code {code}")
        # In a real test, you might raise a specific exception here
        # For this direct run, just print.
    def fail(self, message):
        print(f"ERROR: DummyContext fail called: {message}")
        self.exit(1)

async def direct_run():
    print("--- Starting Direct Run Test ---")
    ctx = DummyContext() # Use dummy context

    # --- Parameters matching the CLI command ---
    agent_ref = "http://localhost:8001/agent-card.json"
    input_data = "Who are you?"
    context_file = None
    registry_url = "http://localhost:8000" # Default, adjust if needed
    key_service_override = None
    auth_key_override = None
    output_artifacts = None

    # --- Core Logic Copied & Adapted from run_command ---
    global terminate_requested # Allow modification
    terminate_requested = False # Reset flag

    if not _agentvault_lib_imported:
        utils.display_error("Cannot run task: Core 'agentvault' library failed to import.")
        return 1 # Simulate exit code

    # 1. Load Agent Card
    agent_card = await _load_agent_card(agent_ref, registry_url, ctx) # Pass dummy ctx
    if agent_card is None: return 1

    # 2. Process Input Data (Simplified)
    processed_input_text = input_data

    # 3. Load MCP Context (Skipped for this test)
    mcp_context_data = None

    # 4. Load Keys (Simplified - assumes KeyManager works)
    try:
        manager = key_manager.KeyManager(use_keyring=True)
        # Basic check if auth is needed (adapt based on actual card if needed)
        if agent_card.auth_schemes and agent_card.auth_schemes[0].scheme != 'none':
             service_id = key_service_override or agent_card.auth_schemes[0].service_identifier or agent_card.human_readable_id
             if not manager.get_key(service_id) and not (manager.get_oauth_client_id(service_id) and manager.get_oauth_client_secret(service_id)):
                 utils.display_error(f"Credentials not found for service '{service_id}'.")
                 return 1
             utils.display_info(f"Credentials likely found for service '{service_id}'.")
        else:
             utils.display_info("Agent uses 'none' auth or no schemes defined.")
    except Exception as e:
        utils.display_error(f"Key loading failed: {e}")
        return 1

    # 5. Prepare Initial Message
    initial_message = av_models.Message(role="user", parts=[av_models.TextPart(content=processed_input_text)])

    # 6. Instantiate Client and Run Task
    task_id: Optional[str] = None
    final_task_state: Optional[av_models.TaskState] = None
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    # We won't set the signal handler here for simplicity in direct run

    exit_code = 1 # Default to failure
    try:
        async with av_client.AgentVaultClient() as client:
            try:
                utils.display_info("Initiating task with agent...")
                task_id = await client.initiate_task(
                    agent_card=agent_card, initial_message=initial_message, key_manager=manager,
                    mcp_context=mcp_context_data, webhook_url=None
                )
                utils.display_success(f"Task initiated successfully. Task ID: {task_id}")

                print("[bold green]Waiting for events...", flush=True) # Simple print
                async for event in client.receive_messages(
                    agent_card=agent_card, task_id=task_id, key_manager=manager
                ):
                    # Simplified event printing
                    print(f"  EVENT: {type(event).__name__} - {str(event)[:150]}...")

                    if isinstance(event, av_models.TaskStatusUpdateEvent):
                        final_task_state = event.state
                        if event.state in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                            utils.display_info("Task reached terminal state.")
                            break
                    # Add basic printing for other event types if needed

            except av_exceptions.A2AError as e: utils.display_error(f"A2A communication error: {e}"); exit_code = 1
            except Exception as e: utils.display_error(f"An unexpected error occurred during task execution: {e}"); exit_code = 1
            finally:
                 if task_id and final_task_state not in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                     utils.display_info("-" * 20)
                     print("[bold cyan]Fetching final task status...", flush=True)
                     try: final_task = await client.get_task_status(agent_card, task_id, manager); final_task_state = final_task.state
                     except av_exceptions.A2AError as e: utils.display_error(f"Could not fetch final task status: {e}")
                     except Exception as e: utils.display_error(f"Unexpected error fetching final status: {e}")
                     utils.display_info(f"Final Task State: {final_task_state.value if final_task_state else 'Unknown/Fetch Failed'}")

                 # Determine final exit code based on state
                 if final_task_state == av_models.TaskState.COMPLETED: exit_code = 0
                 elif final_task_state == av_models.TaskState.FAILED: exit_code = 1
                 elif final_task_state == av_models.TaskState.CANCELED: exit_code = 2
                 elif final_task_state == av_models.TaskState.INPUT_REQUIRED: exit_code = 2
                 else: exit_code = 1 # Default to error if unknown/fetch failed

    except Exception as e:
        utils.display_error(f"Failed to initialize A2A client: {e}")
        exit_code = 1

    print(f"--- Direct Run Test Finished with Exit Code: {exit_code} ---")
    return exit_code

# --- Run the async function ---
if __name__ == "__main__":
    asyncio.run(direct_run())