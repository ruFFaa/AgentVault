import pytest
import subprocess
import shutil
import sys
import io
import contextlib
import os
from pathlib import Path
from unittest.mock import patch, call, MagicMock, ANY
import typer
from typing import NamedTuple, Optional, Any, List
import logging
import re

# Import the CLI module
try:
    from agentvault_server_sdk.packager.cli import DOCKERIGNORE_CONTENT
except ImportError:
    script_dir = Path(__file__).parent.parent
    src_dir = script_dir / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(script_dir / "src"))
    else: # Maybe running from project root?
        sdk_dir = Path(__file__).parent.parent.parent / "agentvault_server_sdk"
        if (sdk_dir / "src").is_dir():
             sys.path.insert(0, str(sdk_dir / "src"))

    try:
        from agentvault_server_sdk.packager.cli import DOCKERIGNORE_CONTENT
    except ImportError as e:
        pytest.fail(f"Could not import components from agentvault_server_sdk.packager.cli: {e}. Check PYTHONPATH or script location.")

# --- Test Cases for Direct Function Calls ---

def test_package_agent_dockerfile_generation(tmp_path: Path):
    """Test that the package_agent function generates a Dockerfile and .dockerignore."""
    # Import the function directly
    from agentvault_server_sdk.packager.cli import package_agent
    
    output_dir = tmp_path / "package_output"
    entrypoint = "my_agent.main:app"
    python_version = "3.10"
    suffix = "slim-bullseye"
    port = 8080
    python_major_minor = ".".join(python_version.split('.')[:2])

    # Call the function directly with the arguments it expects
    package_agent(
        output_dir=output_dir,
        entrypoint_path=entrypoint,
        python_version=python_version,
        base_image_suffix=suffix,
        port=port,
        requirements_path=None,
        app_dir="/app",
        agent_card_path=None
    )

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
    assert "# Secrets / Config" in ignore_content
    assert ".env*" in ignore_content
    assert "!/.env.example" in ignore_content


def test_package_agent_with_requirements_file(tmp_path: Path):
    """Test providing a specific requirements file."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    output_dir = tmp_path / "package_output_req"
    entrypoint = "my_agent.main:app"
    req_file = tmp_path / "custom_reqs.txt"
    req_content = "fastapi==0.111.0\nagentvault-server-sdk\n"
    req_file.write_text(req_content)

    # Call function directly
    package_agent(
        output_dir=output_dir,
        entrypoint_path=entrypoint,
        python_version="3.11",
        base_image_suffix="slim-bookworm",
        port=8000,
        requirements_path=req_file,
        app_dir="/app",
        agent_card_path=None
    )

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
    from agentvault_server_sdk.packager.cli import package_agent
    
    caplog.set_level(logging.WARNING) # Capture WARNING level logs
    output_dir = tmp_path / "package_output_def_req"
    entrypoint = "my_agent.main:app"
    default_req_content = "uvicorn\n# sdk missing\n"

    # Create the default file in the *current* directory for the test
    monkeypatch.chdir(tmp_path) # Change CWD for the test
    default_req_file = tmp_path / "requirements.txt"
    default_req_file.write_text(default_req_content)

    # Call function directly
    package_agent(
        output_dir=output_dir,
        entrypoint_path=entrypoint,
        python_version="3.11",
        base_image_suffix="slim-bookworm",
        port=8000,
        requirements_path=None, # Default should be used
        app_dir="/app",
        agent_card_path=None
    )

    copied_req_path = output_dir / "requirements.txt"
    assert copied_req_path.is_file(), "Default requirements file was not copied"
    assert copied_req_path.read_text() == default_req_content
    
    # Check for warning in logs
    assert "SDK dependency possibly missing" in caplog.text


def test_package_agent_default_requirements_missing(tmp_path: Path, monkeypatch, caplog):
    """Test when default requirements.txt is missing."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    caplog.set_level(logging.WARNING) # Capture WARNING level logs
    output_dir = tmp_path / "package_output_no_req"
    entrypoint = "my_agent.main:app"

    # Ensure the default file does NOT exist in CWD
    monkeypatch.chdir(tmp_path)
    default_req_file = tmp_path / "requirements.txt"
    if default_req_file.exists(): default_req_file.unlink()

    # Call function directly
    package_agent(
        output_dir=output_dir,
        entrypoint_path=entrypoint,
        python_version="3.11",
        base_image_suffix="slim-bookworm",
        port=8000,
        requirements_path=None, # No file provided
        app_dir="/app",
        agent_card_path=None
    )

    copied_req_path = output_dir / "requirements.txt"
    assert not copied_req_path.exists(), "Requirements file should not have been copied"
    
    # Check for warning in logs
    assert "Default requirements.txt not found, skipping copy" in caplog.text


def test_package_agent_with_agent_card(tmp_path: Path, caplog):
    """Test providing the --agent-card option."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    caplog.set_level(logging.INFO) # Capture INFO level logs for this test
    output_dir = tmp_path / "package_output_card"
    entrypoint = "my_agent.main:app"
    card_file = tmp_path / "my-card.json"
    card_content = '{"schemaVersion": "1.0", "name": "Test"}' # Minimal valid content
    card_file.write_text(card_content)

    # Call function directly
    package_agent(
        output_dir=output_dir,
        entrypoint_path=entrypoint,
        python_version="3.11",
        base_image_suffix="slim-bookworm",
        port=8000,
        requirements_path=None,
        app_dir="/app",
        agent_card_path=card_file
    )

    # Verify the card was copied
    copied_card_path = output_dir / card_file.name
    assert copied_card_path.is_file(), "Agent card file was not copied"
    assert copied_card_path.read_text() == card_content
    
    # Check for log message
    assert f"Copied {card_file}" in caplog.text and f"to {copied_card_path}" in caplog.text


# --- Tests for Error Handling ---

@patch("agentvault_server_sdk.packager.cli.Path.mkdir")
def test_package_agent_output_dir_creation_error(mock_mkdir, tmp_path: Path):
    """Test error handling when output directory creation fails."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    # Setup the mock to raise an exception
    mock_mkdir.side_effect = OSError("Permission denied")
    output_dir = tmp_path / "uncreatable_dir"
    
    # Call function directly and check for exception
    with pytest.raises(typer.Exit) as excinfo:
        package_agent(
            output_dir=output_dir,
            entrypoint_path="main:app",
            python_version="3.11",
            base_image_suffix="slim-bookworm",
            port=8000,
            requirements_path=None,
            app_dir="/app",
            agent_card_path=None
        )
    
    # Check exit code
    assert excinfo.value.exit_code == 1
    
    # Verify mkdir was called
    mock_mkdir.assert_called_once()


@patch("agentvault_server_sdk.packager.cli.shutil.copyfile")
def test_package_agent_requirements_copy_error(mock_copyfile, tmp_path: Path):
    """Test error handling when copying requirements file fails."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    # Setup
    output_dir = tmp_path / "req_copy_error"
    output_dir.mkdir(parents=True, exist_ok=True)
    req_file = tmp_path / "myreqs.txt"
    req_file.touch()
    
    # Configure mock to raise the exception
    mock_copyfile.side_effect = IOError("Disk full")
    
    # Call function directly and check for exception
    with pytest.raises(typer.Exit) as excinfo:
        package_agent(
            output_dir=output_dir,
            entrypoint_path="main:app",
            python_version="3.11",
            base_image_suffix="slim-bookworm",
            port=8000,
            requirements_path=req_file,
            app_dir="/app",
            agent_card_path=None
        )
    
    # Check exit code
    assert excinfo.value.exit_code == 1
    
    # Verify copyfile was called
    mock_copyfile.assert_called_once()


@patch("agentvault_server_sdk.packager.cli.shutil.copyfile")
def test_package_agent_agent_card_copy_error(mock_copyfile, tmp_path: Path):
    """Test error handling when copying agent card file fails (warning only)."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    # Setup
    output_dir = tmp_path / "card_copy_error"
    output_dir.mkdir(parents=True, exist_ok=True)
    card_file = tmp_path / "mycard.json"
    card_file.touch()
    
    # Setup side effect that only fails for the card copy
    def copy_side_effect(src, dst):
        if Path(src) == card_file:
            raise IOError("Card read error")
        return None
    
    mock_copyfile.side_effect = copy_side_effect
    
    # This should NOT raise an exception (card copy error is non-fatal)
    package_agent(
        output_dir=output_dir,
        entrypoint_path="main:app",
        python_version="3.11",
        base_image_suffix="slim-bookworm",
        port=8000,
        requirements_path=None,
        app_dir="/app",
        agent_card_path=card_file
    )
    
    # Should still have created the Dockerfile (main output)
    assert (output_dir / "Dockerfile").is_file()
    
    # Verify copyfile was called with card file
    mock_copyfile.assert_called_with(card_file, output_dir / card_file.name)


@patch("agentvault_server_sdk.packager.cli.Path.write_text")
def test_package_agent_dockerfile_write_error(mock_write_text, tmp_path: Path):
    """Test error handling when writing the Dockerfile fails."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    # Setup
    output_dir = tmp_path / "docker_write_error"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure mock to raise exception
    mock_write_text.side_effect = IOError("Cannot write Dockerfile")
    
    # Call function directly and check for exception
    with pytest.raises(typer.Exit) as excinfo:
        package_agent(
            output_dir=output_dir,
            entrypoint_path="main:app",
            python_version="3.11",
            base_image_suffix="slim-bookworm",
            port=8000,
            requirements_path=None,
            app_dir="/app",
            agent_card_path=None
        )
    
    # Check exit code
    assert excinfo.value.exit_code == 1
    
    # Verify write_text was called
    mock_write_text.assert_called_once()


def test_package_agent_dockerignore_write_error(tmp_path: Path):
    """Test error handling when writing the .dockerignore fails (should warn)."""
    from agentvault_server_sdk.packager.cli import package_agent
    
    # Setup
    output_dir = tmp_path / "ignore_write_error"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a patcher for Path.write_text
    original_write_text = Path.write_text
    
    def mock_write_text(path_self, content, *args, **kwargs):
        # Only raise error for .dockerignore file
        if path_self.name == ".dockerignore":
            raise IOError("Cannot write .dockerignore")
        # For all other files, call the original function
        return original_write_text(path_self, content, *args, **kwargs)
    
    # Apply the patch
    with patch.object(Path, "write_text", mock_write_text):
        # Execute the command - should complete with warning but no failure
        package_agent(
            output_dir=output_dir,
            entrypoint_path="main:app",
            python_version="3.11",
            base_image_suffix="slim-bookworm",
            port=8000,
            requirements_path=None,
            app_dir="/app",
            agent_card_path=None
        )
        
        # Should succeed (dockerignore error is just a warning)
        # The Dockerfile should exist
        assert (output_dir / "Dockerfile").is_file()
        # The .dockerignore should not exist
        assert not (output_dir / ".dockerignore").exists()