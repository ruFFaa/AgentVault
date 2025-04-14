import logging
from fastapi import FastAPI, Request, Response, status # Added Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
# --- ADDED: StaticFiles and HTMLResponse ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
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
# --- MODIFIED: Import utils router ---
from agentvault_registry.routers import agent_cards, utils
# --- END MODIFIED ---


# --- Logging Setup ---
# Basic configuration is done in config.py upon import
logger = logging.getLogger(__name__)

# --- ADDED: Define path to static files ---
STATIC_DIR = Path(__file__).parent / "static"
# --- END ADDED ---


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
# --- End Rate Limiting Middleware ---


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
# --- ADDED: Include utils router ---
app.include_router(
    utils.router,
    prefix=settings.API_V1_STR + "/utils",
    tags=["Utilities"]
)
# --- END ADDED ---

# Placeholder: Import and include other routers later
# from .routers import developers # Example
# app.include_router(developers.router, prefix=settings.API_V1_STR + "/developers", tags=["Developers"])


# --- ADDED: Mount Static Files ---
# This serves files from the 'static' directory under the path '/static'
# check_dir=False prevents FastAPI from raising an error if the dir doesn't exist on startup
# (though it should exist based on previous steps)
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Mounted static files directory: {STATIC_DIR}")
else:
    logger.error(f"Static files directory not found at: {STATIC_DIR}. UI will not be served correctly.")
# --- END ADDED ---


# --- Root Endpoint ---
@app.get("/", tags=["Status"], include_in_schema=False) # Hide from API docs
async def read_root_redirect():
    """Redirects root path to the UI."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui")


# --- ADDED: UI Endpoint ---
@app.get("/ui", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_ui():
    """Serves the main HTML file for the Web UI."""
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
# --- END ADDED ---


# --- Health Check Endpoint ---
@app.get("/health", tags=["Status"])
# Apply rate limit decorator (optional, often good to have lenient limits here)
# @limiter.limit("10/second")
async def health_check(request: Request): # Inject Request
    """Simple health check endpoint."""
    # In the future, this could check database connectivity etc.
    return {"status": "ok"}

# --- Application Lifespan Events (Optional) ---
# Example: Connect/disconnect database pool
# @app.on_event("startup")
# async def startup_event():
#     logger.info("Application startup: Connecting to database...")
#     # Add database connection logic here if needed globally
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     logger.info("Application shutdown: Disconnecting from database...")
#     # Add database disconnection logic here

logger.info(f"{settings.PROJECT_NAME} application initialized.")
