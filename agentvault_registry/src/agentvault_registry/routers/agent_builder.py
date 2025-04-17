import logging
import os
import sys
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List

import jinja2
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

# Local imports
from agentvault_registry import schemas, models, security
from agentvault_registry.config import settings # May need BASE_URL etc. later

logger = logging.getLogger(__name__)

# --- Helper Functions ---
# (Copied from create_package_agent.py for now, consider moving to shared utils later)
def _generate_agent_id(agent_name: str, author_name: Optional[str]) -> str:
    """Generates a default agent ID."""
    org_part = author_name.lower().replace(" ", "-").replace("_", "-") if author_name else "my-org"
    name_part = agent_name.lower().replace(" ", "-").replace("_", "-").replace("agent", "").strip("-")
    if not name_part: name_part = "agent" # Fallback if name was just "Agent"
    return f"{org_part}/{name_part}"

def _generate_package_name(agent_name: str) -> str:
    """Generates a Python-friendly package name."""
    return agent_name.lower().replace("-", "_").replace(" ", "_").replace("agent", "").strip("_") + "_agent"

# --- Router Setup ---
router = APIRouter(
    prefix="/agent-builder",
    tags=["Agent Builder"],
    dependencies=[Depends(security.get_current_developer)] # Require developer login
)

# --- Template Configuration ---
# Assumes templates are located relative to this file's location in the src structure
TEMPLATE_ROOT_DIR = Path(__file__).parent.parent / "agent_templates"
COMMON_TEMPLATE_DIR = TEMPLATE_ROOT_DIR / "common"
SIMPLE_WRAPPER_TEMPLATE_DIR = TEMPLATE_ROOT_DIR / "simple_wrapper"
ADK_AGENT_TEMPLATE_DIR = TEMPLATE_ROOT_DIR / "adk_agent"

# --- Endpoint ---
@router.post(
    "/generate",
    response_class=FileResponse, # Specify FileResponse for direct download
    summary="Generate Agent Package",
    description="Generates a downloadable ZIP archive containing boilerplate code and configuration for a new AgentVault agent based on the provided configuration.",
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "Successful Response: ZIP archive containing the generated agent project.",
        },
        422: {"description": "Validation Error in configuration."},
        500: {"description": "Internal Server Error during generation."},
    }
)
async def generate_agent_package(
    config: schemas.AgentBuildConfig,
    current_developer: models.Developer = Depends(security.get_current_developer) # Get authenticated developer
):
    """
    Generates agent code based on input configuration and returns a ZIP file.
    """
    logger.info(f"Received agent generation request from developer {current_developer.id} for agent '{config.agent_name}', type '{config.agent_builder_type}'.")

    # --- 1. Determine Template Directory and Required Files ---
    template_subdir_path: Path
    type_specific_templates: List[str]
    common_templates: List[str] = [
        ".gitignore.j2", "Dockerfile.j2", ".env.example.j2", "INSTRUCTIONS.md.j2"
    ]

    if config.agent_builder_type == "simple_wrapper":
        template_subdir_path = SIMPLE_WRAPPER_TEMPLATE_DIR
        type_specific_templates = ["agent.py.j2", "main.py.j2", "requirements.txt.j2", "agent-card.json.j2"]
        # Add specific context needed only for simple wrapper
        llm_backend_type = config.wrapper_llm_backend_type
    elif config.agent_builder_type == "adk_agent":
        template_subdir_path = ADK_AGENT_TEMPLATE_DIR
        type_specific_templates = ["agent.py.j2", "main.py.j2", "tools.py.j2", "requirements.txt.j2", "agent-card.json.j2"]
        # Add specific context needed only for ADK agent
        llm_backend_type = "adk_native" # Set backend type for common templates
    else:
        # Should be caught by Pydantic validation, but double-check
        logger.error(f"Invalid agent_builder_type received: {config.agent_builder_type}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid agent builder type specified.")

    # --- 2. Prepare Template Context ---
    package_name = _generate_package_name(config.agent_name)
    final_agent_id = config.human_readable_id or _generate_agent_id(config.agent_name, current_developer.name)
    # Use defaults for missing optional fields if necessary (though Pydantic handles defaults)
    context = {
        "agent_name": config.agent_name,
        "agent_description": config.agent_description,
        "agent_id": final_agent_id,
        "agent_port": 8001, # Default port, could make configurable later
        "author_name": current_developer.name,
        "author_email": current_developer.email,
        "python_version": "3.11", # Default, could make configurable later
        "base_image_suffix": "slim-bookworm", # Default, could make configurable later
        "sdk_version_req": ">=0.1.0,<0.2.0", # Default, could make configurable later
        "package_name": package_name,
        "fastapi_app_variable": "app",
        # --- Type Specific ---
        "agent_builder_type": config.agent_builder_type,
        "wrapper_llm_backend_type": config.wrapper_llm_backend_type,
        "wrapper_model_name": config.wrapper_model_name,
        "wrapper_system_prompt": config.wrapper_system_prompt,
        "adk_model_name": config.adk_model_name,
        "adk_instruction": config.adk_instruction,
        "adk_tools": config.adk_tools or [], # Ensure it's a list
        "wrapper_auth_type": config.wrapper_auth_type,
        "wrapper_service_id": config.wrapper_service_id,
        # --- Add llm_backend_type for common templates ---
        "llm_backend_type": llm_backend_type
    }
    logger.debug(f"Template context generated for task {final_agent_id}: {context}")

    # --- 3. Generate Files in Temporary Directory ---
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            logger.info(f"Created temporary directory for generation: {tmpdir_path}")

            # Create necessary subdirectories within temp dir
            src_dir = tmpdir_path / "src" / package_name
            tests_dir = tmpdir_path / "tests"
            src_dir.mkdir(parents=True, exist_ok=True)
            tests_dir.mkdir(exist_ok=True)

            # Setup Jinja2 environment
            # Load templates from BOTH common and type-specific directories
            jinja_loader = jinja2.FileSystemLoader([COMMON_TEMPLATE_DIR, template_subdir_path])
            env = jinja2.Environment(loader=jinja_loader, autoescape=False, keep_trailing_newline=True)

            # Render common templates
            for template_name in common_templates:
                template = env.get_template(template_name)
                rendered_content = template.render(context)
                target_filename = template_name[:-3] # Remove .j2
                target_path = tmpdir_path / target_filename
                target_path.write_text(rendered_content, encoding="utf-8")
                logger.debug(f"Rendered common template '{template_name}' to '{target_path}'")

            # Render type-specific templates
            for template_name in type_specific_templates:
                template = env.get_template(template_name)
                rendered_content = template.render(context)
                target_filename = template_name[:-3] # Remove .j2
                # Determine target path (src, tests, or root)
                if template_name.startswith("agent.py") or template_name.startswith("main.py") or template_name.startswith("tools.py"):
                    target_path = src_dir / target_filename
                elif template_name.startswith("test_"):
                     target_path = tests_dir / target_filename
                else:
                    target_path = tmpdir_path / target_filename
                target_path.parent.mkdir(parents=True, exist_ok=True) # Ensure parent exists
                target_path.write_text(rendered_content, encoding="utf-8")
                logger.debug(f"Rendered type-specific template '{template_name}' to '{target_path}'")

            # --- 4. Create ZIP Archive ---
            zip_filename_base = f"{package_name}_generated"
            # Create zip in a location *outside* the temp dir being zipped
            zip_output_path = Path(tempfile.gettempdir()) / zip_filename_base
            logger.info(f"Creating ZIP archive from '{tmpdir_path}' to '{zip_output_path}.zip'")
            zip_path_str = shutil.make_archive(
                base_name=str(zip_output_path), # Path without extension
                format='zip',
                root_dir=tmpdir_path # Directory to archive contents of
            )
            zip_path = Path(zip_path_str)

            if not zip_path.is_file():
                raise IOError("Failed to create ZIP archive.")

            logger.info(f"ZIP archive created successfully: {zip_path}")

            # --- 5. Return FileResponse ---
            # Use the package_name for the download filename
            download_filename = f"{package_name}.zip"
            return FileResponse(
                path=zip_path,
                media_type='application/zip',
                filename=download_filename
            )

    except jinja2.TemplateNotFound as e:
        logger.error(f"Template not found during generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: Template file missing ({e})")
    except Exception as e:
        logger.exception(f"Error during agent package generation for '{config.agent_name}'")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {type(e).__name__}")

# --- Include this router in main.py ---
# (Ensure this is done in agentvault_registry/main.py)
# from .routers import agent_builder
# app.include_router(agent_builder.router)
