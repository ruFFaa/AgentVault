import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import io # Import io for mock_open

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

# Import the FastAPI app instance and the dependency class
from agentvault_registry.main import app, StaticFileReader

# Use the sync_test_client fixture implicitly defined in conftest.py

# --- Test /health endpoint ---

def test_health_check(sync_test_client: TestClient):
    """Test the /health endpoint returns status ok."""
    response = sync_test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

# --- Test / endpoint redirect ---

@patch("agentvault_registry.main.StaticFileReader") # Patch the dependency class
def test_root_redirect(mock_reader_cls, sync_test_client: TestClient):
    """Test the root / endpoint redirects to /ui."""
    # Configure the mock instance that will be returned
    mock_reader_instance = MagicMock()
    mock_reader_instance.get_content.return_value = "<html><body>Mock UI Page</body></html>"
    mock_reader_cls.return_value = mock_reader_instance

    # Override the dependency *before* making the request that follows the redirect
    app.dependency_overrides[StaticFileReader] = lambda: mock_reader_instance

    # Make request without following redirects to check status code and location header
    response = sync_test_client.get("/", allow_redirects=False)
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == "/ui"

    # Also test that following the redirect works
    response_followed = sync_test_client.get("/") # Follow redirect
    assert response_followed.status_code == status.HTTP_200_OK
    assert "<body>" in response_followed.text
    assert "Mock UI Page" in response_followed.text
    # Check the mock was called for the target page
    mock_reader_instance.get_content.assert_called_once_with("index.html")

    # Clear overrides after test
    app.dependency_overrides = {}


# --- Tests for UI HTML endpoints ---

# Define the routes and their corresponding filenames and expected error messages
# (Extract this from main.py or define manually)
# Note: This needs to be kept in sync with main.py if routes are added/changed
UI_ROUTES_FILES_ERRORS = {
    "/ui": {"file": "index.html", "err_404": "UI index file not found.", "err_500": "Could not load UI."},
    "/ui/developer": {"file": "developer/index.html", "err_404": "Developer UI index file not found.", "err_500": "Could not load Developer UI."},
    "/ui/register": {"file": "register.html", "err_404": "Registration page file not found.", "err_500": "Could not load registration page."},
    "/ui/login": {"file": "login.html", "err_404": "Login page file not found.", "err_500": "Could not load login page."},
    "/ui/forgot-password": {"file": "forgot-password.html", "err_404": "Forgot password page file not found.", "err_500": "Could not load forgot password page."},
    "/ui/recover-with-key": {"file": "recover-with-key.html", "err_404": "Account recovery page file not found.", "err_500": "Could not load account recovery page."},
    "/ui/set-new-password": {"file": "set-new-password.html", "err_404": "Set new password page file not found.", "err_500": "Could not load set new password page."},
    "/ui/verify-success": {"file": "verify-success.html", "err_404": "Verification success page not found.", "err_500": "Could not load verification success page."},
    "/ui/verify-failed": {"file": "verify-failed.html", "err_404": "Verification failed page not found.", "err_500": "Could not load verification failed page."},
    "/ui/reset-requested": {"file": "reset-requested.html", "err_404": "Reset requested page not found.", "err_500": "Could not load reset requested page."},
    "/ui/reset-success": {"file": "reset-success.html", "err_404": "Reset success page not found.", "err_500": "Could not load reset success page."},
    "/ui/reset-failed": {"file": "reset-failed.html", "err_404": "Reset failed page not found.", "err_500": "Could not load reset failed page."},
}

# --- Mock Dependency Class ---
class MockStaticFileReader:
    """Mock implementation of StaticFileReader for testing."""
    def __init__(self, behavior="success", content=""):
        self.behavior = behavior
        self.content = content
        self.filename_called_with = None
        self.call_count = 0

    def get_content(self, filename: str) -> str:
        """Mocked get_content method."""
        self.filename_called_with = filename
        self.call_count += 1
        if self.behavior == "success":
            return self.content
        elif self.behavior == "not_found":
            raise FileNotFoundError(f"Mock: {filename} not found")
        elif self.behavior == "read_error":
            raise IOError(f"Mock: Cannot read {filename}")
        else:
            raise ValueError("Invalid mock behavior")

# --- Fixture for Dependency Override ---
@pytest.fixture
def override_dependency(request):
    """Fixture to manage dependency overrides for StaticFileReader."""
    # Default mock behavior (can be overridden by test markers)
    behavior = "success"
    content = "<html><body>Default Mock Content</body></html>"

    if hasattr(request, "param"):
        if isinstance(request.param, dict):
            behavior = request.param.get("behavior", behavior)
            content = request.param.get("content", content)
        else: # Assume it's just the behavior string
            behavior = request.param

    mock_reader = MockStaticFileReader(behavior=behavior, content=content)

    # Apply the override before the test runs
    original_override = app.dependency_overrides.get(StaticFileReader)
    app.dependency_overrides[StaticFileReader] = lambda: mock_reader

    yield mock_reader # Provide the mock instance to the test if needed

    # Clear the override after the test finishes
    if original_override:
        app.dependency_overrides[StaticFileReader] = original_override
    else:
        # Use try-except for robustness, in case the key wasn't added
        try:
            del app.dependency_overrides[StaticFileReader]
        except KeyError:
            pass


# --- Test Cases ---
@pytest.mark.parametrize("route_path, route_info", UI_ROUTES_FILES_ERRORS.items())
@pytest.mark.parametrize("override_dependency", ["success"], indirect=True)
def test_ui_routes_success(
    sync_test_client: TestClient,
    override_dependency: MockStaticFileReader, # Use the fixture
    route_path: str,
    route_info: dict
):
    """Test that UI routes return 200 OK and HTML content when file exists."""
    filename = route_info["file"]
    # Arrange: Override fixture provides the mock configured for success
    # Set specific content for this test run
    mock_html_content = f"<html><body>Mock Page for {filename}</body></html>"
    override_dependency.content = mock_html_content

    # Act
    response = sync_test_client.get(route_path)

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "<body>" in response.text
    assert f"Mock Page for {filename}" in response.text
    assert override_dependency.filename_called_with == filename # Verify correct file requested
    assert override_dependency.call_count == 1


@pytest.mark.parametrize("route_path, route_info", UI_ROUTES_FILES_ERRORS.items())
@pytest.mark.parametrize("override_dependency", ["not_found"], indirect=True)
def test_ui_routes_file_not_found(
    sync_test_client: TestClient,
    override_dependency: MockStaticFileReader, # Use the fixture
    route_path: str,
    route_info: dict
):
    """Test that UI routes return 404 when the HTML file is missing."""
    filename = route_info["file"]
    expected_detail = route_info["err_404"]
    # Arrange: Override fixture provides the mock configured for not_found

    # Act
    response = sync_test_client.get(route_path)

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # --- MODIFIED: Assert exact detail message ---
    assert response.json() == {"detail": expected_detail}
    # --- END MODIFIED ---
    assert override_dependency.filename_called_with == filename # Verify correct file requested
    assert override_dependency.call_count == 1


@pytest.mark.parametrize("route_path, route_info", UI_ROUTES_FILES_ERRORS.items())
@pytest.mark.parametrize("override_dependency", ["read_error"], indirect=True)
def test_ui_routes_read_error(
    sync_test_client: TestClient,
    override_dependency: MockStaticFileReader, # Use the fixture
    route_path: str,
    route_info: dict
):
    """Test that UI routes return 500 if reading the HTML file fails."""
    filename = route_info["file"]
    expected_detail = route_info["err_500"]
    # Arrange: Override fixture provides the mock configured for read_error

    # Act
    response = sync_test_client.get(route_path)

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # --- MODIFIED: Assert exact detail message ---
    assert response.json() == {"detail": expected_detail}
    # --- END MODIFIED ---
    assert override_dependency.filename_called_with == filename # Verify correct file requested
    assert override_dependency.call_count == 1
