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

### `KeyManager` (`key_manager.py`)

Handles secure loading, storage, and retrieval of credentials (API keys, OAuth 2.0 Client ID/Secret) needed for agent authentication.

*   **Purpose:** Abstracts credential sources so your client code doesn't need to handle each case explicitly. Provides a consistent interface (`get_key`, `get_oauth_client_id`, etc.) regardless of where the credential is stored.
*   **Initialization:**
    ```python
    from agentvault import KeyManager
    import pathlib

    # Recommended: Load from environment variables AND OS keyring (if available)
    # Keyring is checked only if the key isn't found in env vars first.
    km_env_keyring = KeyManager(use_keyring=True)

    # Load ONLY from a specific .env file (disable env vars and keyring)
    # key_file_path = pathlib.Path("path/to/your/keys.env")
    # km_file_only = KeyManager(key_file_path=key_file_path, use_env_vars=False, use_keyring=False)

    # Load from file AND environment (file takes priority over env)
    # key_file_path = pathlib.Path("path/to/your/keys.json")
    # km_file_env = KeyManager(key_file_path=key_file_path, use_env_vars=True, use_keyring=False)
    ```
*   **Priority Order:** When retrieving credentials, `KeyManager` checks sources in this order:
    1.  **File Cache:** If `key_file_path` was provided during init and the file contained the credential.
    2.  **Environment Variable Cache:** If `use_env_vars=True` (default) and the corresponding environment variable was set during init.
    3.  **OS Keyring:** If `use_keyring=True` and the credential was not found in the file or environment caches. This check happens *on demand* when a `get_...` method is called.
*   **Service Identifier (`service_id`):** This is the crucial string used to look up credentials. It's a *local* name you choose (e.g., "openai", "my-agent-key", "google-oauth-agent") that maps to the credentials needed for a specific agent or service.
    *   It often corresponds to the `authSchemes[].service_identifier` field in an Agent Card.
    *   If the Agent Card omits `service_identifier`, the client might default to using the agent's `humanReadableId` or require the user/developer to specify which local `service_id` to use (e.g., via `agentvault_cli run --key-service <your_local_id>`).
*   **Storage Conventions:**
    *   **Environment Variables:**
        *   API Key: `AGENTVAULT_KEY_<SERVICE_ID_UPPER>`
        *   OAuth Client ID: `AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_ID`
        *   OAuth Client Secret: `AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_SECRET`
    *   **`.env` File:**
        *   API Key: `<service_id_lower>=your_api_key`
        *   OAuth Client ID: `AGENTVAULT_OAUTH_<service_id_lower>_CLIENT_ID=your_client_id`
        *   OAuth Client Secret: `AGENTVAULT_OAUTH_<service_id_lower>_CLIENT_SECRET=your_client_secret`
    *   **`.json` File:**
        ```json
        {
          "service_id_lower": "your_api_key",
          "another_service": {
            "apiKey": "another_api_key",
            "oauth": {
              "clientId": "oauth_client_id",
              "clientSecret": "oauth_client_secret"
            }
          }
        }
        ```
    *   **OS Keyring:** Uses specific service/username conventions (see `key_manager.py` source for details, e.g., service=`agentvault:oauth:<norm_id>`, username=`clientId`). Use `agentvault_cli config set <service_id> --keyring` or `--oauth-configure` to store securely.
*   **Retrieving Credentials:**
    ```python
    km = KeyManager(use_keyring=True) # Example instance

    # Get API Key (returns None if not found)
    api_key = km.get_key("openai")
    if api_key:
        source = km.get_key_source("openai") # 'env', 'file', 'keyring', or None
        print(f"Found OpenAI API Key (Source: {source})")

    # Get OAuth Credentials (return None if not found or incomplete)
    client_id = km.get_oauth_client_id("google-oauth-agent")
    client_secret = km.get_oauth_client_secret("google-oauth-agent")
    if client_id and client_secret:
        status = km.get_oauth_config_status("google-oauth-agent")
        print(f"Found Google OAuth Credentials ({status})")
        print(f"  Client ID: {client_id}")
        # Note: AgentVaultClient uses these to automatically fetch the Bearer token.
    ```
*   **Storing Credentials (Primarily for CLI/Setup):**
    ```python
    from agentvault import KeyManagementError

    km = KeyManager(use_keyring=True)
    try:
        # Store API Key securely in OS keyring
        km.set_key_in_keyring("my-new-service", "sk-abc...")
        print("API Key stored successfully.")

        # Store OAuth creds securely in OS keyring
        km.set_oauth_creds_in_keyring("my-oauth-service", "client_id_123", "client_secret_xyz")
        print("OAuth credentials stored successfully.")

    except KeyManagementError as e:
        # Handle cases where keyring is unavailable or write fails
        print(f"Failed to store credentials in keyring: {e}")
    except ValueError as e:
        print(f"Invalid input for storing credentials: {e}")
    ```

### `AgentVaultClient` (`client.py`)

The primary class for making asynchronous A2A calls to remote agents.

*   **Purpose:** Handles HTTP requests (using `httpx`), authentication logic (including OAuth2 Client Credentials token fetching/caching), JSON-RPC formatting, SSE streaming, and response parsing according to the [A2A Profile v0.2](../a2a_profile_v0.2.md).
*   **Usage:** Best used as an async context manager (`async with`) to ensure the underlying HTTP client is properly closed. Requires an `AgentCard` instance (loaded via `agent_card_utils`) and a `KeyManager` instance for authentication.

    ```python
    import asyncio
    import logging
    import pathlib
    from agentvault import (
        AgentVaultClient, KeyManager, Message, TextPart,
        agent_card_utils, exceptions as av_exceptions, models as av_models
    )

    # Configure logging for visibility
    logging.basicConfig(level=logging.INFO)

    async def run_agent_task(agent_ref: str, input_text: str):
        # Initialize KeyManager - typically done once per application
        key_manager = KeyManager(use_keyring=True)
        agent_card = None
        task_id = None

        try:
            # --- 1. Load Agent Card ---
            print(f"Loading agent card: {agent_ref}")
            # (Simplified loading logic - see previous version for URL/File/ID handling)
            agent_card = await agent_card_utils.fetch_agent_card_from_url(agent_ref) # Example URL load

            if not agent_card:
                 print(f"Error: Could not load agent card for {agent_ref}")
                 return
            print(f"Loaded Agent: {agent_card.name}")

            # --- 2. Prepare Initial Message ---
            initial_message = Message(role="user", parts=[TextPart(content=input_text)])
            mcp_data = {"user_preference": "verbose"} # Optional MCP context

            # --- 3. Interact using AgentVaultClient ---
            async with AgentVaultClient() as client:
                # Initiate the task
                # AgentVaultClient automatically handles authentication (apiKey or oauth2)
                # based on agent_card.authSchemes and credentials from key_manager.
                print(f"Initiating task...")
                task_id = await client.initiate_task(
                    agent_card=agent_card,
                    initial_message=initial_message,
                    key_manager=key_manager,
                    mcp_context=mcp_data,
                )
                print(f"Task initiated: {task_id}")

                # Stream and process events
                print("Streaming events...")
                final_response_text = ""
                async for event in client.receive_messages(
                    agent_card=agent_card, task_id=task_id, key_manager=key_manager
                ):
                    if isinstance(event, av_models.TaskStatusUpdateEvent):
                        print(f"  Status Update: {event.state} "
                              f"(Msg: {event.message or 'N/A'})")
                        if event.state in [av_models.TaskState.COMPLETED,
                                           av_models.TaskState.FAILED,
                                           av_models.TaskState.CANCELED]:
                            print("  Terminal state reached.")
                            break
                    elif isinstance(event, av_models.TaskMessageEvent):
                        print(f"  Message Received (Role: {event.message.role}):")
                        for part in event.message.parts:
                            if isinstance(part, TextPart):
                                print(f"    Text: {part.content}")
                                if event.message.role == "assistant":
                                    final_response_text += part.content + "\n"
                            # --- ADDED: Example handling other part types ---
                            elif isinstance(part, av_models.FilePart):
                                print(f"    File Ref: {part.url} (Type: {part.media_type}, Name: {part.filename})")
                            elif isinstance(part, av_models.DataPart):
                                print(f"    Data (Type: {part.media_type}): {part.content}")
                            # --- END ADDED ---
                            else:
                                print(f"    Part (Type: {getattr(part, 'type', 'Unknown')}): {part}")
                    elif isinstance(event, av_models.TaskArtifactUpdateEvent):
                         artifact = event.artifact
                         print(f"  Artifact Update (ID: {artifact.id}, Type: {artifact.type}):")
                         if artifact.url: print(f"    URL: {artifact.url}")
                         if artifact.media_type: print(f"    Media Type: {artifact.media_type}")
                         # Handle content display/saving based on size/type
                         if artifact.content:
                             content_repr = repr(artifact.content)
                             print(f"    Content: {content_repr[:100]}{'...' if len(content_repr) > 100 else ''}")
                         else:
                             print("    Content: [Not provided directly]")
                    # --- ADDED: Handling potential error events within stream ---
                    # Note: A2ARemoteAgentError might also be raised by receive_messages
                    # if the stream itself returns an error status initially.
                    elif isinstance(event, dict) and event.get("error"): # Check for error structure
                         print(f"  ERROR received via SSE stream: {event}")
                         # Decide how to handle stream errors (e.g., break, log, append to response)
                         final_response_text += f"\n[Stream Error: {event.get('message', 'Unknown')}]"
                         break # Example: Stop processing on stream error
                    # --- END ADDED ---
                    else:
                        print(f"  Received unknown event type: {type(event)}")

                print("\n--- Final Aggregated Agent Response ---")
                print(final_response_text.strip())
                print("---------------------------------------")

        # --- 5. Handle Potential Errors ---
        except av_exceptions.AgentCardError as e:
            print(f"Error loading or validating agent card: {e}")
        except av_exceptions.A2AAuthenticationError as e:
            print(f"Authentication error: {e}")
            print("Hint: Ensure credentials for the required service_id are configured.")
        except av_exceptions.A2AConnectionError as e:
            print(f"Connection error communicating with agent or token endpoint: {e}")
        except av_exceptions.A2ARemoteAgentError as e:
            # Agent returned an error (e.g., JSON-RPC error or non-2xx HTTP status)
            print(f"Agent returned an error:")
            print(f"  Status Code (if HTTP/RPC error): {e.status_code}") # Can be HTTP status or RPC code
            print(f"  Message: {e}")
            print(f"  Response Body/Data: {e.response_body}") # Contains JSON RPC error data or HTTP body
        except av_exceptions.A2AMessageError as e:
             print(f"A2A protocol message error (e.g., invalid format): {e}")
        except av_exceptions.A2ATimeoutError as e:
             print(f"A2A request timed out: {e}")
        except av_exceptions.KeyManagementError as e:
             print(f"Error managing local keys/credentials: {e}")
        except NotImplementedError as e:
             print(f"Functionality not implemented: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {type(e).__name__}: {e}")
            logging.exception("Unexpected error details:")

    # Example usage:
    # asyncio.run(run_agent_task("https://some-agent.com/agent-card.json", "Summarize this document."))
    ```

### Models (`agentvault.models`)

Pydantic models defining the data structures for Agent Cards and the A2A protocol. Refer to the source code docstrings or the [A2A Profile v0.2](../a2a_profile_v0.2.md) for details on specific models like `AgentCard`, `Message`, `Task`, `TaskState`, `A2AEvent`, etc.

### Exceptions (`agentvault.exceptions`)

Custom exceptions provide granular error handling. Catching these allows for more robust client applications.

*   **`AgentCardError`**: Issues loading/validating the Agent Card.
*   **`A2AAuthenticationError`**: Missing/invalid credentials, OAuth flow failures. Check KeyManager setup.
*   **`A2AConnectionError`**: Network issues connecting to the agent or token endpoint (DNS, connection refused).
*   **`A2ATimeoutError`**: Request timed out.
*   **`A2ARemoteAgentError`**: The agent returned an error. Check `e.status_code` (can be HTTP status or JSON-RPC error code) and `e.response_body` (can be HTTP response text or JSON-RPC error data) for details from the agent.
*   **`A2AMessageError`**: Invalid JSON-RPC format or unexpected response structure from the agent.
*   **`KeyManagementError`**: Issues saving/loading keys with `KeyManager`.

See the example above for a basic `try...except` block structure.

### Utilities (`agentvault.agent_card_utils`, `agentvault.mcp_utils`)

*   **`agent_card_utils`**: Functions like `load_agent_card_from_file` and `fetch_agent_card_from_url` simplify obtaining and validating `AgentCard` objects.
*   **`mcp_utils`**: Contains helpers for handling Model Context Protocol data.
    *   `format_mcp_context`: (Primarily for advanced clients or server-side) Validates and formats a dictionary intended as MCP context.
    *   `get_mcp_context`: (Client-side) Safely extracts the `mcp_context` dictionary from a received `Message`'s metadata.
