import asyncio
import logging
import pathlib
import argparse # Use argparse for simple CLI args
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import AgentVault components
try:
    from agentvault import (
        AgentVaultClient, KeyManager, Message, TextPart,
        agent_card_utils, exceptions as av_exceptions, models as av_models
    )
    _AGENTVAULT_AVAILABLE = True
except ImportError as e:
    logger.critical(f"Failed to import agentvault library: {e}. Please install it ('pip install -e ../../agentvault_library').")
    exit(1)

# --- Default Values ---
# Point to the basic echo agent by default for easy testing
DEFAULT_AGENT_REF = "http://localhost:8000/agent-card.json"


async def run_agent_task(agent_ref: str, input_text: str, key_service_override: Optional[str] = None):
    """
    Connects to an agent using the library and streams its response.
    """
    # Initialize KeyManager - loads from env/file/keyring
    # Pass the key_service_override if provided by the user
    key_manager = KeyManager(use_keyring=True) # Enable keyring by default
    agent_card = None
    task_id = None

    try:
        # --- 1. Load Agent Card ---
        logger.info(f"Loading agent card: {agent_ref}")
        if agent_ref.startswith("http"):
            agent_card = await agent_card_utils.fetch_agent_card_from_url(agent_ref)
        else:
            agent_path = pathlib.Path(agent_ref)
            if agent_path.is_file():
                agent_card = agent_card_utils.load_agent_card_from_file(agent_path)
            else:
                # Simple example doesn't include registry lookup by ID
                raise ValueError(f"Agent reference '{agent_ref}' is not a valid URL or local file path.")

        if not agent_card:
             print(f"Error: Could not load agent card for {agent_ref}")
             return

        logger.info(f"Loaded Agent: {agent_card.name}")

        # --- 2. Prepare Initial Message ---
        initial_message = Message(role="user", parts=[TextPart(content=input_text)])

        # --- 3. Interact using AgentVaultClient ---
        async with AgentVaultClient() as client:
            logger.info(f"Initiating task...")
            # Pass key_service_override to initiate_task if needed (client handles lookup)
            # The client will determine the actual service_id based on card/override
            task_id = await client.initiate_task(
                agent_card=agent_card,
                initial_message=initial_message,
                key_manager=key_manager
                # Note: KeyManager needs the correct service_id configured if auth is required.
                # The client library currently uses authScheme.service_identifier or agent_card.humanReadableId
                # if no override is provided *and* no service_identifier is in the card.
                # This example doesn't explicitly pass the override to initiate_task,
                # relying on the user having configured the correct service_id in KeyManager.
            )
            logger.info(f"Task initiated: {task_id}")

            # --- 4. Stream and Process Events ---
            logger.info("Streaming events...")
            final_response_text = ""
            async for event in client.receive_messages(
                agent_card=agent_card, task_id=task_id, key_manager=key_manager
            ):
                if isinstance(event, av_models.TaskStatusUpdateEvent):
                    logger.info(f"  Status Update: {event.state} "
                                f"(Msg: {event.message or 'N/A'})")
                    if event.state in [av_models.TaskState.COMPLETED,
                                       av_models.TaskState.FAILED,
                                       av_models.TaskState.CANCELED]:
                        logger.info("  Terminal state reached.")
                        break
                elif isinstance(event, av_models.TaskMessageEvent):
                    logger.info(f"  Message Received (Role: {event.message.role}):")
                    for part in event.message.parts:
                        if isinstance(part, TextPart):
                            logger.info(f"    Text: {part.content}")
                            if event.message.role == "assistant":
                                final_response_text += part.content + "\n"
                        else:
                            logger.info(f"    Part (Type: {getattr(part, 'type', 'Unknown')}): {part}")
                elif isinstance(event, av_models.TaskArtifactUpdateEvent):
                     artifact = event.artifact
                     logger.info(f"  Artifact Update (ID: {artifact.id}, Type: {artifact.type}):")
                     if artifact.url: logger.info(f"    URL: {artifact.url}")
                     if artifact.media_type: logger.info(f"    Media Type: {artifact.media_type}")
                     if artifact.content:
                         content_repr = repr(artifact.content)
                         logger.info(f"    Content: {content_repr[:150]}{'...' if len(content_repr) > 150 else ''}")
                     else:
                         logger.info("    Content: [Not provided directly]")
                elif isinstance(event, dict) and event.get("error"):
                     logger.error(f"  ERROR received via SSE stream: {event}")
                     final_response_text += f"\n[Stream Error: {event.get('message', 'Unknown')}]"
                     break
                else:
                    logger.warning(f"  Received unknown event type: {type(event)}")

            print("\n--- Final Aggregated Agent Response ---")
            print(final_response_text.strip())
            print("---------------------------------------")

    # --- 5. Handle Potential Errors ---
    except av_exceptions.AgentCardError as e:
        logger.error(f"Error loading or validating agent card: {e}", exc_info=True)
    except av_exceptions.A2AAuthenticationError as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        print("\nError: Authentication failed. Ensure credentials are configured correctly for the agent's required service identifier.")
        if key_service_override:
            print(f"       (Tried using service ID: '{key_service_override}')")
        else:
            print(f"       (Agent might require a specific service ID - check its card or use --key-service)")
    except av_exceptions.A2AConnectionError as e:
        logger.error(f"Connection error: {e}", exc_info=True)
        print(f"\nError: Could not connect to the agent or its token endpoint: {e}")
    except av_exceptions.A2ARemoteAgentError as e:
        logger.error(f"Agent returned an error: Status={e.status_code}, Body={e.response_body}", exc_info=False)
        print(f"\nError: Agent returned an error (Status/Code: {e.status_code}): {e}")
    except av_exceptions.A2AMessageError as e:
         logger.error(f"A2A protocol message error: {e}", exc_info=True)
         print(f"\nError: Invalid message format from agent: {e}")
    except av_exceptions.A2ATimeoutError as e:
         logger.error(f"A2A request timed out: {e}", exc_info=True)
         print(f"\nError: Request to agent timed out: {e}")
    except av_exceptions.KeyManagementError as e:
         logger.error(f"Key management error: {e}", exc_info=True)
         print(f"\nError: Failed to load local credentials: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}") # Log full traceback
        print(f"\nAn unexpected error occurred: {type(e).__name__}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a task on an AgentVault agent using the library.")
    parser.add_argument(
        "--agent-ref",
        default=DEFAULT_AGENT_REF,
        help=f"Agent reference (URL or local file path). Default: {DEFAULT_AGENT_REF}"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input text prompt for the agent."
    )
    parser.add_argument(
        "--key-service",
        default=None,
        help="Optional: Service ID for KeyManager lookup if agent requires auth and card doesn't specify."
    )

    args = parser.parse_args()

    asyncio.run(run_agent_task(args.agent_ref, args.input, args.key_service))
