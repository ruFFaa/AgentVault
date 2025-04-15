import pytest
import subprocess
import shutil
import sys
import os
from pathlib import Path
import typer
import click # Import click to get exceptions
from typer import Exit
from typer.testing import CliRunner # Keep runner for potential future use? No, remove.
from unittest.mock import patch, call, MagicMock, ANY
from typing import NamedTuple, Optional, Any, List

# Import the Typer app and the main function
try:
    # --- MODIFIED: Import only app and main ---
    from automation_scripts.find_run_task import app, main as script_main
    # --- END MODIFIED ---
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "automation_scripts"))
    try:
        # --- MODIFIED: Import only app and main ---
        from find_run_task import app, main as script_main
        # --- END MODIFIED ---
    except ImportError as e:
        pytest.fail(f"Could not import 'app' or 'main' from find_run_task.py: {e}. Check PYTHONPATH or script location.")


# --- Fixtures ---
@pytest.fixture
def mock_helpers(mocker):
    """Mocks the helper functions used by the script."""
    mock_find_exe = mocker.patch("automation_scripts.find_run_task._find_executable", return_value="/fake/path/to/fzf")
    mock_pipe_fzf = mocker.patch("automation_scripts.find_run_task._run_discover_pipe_fzf", return_value=("agent-id-123   Agent One   Desc 1", 0))
    mock_config_get = mocker.patch("automation_scripts.find_run_task._run_config_get", return_value=(0, "Source: KEYRING", ""))
    mock_agent_run = mocker.patch("automation_scripts.find_run_task._run_agent_task", return_value=0)

    return {
        "find_exe": mock_find_exe,
        "pipe_fzf": mock_pipe_fzf,
        "config_get": mock_config_get,
        "agent_run": mock_agent_run,
    }

# --- Test Cases ---

def test_find_run_success_defaults(tmp_path: Path, mock_helpers):
    """Test the default successful workflow by calling main directly."""
    search = "weather"
    prompt = "Forecast London?"
    expected_agent_id = "agent-id-123"

    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term=search,
            input_prompt=prompt,
            input_file=None, key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None
        )
    assert e.value.exit_code == 0

    mock_helpers["find_exe"].assert_called_once_with("fzf", None)
    mock_helpers["pipe_fzf"].assert_called_once_with(
        ['agentvault_cli', 'discover', search, '--limit', '250'],
        ['/fake/path/to/fzf', '--height', '40%', '--border', '--header', ANY]
    )
    mock_helpers["config_get"].assert_not_called()
    mock_helpers["agent_run"].assert_called_once_with(
        ['agentvault_cli', 'run', '--agent', expected_agent_id, '--input', prompt]
    )

def test_find_run_with_input_file(tmp_path: Path, mock_helpers):
    """Test using --input-file instead of positional prompt."""
    search = "utility"
    input_content = "Process this data."
    input_file = tmp_path / "input.txt"
    input_file.write_text(input_content)
    expected_agent_id = "agent-id-123"

    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term=search,
            input_prompt=None,
            input_file=input_file,
            key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None
        )
    assert e.value.exit_code == 0

    mock_helpers["agent_run"].assert_called_once_with(
        ['agentvault_cli', 'run', '--agent', expected_agent_id, '--input', f'@{input_file}']
    )

def test_find_run_input_prompt_and_file_error(tmp_path: Path):
    """Test error when both input prompt and file are provided."""
    input_file = tmp_path / "dummy.txt"
    input_file.touch()
    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term="search",
            input_prompt="prompt",
            input_file=input_file,
            key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None
        )
    assert e.value.exit_code == 1

def test_find_run_no_input_error():
    """Test error when neither input prompt nor file are provided."""
    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term="search",
            input_prompt=None,
            input_file=None,
            key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None
        )
    assert e.value.exit_code == 1

def test_find_run_fzf_not_found(mock_helpers):
    """Test failure when fzf executable is not found."""
    mock_helpers["find_exe"].return_value = None
    with pytest.raises(click.exceptions.Exit) as e:
        script_main(search_term="search", input_prompt="prompt", input_file=None, key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None)
    assert e.value.exit_code == 1
    mock_helpers["pipe_fzf"].assert_not_called()
    mock_helpers["agent_run"].assert_not_called()

def test_find_run_fzf_cancelled(mock_helpers):
    """Test graceful exit when fzf is cancelled (exit code 130)."""
    mock_helpers["pipe_fzf"].return_value = ("", 130)
    with pytest.raises(click.exceptions.Exit) as e:
        script_main(search_term="search", input_prompt="prompt", input_file=None, key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None)
    assert e.value.exit_code == 0 # Graceful exit from typer.Exit()
    mock_helpers["agent_run"].assert_not_called()

def test_find_run_fzf_no_selection(mock_helpers):
    """Test exit with error when fzf returns no selection."""
    mock_helpers["pipe_fzf"].return_value = ("", 0)
    with pytest.raises(click.exceptions.Exit) as e:
        script_main(search_term="search", input_prompt="prompt", input_file=None, key_service=None, registry_url=None, fzf_path=None, cli_cmd_list=None)
    assert e.value.exit_code == 1
    mock_helpers["agent_run"].assert_not_called()

def test_find_run_key_check_warning(mock_helpers):
    """Test warning when config get suggests key is missing."""
    search = "secure-agent"
    prompt = "Do something secure"
    key_id = "secure-key"
    expected_agent_id = "agent-id-123"

    mock_helpers["config_get"].return_value = (0, "Status: Not Found", "")
    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term=search, input_prompt=prompt, input_file=None,
            key_service=key_id,
            registry_url=None, fzf_path=None, cli_cmd_list=None
        )
    assert e.value.exit_code == 0

    mock_helpers["config_get"].assert_called_once_with(['agentvault_cli', 'config', 'get', key_id])
    mock_helpers["agent_run"].assert_called_once_with(
        ['agentvault_cli', 'run', '--agent', expected_agent_id, '--input', prompt, '--key-service', key_id]
    )

def test_find_run_custom_cli_cmd(mock_helpers):
    """Test using a custom CLI command list."""
    search = "test"
    prompt = "test"
    expected_agent_id = "agent-id-123"
    custom_cli = ["python", "-m", "agentvault_cli"]

    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term=search, input_prompt=prompt, input_file=None, key_service=None, registry_url=None, fzf_path=None,
            cli_cmd_list=custom_cli
        )
    assert e.value.exit_code == 0

    mock_helpers["pipe_fzf"].assert_called_once_with(
        custom_cli + ["discover", search, "--limit", "250"], ANY
    )
    mock_helpers["agent_run"].assert_called_once_with(
        custom_cli + ["run", "--agent", expected_agent_id, "--input", prompt]
    )

def test_find_run_registry_url_passthrough(mock_helpers):
    """Test that the registry URL is passed to discover and run."""
    search = "test"
    prompt = "test"
    registry = "http://my-registry.test"
    expected_agent_id = "agent-id-123"

    with pytest.raises(click.exceptions.Exit) as e:
        script_main(
            search_term=search, input_prompt=prompt, input_file=None, key_service=None,
            registry_url=registry,
            fzf_path=None, cli_cmd_list=None
        )
    assert e.value.exit_code == 0

    mock_helpers["pipe_fzf"].assert_called_once_with(
        ['agentvault_cli', 'discover', search, '--limit', '250', '--registry', registry], ANY
    )
    mock_helpers["agent_run"].assert_called_once_with(
        ['agentvault_cli', 'run', '--agent', expected_agent_id, '--input', prompt, '--registry', registry]
    )
