import pytest
from typer.testing import CliRunner
from pathlib import Path

# Import the Typer app instance
from agentvault_server_sdk.packager.cli import app

runner = CliRunner()

def test_package_agent_dockerfile_generation(tmp_path: Path):
    """Test that the 'package' command generates a Dockerfile."""
    output_dir = tmp_path / "package_output"
    entrypoint = "my_agent.main:app"
    python_version = "3.10"
    suffix = "slim-bullseye"
    port = 8080
    # --- ADDED: Calculate major.minor version for assertion ---
    python_major_minor = ".".join(python_version.split('.')[:2])
    # --- END ADDED ---

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

    print(f"CLI Output:\n{result.stdout}") # Print output for debugging if needed
    assert result.exit_code == 0, f"CLI command failed with exit code {result.exit_code}"

    dockerfile_path = output_dir / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile was not created"

    content = dockerfile_path.read_text()
    # Check for key rendered values
    assert f"FROM python:{python_version}-{suffix}" in content
    assert 'WORKDIR /app' in content # Default app dir
    assert 'COPY requirements.txt ./' in content # Default requirements file name
    assert f'pip install --no-cache-dir -r requirements.txt' in content
    # --- MODIFIED: Use correct major.minor version in assertion ---
    assert f'COPY --from=builder /usr/local/lib/python{python_major_minor}/site-packages' in content
    # --- END MODIFIED ---
    assert 'USER appuser' in content
    assert f'EXPOSE {port}' in content
    assert f'CMD ["uvicorn", "{entrypoint}", "--host", "0.0.0.0", "--port", "{port}"]' in content

def test_package_agent_requires_output_dir():
    """Test that the command fails if output directory is missing."""
    result = runner.invoke(app, ["--entrypoint", "main:app"])
    assert result.exit_code != 0
    assert "Missing option '--output-dir'" in result.stdout

def test_package_agent_requires_entrypoint():
    """Test that the command fails if entrypoint is missing."""
    result = runner.invoke(app, ["--output-dir", "./temp_out"])
    assert result.exit_code != 0
    assert "Missing option '--entrypoint'" in result.stdout

# TODO: Add tests for --requirements handling
# TODO: Add tests for .dockerignore generation
