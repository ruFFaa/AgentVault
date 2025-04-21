import pytest
import zipfile
import io
import shutil
from pathlib import Path
import tempfile
from typing import Dict, Optional, Any, List
from unittest.mock import patch, MagicMock, ANY, call

from fastapi import status
from fastapi.testclient import TestClient

# Local imports
from agentvault_registry import schemas, models, security

# Fixtures are implicitly used from conftest.py

BUILDER_URL = "/agent-builder" # Base prefix for builder routes

# --- Test Data ---
def get_base_config(builder_type="simple_wrapper", **overrides) -> Dict:
    base = {
        "agent_name": "Test Builder Agent",
        "agent_description": "Generated via test",
        "agent_builder_type": builder_type,
        "wrapper_auth_type": "none", # Default
    }
    if builder_type == "simple_wrapper":
        base.update({
            "wrapper_llm_backend_type": "local_openai_compatible",
            "wrapper_model_name": "test-model",
        })
    elif builder_type == "adk_agent":
        base.update({
            "adk_model_name": "gemini-1.5-flash-latest",
            "adk_instruction": "Follow the user's instructions carefully.",
        })
    base.update(overrides)
    return base

# --- Mocks ---
@pytest.fixture(autouse=True)
def mock_builder_helpers(mocker):
    """Mock file system and generation helpers used by the endpoint."""
    mock_tempdir = mocker.patch("tempfile.TemporaryDirectory")
    # Make TemporaryDirectory return a real path from tmp_path fixture
    @pytest.fixture(autouse=True)
    def setup_tempdir(tmp_path):
        mock_tempdir.return_value.__enter__.return_value = tmp_path / "agent_gen_temp"
        (tmp_path / "agent_gen_temp").mkdir(exist_ok=True) # Ensure it exists for make_archive

    mock_make_archive = mocker.patch("shutil.make_archive")
    # Simulate make_archive returning the path to the created zip
    mock_make_archive.return_value = str(Path(tempfile.gettempdir()) / "mock_archive.zip")
    # Create a dummy zip file for FileResponse to find
    dummy_zip_path = Path(tempfile.gettempdir()) / "mock_archive.zip"
    with zipfile.ZipFile(dummy_zip_path, 'w') as zf:
        zf.writestr("dummy.txt", "dummy content")

    mock_path_write = mocker.patch("pathlib.Path.write_text")
    mock_path_mkdir = mocker.patch("pathlib.Path.mkdir")

    yield {
        "tempdir": mock_tempdir,
        "make_archive": mock_make_archive,
        "write_text": mock_path_write,
        "mkdir": mock_path_mkdir,
        "dummy_zip_path": dummy_zip_path, # Return path for cleanup
    }

    # Cleanup dummy zip
    if dummy_zip_path.exists():
        dummy_zip_path.unlink()


# --- Test Cases ---

def test_generate_simple_wrapper_success(
    sync_test_client: TestClient,
    mock_developer: models.Developer,
    override_get_current_developer: None,
    mock_builder_helpers
):
    """Test successful generation of a simple wrapper agent package."""
    config_payload = get_base_config(
        builder_type="simple_wrapper",
        agent_name="My Simple Wrapper",
        human_readable_id="test-dev/simple-wrap",
        wrapper_llm_backend_type="openai_api",
        wrapper_model_name="gpt-4o",
        wrapper_system_prompt="You are helpful."
    )

    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )

    # --- Check status and headers, not content ---
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("content-type") == "application/zip"
    assert "content-disposition" in response.headers
    assert 'filename="my_simple_wrapper_agent.zip"' in response.headers["content-disposition"]

    mock_builder_helpers["make_archive"].assert_called_once()
    mock_builder_helpers["write_text"].assert_called() # Check files were written


def test_generate_adk_agent_success(
    sync_test_client: TestClient,
    mock_developer: models.Developer,
    override_get_current_developer: None,
    mock_builder_helpers
):
    """Test successful generation of an ADK agent package."""
    config_payload = get_base_config(
        builder_type="adk_agent",
        agent_name="My ADK Agent",
        adk_model_name="gemini-1.5-pro-latest",
        adk_instruction="Be a research assistant.",
        adk_tools=["get_current_time", "google_search"]
    )

    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )

    # --- Check status and headers, not content ---
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("content-type") == "application/zip"
    assert "content-disposition" in response.headers
    assert 'filename="my_adk_agent.zip"' in response.headers["content-disposition"]

    mock_builder_helpers["make_archive"].assert_called_once()
    mock_builder_helpers["write_text"].assert_called()


def test_generate_auth_failure(sync_test_client: TestClient):
    """Test endpoint requires authentication."""
    config_payload = get_base_config()
    response = sync_test_client.post(f"{BUILDER_URL}/generate", json=config_payload)
    # Depends(get_current_developer) should raise 401/403 without token
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


def test_generate_validation_missing_type(sync_test_client: TestClient, override_get_current_developer: None):
    """Test validation error for missing agent_builder_type."""
    config_payload = get_base_config()
    del config_payload["agent_builder_type"] # Remove required field
    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # --- Check detail structure ---
    details = response.json()["detail"]
    assert isinstance(details, list)
    assert any(err.get("loc") == ["body", "agent_builder_type"] and err.get("type") == "missing" for err in details)


def test_generate_validation_missing_wrapper_field(sync_test_client: TestClient, override_get_current_developer: None):
    """Test validation error for missing required field for simple_wrapper."""
    config_payload = get_base_config(builder_type="simple_wrapper")
    del config_payload["wrapper_model_name"] # Remove required field for this type
    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # --- Check detail structure ---
    details = response.json()["detail"]
    assert isinstance(details, list)
    assert any("'wrapper_model_name' is required" in err.get("msg", "") for err in details)


def test_generate_validation_missing_adk_field(sync_test_client: TestClient, override_get_current_developer: None):
    """Test validation error for missing required field for adk_agent."""
    config_payload = get_base_config(builder_type="adk_agent")
    del config_payload["adk_instruction"] # Remove required field for this type
    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # --- Check detail structure ---
    details = response.json()["detail"]
    assert isinstance(details, list)
    assert any("'adk_instruction' is required" in err.get("msg", "") for err in details)


def test_generate_validation_missing_service_id_for_apikey(sync_test_client: TestClient, override_get_current_developer: None):
    """Test validation error when apiKey auth is chosen but service_id is missing."""
    config_payload = get_base_config(
        builder_type="adk_agent", # Type doesn't matter here
        wrapper_auth_type="apiKey",
        wrapper_service_id=None # Explicitly None or missing
    )
    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # --- Check detail structure ---
    details = response.json()["detail"]
    assert isinstance(details, list)
    assert any("'wrapper_service_id' is required" in err.get("msg", "") for err in details)

# --- MODIFIED: Raise OSError and check for "OSError" ---
@patch("shutil.make_archive", side_effect=OSError("Disk full!")) # Mock archive creation failure
def test_generate_archive_creation_error(
    mock_make_archive,
    sync_test_client: TestClient,
    mock_developer: models.Developer,
    override_get_current_developer: None,
    mock_builder_helpers # Need this for other mocks like write_text
):
    """Test internal server error if zip archiving fails."""
    config_payload = get_base_config()

    response = sync_test_client.post(
        f"{BUILDER_URL}/generate",
        json=config_payload,
        headers={"Authorization": "Bearer fake-token"}
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Internal Server Error" in response.json()["detail"]
    assert "OSError" in response.json()["detail"] # Check if correct exception type is included
    mock_make_archive.assert_called_once()
# --- END MODIFIED ---
