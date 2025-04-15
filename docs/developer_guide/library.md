# Developer Guide: Client Library (`agentvault`)

The `agentvault` library is the core Python package for interacting with the AgentVault ecosystem from the client-side. It enables applications, scripts, or even other agents to discover A2A agents, manage credentials securely, and communicate using the A2A protocol.

## Installation

Install the library from PyPI:

```bash
pip install agentvault
```

For optional OS Keyring support (recommended for secure credential storage):

```bash
pip install "agentvault[os_keyring]"
```

See the main [Installation Guide](../installation.md) for more details, including setting up a development environment.

## Key Components

### `KeyManager`

Handles secure loading, storage, and retrieval of credentials needed for agent authentication.

*   **Purpose:** Abstracts credential sources (environment variables, files, OS keyring) so your client code doesn't need to handle each case explicitly.
*   **Initialization:**
    ```python
    from agentvault import KeyManager
    import pathlib

    # Load from environment variables (default) and OS keyring (if enabled)
    km_env_keyring = KeyManager(use_keyring=True)

    # Load ONLY from a specific .env file (disable env vars and keyring)
    # key_file = pathlib.Path("path/to/your/keys.env")
    # km_file_only = KeyManager(key_file_path=key_file, use_env_vars=False, use_keyring=False)

    # Load from file AND environment (file takes priority)
    # km_file_env = KeyManager(key_file_path=key_file, use_env_vars=True)
    ```
*   **Priority Order:** File (`key_file_path`) > Environment Variables (`use_env_vars=True`) > OS Keyring (`use_keyring=True`, only checked on demand via `get_` methods if not found in file/env cache).
*   **Service Identifier (`service_id`):** This is the key used to look up credentials. It's a *local* name you choose (e.g., "openai", "my-agent-key", "google-oauth-agent") that maps to the credentials needed for a specific agent or service. It often corresponds to the `service_identifier` field in an Agent Card's `authSchemes`.
*   **Retrieving Credentials:**
    ```python
    # Get API Key (returns None if not found)
    api_key = km_env_keyring.get_key("openai")
    if api_key:
        print("Found OpenAI API Key")

    # Get OAuth Credentials (return None if not found or incomplete)
    client_id = km_env_keyring.get_oauth_client_id("google-oauth-agent")
    client_secret = km_env_keyring.get_oauth_client_secret("google-oauth-agent")
    if client_id and client_secret:
        print(f"Found Google OAuth Client ID: {client_id}")

    # Check source
    source = km_env_keyring.get_key_source("openai") # e.g., 'keyring', 'env', 'file', None
    oauth_status = km_env_keyring.get_oauth_config_status("google-oauth-agent") # e.g., "Configured (Source: KEYRING)"
    print(f"OpenAI key source: {source}")
    print(f"Google OAuth status: {oauth_status}")
    ```
*   **Storing Credentials (Primarily for CLI/Setup):**
    ```python
    from agentvault import KeyManagementError

    try:
        # Store API Key securely (requires keyring backend)
        km_env_keyring.set_key_in_keyring("my-new-service", "sk-abc...")

        # Store OAuth creds securely (requires keyring backend)
        km_env_keyring.set_oauth_creds_in_keyring("my-oauth-service", "client_id_123", "client_secret_xyz")
    except KeyManagementError as e:
        print(f"Failed to store credentials in keyring: {e}")
    except ValueError as e:
        print(f"Invalid input for storing credentials: {e}")
    ```
*   **Storage Conventions:** See the `KeyManager` docstring or the [Security Guide](../security.md#credential-management-keymanager) for details on environment variable names and file formats.

### `AgentVaultClient`

The primary class for making asynchronous A2A calls to remote agents.

*   **Purpose:** Handles HTTP requests, authentication, JSON-RPC formatting, SSE streaming, and response parsing according to the [A2A Profile v0.2](../a2a_profile_v0.2.md).
*   **Usage:** Best used as an async context manager. Requires an `AgentCard` instance (loaded via `agent_card_utils`) and a `KeyManager` instance for authentication.
    ```python
    import asyncio
    import logging # Import logging
    from agentvault import (
        AgentVaultClient, KeyManager, Message, TextPart,
        agent_card_utils, exceptions as av_exceptions, models as av_models
    )

    async def run_agent_task(agent_ref: str, input_text: str):
        key_manager = KeyManager(use_keyring=True) # Use keyring and env vars
        agent_card = None
        task_id = None

        try:
            # Load agent card (adjust based on agent_ref type)
            if agent_ref.startswith("http"):
                agent_card = await agent_card_utils.fetch_agent_card_from_url(agent_ref)
            else: # Assume ID or file path (add more robust handling if needed)
                # This part might need adjustment based on whether it's an ID or file
                # For simplicity, assuming fetch_agent_card_from_url handles IDs via registry later
                # Or use load_agent_card_from_file(pathlib.Path(agent_ref))
                raise NotImplementedError("Loading by ID/File needs specific implementation here")

            if not agent_card:
                 print(f"Error: Could not load agent card for {agent_ref}")
                 return

            initial_message = Message(role="user", parts=[TextPart(content=input_text)])

            async with AgentVaultClient() as client:
                # 1. Initiate Task
                print(f"Initiating task with {agent_card.name}...")
                task_id = await client.initiate_task(
                    agent_card=agent_card,
                    initial_message=initial_message,
                    key_manager=key_manager
                    # mcp_context={"user_pref": "concise"}, # Optional MCP
                    # webhook_url="https://...", # Optional webhook
                )
                print(f"Task initiated: {task_id}")

                # 2. Stream Events
                print("Streaming events...")
                final_response = ""
                async for event in client.receive_messages(
                    agent_card=agent_card, task_id=task_id, key_manager=key_manager
                ):
                    if isinstance(event, av_models.TaskStatusUpdateEvent):
                        print(f"  Status: {event.state} (Msg: {event.message or ''})")
                        if event.state in [av_models.TaskState.COMPLETED, av_models.TaskState.FAILED, av_models.TaskState.CANCELED]:
                            print("  Terminal state reached.")
                            break
                    elif isinstance(event, av_models.TaskMessageEvent):
                        print(f"  Message ({event.message.role}):")
                        for part in event.message.parts:
                            if isinstance(part, TextPart):
                                print(f"    Text: {part.content}")
                                if event.message.role == "assistant":
                                    final_response += part.content + "\n"
                            # Add handling for FilePart, DataPart if needed
                            else:
                                print(f"    Part ({part.type}): {part}")
                    elif isinstance(event, av_models.TaskArtifactUpdateEvent):
                         print(f"  Artifact ({event.artifact.type}, ID: {event.artifact.id}):")
                         print(f"    Content: {str(event.artifact.content)[:100]}...") # Example
                         print(f"    URL: {event.artifact.url}")
                         print(f"    Media Type: {event.artifact.media_type}")
                    else:
                        print(f"  Unknown Event: {event}")

                # 3. (Optional) Get Final Status if needed
                # final_task_status = await client.get_task_status(agent_card, task_id, key_manager)
                # print(f"Final task status check: {final_task_status.state}")

                print("\n--- Final Agent Response ---")
                print(final_response.strip())
                print("--------------------------")

        except av_exceptions.AgentCardError as e:
            print(f"Error loading agent card: {e}")
        except av_exceptions.A2AAuthenticationError as e:
            print(f"Authentication error: {e}")
            print("Hint: Ensure credentials for the required service_id are configured using 'agentvault config set'.")
        except av_exceptions.A2AConnectionError as e:
            print(f"Connection error: {e}")
        except av_exceptions.A2ARemoteAgentError as e:
            print(f"Agent returned an error: {e.status_code} - {e}")
            print(f"  Response Body: {e.response_body}")
        except av_exceptions.A2AError as e:
            print(f"A2A protocol error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            logging.exception("Unexpected error details:")

    # Example usage (replace with a real agent reference)
    # asyncio.run(run_agent_task("http://localhost:8000/agent-card.json", "Tell me a joke."))
    ```

### Models (`agentvault.models`)

Pydantic models defining the data structures for Agent Cards and the A2A protocol. Refer to the source code docstrings or the [A2A Profile v0.2](../a2a_profile_v0.2.md) for details on specific models like `AgentCard`, `Message`, `Task`, `TaskState`, `A2AEvent`, etc.

### Exceptions (`agentvault.exceptions`)

Custom exceptions provide granular error handling. Key exceptions to catch include:

*   `AgentCardError`: Problems loading or validating the Agent Card.
*   `A2AAuthenticationError`: Missing or invalid credentials, OAuth flow failures.
*   `A2AConnectionError`: Network issues connecting to the agent or token endpoint.
*   `A2ATimeoutError`: Request timed out.
*   `A2ARemoteAgentError`: The agent returned a non-2xx HTTP status or a JSON-RPC error object. Access `e.status_code` and `e.response_body`.
*   `A2AMessageError`: Invalid JSON-RPC format, unexpected response structure.
*   `KeyManagementError`: Issues saving/loading keys with `KeyManager`.

### Utilities (`agentvault.agent_card_utils`, `agentvault.mcp_utils`)

*   **`agent_card_utils`**: Functions like `load_agent_card_from_file` and `fetch_agent_card_from_url` simplify obtaining and validating `AgentCard` objects.
*   **`mcp_utils`**:
    *   `format_mcp_context`: (Primarily for server-side or advanced clients) Validates and formats a dictionary intended as MCP context.
    *   `get_mcp_context`: (Client-side) Safely extracts the `mcp_context` dictionary from a received `Message`'s metadata.
