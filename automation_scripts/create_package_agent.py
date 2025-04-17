import typer
import logging
import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List # Added List
import jinja2

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="create-package-agent",
    help="Generates a boilerplate AgentVault agent project structure, including packaging artifacts.",
    add_completion=False
)

# --- Constants ---
TEMPLATE_DIR = Path(__file__).parent / "templates" / "package_agent"
EXPECTED_TEMPLATES = [
    "pyproject.toml.j2",
    "README.md.j2",
    ".gitignore.j2",
    "src/agent_package_name/__init__.py.j2",
    "src/agent_package_name/main.py.j2",
    "src/agent_package_name/agent.py.j2",
    "tests/__init__.py.j2",
    "tests/test_agent.py.j2",
    "agent-card.json.j2",
    "requirements.txt.j2",
    # --- ADDED: .env.example template ---
    ".env.example.j2",
    # --- END ADDED ---
]

# --- Helper Functions (Refactored Subprocess Calls) ---

def _run_sdk_packager(
    output_dir: Path,
    package_name: str,
    fastapi_app_variable: str,
    python_version: str,
    agent_port: int,
    # --- MODIFIED: Removed requirements_path and agent_card_path ---
    # requirements_path: Optional[Path],
    # agent_card_path: Optional[Path]
    # --- END MODIFIED ---
) -> bool:
    """Runs the agentvault-sdk package command."""
    typer.echo("\nRunning AgentVault SDK packager...")
    sdk_package_cmd = [
        sys.executable,
        "-m", "agentvault_server_sdk.packager.cli",
        "--output-dir", str(output_dir),
        "--entrypoint", f"{package_name}.main:{fastapi_app_variable}",
        "--python", python_version,
        "--port", str(agent_port),
    ]
    # --- MODIFIED: Removed conditional extend for reqs/card ---
    # if requirements_path:
    #     sdk_package_cmd.extend(["--requirements", str(requirements_path)])
    # if agent_card_path:
    #     sdk_package_cmd.extend(["--agent-card", str(agent_card_path)])
    # --- END MODIFIED ---

    logger.info(f"Executing SDK packager command: {' '.join(sdk_package_cmd)}")
    try:
        # Use check=True, but capture output to avoid interfering with CliRunner
        result = subprocess.run(sdk_package_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        logger.debug(f"SDK Packager stdout:\n{result.stdout}")
        logger.debug(f"SDK Packager stderr:\n{result.stderr}")
        typer.secho("SDK Packager completed successfully.", fg=typer.colors.GREEN)
        return True
    except FileNotFoundError:
         typer.secho(f"Error: Could not find '{sys.executable} -m agentvault_server_sdk.packager.cli'. Is the SDK installed correctly in the environment?", fg=typer.colors.RED)
         return False
    except subprocess.CalledProcessError as e:
        typer.secho(f"Error: AgentVault SDK packager failed (exit code {e.returncode}).", fg=typer.colors.RED)
        typer.echo("--- SDK Packager Output ---")
        typer.echo(e.stdout)
        typer.echo(e.stderr)
        typer.echo("---------------------------")
        return False
    except Exception as e:
        typer.secho(f"An unexpected error occurred while running the SDK packager: {e}", fg=typer.colors.RED)
        logger.exception("Unexpected error during SDK packager subprocess run.")
        return False

def _run_docker_build(output_dir: Path, tag: str) -> bool:
    """Runs the docker build command."""
    typer.echo("\nAttempting to build Docker image...")
    docker_build_cmd = ["docker", "build", "-t", tag, "."]
    logger.info(f"Executing Docker build command in '{output_dir}': {' '.join(docker_build_cmd)}")
    try:
        result = subprocess.run(docker_build_cmd, cwd=output_dir, check=True, capture_output=True, text=True, encoding='utf-8')
        logger.debug(f"Docker build stdout:\n{result.stdout}")
        logger.debug(f"Docker build stderr:\n{result.stderr}")
        typer.secho(f"Docker image '{tag}' built successfully.", fg=typer.colors.GREEN)
        return True
    except FileNotFoundError:
        typer.secho("Error: 'docker' command not found. Is Docker installed and in your PATH?", fg=typer.colors.RED)
        return False
    except subprocess.CalledProcessError as e:
        typer.secho(f"Error: Docker build failed (exit code {e.returncode}).", fg=typer.colors.RED)
        typer.echo("--- Docker Build Output ---")
        typer.echo(e.stdout)
        typer.echo(e.stderr)
        typer.echo("-------------------------")
        return False
    except Exception as e:
        typer.secho(f"An unexpected error occurred during Docker build: {e}", fg=typer.colors.RED)
        logger.exception("Unexpected error during docker build subprocess run.")
        return False

# --- (Keep other helper functions: _validate_templates_exist, _generate_agent_id, _generate_package_name) ---
def _validate_templates_exist():
    """Checks if all expected template files exist."""
    missing = []
    if not TEMPLATE_DIR.is_dir():
        logger.error(f"Template directory not found: {TEMPLATE_DIR}")
        return False, [str(TEMPLATE_DIR)]

    for template_file in EXPECTED_TEMPLATES:
        full_template_path = TEMPLATE_DIR / template_file
        if not full_template_path.is_file():
            missing.append(str(template_file))

    if missing:
        logger.error(f"Missing required template files in {TEMPLATE_DIR}: {', '.join(missing)}")
        return False, missing
    logger.debug("All expected template files found.")
    return True, []

def _generate_agent_id(agent_name: str, author_name: Optional[str]) -> str:
    """Generates a default agent ID."""
    org_part = author_name.lower().replace(" ", "-").replace("_", "-") if author_name else "my-org"
    name_part = agent_name.lower().replace(" ", "-").replace("_", "-").replace("agent", "").strip("-")
    if not name_part: name_part = "agent" # Fallback if name was just "Agent"
    return f"{org_part}/{name_part}"

def _generate_package_name(agent_name: str) -> str:
    """Generates a Python-friendly package name."""
    return agent_name.lower().replace("-", "_").replace(" ", "_").replace("agent", "").strip("_") + "_agent"


@app.command()
def main(
    agent_name: str = typer.Argument(..., help="The display name for the new agent (e.g., 'My Echo Agent')."),
    output_dir: Path = typer.Argument(..., help="Directory where the new agent project structure will be created."),
    author_name: str = typer.Option("Agent Developer", "--author", "-a", help="Developer name for pyproject.toml."),
    author_email: str = typer.Option("developer@example.com", "--email", "-e", help="Developer email for pyproject.toml."),
    python_version: str = typer.Option("3.11", "--py", help="Python version for pyproject.toml and Dockerfile."),
    sdk_version_req: str = typer.Option(">=0.1.0,<0.2.0", "--sdk-ver", help="Version requirement for agentvault-server-sdk."),
    agent_id: Optional[str] = typer.Option(None, "--id", help="Specific human-readable ID (e.g., 'my-org/my-agent'). Auto-generated if omitted."),
    agent_description: str = typer.Option("A basic AgentVault agent.", "--desc", help="Description for agent card and pyproject.toml."),
    agent_port: int = typer.Option(8001, "--port", "-p", help="Default port the agent server will listen on."),
    docker_build: bool = typer.Option(False, "--build", help="Attempt to build the Docker image after generating files."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite the output directory if it already exists."),
):
    """
    Creates a new AgentVault agent project directory with boilerplate code,
    configuration files, and Docker packaging support.
    """
    typer.echo(f"Creating new AgentVault agent project '{agent_name}' in '{output_dir}'...")

    # --- 1. Validations ---
    templates_ok, missing_templates = _validate_templates_exist()
    if not templates_ok:
        typer.secho(f"Error: Missing required template files in {TEMPLATE_DIR}. Cannot proceed.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if output_dir.exists():
        if force:
            typer.echo(f"Warning: Output directory '{output_dir}' exists. Overwriting contents due to --force flag.")
            try:
                shutil.rmtree(output_dir)
                logger.info(f"Removed existing directory: {output_dir}")
            except OSError as e:
                 typer.secho(f"Error: Could not remove existing directory '{output_dir}': {e}", fg=typer.colors.RED)
                 raise typer.Exit(code=1)
        else:
            typer.secho(f"Error: Output directory '{output_dir}' already exists. Use --force to overwrite.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    # --- 2. Create Directories ---
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        package_name = _generate_package_name(agent_name)
        src_dir = output_dir / "src" / package_name
        tests_dir = output_dir / "tests"
        src_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(exist_ok=True)
        logger.info(f"Created directory structure: {output_dir}")
        logger.info(f" - Source directory: {src_dir}")
        logger.info(f" - Tests directory: {tests_dir}")
    except OSError as e:
        typer.secho(f"Error creating directory structure in '{output_dir}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # --- 3. Prepare Template Context ---
    final_agent_id = agent_id if agent_id else _generate_agent_id(agent_name, author_name)
    context = {
        "agent_name": agent_name,
        "agent_description": agent_description,
        "agent_id": final_agent_id,
        "agent_port": agent_port,
        "author_name": author_name,
        "author_email": author_email,
        "python_version": python_version,
        "sdk_version_req": sdk_version_req,
        "package_name": package_name,
        "fastapi_app_variable": "app",
        # --- ADDED: Context for .env.example ---
        "llm_backend_type": "simple_wrapper", # Default for example, builder would pass correct one
        "wrapper_auth_type": "none", # Default for example
        # --- END ADDED ---
    }
    logger.debug(f"Template context prepared: {context}")

    # --- 4. Setup Jinja2 Environment ---
    try:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
            autoescape=False,
            keep_trailing_newline=True
        )
        logger.info(f"Jinja2 environment loaded from: {TEMPLATE_DIR}")
    except Exception as e:
        typer.secho(f"Error setting up Jinja2 environment: {e}", fg=typer.colors.RED)
        logger.exception("Jinja2 environment setup failed.")
        raise typer.Exit(code=1)

    # --- 5. Render and Write Templates ---
    typer.echo("Generating project files from templates...")
    files_generated = 0
    files_failed = 0
    # --- REMOVED: No longer need to track these paths for packager ---
    # generated_card_path: Optional[Path] = None
    # generated_req_path: Optional[Path] = None
    # --- END REMOVED ---

    for template_file in EXPECTED_TEMPLATES:
        try:
            template = env.get_template(template_file)
            rendered_content = template.render(context)

            if template_file.startswith("src/agent_package_name/"):
                relative_output = template_file.replace("src/agent_package_name/", f"src/{package_name}/", 1)
            else:
                relative_output = template_file

            if relative_output.endswith(".j2"):
                relative_output = relative_output[:-3]

            target_path = output_dir / relative_output
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(rendered_content, encoding="utf-8")
            logger.info(f"Rendered and wrote: {target_path}")
            files_generated += 1

            # --- REMOVED: No longer need to track these paths for packager ---
            # if relative_output == "agent-card.json":
            #     generated_card_path = target_path
            # if relative_output == "requirements.txt":
            #     generated_req_path = target_path
            # --- END REMOVED ---

        except jinja2.TemplateNotFound:
            typer.secho(f"Error: Template '{template_file}' not found during rendering.", fg=typer.colors.RED)
            files_failed += 1
        except Exception as e:
            typer.secho(f"Error processing template '{template_file}': {e}", fg=typer.colors.RED)
            logger.exception(f"Failed to render/write template: {template_file}")
            files_failed += 1

    if files_failed > 0:
        typer.secho(f"Errors occurred during file generation. Aborting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    else:
        typer.echo(f"Successfully generated {files_generated} project files.")

    # --- 6. Run SDK Packager (Using Helper) ---
    # --- MODIFIED: Call helper without reqs/card paths ---
    packager_success = _run_sdk_packager(
        output_dir=output_dir,
        package_name=package_name,
        fastapi_app_variable=context['fastapi_app_variable'],
        python_version=python_version,
        agent_port=agent_port
        # requirements_path=None, # Pass None explicitly
        # agent_card_path=None    # Pass None explicitly
    )
    # --- END MODIFIED ---
    if not packager_success:
        raise typer.Exit(code=1) # Exit if packager failed

    # --- 7. Optional Docker Build (Using Helper) ---
    if docker_build:
        build_success = _run_docker_build(
            output_dir=output_dir,
            tag=f"{final_agent_id.replace('/', '-')}:latest"
        )
        # Don't exit if build fails, just warn

    typer.echo(f"\n✅ Agent project '{agent_name}' created successfully in '{output_dir}'.")


if __name__ == "__main__":
    templates_ok, _ = _validate_templates_exist()
    if not templates_ok:
        print(f"ERROR: Required template files missing in {TEMPLATE_DIR}. Cannot start script.", file=sys.stderr)
        sys.exit(1)
    app()
