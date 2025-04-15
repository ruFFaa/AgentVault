import typer
import logging
import sys
import os
import json
import httpx
from pathlib import Path
from typing import Optional, Dict, Any

# Attempt to import AgentVault components
try:
    from agentvault import KeyManager, exceptions as av_exceptions
    _AGENTVAULT_LIB_AVAILABLE = True
except ImportError:
    print("ERROR: Failed to import agentvault library. Please ensure it's installed.", file=sys.stderr)
    KeyManager = None # type: ignore
    av_exceptions = None # type: ignore
    _AGENTVAULT_LIB_AVAILABLE = False

# Attempt to import Jinja2 and PyYAML (optional for now)
try:
    import jinja2
    _JINJA_AVAILABLE = True
except ImportError:
    jinja2 = None # type: ignore
    _JINJA_AVAILABLE = False

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    yaml = None # type: ignore
    _YAML_AVAILABLE = False


# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="deploy-register-agent",
    help="Handles agent deployment templating and registration/update with the AgentVault Registry.",
    add_completion=False
)

# --- Helper Functions (Placeholders) ---

def _render_deployment_template(template_path: Path, vars_path: Optional[Path]) -> Optional[str]:
    """Loads variables, renders the Jinja2 template."""
    if not _JINJA_AVAILABLE:
        typer.secho("Error: Jinja2 library not found, cannot process deployment template.", fg=typer.colors.RED)
        return None
    if not _YAML_AVAILABLE and vars_path and vars_path.suffix.lower() == ".yaml":
         typer.secho("Error: PyYAML library not found, cannot process YAML variable file.", fg=typer.colors.RED)
         return None

    logger.info(f"Processing deployment template: {template_path}")
    template_dir = template_path.parent
    template_name = template_path.name
    variables = {}

    # Load variables if provided
    if vars_path:
        logger.info(f"Loading deployment variables from: {vars_path}")
        try:
            content = vars_path.read_text(encoding="utf-8")
            if vars_path.suffix.lower() == ".json":
                variables = json.loads(content)
            elif vars_path.suffix.lower() in [".yaml", ".yml"] and _YAML_AVAILABLE:
                 variables = yaml.safe_load(content)
            else:
                 typer.secho(f"Error: Unsupported variable file format: {vars_path.suffix}. Use .json or .yaml (requires PyYAML).", fg=typer.colors.RED)
                 return None
            if not isinstance(variables, dict):
                typer.secho(f"Error: Variable file {vars_path} does not contain a valid dictionary/object.", fg=typer.colors.RED)
                return None
        except Exception as e:
            typer.secho(f"Error reading or parsing variable file {vars_path}: {e}", fg=typer.colors.RED)
            logger.exception("Variable file processing failed.")
            return None

    # Render template
    try:
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), autoescape=False)
        template = env.get_template(template_name)
        rendered_content = template.render(variables)
        logger.info("Deployment template rendered successfully.")
        return rendered_content
    except Exception as e:
        typer.secho(f"Error rendering deployment template {template_path}: {e}", fg=typer.colors.RED)
        logger.exception("Template rendering failed.")
        return None

def _apply_deployment(manifest_content: str):
    """Placeholder for applying the deployment (e.g., kubectl apply)."""
    typer.echo("\n--- Deployment Manifest (Placeholder) ---")
    typer.echo(manifest_content)
    typer.echo("-----------------------------------------")
    typer.echo("Placeholder: Apply this manifest using appropriate tools (e.g., kubectl apply -f -).")
    # Example using subprocess (requires kubectl in PATH):
    # try:
    #     process = subprocess.run(
    #         ["kubectl", "apply", "-f", "-"],
    #         input=manifest_content,
    #         capture_output=True, text=True, check=True, encoding='utf-8'
    #     )
    #     typer.secho("kubectl apply successful.", fg=typer.colors.GREEN)
    #     logger.info(f"kubectl apply stdout:\n{process.stdout}")
    #     if process.stderr: logger.warning(f"kubectl apply stderr:\n{process.stderr}")
    #     return True
    # except FileNotFoundError:
    #     typer.secho("Error: 'kubectl' command not found. Cannot apply manifest.", fg=typer.colors.RED)
    #     return False
    # except subprocess.CalledProcessError as e:
    #     typer.secho(f"Error: kubectl apply failed (exit code {e.returncode}).", fg=typer.colors.RED)
    #     typer.echo(f"Stderr:\n{e.stderr}")
    #     return False
    # except Exception as e:
    #      typer.secho(f"An unexpected error occurred during kubectl apply: {e}", fg=typer.colors.RED)
    #      return False
    return True # Placeholder returns success

async def _register_or_update_card(
    registry_url: str,
    developer_api_key: str,
    card_data: Dict[str, Any],
    card_file_path: Path # For logging/context
) -> bool:
    """Registers a new card or updates an existing one based on ID."""
    if not card_data or not isinstance(card_data, dict):
         typer.secho("Error: Invalid card data provided for registration.", fg=typer.colors.RED)
         return False

    # Extract ID for checking existence (assuming it's present after validation)
    # A robust implementation might re-validate here or trust prior steps
    card_id = card_data.get("humanReadableId") # Or maybe a UUID if the card format changes
    if not card_id:
         # Fallback or error? Let's assume create_package_agent generated one.
         # If loaded from existing file, it *must* have an ID.
         # For now, let's error if it's missing from the loaded data.
         typer.secho(f"Error: Cannot register/update card from {card_file_path} - missing 'humanReadableId'.", fg=typer.colors.RED)
         return False

    api_base = registry_url.rstrip("/") + "/api/v1/agent-cards"
    headers = {"X-Api-Key": developer_api_key, "Content-Type": "application/json"}
    card_payload = {"card_data": card_data}

    async with httpx.AsyncClient() as client:
        # Check if card exists (using GET by ID - adjust if registry uses humanReadableId)
        # This assumes the registry API has a GET /agent-cards/id/{humanReadableId} endpoint
        # If not, we might have to try PUT first and fallback to POST on 404.
        # Let's assume a GET by ID exists for now.
        check_url = f"{api_base}/id/{card_id}" # Assuming endpoint exists
        logger.info(f"Checking if agent card '{card_id}' exists at {check_url}...")
        try:
            check_response = await client.get(check_url) # No auth needed for public GET
            card_exists = check_response.status_code == 200
        except httpx.RequestError as e:
            typer.secho(f"Error checking registry for card '{card_id}': {e}", fg=typer.colors.RED)
            return False

        if card_exists:
            # Update existing card (PUT)
            update_url = f"{api_base}/{card_id}" # Assuming PUT uses UUID if available, or maybe humanReadableId? Needs clarification. Let's assume UUID for now if present, else error?
            # For now, let's assume PUT uses the humanReadableId if that's our primary key
            # This needs alignment with the actual registry API design.
            # Let's *assume* for now the registry PUT uses the ID found *within* the card_data payload if needed,
            # or that the POST/PUT logic handles ID generation/lookup correctly.
            # A safer approach might be to always POST and let the registry handle conflicts if ID exists.
            # Let's try POST first, then PUT on conflict? No, let's check then PUT/POST.

            # We need the UUID from the card data if it exists, or from the check response?
            # Let's assume the check response gives us the UUID if needed.
            card_uuid = None
            try:
                card_uuid = check_response.json().get("id")
            except Exception:
                logger.warning(f"Could not extract UUID from existing card check response for {card_id}.")

            if not card_uuid:
                 typer.secho(f"Error: Card '{card_id}' exists but could not determine its UUID for update.", fg=typer.colors.RED)
                 return False

            update_url = f"{api_base}/{card_uuid}"
            logger.info(f"Card '{card_id}' found (UUID: {card_uuid}). Attempting update (PUT {update_url})...")
            try:
                response = await client.put(update_url, json=card_payload, headers=headers)
                response.raise_for_status()
                typer.secho(f"Agent card '{card_id}' updated successfully.", fg=typer.colors.GREEN)
                return True
            except httpx.HTTPStatusError as e:
                typer.secho(f"Error updating agent card '{card_id}' (HTTP {e.response.status_code}): {e.response.text}", fg=typer.colors.RED)
                return False
            except httpx.RequestError as e:
                typer.secho(f"Network error updating agent card '{card_id}': {e}", fg=typer.colors.RED)
                return False

        else:
            # Create new card (POST)
            create_url = api_base + "/"
            logger.info(f"Card '{card_id}' not found. Attempting creation (POST {create_url})...")
            try:
                response = await client.post(create_url, json=card_payload, headers=headers)
                response.raise_for_status() # Raises for 4xx/5xx
                typer.secho(f"Agent card '{card_id}' created successfully.", fg=typer.colors.GREEN)
                return True
            except httpx.HTTPStatusError as e:
                typer.secho(f"Error creating agent card '{card_id}' (HTTP {e.response.status_code}): {e.response.text}", fg=typer.colors.RED)
                return False
            except httpx.RequestError as e:
                typer.secho(f"Network error creating agent card '{card_id}': {e}", fg=typer.colors.RED)
                return False


# --- Main Command ---
@app.command()
def main(
    agent_dir: Path = typer.Argument(
        ...,
        help="Path to the agent project directory (containing agent-card.json).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True
    ),
    registry_url: Optional[str] = typer.Option(
        os.environ.get("AGENTVAULT_REGISTRY_URL", "http://localhost:8000"),
        "--registry", "-r",
        help="URL of the AgentVault Registry API. Defaults to AGENTVAULT_REGISTRY_URL env var or http://localhost:8000.",
        show_default=False # Show calculated default in help text instead
    ),
    developer_key_service: str = typer.Option(
        ..., # Make required
        "--dev-key-id",
        help="Service ID used to look up the Developer API key in local KeyManager (e.g., 'my-registry-key'). Required for registry operations."
    ),
    deployment_template: Optional[Path] = typer.Option(
        None,
        "--template", "-t",
        help="Path to a Jinja2 template for deployment manifests (e.g., Kubernetes YAML).",
        exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    deployment_vars: Optional[Path] = typer.Option(
        None,
        "--vars", "-v",
        help="Path to a YAML/JSON file containing variables for the deployment template.",
        exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    skip_deploy: bool = typer.Option(False, "--skip-deploy", help="Skip the deployment templating/application step."),
    skip_register: bool = typer.Option(False, "--skip-register", help="Skip the registry submission/update step."),
):
    """
    Deploys an agent (via templating) and registers/updates its card in the AgentVault Registry.
    """
    if not _AGENTVAULT_LIB_AVAILABLE:
        typer.secho("Error: Core 'agentvault' library not found. Cannot proceed.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Starting deployment/registration process for agent in: {agent_dir}")

    # --- 1. Load Agent Card ---
    card_file_path = agent_dir / "agent-card.json"
    if not card_file_path.is_file():
        typer.secho(f"Error: agent-card.json not found in directory: {agent_dir}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        card_data = json.loads(card_file_path.read_text(encoding="utf-8"))
        # Basic check - could add full validation here if desired
        if not isinstance(card_data, dict) or "humanReadableId" not in card_data:
             typer.secho(f"Error: Invalid format or missing 'humanReadableId' in {card_file_path}", fg=typer.colors.RED)
             raise typer.Exit(code=1)
        logger.info(f"Successfully loaded agent card: {card_data.get('humanReadableId')}")
    except Exception as e:
        typer.secho(f"Error reading or parsing {card_file_path}: {e}", fg=typer.colors.RED)
        logger.exception("Agent card loading failed.")
        raise typer.Exit(code=1)

    # --- 2. Get Developer API Key ---
    dev_api_key: Optional[str] = None
    if not skip_register: # Only need key if registering
        typer.echo(f"Retrieving developer API key using service ID: '{developer_key_service}'...")
        try:
            # Enable keyring by default for automation scripts
            key_manager = KeyManager(use_keyring=True)
            dev_api_key = key_manager.get_key(developer_key_service)
            if not dev_api_key:
                typer.secho(f"Error: Developer API key not found for service ID '{developer_key_service}'.", fg=typer.colors.RED)
                typer.echo("Use 'agentvault config set <service_id> --keyring' to store it.")
                raise typer.Exit(code=1)
            logger.info("Developer API key retrieved successfully.")
        except av_exceptions.KeyManagementError as e:
             typer.secho(f"Error accessing KeyManager: {e}", fg=typer.colors.RED)
             raise typer.Exit(code=1)
        except Exception as e:
             typer.secho(f"Unexpected error retrieving developer key: {e}", fg=typer.colors.RED)
             logger.exception("Developer key retrieval failed.")
             raise typer.Exit(code=1)

    # --- 3. Deployment Templating (Placeholder) ---
    if not skip_deploy:
        if deployment_template:
            rendered_manifest = _render_deployment_template(deployment_template, deployment_vars)
            if rendered_manifest:
                apply_success = _apply_deployment(rendered_manifest)
                if not apply_success:
                    typer.secho("Deployment application step failed (see logs).", fg=typer.colors.YELLOW)
                    # Decide whether to continue to registration or exit
                    # raise typer.Exit(code=1)
            else:
                 typer.secho("Deployment template rendering failed. Skipping deployment.", fg=typer.colors.RED)
                 # Decide whether to continue to registration or exit
                 # raise typer.Exit(code=1)
        else:
            typer.echo("Skipping deployment: No deployment template provided.")
    else:
        typer.echo("Skipping deployment step as requested.")

    # --- 4. Register/Update Card (Placeholder) ---
    if not skip_register:
        if not dev_api_key: # Should have been caught earlier, but double check
             typer.secho("Error: Cannot register/update card without developer API key.", fg=typer.colors.RED)
             raise typer.Exit(code=1)
        if not registry_url:
             typer.secho("Error: Cannot register/update card without registry URL.", fg=typer.colors.RED)
             raise typer.Exit(code=1)

        typer.echo(f"Attempting to register/update agent card at registry: {registry_url}")
        # Run the async registration function
        try:
            success = asyncio.run(_register_or_update_card(registry_url, dev_api_key, card_data, card_file_path))
            if not success:
                 typer.secho("Registry registration/update failed.", fg=typer.colors.RED)
                 raise typer.Exit(code=1)
        except Exception as e:
             typer.secho(f"An unexpected error occurred during registry interaction: {e}", fg=typer.colors.RED)
             logger.exception("Registry interaction failed.")
             raise typer.Exit(code=1)

    else:
        typer.echo("Skipping registry registration/update step as requested.")

    typer.echo("\n✅ Deployment/Registration script finished.")


if __name__ == "__main__":
    if not _AGENTVAULT_LIB_AVAILABLE:
        print("FATAL: AgentVault library not found, cannot run script.", file=sys.stderr)
        sys.exit(1)
    app()
