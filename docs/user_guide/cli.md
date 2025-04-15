# User Guide: AgentVault CLI (`agentvault_cli`)

The `agentvault_cli` is your command-line tool for interacting with the AgentVault ecosystem. It allows you to manage credentials for accessing agents, discover agents registered in the central registry, and execute tasks on remote A2A-compliant agents.

## Installation

*(Link to main installation guide - coming soon)*

## Core Commands

The CLI is structured around several main commands:

```bash
agentvault_cli --help
```

This will show the main available command groups.

### `config`

Manage local API keys and OAuth credentials required to authenticate with different agents or services. Credentials can be stored securely in the OS keyring or referenced via environment variables or files.

**Usage:**

```bash
agentvault_cli config --help
agentvault_cli config set --help
agentvault_cli config get --help
agentvault_cli config list --help
```

**Key Subcommands:**

*   **`set <service_id> [OPTIONS]`**: Configure how credentials for a specific service are sourced or stored.
    *   `--env`: Provides guidance on setting API keys or OAuth credentials via environment variables (e.g., `AGENTVAULT_KEY_<SERVICE_ID>`, `AGENTVAULT_OAUTH_<SERVICE_ID>_CLIENT_ID`).
    *   `--file <path>`: Provides guidance on setting credentials within a specified file (supports `.env` and `.json` formats).
    *   `--keyring`: Prompts securely for an API key and stores it in the operating system's keyring associated with the `<service_id>`. This is the recommended method for storing keys directly via the CLI.
    *   `--oauth-configure`: Prompts securely for an OAuth 2.0 Client ID and Client Secret and stores them in the OS keyring. Required for agents using the `oauth2` authentication scheme.

    *Example (Store API Key securely):*
    ```bash
    agentvault_cli config set my-openai-service --keyring
    # Prompts for key input
    ```
    *Example (Configure OAuth):*
    ```bash
    agentvault_cli config set my-google-agent --oauth-configure
    # Prompts for Client ID and Client Secret
    ```

*   **`get <service_id> [OPTIONS]`**: Checks how credentials for a service are currently being sourced (Environment, File, Keyring).
    *   `--show-key`: Displays the first few characters of the found API key (use with caution).
    *   `--show-oauth-id`: Displays the configured OAuth Client ID if found.

    *Example:*
    ```bash
    agentvault_cli config get my-openai-service
    agentvault_cli config get my-google-agent --show-oauth-id
    ```

*   **`list`**: Shows a summary of services for which credentials have been detected from environment variables or specified key files during initialization. *Note: Does not actively scan the keyring.*

### `discover`

Search for agents registered in the central AgentVault Registry.

**Usage:**

```bash
agentvault_cli discover --help
agentvault_cli discover [SEARCH_QUERY] [OPTIONS]
```

*   **`[SEARCH_QUERY]` (Optional):** Text to search for in agent names or descriptions.
*   **`--registry <url>`:** Specify the URL of the AgentVault Registry (defaults to `http://localhost:8000` or `AGENTVAULT_REGISTRY_URL` env var).
*   **`--limit <n>`:** Maximum results per page (default: 25).
*   **`--offset <n>`:** Number of results to skip (for pagination).

*Example:*
```bash
# List first 10 agents containing "weather"
agentvault_cli discover weather --limit 10

# List next page of weather agents
agentvault_cli discover weather --limit 10 --offset 10
```

### `run`

Execute a task on a specific remote agent using the A2A protocol.

**Usage:**

```bash
agentvault_cli run --help
agentvault_cli run --agent <agent_ref> --input <input_data> [OPTIONS]
```

*   **`--agent <agent_ref>` / `-a <agent_ref>` (Required):** Identifies the target agent. Can be:
    *   An Agent ID from the registry (e.g., `my-org/my-agent`).
    *   A direct URL to the agent's `agent-card.json`.
    *   A local file path to the agent's `agent-card.json`.
*   **`--input <input_data>` / `-i <input_data>` (Required):** The input text for the agent. Prefix with `@` to read input from a file (e.g., `--input @prompt.txt`).
*   **`--context-file <path>`:** Path to a local JSON file containing MCP context data to send with the initial message.
*   **`--registry <url>`:** Registry URL (used if `<agent_ref>` is an ID).
*   **`--key-service <service_id>`:** Override the service ID used for looking up authentication credentials (useful if the Agent Card is ambiguous or missing a `service_identifier`).
*   **`--auth-key <key>`:** Directly provide the API key (INSECURE, for testing only). Overrides `KeyManager` lookup for `apiKey` schemes.
*   **`--output-artifacts <directory>`:** If provided, artifact content larger than 1KB received via SSE will be saved to files in this directory instead of being printed to the console.

*Example:*
```bash
# Run task on agent by ID with text input
agentvault_cli run --agent examples/simple-agent --input "Explain A2A."

# Run task using agent card URL and input from file, saving large artifacts
agentvault_cli run -a http://localhost:8000/agent-card.json -i @my_prompt.txt --output-artifacts ./task_outputs
```

The `run` command streams events (status changes, messages, artifacts) from the agent in real-time using Server-Sent Events (SSE).

## Usage Tips

### Re-running `run` Commands

The `agentvault_cli run` command can sometimes involve long agent identifiers or input strings. To easily recall and reuse previous commands:

*   **Shell History Search (Ctrl+R):** Most shells allow you to search your command history interactively. Press `Ctrl+R` and start typing parts of the command you want to find (e.g., `run`, the agent ID, part of the input).
*   **`history` Command:** Use `history | grep agentvault_cli run` (or similar filter) to list previous run commands. You can then execute a specific command number (e.g., `!123`).
*   **`fzf` (Fuzzy Finder):** If you have `fzf` installed, you can pipe your history to it for interactive fuzzy searching: `history | fzf`. Select the desired command and press Enter to execute it. This is very powerful for quickly finding complex commands.

### Interactive Agent Selection (`discover` + `fzf`)

If you have command-line tools like `fzf` (fuzzy finder) and `awk` installed, you can create powerful interactive workflows. For example, to discover agents, select one interactively, and then immediately run a task on it:

```bash
# Example: Discover agents matching "weather", select one, run with input
agentvault_cli discover weather | fzf --height 40% --border --header "Select Agent:" | awk '{print $1}' | xargs -I {} agentvault_cli run --agent {} --input "What is the forecast for London?"
```

**Explanation:**

1.  `agentvault_cli discover weather`: Lists agents matching "weather".
2.  `| fzf ...`: Pipes the list to `fzf` for interactive selection.
3.  `| awk '{print $1}'`: Extracts the first column (the Agent ID) from the line selected in `fzf`. *Note: You might need to adjust `$1` if the ID is in a different column based on your terminal width or `discover` output format.*
4.  `| xargs -I {} ...`: Takes the extracted ID (`{}`) and inserts it into the `agentvault_cli run` command.

This allows you to quickly find and use agents without manually copying and pasting IDs.
