# AgentVault Server SDK - OAuth2 Agent Example

This example demonstrates how to build an A2A agent that requires OAuth2 Client Credentials authentication using the `agentvault-server-sdk` and FastAPI.

## Components

*   **`.env.example`**: Example environment variables for setting the mock Client ID and Secret the *server* will accept.
*   **`agent-card.json`**: Describes the agent, specifying the `oauth2` auth scheme and the `/token` endpoint URL.
*   **`requirements.txt`**: Python dependencies (`fastapi`, `uvicorn`, `agentvault-server-sdk`, `python-dotenv`).
*   **`src/oauth_agent_example/agent.py`**: Defines the simple `OAuthProtectedAgent` logic.
*   **`src/oauth_agent_example/main.py`**:
    *   Sets up the FastAPI application.
    *   Includes the SDK's A2A router at `/a2a`.
    *   **Adds a custom `POST /token` endpoint** to handle the OAuth2 Client Credentials grant flow, validating against environment variables.
    *   **Adds a FastAPI dependency (`verify_token`)** using `HTTPBearer` to protect the `/a2a` router, ensuring requests have a valid mock Bearer token obtained from `/token`.
    *   Includes the required SDK exception handlers.

## Setup

1.  **Navigate:** Open your terminal in this directory (`examples/oauth_agent_example`).
2.  **Install Dependencies:** Create and activate a virtual environment, then install the requirements.
    ```bash
    # Create venv (optional, recommended)
    # python -m venv .venv
    # source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate    # On Windows

    pip install -r requirements.txt
    ```
    *Note:* This installs the SDK and core library from your local source tree.
3.  **Configure Server Credentials:**
    *   Copy `.env.example` to `.env`.
    *   Review the `MOCK_CLIENT_ID` and `MOCK_CLIENT_SECRET` in `.env`. These are the credentials the *server* will expect the *client* to provide to the `/token` endpoint. You can change them if desired.

## Running the Server

Start the FastAPI server using Uvicorn. It will load the credentials from the `.env` file.

```bash
uvicorn src.oauth_agent_example.main:app --reload --port 8002
```
*   `--reload`: Enables auto-reloading for development.
*   `--port 8002`: Specifies the port (matches `agent-card.json`).

The server should start, hosting the `/a2a` endpoint and the `/token` endpoint.

## Configuring Client Credentials

Before you can interact with this agent using `agentvault_cli`, you need to configure the *client-side* credentials that match the ones the server expects.

1.  **Open a NEW terminal window/tab** (keep the server running).
2.  **Activate the AgentVault virtual environment** if you haven't already (`source .venv/bin/activate` or similar).
3.  **Use `agentvault config set`:** Use the `service_identifier` from `agent-card.json` (`example-oauth-agent`) and the `--oauth-configure` flag. Enter the **same Client ID and Secret** that are defined in the server's `.env` file when prompted.

    ```bash
    agentvault config set example-oauth-agent --oauth-configure
    # --> Enter OAuth Client ID for 'example-oauth-agent': test-client-id-123
    # --> Enter OAuth Client Secret for 'example-oauth-agent': ************************
    # --> Confirm OAuth Client Secret for 'example-oauth-agent': ************************
    # SUCCESS: OAuth credentials for 'example-oauth-agent' stored successfully in keyring.
    ```

## Testing with AgentVault CLI

Now that the server is running and client credentials are configured, you can test the interaction:

```bash
agentvault run --agent http://localhost:8002/agent-card.json --input "Test OAuth Auth"
```

**Expected Behavior:**

1.  The `agentvault` client library (used by the CLI) will load the agent card.
2.  It sees the `oauth2` scheme and the `tokenUrl`.
3.  It uses the `KeyManager` to retrieve the Client ID/Secret you configured for `example-oauth-agent`.
4.  It makes a `POST` request to `http://localhost:8002/token` with the credentials.
5.  The server's `/token` endpoint validates the credentials against the `.env` file and returns a mock access token.
6.  The client library receives the token.
7.  It makes the `POST` request to `http://localhost:8002/a2a` for the `tasks/send` method, including the `Authorization: Bearer <mock_access_token>` header.
8.  The server's `verify_token` dependency validates the token.
9.  The SDK router calls the agent's `handle_task_send` method.
10. The agent starts the task and sends back SSE events confirming authentication worked.

You should see output similar to the Basic Echo example, but the underlying process involves the OAuth token exchange. If authentication fails (e.g., wrong client credentials configured), the `run` command will report an authentication error.
