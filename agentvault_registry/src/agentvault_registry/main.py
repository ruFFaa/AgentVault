import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import settings - this also triggers loading from .env
from .config import settings

# --- Logging Setup ---
# Basic configuration is done in config.py upon import
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for discovering and managing Agent Cards in the AgentVault ecosystem.",
    version="0.1.0", # Consider linking this to pyproject.toml version later
    openapi_url=f"{settings.API_V1_STR}/openapi.json", # Standard OpenAPI endpoint
    docs_url="/docs", # Swagger UI
    redoc_url="/redoc" # ReDoc UI
)

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
# Placeholder: Import and include routers for different parts of the API later
# from .routers import agent_cards, developers # Example
# app.include_router(agent_cards.router, prefix=settings.API_V1_STR + "/agent-cards", tags=["Agent Cards"])
# app.include_router(developers.router, prefix=settings.API_V1_STR + "/developers", tags=["Developers"])


# --- Root Endpoint ---
@app.get("/", tags=["Status"])
async def read_root():
    """Provides a simple status message for the API root."""
    logger.info("Root endpoint '/' accessed.")
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}

# --- Health Check Endpoint ---
@app.get("/health", tags=["Status"])
async def health_check():
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
