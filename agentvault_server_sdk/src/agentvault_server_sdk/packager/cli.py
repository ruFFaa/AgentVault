"""
Command-line interface for the AgentVault Server SDK utilities,
starting with the agent packager.
"""

import typer
import logging
import shutil # Import shutil for file copying
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


@app.command()
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
        help="Path to the requirements.txt file (optional, defaults to './requirements.txt' relative to CWD).",
        exists=True, # Typer handles error if specified path doesn't exist
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
    Generates a Dockerfile and copies requirements for packaging an AgentVault agent.
    """
    typer.echo(f"Starting Dockerfile generation for entrypoint '{entrypoint_path}'...")
    logger.info(f"Generating Dockerfile in output directory: {output_dir}")

    # --- Requirements File Handling ---
    source_req_path: Optional[Path] = None
    req_file_in_dockerfile = "requirements.txt" # Name used inside Dockerfile

    if requirements_path:
        # User specified a path, Typer already validated existence
        source_req_path = requirements_path
        typer.echo(f"Using specified requirements file: {source_req_path}")
    else:
        # Default to requirements.txt in current working directory
        default_req_path = Path("./requirements.txt").resolve()
        if default_req_path.is_file():
            source_req_path = default_req_path
            typer.echo(f"Using default requirements file: {source_req_path}")
        else:
            # --- MODIFIED: Use typer.echo for warning ---
            typer.echo(
                "Warning: Default './requirements.txt' not found. Docker build might fail if dependencies are needed."
            )
            # --- END MODIFIED ---
            logger.warning("Default requirements.txt not found, skipping copy.")
            # Proceed without error, Docker build will handle missing file if needed

    # --- Ensure output directory exists ---
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured output directory exists: {output_dir}")
    except OSError as e:
        typer.secho(f"Error creating output directory '{output_dir}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # --- Copy requirements file if source exists ---
    if source_req_path:
        dest_req_path = output_dir / req_file_in_dockerfile
        try:
            # --- Check for SDK dependency (Warning only for now) ---
            req_content = source_req_path.read_text(encoding="utf-8")
            if "agentvault-server-sdk" not in req_content and "agentvault " not in req_content: # Basic check
                 # --- MODIFIED: Use typer.echo for warning ---
                 typer.echo(
                    f"Warning: '{source_req_path.name}' does not appear to include 'agentvault-server-sdk' or 'agentvault'. Ensure your agent's dependencies are listed."
                 )
                 # --- END MODIFIED ---
                 logger.warning(f"SDK dependency possibly missing from {source_req_path}")
            # --- End Check ---

            shutil.copyfile(source_req_path, dest_req_path)
            typer.echo(f"Copied requirements file to: {dest_req_path}")
            logger.info(f"Copied {source_req_path} to {dest_req_path}")
        except Exception as e:
            typer.secho(f"Error copying requirements file from '{source_req_path}' to '{dest_req_path}': {e}", fg=typer.colors.RED)
            logger.exception(f"Failed to copy requirements file.")
            raise typer.Exit(code=1)


    # --- Dockerfile Generation ---
    python_version_tag = f"{python_version}-{base_image_suffix}"
    python_major_minor = ".".join(python_version.split('.')[:2])

    context = {
        "PYTHON_VERSION_TAG": python_version_tag,
        "APP_DIR": app_dir,
        "REQUIREMENTS_FILE": req_file_in_dockerfile,
        "ENTRYPOINT_MODULE_PATH": entrypoint_path,
        "PORT": str(port),
        "PYTHON_MAJOR_MINOR": python_major_minor,
    }

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

    dockerfile_path = output_dir / "Dockerfile"
    try:
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
        typer.secho(f"Successfully generated Dockerfile: {dockerfile_path}", fg=typer.colors.GREEN)
    except IOError as e:
        typer.secho(f"Error writing Dockerfile to '{dockerfile_path}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # TODO: Add logic for .dockerignore generation (Task 2.2.A.21)
    # TODO: Add optional docker build step (Task 2.2.A.7)

if __name__ == "__main__":
    app()
