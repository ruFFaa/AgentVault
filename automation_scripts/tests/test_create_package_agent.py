import pytest
import subprocess
import shutil
import sys
import io
import contextlib
import os
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, call, MagicMock
from typing import NamedTuple, Optional, Any, List

# Import the Typer app and the main function, helpers, constants
try:
    from automation_scripts.create_package_agent import app, main as script_main, TEMPLATE_DIR, Path as ScriptPath, _validate_templates_exist
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "automation_scripts"))
    try:
        from create_package_agent import app, main as script_main, TEMPLATE_DIR, Path as ScriptPath, _validate_templates_exist
    except ImportError as e:
        pytest.fail(f"Could not import components from create_package_agent.py: {e}. Check PYTHONPATH or script location.")


runner = CliRunner(mix_stderr=True)

# --- Test Cases ---

@pytest.fixture(autouse=True)
def mock_script_helpers(mocker):
    """Auto-used fixture to mock helper functions that call subprocess."""
    mock_packager = mocker.patch("automation_scripts.create_package_agent._run_sdk_packager", return_value=True)
    mock_docker = mocker.patch("automation_scripts.create_package_agent._run_docker_build", return_value=True)
    mock_rmtree = mocker.patch("shutil.rmtree")
    return mock_packager, mock_docker, mock_rmtree

# --- Tests using runner.invoke (Keep passing tests) ---
def test_create_package_custom_options(tmp_path: Path, mock_script_helpers):
    """Test providing custom options."""
    mock_packager, mock_docker, _ = mock_script_helpers
    agent_name = "My Custom Agent"
    output_dir = tmp_path / "custom_agent"
    package_name = "my_custom_agent"
    agent_id = "my-org/my-custom"
    author = "Test Author"
    email = "test@author.com"
    py_ver = "3.10"
    sdk_ver = ">=0.1.1,<0.2.0"
    desc = "A very custom agent."
    port = 9999
    args = [
        agent_name, str(output_dir),
        "--author", author, "--email", email, "--py", py_ver,
        "--sdk-ver", sdk_ver, "--id", agent_id, "--desc", desc,
        "--port", str(port),
    ]
    result = runner.invoke(app, args, catch_exceptions=True)
    assert result.exit_code == 0, f"Script failed: {result.output}\nException: {result.exception}"
    # Basic check that output dir was created
    assert output_dir.is_dir()
    mock_packager.assert_called_once()
    mock_docker.assert_not_called()

def test_create_package_output_dir_exists_no_force(tmp_path: Path):
    """Test failure when output directory exists without --force."""
    agent_name = "Test Agent"
    output_dir = tmp_path / "existing_dir"
    output_dir.mkdir()
    args = [agent_name, str(output_dir)]
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert "--force" in result.output

def test_create_package_docker_build_flag(tmp_path: Path, mock_script_helpers):
    """Test that --build flag triggers docker build command."""
    mock_packager, mock_docker, _ = mock_script_helpers
    agent_name = "Docker Build Test"
    output_dir = tmp_path / "docker_build_test"
    agent_id = "test-org/docker-build-test"
    args = [agent_name, str(output_dir), "--build", "--author", "Test Org"]
    result = runner.invoke(app, args, catch_exceptions=True)
    assert result.exit_code == 0, f"Script failed: {result.output}\nException: {result.exception}"
    mock_packager.assert_called_once()
    mock_docker.assert_called_once_with(
        output_dir=output_dir,
        tag=f"{agent_id.replace('/', '-')}:latest"
    )

# --- Test _validate_templates_exist helper directly ---
# --- MODIFIED: More sophisticated Path mocking for these tests ---
def test_validate_templates_exist_helper_missing(mocker):
    """Test the _validate_templates_exist helper directly when a file is missing."""
    # Store original Path methods
    original_is_file = Path.is_file
    original_is_dir = Path.is_dir

    def mock_is_file(self):
        # Check the specific file we want to simulate as missing
        if "pyproject.toml.j2" in str(self):
            return False
        # Assume other template files exist if they are within TEMPLATE_DIR
        if str(self).startswith(str(TEMPLATE_DIR)):
            return True
        # Fallback to original for other paths if needed, though unlikely in this helper
        return original_is_file(self)

    def mock_is_dir(self):
        # Only return True for the TEMPLATE_DIR itself
        return str(self) == str(TEMPLATE_DIR)

    # Patch the methods directly on pathlib.Path for the duration of this test
    with patch('pathlib.Path.is_file', side_effect=mock_is_file, autospec=True), \
         patch('pathlib.Path.is_dir', side_effect=mock_is_dir, autospec=True):
        is_valid, missing = _validate_templates_exist()

    assert is_valid is False
    assert "pyproject.toml.j2" in missing

def test_validate_templates_exist_helper_success(mocker):
    """Test the _validate_templates_exist helper directly when all files exist."""
    # Patch methods to always return True within the helper's context
    with patch('pathlib.Path.is_file', return_value=True), \
         patch('pathlib.Path.is_dir', return_value=True):
        is_valid, missing = _validate_templates_exist()

    assert is_valid is True
    assert missing == []
# --- END MODIFIED ---

def test_create_package_missing_template_exit(tmp_path: Path, mocker):
    """Test that the main command exits if template validation fails."""
    mock_validate = mocker.patch("automation_scripts.create_package_agent._validate_templates_exist", return_value=(False, ["some_template.j2"]))
    mock_packager = mocker.patch("automation_scripts.create_package_agent._run_sdk_packager")
    mock_docker = mocker.patch("automation_scripts.create_package_agent._run_docker_build")

    agent_name = "Missing Template Test"
    output_dir = tmp_path / "missing_template_test"
    args = [agent_name, str(output_dir)]

    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "Missing required template files" in result.output
    mock_validate.assert_called_once()
    mock_packager.assert_not_called()
    mock_docker.assert_not_called()

# --- Re-add success tests that were failing, using the helper mocks ---
def test_create_package_success_defaults_redux(tmp_path: Path, mock_script_helpers):
    """Re-test basic successful run with default options, mocking helpers."""
    mock_packager, mock_docker, _ = mock_script_helpers
    agent_name = "My Test Agent Defaults"
    output_dir = tmp_path / "test_agent_defaults"
    package_name = "my_test_agent_defaults_agent"
    agent_id = "agent-developer/my-test-agent-defaults"

    args = [agent_name, str(output_dir)]
    result = runner.invoke(app, args, catch_exceptions=True)

    assert result.exit_code == 0, f"Script failed: {result.output}\nException: {result.exception}"
    assert output_dir.is_dir() # Check directory creation
    assert (output_dir / "pyproject.toml").is_file() # Check a key file exists
    mock_packager.assert_called_once() # Check helper was called
    mock_docker.assert_not_called()

def test_create_package_output_dir_exists_with_force_redux(tmp_path: Path, mock_script_helpers):
    """Re-test overwriting an existing directory with --force, mocking helpers."""
    mock_packager, mock_docker, mock_rmtree = mock_script_helpers
    agent_name = "Test Agent Force"
    output_dir = tmp_path / "existing_dir_force"
    output_dir.mkdir()
    (output_dir / "old_file.txt").touch()

    args = [agent_name, str(output_dir), "--force"]
    result = runner.invoke(app, args, catch_exceptions=True)

    assert result.exit_code == 0, f"Script failed: {result.output}\nException: {result.exception}"
    assert "Overwriting contents due to --force flag" in result.output
    mock_rmtree.assert_called_once_with(output_dir)
    assert (output_dir / "pyproject.toml").is_file()
    mock_packager.assert_called_once()
    mock_docker.assert_not_called()
