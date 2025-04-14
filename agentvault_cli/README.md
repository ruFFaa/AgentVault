# AgentVault CLI

The `agentvault_cli` provides a command-line interface for interacting with the AgentVault ecosystem. You can manage local credentials, discover agents in the registry, and run tasks on remote A2A agents.

## Installation

*(Instructions to be added later once packaging is finalized)*

## Usage

The main commands are:

*   `agentvault_cli config`: Manage local API keys and OAuth credentials.
*   `agentvault_cli discover`: Find agents listed in the AgentVault Registry.
*   `agentvault_cli run`: Execute tasks on remote A2A agents.

Use `--help` with any command for more details (e.g., `agentvault_cli run --help`).

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
