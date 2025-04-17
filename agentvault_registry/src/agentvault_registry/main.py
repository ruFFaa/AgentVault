import logging
from fastapi import FastAPI, Request, Response, status, HTTPException # Added HTTPException
from fastapi.middleware.cors import CORSMiddleware
# --- ADDED: StaticFiles and HTMLResponse ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse # Added RedirectResponse
from pathlib import Path
# --- END ADDED ---
# --- ADDED: Import json for card serving ---
import json
# --- END ADDED ---


# --- Rate Limiting Imports ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
# --- End Rate Limiting Imports ---

# Import settings - this also triggers loading from .env
from agentvault_registry.config import settings
# Import the router
# --- MODIFIED: Import auth, developers, and agent_builder routers ---
from agentvault_registry.routers import agent_cards, utils, auth, developers, agent_builder # Added agent_builder
# --- END MODIFIED ---


# --- Logging Setup ---
# Basic configuration is done in config.py upon import
logger = logging.getLogger(__name__)

# --- Define path to static files ---
STATIC_DIR = Path(__file__).parent / "static"


# --- Rate Limiter Setup ---
# Define default rate limits (adjust as needed)
# Example: 100 requests per minute for general access
default_limits = ["100/minute"]
limiter = Limiter(key_func=get_remote_address, default_limits=default_limits)
logger.info(f"Rate limiter initialized with default limits: {default_limits}")

# --- FastAPI App Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for discovering and managing Agent Cards in the AgentVault ecosystem.",
    version="0.1.0", # Consider linking this to pyproject.toml version later
    openapi_url=f"{settings.API_V1_STR}/openapi.json", # Standard OpenAPI endpoint
    docs_url="/docs", # Swagger UI
    redoc_url="/redoc" # ReDoc UI
)

# --- Apply Rate Limiting Middleware ---
# State is used by the middleware and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Add the middleware itself
app.add_middleware(SlowAPIMiddleware)
logger.info("SlowAPI rate limiting middleware added.")


# --- CORS Middleware ---
# Controls which origins (domains) can make requests to the API.
# Important for security in production.
if settings.ALLOWED_ORIGINS:
    logger.info(f"Configuring CORS with allowed origins: {settings.ALLOWED_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.ALLOWED_ORIGINS], # Handles AnyHttpUrl types
        allow_credentials=True, # Allow cookies if needed (may not be needed for this API)
        allow_methods=["*"],    # Allow all standard HTTP methods
        allow_headers=["*"],    # Allow all headers
    )
else:
    logger.warning("CORS middleware not configured as ALLOWED_ORIGINS is empty.")

# --- API Routers ---
# Include the Agent Cards router
app.include_router(
    agent_cards.router,
    prefix=settings.API_V1_STR + "/agent-cards", # Set the base path for these endpoints
    tags=["Agent Cards"] # Tag for OpenAPI documentation grouping
)
# Include utils router
app.include_router(
    utils.router,
    prefix=settings.API_V1_STR + "/utils",
    tags=["Utilities"]
)
# --- ADDED: Include Auth, Developer, and Agent Builder routers ---
app.include_router(auth.router) # Prefix is defined within auth.py
app.include_router(developers.router) # Prefix is defined within developers.py
app.include_router(agent_builder.router) # Prefix is defined within agent_builder.py
logger.info("Included developers router.")
logger.info("Included agent_builder router.") # Log inclusion
# --- END ADDED ---


# --- Mount Static Files ---
# This serves files from the 'static' directory under the path '/static'
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")
    logger.info(f"Mounted static files directory: {STATIC_DIR}")
else:
    logger.error(f"Static files directory not found at: {STATIC_DIR}. UI will not be served correctly.")


# --- Root Endpoint ---
@app.get("/", tags=["Status"], include_in_schema=False) # Hide from API docs
async def read_root_redirect():
    """Redirects root path to the UI."""
    return RedirectResponse(url="/ui")


# --- Public UI Endpoint ---
@app.get("/ui", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_ui():
    """Serves the main HTML file for the Public Registry UI."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        logger.error(f"index.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="UI index file not found.")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading index.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load UI.")

# --- ADDED: Developer Portal UI Endpoint ---
@app.get("/ui/developer", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_developer_ui():
    """Serves the main HTML file for the Developer Portal UI."""
    index_path = STATIC_DIR / "developer/index.html"
    if not index_path.is_file():
        logger.error(f"developer/index.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="Developer UI index file not found.")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading developer/index.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load Developer UI.")
# --- END ADDED ---

# --- ADDED: Specific Routes for Login/Register HTML ---
@app.get("/ui/register", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_register_ui():
    """Serves the registration HTML page."""
    register_path = STATIC_DIR / "register.html"
    if not register_path.is_file():
        logger.error(f"register.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="Registration page file not found.")
    try:
        with open(register_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading register.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load registration page.")

@app.get("/ui/login", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_login_ui():
    """Serves the login HTML page."""
    login_path = STATIC_DIR / "login.html"
    if not login_path.is_file():
        logger.error(f"login.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="Login page file not found.")
    try:
        with open(login_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading login.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load login page.")

# --- ADDED: Forgot Password UI Route ---
@app.get("/ui/forgot-password", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_forgot_password_ui():
    """Serves the forgot password HTML page."""
    forgot_path = STATIC_DIR / "forgot-password.html"
    if not forgot_path.is_file():
        logger.error(f"forgot-password.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="Forgot password page file not found.")
    try:
        with open(forgot_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading forgot-password.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load forgot password page.")

# --- ADDED: Recover with Key UI Route ---
@app.get("/ui/recover-with-key", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_recover_with_key_ui():
    """Serves the recover account with key HTML page."""
    recover_path = STATIC_DIR / "recover-with-key.html"
    if not recover_path.is_file():
        logger.error(f"recover-with-key.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="Account recovery page file not found.")
    try:
        with open(recover_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading recover-with-key.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load account recovery page.")

# --- ADDED: Set New Password UI Route ---
@app.get("/ui/set-new-password", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_set_new_password_ui():
    """Serves the set new password HTML page (used after recovery)."""
    set_pass_path = STATIC_DIR / "set-new-password.html"
    if not set_pass_path.is_file():
        logger.error(f"set-new-password.html not found in static directory: {STATIC_DIR}")
        raise HTTPException(status_code=404, detail="Set new password page file not found.")
    try:
        with open(set_pass_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception(f"Error reading set-new-password.html: {e}")
        raise HTTPException(status_code=500, detail="Could not load set new password page.")
# --- END ADDED ---


# --- Health Check Endpoint ---
@app.get("/health", tags=["Status"])
# Apply rate limit decorator (optional, often good to have lenient limits here)
# @limiter.limit("10/second")
async def health_check(request: Request): # Inject Request
    """Simple health check endpoint."""
    # In the future, this could check database connectivity etc.
    return {"status": "ok"}

logger.info(f"{settings.PROJECT_NAME} application initialized.")
