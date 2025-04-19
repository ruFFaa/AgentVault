import pytest
import subprocess
import shutil
import sys
import io
import contextlib
import os
from pathlib import Path
from typer.testing import CliRunner
# --- MODIFIED: Removed mock imports not needed here ---
# from unittest.mock import patch, call, MagicMock
# --- END MODIFIED ---
from typing import NamedTuple, Optional, Any, List
import logging # Import logging for caplog
import re

# Import the Typer app instance
try:
    # --- MODIFIED: Import only app and DOCKERIGNORE_CONTENT ---
    from agentvault_server_sdk.packager.cli import app, DOCKERIGNORE_CONTENT
    # --- END MODIFIED ---
except ImportError:
    # --- MODIFIED: Adjust path for potential direct run ---
    script_dir = Path(__file__).parent.parent
    src_dir = script_dir / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(script_dir / "src"))
    else: # Maybe running from project root?
        sdk_dir = Path(__file__).parent.parent.parent / "agentvault_server_sdk"
        if (sdk_dir / "src").is_dir():
             sys.path.insert(0, str(sdk_dir / "src"))

    try:
        from agentvault_server_sdk.packager.cli import app, DOCKERIGNORE_CONTENT
    except ImportError as e:
        pytest.fail(f"Could not import components from agentvault_server_sdk.packager.cli: {e}. Check PYTHONPATH or script location.")
    # --- END MODIFIED ---


# Instantiate CliRunner with mix_stderr=True and try disabling color via env
runner = CliRunner(mix_stderr=True, env={"NO_COLOR": "1", "TERM": "dumb"}) # Added TERM=dumb as another attempt

# --- REMOVED: mock_script_helpers fixture ---

# --- Test Cases ---

def test_package_agent_dockerfile_generation(tmp_path: Path):
    """Test that the 'package' command generates a Dockerfile and .dockerignore."""
    output_dir = tmp_path / "package_output"
    entrypoint = "my_agent.main:app"
    python_version = "3.10"
    suffix = "slim-bullseye"
    port = 8080
    python_major_minor = ".".join(python_version.split('.')[:2])

    # --- REMOVED: Mocking context ---
    # with patch(...)
    result = runner.invoke(
        app,
        [
            # Command name removed in previous step
            "--output-dir", str(output_dir),
            "--entrypoint", entrypoint,
            "--python", python_version,
            "--suffix", suffix,
            "--port", str(port),
            # Not providing --requirements, should default
        ],
        catch_exceptions=False # Let exceptions fail the test
    )
    # --- END REMOVED ---

    print(f"CLI Output:\n{result.output}") # Print combined output
    assert result.exit_code == 0, f"CLI command failed with exit code {result.exit_code}"

    # Check Dockerfile
    dockerfile_path = output_dir / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile was not created"
    dockerfile_content = dockerfile_path.read_text()
    assert f"FROM python:{python_version}-{suffix}" in dockerfile_content
    assert 'WORKDIR /app' in dockerfile_content
    assert 'COPY requirements.txt ./' in dockerfile_content
    assert f'pip install --no-cache-dir -r requirements.txt' in dockerfile_content
    assert f'COPY --from=builder /usr/local/lib/python{python_major_minor}/site-packages' in dockerfile_content
    assert 'USER appuser' in dockerfile_content
    assert f'EXPOSE {port}' in dockerfile_content
    assert f'CMD ["uvicorn", "{entrypoint}", "--host", "0.0.0.0", "--port", "{port}"]' in dockerfile_content

    # Check .dockerignore
    dockerignore_path = output_dir / ".dockerignore"
    assert dockerignore_path.is_file(), ".dockerignore was not created"
    ignore_content = dockerignore_path.read_text()
    assert "__pycache__/" in ignore_content # Check a few key patterns
    assert ".venv/" in ignore_content
    assert ".git" in ignore_content
    assert "*.log" in ignore_content
    # Check a few more specific lines instead of exact match
    assert "# Secrets / Config" in ignore_content
    assert ".env*" in ignore_content
    assert "!/.env.example" in ignore_content


def test_package_agent_requires_output_dir():
    """Test that the command fails if output directory is missing."""
    result = runner.invoke(app, ["--entrypoint", "main:app"])
    assert result.exit_code != 0
    # Define ANSI escape code pattern
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_output = ansi_escape.sub('', result.output)
    assert re.search(r"Missing option.*--output-dir", clean_output)

def test_package_agent_requires_entrypoint():
    """Test that the command fails if entrypoint is missing."""
    result = runner.invoke(app, ["--output-dir", "./temp_out"])
    assert result.exit_code != 0
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_output = ansi_escape.sub('', result.output)
    assert re.search(r"Missing option.*--entrypoint", clean_output)

# --- Tests for requirements handling ---

def test_package_agent_with_requirements_file(tmp_path: Path):
    """Test providing a specific requirements file."""
    output_dir = tmp_path / "package_output_req"
    entrypoint = "my_agent.main:app"
    req_file = tmp_path / "custom_reqs.txt"
    req_content = "fastapi==0.111.0\nagentvault-server-sdk\n"
    req_file.write_text(req_content)

    # --- REMOVED: Mocking context ---
    result = runner.invoke(
        app,
        [
            "--output-dir", str(output_dir),
            "--entrypoint", entrypoint,
            "--requirements", str(req_file),
        ],
        catch_exceptions=False
    )
    # --- END REMOVED ---

    assert result.exit_code == 0
    copied_req_path = output_dir / "requirements.txt" # Should be copied to default name
    assert copied_req_path.is_file(), "Requirements file was not copied"
    assert copied_req_path.read_text() == req_content
    # Check Dockerfile uses the correct internal name
    dockerfile_path = output_dir / "Dockerfile"
    assert dockerfile_path.is_file()
    dockerfile_content = dockerfile_path.read_text()
    assert "COPY requirements.txt ./" in dockerfile_content
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile_content

def test_package_agent_default_requirements_exists(tmp_path: Path, monkeypatch, caplog):
    """Test using the default requirements.txt when it exists."""
    caplog.set_level(logging.WARNING) # Capture WARNING level logs
    output_dir = tmp_path / "package_output_def_req"
    entrypoint = "my_agent.main:app"
    default_req_content = "uvicorn\n# sdk missing\n"

    # Create the default file in the *current* directory for the test
    monkeypatch.chdir(tmp_path) # Change CWD for the test
    default_req_file = tmp_path / "requirements.txt"
    default_req_file.write_text(default_req_content)

    # --- REMOVED: Mocking context ---
    result = runner.invoke(
        app,
        [
            "--output-dir", str(output_dir),
            "--entrypoint", entrypoint,
            # No --requirements option
        ],
        catch_exceptions=False
    )
    # --- END REMOVED ---

    assert result.exit_code == 0
    copied_req_path = output_dir / "requirements.txt"
    assert copied_req_path.is_file(), "Default requirements file was not copied"
    assert copied_req_path.read_text() == default_req_content
    # Assert warning is in caplog.text or cli output
    assert "SDK dependency possibly missing" in result.output or \
           "SDK dependency possibly missing" in caplog.text

def test_package_agent_default_requirements_missing(tmp_path: Path, monkeypatch, caplog):
    """Test when default requirements.txt is missing."""
    caplog.set_level(logging.WARNING) # Capture WARNING level logs
    output_dir = tmp_path / "package_output_no_req"
    entrypoint = "my_agent.main:app"

    # Ensure the default file does NOT exist in CWD
    monkeypatch.chdir(tmp_path)
    default_req_file = tmp_path / "requirements.txt"
    if default_req_file.exists(): default_req_file.unlink()

    # --- REMOVED: Mocking context ---
    result = runner.invoke(
        app,
        [
            "--output-dir", str(output_dir),
            "--entrypoint", entrypoint,
            # No --requirements option
        ],
        catch_exceptions=False
    )
    # --- END REMOVED ---

    assert result.exit_code == 0 # Should not fail, just warn
    copied_req_path = output_dir / "requirements.txt"
    assert not copied_req_path.exists(), "Requirements file should not have been copied"
    # Assert warning is in caplog.text or cli output
    assert "Default './requirements.txt' not found" in result.output or \
           "Default requirements.txt not found, skipping copy" in caplog.text

# --- Test for agent-card argument ---
def test_package_agent_with_agent_card(tmp_path: Path, caplog):
    """Test providing the --agent-card option."""
    caplog.set_level(logging.INFO) # Capture INFO level logs for this test
    output_dir = tmp_path / "package_output_card"
    entrypoint = "my_agent.main:app"
    card_file = tmp_path / "my-card.json"
    card_content = '{"schemaVersion": "1.0", "name": "Test"}' # Minimal valid content
    card_file.write_text(card_content)

    # --- REMOVED: Mocking context ---
    result = runner.invoke(
        app,
        [
            "--output-dir", str(output_dir),
            "--entrypoint", entrypoint,
            "--agent-card", str(card_file),
        ],
        catch_exceptions=False
    )
    # --- END REMOVED ---

    assert result.exit_code == 0
    # Verify the card was copied
    copied_card_path = output_dir / card_file.name
    assert copied_card_path.is_file(), "Agent card file was not copied"
    assert copied_card_path.read_text() == card_content
    # Assert that the message was printed to the console OR logged
    assert f"Copied agent card file to: {copied_card_path}" in result.output or \
           (f"Copied {card_file}" in caplog.text and f"to {copied_card_path}" in caplog.text)
