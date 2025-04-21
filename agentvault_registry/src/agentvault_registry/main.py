import logging
from fastapi import FastAPI, Request, Response, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
import json


# --- Rate Limiting Imports ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
# --- End Rate Limiting Imports ---

# Import settings - this also triggers loading from .env
from agentvault_registry.config import settings
# Import the router
from agentvault_registry.routers import agent_cards, utils, auth, developers, agent_builder


# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Define path to static files ---
STATIC_DIR = Path(__file__).parent / "static"


# --- Rate Limiter Setup ---
default_limits = ["100/minute"]
limiter = Limiter(key_func=get_remote_address, default_limits=default_limits)
logger.info(f"Rate limiter initialized with default limits: {default_limits}")

# --- FastAPI App Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for discovering and managing Agent Cards in the AgentVault ecosystem.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Apply Rate Limiting Middleware ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
logger.info("SlowAPI rate limiting middleware added.")


# --- CORS Middleware ---
if settings.ALLOWED_ORIGINS:
    logger.info(f"Configuring CORS with allowed origins: {settings.ALLOWED_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.ALLOWED_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.warning("CORS middleware not configured as ALLOWED_ORIGINS is empty.")

# --- API Routers ---
app.include_router(
    agent_cards.router,
    prefix=settings.API_V1_STR + "/agent-cards",
    tags=["Agent Cards"]
)
app.include_router(
    utils.router,
    prefix=settings.API_V1_STR + "/utils",
    tags=["Utilities"]
)
app.include_router(auth.router)
app.include_router(developers.router)
app.include_router(agent_builder.router)
logger.info("Included API routers.")


# --- Mount Static Files (Direct Access) ---
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")
    logger.info(f"Mounted static files directory for direct access: {STATIC_DIR}")
else:
    logger.error(f"Static files directory not found at: {STATIC_DIR}. Direct static file serving will fail.")


# --- ADDED: Dependency Class for Static File Reading ---
class StaticFileReader:
    """Dependency class to handle reading static files."""
    def __init__(self, base_dir: Path = STATIC_DIR):
        # Store base_dir on the instance
        self.base_dir = base_dir
        logger.debug(f"StaticFileReader initialized with base_dir: {self.base_dir}")

    def get_content(self, filename: str) -> str:
        """Reads content of a file in the static directory."""
        file_path = self.base_dir / filename
        logger.debug(f"Attempting to read static file: {file_path}")
        if not file_path.is_file():
            logger.error(f"Static file '{filename}' not found in {self.base_dir}")
            raise FileNotFoundError(f"{filename} not found")
        try:
            content = file_path.read_text(encoding="utf-8")
            logger.debug(f"Successfully read static file: {filename}")
            return content
        except Exception as e:
            logger.exception(f"Error reading static file '{filename}': {e}")
            raise IOError(f"Could not read {filename}")
# --- END ADDED ---


# --- Root Endpoint ---
@app.get("/", tags=["Status"], include_in_schema=False)
async def read_root_redirect():
    """Redirects root path to the UI."""
    return RedirectResponse(url="/ui")


# --- UI Routes (Explicitly Defined with Dependency Injection) ---

@app.get("/ui", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_ui(reader: StaticFileReader = Depends()): # Inject the class
    """Serves the main HTML file for the Public Registry UI."""
    try:
        html_content = reader.get_content("index.html")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
         raise HTTPException(status_code=404, detail="UI index file not found.")
    except IOError:
         raise HTTPException(status_code=500, detail="Could not load UI.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading UI.")

@app.get("/ui/developer", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_developer_ui(reader: StaticFileReader = Depends()):
    """Serves the main HTML file for the Developer Portal UI."""
    try:
        html_content = reader.get_content("developer/index.html") # Correct path
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
         raise HTTPException(status_code=404, detail="Developer UI index file not found.")
    except IOError:
         raise HTTPException(status_code=500, detail="Could not load Developer UI.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui/developer route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading Developer UI.")

@app.get("/ui/register", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_register_ui(reader: StaticFileReader = Depends()):
    """Serves the registration HTML page."""
    try:
        html_content = reader.get_content("register.html")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Registration page file not found.")
    except IOError:
        raise HTTPException(status_code=500, detail="Could not load registration page.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui/register route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading registration page.")

@app.get("/ui/login", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_login_ui(reader: StaticFileReader = Depends()):
    """Serves the login HTML page."""
    try:
        html_content = reader.get_content("login.html")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Login page file not found.")
    except IOError:
        raise HTTPException(status_code=500, detail="Could not load login page.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui/login route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading login page.")

@app.get("/ui/forgot-password", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_forgot_password_ui(reader: StaticFileReader = Depends()):
    """Serves the forgot password HTML page."""
    try:
        html_content = reader.get_content("forgot-password.html")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Forgot password page file not found.")
    except IOError:
        raise HTTPException(status_code=500, detail="Could not load forgot password page.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui/forgot-password route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading forgot password page.")

@app.get("/ui/recover-with-key", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_recover_with_key_ui(reader: StaticFileReader = Depends()):
    """Serves the recover account with key HTML page."""
    try:
        html_content = reader.get_content("recover-with-key.html")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Account recovery page file not found.")
    except IOError:
        raise HTTPException(status_code=500, detail="Could not load account recovery page.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui/recover-with-key route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading account recovery page.")

@app.get("/ui/set-new-password", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_set_new_password_ui(reader: StaticFileReader = Depends()):
    """Serves the set new password HTML page (used after recovery)."""
    try:
        html_content = reader.get_content("set-new-password.html")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Set new password page file not found.")
    except IOError:
        raise HTTPException(status_code=500, detail="Could not load set new password page.")
    except Exception as e:
         logger.exception(f"Unexpected error in /ui/set-new-password route: {e}")
         raise HTTPException(status_code=500, detail="Internal server error loading set new password page.")

@app.get("/ui/verify-success", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_verify_success_ui(reader: StaticFileReader = Depends()):
    """Serves the email verification success page."""
    try: return HTMLResponse(content=reader.get_content("verify-success.html"))
    except FileNotFoundError: raise HTTPException(status_code=404, detail="Verification success page not found.")
    except IOError: raise HTTPException(status_code=500, detail="Could not load verification success page.")
    except Exception as e: logger.exception(f"Unexpected error in /ui/verify-success route: {e}"); raise HTTPException(status_code=500, detail="Internal server error loading page.")

@app.get("/ui/verify-failed", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_verify_failed_ui(reader: StaticFileReader = Depends()):
    """Serves the email verification failed page."""
    try: return HTMLResponse(content=reader.get_content("verify-failed.html"))
    except FileNotFoundError: raise HTTPException(status_code=404, detail="Verification failed page not found.")
    except IOError: raise HTTPException(status_code=500, detail="Could not load verification failed page.")
    except Exception as e: logger.exception(f"Unexpected error in /ui/verify-failed route: {e}"); raise HTTPException(status_code=500, detail="Internal server error loading page.")

@app.get("/ui/reset-requested", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_reset_requested_ui(reader: StaticFileReader = Depends()):
    """Serves the password reset requested confirmation page."""
    try: return HTMLResponse(content=reader.get_content("reset-requested.html"))
    except FileNotFoundError: raise HTTPException(status_code=404, detail="Reset requested page not found.")
    except IOError: raise HTTPException(status_code=500, detail="Could not load reset requested page.")
    except Exception as e: logger.exception(f"Unexpected error in /ui/reset-requested route: {e}"); raise HTTPException(status_code=500, detail="Internal server error loading page.")

@app.get("/ui/reset-success", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_reset_success_ui(reader: StaticFileReader = Depends()):
    """Serves the password reset success page."""
    try: return HTMLResponse(content=reader.get_content("reset-success.html"))
    except FileNotFoundError: raise HTTPException(status_code=404, detail="Reset success page not found.")
    except IOError: raise HTTPException(status_code=500, detail="Could not load reset success page.")
    except Exception as e: logger.exception(f"Unexpected error in /ui/reset-success route: {e}"); raise HTTPException(status_code=500, detail="Internal server error loading page.")

@app.get("/ui/reset-failed", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
async def read_reset_failed_ui(reader: StaticFileReader = Depends()):
    """Serves the password reset failed page."""
    try: return HTMLResponse(content=reader.get_content("reset-failed.html"))
    except FileNotFoundError: raise HTTPException(status_code=404, detail="Reset failed page not found.")
    except IOError: raise HTTPException(status_code=500, detail="Could not load reset failed page.")
    except Exception as e: logger.exception(f"Unexpected error in /ui/reset-failed route: {e}"); raise HTTPException(status_code=500, detail="Internal server error loading page.")


# --- Health Check Endpoint ---
@app.get("/health", tags=["Status"])
async def health_check(request: Request):
    """Simple health check endpoint."""
    return {"status": "ok"}

logger.info(f"{settings.PROJECT_NAME} application initialized.")
