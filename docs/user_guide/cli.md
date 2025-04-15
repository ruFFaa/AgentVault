# User Guide: AgentVault CLI (`agentvault_cli`)

The `agentvault_cli` is your command-line tool for interacting with the AgentVault ecosystem. It allows you to manage credentials for accessing agents, discover agents registered in the central registry, and execute tasks on remote A2A-compliant agents.

## Installation

Please refer to the main [Installation Guide](../installation.md) for instructions on installing the CLI using `pip`.

## Core Commands

The CLI is structured around several main commands. Get an overview by running:

```bash
agentvault_cli --help
```

### `config`

Manage local API keys and OAuth credentials required to authenticate with different agents or services. Credentials can be stored securely in the OS keyring or referenced via environment variables or files.

**Usage:**

```bash
agentvault_cli config --help
```

This command group helps you configure how the `agentvault_cli run` command (and underlying library) finds the necessary secrets to talk to different agents.

**Key Subcommands:**

*   **`set <service_id> [OPTIONS]`**:
    *   **Purpose:** Configure how credentials for a specific service (identified by `<service_id>`) are sourced or stored. The `<service_id>` is a name *you* choose locally (e.g., `openai`, `my-custom-agent-key`, `google-oauth-agent`) that the `KeyManager` uses to find the right secret. It often corresponds to the `service_identifier` in an Agent Card's `authSchemes`, but can be different.
    *   **Options:**
        *   `--env`: **Guidance Only.** Prints instructions on how to set environment variables (`AGENTVAULT_KEY_<SERVICE_ID_UPPER>`, `AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_ID`, `AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_SECRET`). It does *not* store anything itself.
        *   `--file <path>`: **Guidance Only.** Prints instructions on how to format a `.env` or `.json` file to store credentials that the `KeyManager` could potentially load (if configured during library initialization, which the CLI doesn't do by default).
        *   `--keyring`: **Stores API Key.** Securely prompts for an API key and stores it in your operating system's default keyring, associated with the `<service_id>`. **This is the recommended secure method for storing API keys via the CLI.**
        *   `--oauth-configure`: **Stores OAuth Credentials.** Securely prompts for an OAuth 2.0 Client ID and Client Secret and stores them in the OS keyring, associated with the `<service_id>`. Required for agents using the `oauth2` authentication scheme.

    *Example (Store OpenAI API Key securely):*
    ```bash
    # Use 'openai' as the local service_id
    agentvault_cli config set openai --keyring
    # --> Enter API key: ************
    # --> Confirm API key: ************
    # SUCCESS: API key for 'openai' stored successfully in keyring.
    ```
    *Example (Configure OAuth for a Google agent):*
    ```bash
    # Use 'google-agent-oauth' as the local service_id
    agentvault_cli config set google-agent-oauth --oauth-configure
    # --> Enter OAuth Client ID for 'google-agent-oauth': <paste_client_id>
    # --> Enter OAuth Client Secret for 'google-agent-oauth': ************
    # --> Confirm OAuth Client Secret for 'google-agent-oauth': ************
    # SUCCESS: OAuth credentials for 'google-agent-oauth' stored successfully in keyring.
    ```
    *Example (Guidance for Environment Variables):*
    ```bash
    agentvault_cli config set anthropic --env
    # --> Guidance: To use environment variables for 'anthropic':
    # -->   For API Key: Set AGENTVAULT_KEY_ANTHROPIC=<your_api_key>
    # -->   ... (OAuth guidance also shown) ...
    ```

*   **`get <service_id> [OPTIONS]`**:
    *   **Purpose:** Checks how credentials for a given `<service_id>` are currently being sourced by the `KeyManager` (Environment, File, Keyring). It checks the cache first, then attempts to load from the keyring if enabled.
    *   **Options:**
        *   `--show-key`: Displays the first few characters of the found API key (use with caution).
        *   `--show-oauth-id`: Displays the configured OAuth Client ID if found.
    *Example:*
    ```bash
    agentvault_cli config get openai
    # --> Credential status for service 'openai':
    # -->   API Key: Found (Source: KEYRING)
    # -->     (Use --show-key to display a masked version)
    # -->   OAuth Credentials: Not Configured

    agentvault_cli config get google-agent-oauth --show-oauth-id
    # --> Credential status for service 'google-agent-oauth':
    # -->   API Key: Not Found
    # -->   OAuth Credentials: Configured (Source: KEYRING)
    # -->     Client ID: 12345-abcde.apps.googleusercontent.com
    ```

*   **`list`**:
    *   **Purpose:** Shows a summary of services for which credentials have been detected *during initialization* from **environment variables** or specified **key files** (if the underlying library was configured with a key file path, which the default CLI is not).
    *   **Note:** This command **does not actively scan the OS keyring**. Keys stored *only* in the keyring will typically not appear in this list unless they were accessed previously by a `get` command in the same CLI invocation.

### `discover`

Search for agents registered in the central AgentVault Registry.

**Usage:**

```bash
agentvault_cli discover --help
agentvault_cli discover [SEARCH_QUERY] [OPTIONS]
```

*   **`[SEARCH_QUERY]` (Optional):** Text to search for (case-insensitive) in agent names or descriptions.
*   **`--registry <url>`:** Specify the URL of the AgentVault Registry API.
    *   Defaults to the value of the `AGENTVAULT_REGISTRY_URL` environment variable if set.
    *   If the environment variable is not set, it defaults to the public registry: `https://agentvault-registry-api.onrender.com`.
    *   *(Note: The public registry runs on a free tier and may take up to 60 seconds to wake up on the first request.)*
*   **`--limit <n>`:** Maximum results per page (default: 25, max: 250).
*   **`--offset <n>`:** Number of results to skip (for pagination, default: 0).
*   **`--tags <tag>` (Repeatable):** Filter by tags. Only agents possessing *all* specified tags will be returned (e.g., `--tags weather --tags forecast`).
*   **`--has-tee [true|false]` (Optional):** Filter agents based on whether they declare TEE support in their Agent Card.
*   **`--tee-type <type>` (Optional):** Filter agents by the specific TEE type declared (e.g., `AWS Nitro Enclaves`, `Intel SGX`).

*Example:*
```bash
# List first 10 agents containing "weather" from the public registry
agentvault_cli discover weather --limit 10

# List agents tagged with "nlp" from a local registry
agentvault_cli discover --tags nlp --registry http://localhost:8000

# Find agents declaring TEE support on the public registry
agentvault_cli discover --has-tee true
```

The output is displayed in a table format.

### `run`

Execute a task on a specific remote agent using the A2A protocol.

**Usage:**

```bash
agentvault_cli run --help
agentvault_cli run --agent <agent_ref> --input <input_data> [OPTIONS]
```

*   **`--agent <agent_ref>` / `-a <agent_ref>` (Required):** Identifies the target agent. This is crucial. It can be:
    *   An **Agent ID** from the registry (e.g., `examples/simple-agent`, `my-org/my-agent`). The CLI will use the `--registry` URL to fetch the corresponding Agent Card.
    *   A direct **URL** to the agent's `agent-card.json` (e.g., `http://localhost:8001/agent-card.json`).
    *   A local **file path** to the agent's `agent-card.json` (e.g., `../examples/basic_a2a_server/agent-card.json`).
*   **`--input <input_data>` / `-i <input_data>` (Required):** The input text for the agent's task.
    *   To read input from a file, prefix the path with `@`. Example: `--input @./prompts/my_request.txt`.
*   **`--context-file <path>`:** Path to a local JSON file containing MCP context data to send with the initial message.
*   **`--registry <url>`:** Registry URL (only used if `<agent_ref>` is an Agent ID). Defaults to `AGENTVAULT_REGISTRY_URL` env var or the public registry `https://agentvault-registry-api.onrender.com`. *(Note the cold start delay for the public instance).*
*   **`--key-service <service_id>`:** **Important for Authentication.** If the agent requires authentication (e.g., `apiKey` or `oauth2`) and its Agent Card doesn't specify a `service_identifier`, or if you want to use credentials stored under a different local name, use this flag to tell the `KeyManager` which local service ID to use for lookup. Example: `--key-service openai`.
*   **`--auth-key <key>`:** **INSECURE - FOR TESTING ONLY.** Directly provide the API key on the command line. This bypasses the `KeyManager` lookup for agents using the `apiKey` scheme. Avoid using this for sensitive keys.
*   **`--output-artifacts <directory>`:** If provided, artifact content larger than 1KB received via SSE will be saved to files in this directory (named using artifact ID and inferred extension) instead of being printed (truncated) to the console.

*Example (Running the basic SDK example agent locally):*
```bash
# Assumes the basic_a2a_server example is running on port 8000
agentvault_cli run --agent http://localhost:8000/agent-card.json --input "Hello Agent!"
```

*Example (Running an agent from the public registry requiring an OpenAI key):*
```bash
# First, ensure the key is configured:
# agentvault config set openai --keyring (and enter key)

# Then run the task (assuming agent 'some-org/openai-agent' uses 'openai' service ID)
# The --registry flag is omitted, so it uses the default public registry
agentvault_cli run --agent some-org/openai-agent --input "Summarize the concept of AI agents."

# Or, if the agent card didn't specify 'openai' as service_identifier:
agentvault_cli run --agent some-org/openai-agent --input "Summarize..." --key-service openai
```

The `run` command connects to the agent and streams Server-Sent Events (SSE) back to your terminal, showing status updates, messages from the agent/tools, and artifact information using `rich` formatting for better readability.

## Usage Tips

*(Same as before - Shell History, fzf + awk)*

### Re-running `run` Commands

The `agentvault_cli run` command can sometimes involve long agent identifiers or input strings. To easily recall and reuse previous commands:

*   **Shell History Search (Ctrl+R):** Most shells allow you to search your command history interactively. Press `Ctrl+R` and start typing parts of the command you want to find (e.g., `run`, the agent ID, part of the input).
*   **`history` Command:** Use `history | grep agentvault_cli run` (or similar filter) to list previous run commands. You can then execute a specific command number (e.g., `!123`).
*   **`fzf` (Fuzzy Finder):** If you have `fzf` installed, you can pipe your history to it for interactive fuzzy searching: `history | fzf`. Select the desired command and press Enter to execute it. This is very powerful for quickly finding complex commands.

### Interactive Agent Selection (`discover` + `fzf`)

If you have command-line tools like `fzf` (fuzzy finder) and `awk` installed, you can create powerful interactive workflows. For example, to discover agents, select one interactively, and then immediately run a task on it:

```bash
# Example: Discover agents matching "weather", select one, run with input
# Assumes default public registry or AGENTVAULT_REGISTRY_URL is set
agentvault_cli discover weather | fzf --height 40% --border --header "Select Agent:" | awk '{print $1}' | xargs -I {} agentvault_cli run --agent {} --input "What is the forecast for London?"
```

**Explanation:**

1.  `agentvault_cli discover weather`: Lists agents matching "weather" from the configured registry.
2.  `| fzf ...`: Pipes the list to `fzf` for interactive selection.
3.  `| awk '{print $1}'`: Extracts the first column (the Agent ID) from the line selected in `fzf`. *Note: You might need to adjust `$1` if the ID is in a different column based on your terminal width or `discover` output format.*
4.  `| xargs -I {} ...`: Takes the extracted ID (`{}`) and inserts it into the `agentvault_cli run` command.

This allows you to quickly find and use agents without manually copying and pasting IDs.
