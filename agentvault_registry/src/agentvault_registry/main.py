import logging
from fastapi import FastAPI, Request, Response, status # Added Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

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


# --- Root Endpoint ---
@app.get("/", tags=["Status"])
# Apply rate limit decorator (optional, middleware covers all by default)
# @limiter.limit("5/second") # Example of route-specific limit
async def read_root(request: Request): # Inject Request to use limiter state if needed
    """Provides a simple status message for the API root."""
    logger.info("Root endpoint '/' accessed.")
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}

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
