import typer
import subprocess
import logging
import sys
import os
import shutil
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any # Added Dict, Any

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="find-run-task",
    help="Discovers agents using agentvault_cli, lets user select one via fzf, then runs a task on the selected agent.",
    add_completion=False
)

# --- Helper Functions ---

def _find_executable(name: str, provided_path: Optional[str]) -> Optional[str]:
    """Finds an executable in PATH or uses the provided path."""
    if provided_path:
        if Path(provided_path).is_file():
            return provided_path
        else:
            logger.warning(f"Provided path for '{name}' not found: {provided_path}")
    found_path = shutil.which(name)
    if found_path:
        return found_path
    logger.error(f"Executable '{name}' not found in PATH and no valid path provided.")
    return None

def _parse_discover_output(fzf_output_line: str) -> Optional[str]:
    """
    Parses a line from the fzf selection (expected to be table output)
    to extract the Agent ID (assumed to be the first column).
    """
    if not fzf_output_line: return None
    parts = [part for part in fzf_output_line.strip().split() if part]
    if parts:
        agent_id = parts[0]
        logger.info(f"Extracted Agent ID: {agent_id}")
        return agent_id
    else:
        logger.warning(f"Could not parse Agent ID from fzf output line: '{fzf_output_line}'")
        return None

# --- ADDED: Subprocess Helper Functions ---
def _run_discover_pipe_fzf(discover_cmd: List[str], fzf_cmd: List[str]) -> Tuple[Optional[str], int]:
    """Runs discover, pipes to fzf, returns selected line and fzf return code."""
    selected_line: Optional[str] = None
    fzf_returncode = -1
    try:
        logger.debug(f"Running discover cmd for fzf pipe: {' '.join(discover_cmd)}")
        discover_proc = subprocess.Popen(discover_cmd, stdout=subprocess.PIPE, text=True, encoding='utf-8')
        logger.debug(f"Running fzf cmd: {' '.join(fzf_cmd)}")
        fzf_proc = subprocess.Popen(fzf_cmd, stdin=discover_proc.stdout, stdout=subprocess.PIPE, text=True, encoding='utf-8')

        # Allow discover_proc stdout to be read by fzf_proc
        if discover_proc.stdout:
            discover_proc.stdout.close()

        fzf_stdout, fzf_stderr = fzf_proc.communicate()
        fzf_returncode = fzf_proc.returncode

        if fzf_returncode == 0 and fzf_stdout:
            selected_line = fzf_stdout.strip()
        elif fzf_stderr:
             logger.warning(f"fzf stderr: {fzf_stderr.strip()}")

    except FileNotFoundError as e:
        typer.secho(f"Error running command: {e}. Check command paths.", fg=typer.colors.RED)
        raise # Re-raise to be caught by main handler
    except Exception as e:
        typer.secho(f"An error occurred during discovery or selection pipeline: {e}", fg=typer.colors.RED)
        logger.exception("Discovery/fzf pipeline failed.")
        raise # Re-raise
    finally:
        # Ensure discover process terminates if fzf finishes early
        if 'discover_proc' in locals() and discover_proc.poll() is None:
            discover_proc.terminate()
            discover_proc.wait()

    return selected_line, fzf_returncode

def _run_config_get(config_cmd: List[str]) -> Tuple[int, str, str]:
    """Runs the config get command and returns status, stdout, stderr."""
    try:
        result = subprocess.run(config_cmd, capture_output=True, text=True, encoding='utf-8')
        logger.debug(f"Config check stdout:\n{result.stdout}")
        logger.debug(f"Config check stderr:\n{result.stderr}")
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        logger.warning(f"Failed to run config check command {' '.join(config_cmd)}: {e}")
        return -1, "", str(e) # Indicate failure with negative code

def _run_agent_task(run_cmd: List[str]) -> int:
    """Runs the agent task command, streaming output."""
    typer.echo("\nExecuting task:")
    typer.echo(f"$ {' '.join(run_cmd)}")
    typer.echo("-" * 20)
    try:
        # Run and allow output to stream directly, check=False to handle agent errors
        process = subprocess.run(run_cmd, check=False, text=True, encoding='utf-8')
        typer.echo("-" * 20)
        return process.returncode
    except FileNotFoundError as e:
         typer.secho(f"Error: Could not execute '{run_cmd[0]} run'. Is the CLI installed correctly?", fg=typer.colors.RED)
         return -1 # Indicate file not found error
    except Exception as e:
        typer.secho(f"An unexpected error occurred while running the task: {e}", fg=typer.colors.RED)
        logger.exception("Task execution failed.")
        return -1 # Indicate other error
# --- END ADDED ---


@app.command()
def main(
    search_term: str = typer.Argument(..., help="The term to use for discovering agents via 'agentvault_cli discover'."),
    input_prompt: Optional[str] = typer.Argument(None, help="The input prompt text to send to the selected agent. Mutually exclusive with --input-file."),
    input_file: Optional[Path] = typer.Option(None, "--input-file", "-i", help="Path to a file containing the input prompt. Mutually exclusive with input_prompt argument.", exists=True, file_okay=True, dir_okay=False, readable=True),
    key_service: Optional[str] = typer.Option(None, "--key-service", "-k", help="The service_id for KeyManager lookup if the agent requires authentication."),
    registry_url: Optional[str] = typer.Option(os.environ.get("AGENTVAULT_REGISTRY_URL"), "--registry", "-r", help="URL of the AgentVault Registry (uses AGENTVAULT_REGISTRY_URL env var if not specified)."),
    fzf_path: Optional[str] = typer.Option(None, "--fzf-path", help="Path to the fzf executable if not in system PATH."),
    cli_cmd_list: Optional[List[str]] = typer.Option(None, "--cli-cmd", help="Command list to invoke agentvault_cli (e.g., ['python', '-m', 'agentvault_cli']). Defaults to ['agentvault_cli']."),
):
    """
    Discovers agents matching SEARCH_TERM, lets you select one interactively using fzf,
    and then runs a task on the selected agent with the provided INPUT_PROMPT or --input-file.
    """
    if input_prompt is None and input_file is None:
        typer.secho("Error: Must provide either an input_prompt argument or use the --input-file option.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if input_prompt is not None and input_file is not None:
        typer.secho("Error: Cannot use both input_prompt argument and --input-file option.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if cli_cmd_list is None: cli_base_cmd = ["agentvault_cli"]
    else: cli_base_cmd = cli_cmd_list

    fzf_executable = _find_executable("fzf", fzf_path)
    if not fzf_executable:
        typer.secho("Error: 'fzf' executable not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    logger.info(f"Using fzf executable: {fzf_executable}")

    discover_cmd = cli_base_cmd + ["discover", search_term, "--limit", "250"]
    if registry_url: discover_cmd.extend(["--registry", registry_url])
    fzf_cmd = [fzf_executable, "--height", "40%", "--border", "--header", f"Select Agent for '{search_term}':"]

    typer.echo(f"Running discovery: {' '.join(discover_cmd)}")
    typer.echo("Select an agent using fzf...")

    # --- MODIFIED: Use helper function ---
    try:
        selected_line, fzf_returncode = _run_discover_pipe_fzf(discover_cmd, fzf_cmd)
    except Exception as e: # Catch errors from the helper
        # Error message already printed by helper
        raise typer.Exit(code=1)
    # --- END MODIFIED ---

    if fzf_returncode == 130:
        typer.echo("Agent selection cancelled.")
        raise typer.Exit() # Graceful exit
    elif fzf_returncode != 0 or not selected_line:
        typer.secho(f"fzf exited with code {fzf_returncode}. No agent selected.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    selected_agent_id = _parse_discover_output(selected_line)
    if not selected_agent_id:
        typer.secho("Error: Could not determine selected agent ID from fzf output.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Selected Agent ID: {selected_agent_id}")

    # --- 3. Optional: Check Key Config (Using Helper) ---
    if key_service:
        typer.echo(f"Checking configuration for key service: '{key_service}'...")
        config_cmd = cli_base_cmd + ["config", "get", key_service]
        # --- MODIFIED: Use helper function ---
        config_rc, config_stdout, config_stderr = _run_config_get(config_cmd)
        # --- END MODIFIED ---
        if config_rc != 0:
             typer.secho(f"Warning: Could not verify config for '{key_service}' (command failed with code {config_rc}).", fg=typer.colors.YELLOW)
             if config_stderr: typer.echo(f"Config check stderr: {config_stderr.strip()}")
        elif "Not Found" in config_stdout or "Not Configured" in config_stdout:
             typer.secho(f"Warning: Credentials for service '{key_service}' may not be configured. The 'run' command might fail.", fg=typer.colors.YELLOW)
        else:
             logger.info(f"Credentials seem to be configured for service '{key_service}'.")


    # --- 4. Construct and Run Task (Using Helper) ---
    run_cmd = cli_base_cmd + ["run", "--agent", selected_agent_id]
    if input_file: run_cmd.extend(["--input", f"@{input_file}"])
    elif input_prompt: run_cmd.extend(["--input", input_prompt])
    if key_service: run_cmd.extend(["--key-service", key_service])
    if registry_url: run_cmd.extend(["--registry", registry_url])

    # --- MODIFIED: Use helper function ---
    final_exit_code = _run_agent_task(run_cmd)
    # --- END MODIFIED ---

    # Report final status based on the run command's exit code
    if final_exit_code == 0:
        typer.secho("Task completed successfully.", fg=typer.colors.GREEN)
    elif final_exit_code == 1:
        typer.secho("Task failed.", fg=typer.colors.RED)
    elif final_exit_code == 2:
        typer.secho("Task canceled or stopped awaiting input.", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"Task command exited with unexpected code: {final_exit_code}", fg=typer.colors.RED)

    raise typer.Exit(code=final_exit_code)


if __name__ == "__main__":
    app()
