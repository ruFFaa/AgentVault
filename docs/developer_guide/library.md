# Developer Guide: Client Library (`agentvault`)

The `agentvault` library is the core Python package for interacting with the AgentVault ecosystem from the client-side. It enables applications, scripts, or even other agents to discover A2A agents, manage credentials securely, and communicate using the A2A protocol.

## Key Components

### `AgentVaultClient`

The primary class for making A2A calls to remote agents.

*   **Purpose:** Handles the underlying HTTP requests (POST for JSON-RPC methods, streaming GET/POST for SSE), authentication header injection, and response/event parsing.
*   **Protocol:** Implements the AgentVault A2A Profile (based on JSON-RPC 2.0 over HTTP POST, Server-Sent Events for streaming). See [A2A Profile v0.2](../a2a_profile_v0.2.md).
*   **Usage:** Designed to be used as an async context manager (`async with AgentVaultClient() as client:`).
*   **Authentication:** Relies on an instance of `KeyManager` passed to its methods to retrieve necessary credentials (API Keys or OAuth tokens) based on the target agent's `AgentCard`.
*   **Main Methods:**
    *   `async initiate_task(agent_card, initial_message, key_manager, mcp_context=None, webhook_url=None) -> str`: Starts a new task or sends the first message to an existing one. Returns the `task_id`. Optionally includes MCP context or a webhook URL for push notifications.
    *   `async send_message(agent_card, task_id, message, key_manager, mcp_context=None) -> bool`: Sends a subsequent message to an ongoing task.
    *   `async get_task_status(agent_card, task_id, key_manager) -> Task`: Retrieves the current state, messages, and artifacts for a task.
    *   `async terminate_task(agent_card, task_id, key_manager) -> bool`: Requests cancellation of an ongoing task.
    *   `async receive_messages(agent_card, task_id, key_manager) -> AsyncGenerator[A2AEvent, None]`: Subscribes to Server-Sent Events for a task, yielding `A2AEvent` objects (like `TaskStatusUpdateEvent`, `TaskMessageEvent`) as they arrive.

### `KeyManager`

Handles secure loading, storage, and retrieval of credentials needed for agent authentication.

*   **Purpose:** Abstracts away the source of credentials, allowing users/applications to configure keys via environment variables, files, or the OS keyring without changing the client code using the `KeyManager`.
*   **Priority:** File > Environment Variables > OS Keyring (Keyring is only checked if enabled and needed).
*   **Sources & Conventions:**
    *   **Environment Variables:**
        *   API Key: `AGENTVAULT_KEY_<SERVICE_ID_UPPER>`
        *   OAuth Client ID: `AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_ID`
        *   OAuth Client Secret: `AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_SECRET`
    *   **File (`.env` format):**
        *   API Key: `<service_id_lower>=...`
        *   OAuth Client ID: `AGENTVAULT_OAUTH_<service_id_lower>_CLIENT_ID=...`
        *   OAuth Client Secret: `AGENTVAULT_OAUTH_<service_id_lower>_CLIENT_SECRET=...`
    *   **File (`.json` format):**
        ```json
        {
          "service_id_lower": "api_key_value",
          "another_service": {
            "apiKey": "...",
            "oauth": {
              "clientId": "...",
              "clientSecret": "..."
            }
          }
        }
        ```
    *   **OS Keyring (requires `pip install agentvault[os_keyring]`):**
        *   API Key: Service=`agentvault:<norm_id>`, Username=`<norm_id>`
        *   OAuth Client ID: Service=`agentvault:oauth:<norm_id>`, Username=`clientId`
        *   OAuth Client Secret: Service=`agentvault:oauth:<norm_id>`, Username=`clientSecret`
*   **Key Methods:**
    *   `__init__(key_file_path=None, use_env_vars=True, use_keyring=False, ...)`: Initializes and loads from file/env.
    *   `get_key(service_id: str) -> Optional[str]`: Retrieves API key.
    *   `get_oauth_client_id(service_id: str) -> Optional[str]`: Retrieves OAuth Client ID.
    *   `get_oauth_client_secret(service_id: str) -> Optional[str]`: Retrieves OAuth Client Secret.
    *   `get_key_source(service_id: str) -> Optional[str]`: Returns where the API key was loaded from ('env', 'file', 'keyring').
    *   `get_oauth_config_status(service_id: str) -> str`: Returns status like "Configured (Source: KEYRING)".
    *   `set_key_in_keyring(service_id: str, key_value: str)`: Stores API key securely.
    *   `set_oauth_creds_in_keyring(service_id: str, client_id: str, client_secret: str)`: Stores OAuth credentials securely.

### Models (`agentvault.models`)

Pydantic models defining the data structures used throughout the library.

*   **Agent Card Models:** `AgentCard`, `AgentProvider`, `AgentCapabilities`, `AgentAuthentication`, `AgentSkill`, `TeeDetails`. These define the structure of `agent-card.json`.
*   **A2A Protocol Models:** `Message`, `Part` (Union of `TextPart`, `FilePart`, `DataPart`), `Artifact`, `Task`, `TaskState` (Enum), `A2AEvent` (Union type for SSE), `TaskStatusUpdateEvent`, `TaskMessageEvent`, `TaskArtifactUpdateEvent`, and various request/response parameter/result models (`TaskSendParams`, `TaskSendResult`, etc.).

### Exceptions (`agentvault.exceptions`)

Custom exception hierarchy for handling errors specific to the library.

*   `AgentVaultError` (Base exception)
*   `AgentCardError`: Base for card-related errors.
    *   `AgentCardValidationError`: Pydantic validation failed.
    *   `AgentCardFetchError`: Network/HTTP error fetching card.
*   `A2AError`: Base for A2A protocol errors.
    *   `A2AConnectionError`: Network issues connecting to agent.
    *   `A2AAuthenticationError`: Authentication failed (missing key, invalid key/token, OAuth flow error).
    *   `A2ARemoteAgentError`: Agent returned a JSON-RPC error or non-2xx HTTP status.
    *   `A2ATimeoutError`: Operation timed out.
    *   `A2AMessageError`: Invalid message format, unexpected response structure, JSON parsing error.
*   `KeyManagementError`: Errors related to loading or storing credentials via `KeyManager`.

### Utilities

*   **`agentvault.agent_card_utils`**:
    *   `parse_agent_card_from_dict(data: dict) -> AgentCard`: Parses and validates data.
    *   `load_agent_card_from_file(file_path: Path) -> AgentCard`: Loads and validates from JSON file.
    *   `async fetch_agent_card_from_url(url: str) -> AgentCard`: Fetches and validates from URL.
*   **`agentvault.mcp_utils`**:
    *   `get_mcp_context(message: Message) -> Optional[Dict]`: Safely extracts MCP context from message metadata (client-side).
    *   `format_mcp_context(context_data: Dict) -> Optional[Dict]`: Validates and formats MCP context data for embedding (server-side/client-side).
