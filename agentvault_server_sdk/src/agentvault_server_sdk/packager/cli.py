"""
Command-line interface for the AgentVault Server SDK utilities,
starting with the agent packager.
"""

import typer
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Create the Typer application
app = typer.Typer(
    name="agentvault-sdk",
    help="Utilities for building and packaging AgentVault A2A agents.",
    add_completion=False # Disable shell completion for now
)

# --- Dockerfile Template ---
# Basic multi-stage Dockerfile
DOCKERFILE_TEMPLATE = """\
# Stage 1: Build environment with dependencies
FROM python:{PYTHON_VERSION_TAG} as builder

WORKDIR /opt/builder

# Install build tools if needed (example for packages needing compilation)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc

# Copy requirements first to leverage Docker cache
COPY {REQUIREMENTS_FILE} ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r {REQUIREMENTS_FILE}

# Stage 2: Final application image
FROM python:{PYTHON_VERSION_TAG}

# Set working directory
WORKDIR {APP_DIR}

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python{PYTHON_MAJOR_MINOR}/site-packages /usr/local/lib/python{PYTHON_MAJOR_MINOR}/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appgroup {APP_DIR}

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE {PORT}

# Command to run the application
CMD ["uvicorn", "{ENTRYPOINT_MODULE_PATH}", "--host", "0.0.0.0", "--port", "{PORT}"]
"""

# --- MODIFIED: Removed explicit name ---
@app.command()
# --- END MODIFIED ---
def package_agent(
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Directory to write Dockerfile and other artifacts.",
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
    ),
    python_version: str = typer.Option(
        "3.11",
        "--python",
        help="Python version for base image tag (e.g., 3.10, 3.11)."
    ),
    base_image_suffix: str = typer.Option(
        "slim-bookworm",
        "--suffix",
        help="Suffix for the python base image (e.g., slim-bookworm, alpine)."
    ),
    entrypoint_path: str = typer.Option(
        ...,
        "--entrypoint",
        "-e",
        help="Python import path to the FastAPI app (e.g., my_agent.main:app)."
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port the application will listen on inside the container."
    ),
    requirements_path: Optional[Path] = typer.Option(
        None,
        "--requirements",
        "-r",
        help="Path to the requirements.txt file (optional, defaults to './requirements.txt').",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    app_dir: str = typer.Option(
        "/app",
        "--app-dir",
        help="Directory inside the container where the application code will reside."
    )
):
    """
    Generates a Dockerfile for packaging an AgentVault agent.
    """
    typer.echo(f"Starting Dockerfile generation for entrypoint '{entrypoint_path}'...")
    logger.info(f"Generating Dockerfile in output directory: {output_dir}")

    # Determine requirements file name for COPY instruction
    req_file_name = requirements_path.name if requirements_path else "requirements.txt"

    # Construct image tag and python major.minor
    python_version_tag = f"{python_version}-{base_image_suffix}"
    python_major_minor = ".".join(python_version.split('.')[:2]) # e.g., "3.11"

    # Prepare template context
    context = {
        "PYTHON_VERSION_TAG": python_version_tag,
        "APP_DIR": app_dir,
        "REQUIREMENTS_FILE": req_file_name,
        "ENTRYPOINT_MODULE_PATH": entrypoint_path,
        "PORT": str(port), # Ensure port is string for format
        "PYTHON_MAJOR_MINOR": python_major_minor,
    }

    # Render the template
    try:
        dockerfile_content = DOCKERFILE_TEMPLATE.format(**context)
        logger.debug("Dockerfile template rendered successfully.")
    except KeyError as e:
        typer.secho(f"Error: Missing key in Dockerfile template context: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Error rendering Dockerfile template: {e}", fg=typer.colors.RED)
        logger.exception("Dockerfile template rendering failed.")
        raise typer.Exit(code=1)

    # Ensure output directory exists
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured output directory exists: {output_dir}")
    except OSError as e:
        typer.secho(f"Error creating output directory '{output_dir}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Write Dockerfile
    dockerfile_path = output_dir / "Dockerfile"
    try:
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
        typer.secho(f"Successfully generated Dockerfile: {dockerfile_path}", fg=typer.colors.GREEN)
    except IOError as e:
        typer.secho(f"Error writing Dockerfile to '{dockerfile_path}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # TODO: Add logic for requirements file copying/checking (Task 2.2.A.20)
    # TODO: Add logic for .dockerignore generation (Task 2.2.A.21)
    # TODO: Add optional docker build step (Task 2.2.A.7)

if __name__ == "__main__":
    app() # Allow running the CLI directly for testing
