import logging
import secrets
from datetime import datetime, timedelta, timezone
# --- MODIFIED: Added Dict ---
from typing import List, Optional, Annotated, Dict
# --- END MODIFIED ---


# --- MODIFIED: Added BackgroundTasks, Query, Response, JSONResponse ---
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body, Query, Response # Added Response, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse # Added JSONResponse
# --- END MODIFIED ---
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

# Local imports
from agentvault_registry import schemas, models, security
from agentvault_registry.database import get_db
from agentvault_registry.crud import developer as developer_crud # Use alias
# --- MODIFIED: Import send_verification_email ---
from agentvault_registry.email_utils import send_verification_email, send_password_reset_email # Added send_verification_email
# --- END MODIFIED ---
# --- ADDED: Import settings ---
from agentvault_registry.config import settings
# --- END ADDED ---


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth", # Set prefix for all routes in this file
    tags=["Authentication"]
)

@router.post(
    "/register",
    # --- MODIFIED: Changed response model for error, added 503 response ---
    # response_model=schemas.RegistrationResponse, # Original success model
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, # Return 503
    summary="Register a new developer account (Temporarily Disabled)",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Registration temporarily disabled"}
    }
    # --- END MODIFIED ---
)
async def register_developer(
    # --- MODIFIED: Keep params for signature, but don't use them yet ---
    background_tasks: BackgroundTasks,
    developer_in: schemas.DeveloperCreate = Body(...),
    db: AsyncSession = Depends(get_db)
    # --- END MODIFIED ---
):
    """
    Handles new developer registration.
    **NOTE: This endpoint is temporarily disabled pending email service activation.**
    """
    # --- MODIFIED: Raise HTTPException immediately ---
    logger.warning("Registration endpoint called while temporarily disabled.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Registration is temporarily disabled pending email service activation. Please check back later."
    )
    # --- END MODIFIED ---

    # --- Original Logic (Commented out or removed for disabling) ---
    # logger.info(f"Registration attempt for email: {developer_in.email}")
    # existing_developer = await developer_crud.get_developer_by_email(db, email=developer_in.email)
    # ... rest of the original registration logic ...
    # --- End Original Logic ---


@router.post("/login", response_model=schemas.Token, summary="Developer Login")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):
    """
    Handles developer login using email and password (OAuth2 Password Flow).
    Verifies credentials and returns a JWT access token.
    """
    logger.info(f"Login attempt for user: {form_data.username}") # username field holds email
    developer = await developer_crud.get_developer_by_email(db, email=form_data.username)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not developer:
        logger.warning(f"Login failed: Developer not found for email {form_data.username}")
        raise credentials_exception

    # --- MODIFIED: Allow login even if not verified, but maybe add warning? ---
    # We need login to work so users can potentially resend verification later if needed.
    # Let's remove the strict verification check *during login* for now.
    # if not developer.is_verified:
    #      logger.warning(f"Login failed: Developer email {form_data.username} not verified.")
    #      # Provide slightly different message for unverified user for better UX, but still 401
    #      raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED, # Still 401, but different detail
    #         detail="Email address not verified. Please check your inbox.",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # --- END MODIFIED ---


    if not security.verify_password(form_data.password, developer.hashed_password):
        logger.warning(f"Login failed: Invalid password for email {form_data.username}")
        raise credentials_exception

    # Password is valid, create JWT
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": str(developer.id)}, expires_delta=access_token_expires
    )
    logger.info(f"Login successful for developer ID: {developer.id}")
    return schemas.Token(access_token=access_token, token_type="bearer")

# --- Email Verification Endpoint ---
@router.get("/verify-email", summary="Verify Email Address", response_description="Email verification status", response_model=Dict[str, str])
async def verify_email(token: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Handles the email verification link clicked by the user."""
    logger.info(f"Received email verification request with token prefix: {token[:6]}...")
    developer = await developer_crud.get_developer_by_verification_token(db, token=token)

    error_msg = "Invalid or expired verification token."
    if not developer:
        logger.warning(f"Verification failed: Token not found.")
        # --- MODIFIED: Redirect on failure ---
        # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        return RedirectResponse(url="/ui/verify-failed", status_code=status.HTTP_303_SEE_OTHER)
        # --- END MODIFIED ---

    if developer.is_verified:
        logger.info(f"Email '{developer.email}' already verified.")
        # --- MODIFIED: Redirect on success (already verified) ---
        # return JSONResponse(content={"status": "already_verified"})
        return RedirectResponse(url="/ui/verify-success?status=already_verified", status_code=status.HTTP_303_SEE_OTHER)
        # --- END MODIFIED ---


    if developer.verification_token_expires is None or developer.verification_token_expires < datetime.now(timezone.utc):
        logger.warning(f"Verification failed: Token expired for email {developer.email}.")
        # Optionally allow resending verification?
        # --- MODIFIED: Redirect on failure ---
        # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        return RedirectResponse(url="/ui/verify-failed?reason=expired", status_code=status.HTTP_303_SEE_OTHER)
        # --- END MODIFIED ---

    # Token is valid, mark as verified
    developer.is_verified = True
    developer.email_verification_token = None
    developer.verification_token_expires = None
    try:
        db.add(developer)
        await db.commit()
        logger.info(f"Email successfully verified for developer: {developer.email} (ID: {developer.id})")
        # --- MODIFIED: Redirect on success ---
        # return JSONResponse(content={"status": "verified"})
        return RedirectResponse(url="/ui/verify-success", status_code=status.HTTP_303_SEE_OTHER)
        # --- END MODIFIED ---
    except Exception as e:
        await db.rollback()
        logger.exception(f"Database error during email verification for {developer.email}")
        # --- MODIFIED: Redirect on failure ---
        # raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update verification status.")
        return RedirectResponse(url="/ui/verify-failed?reason=dberror", status_code=status.HTTP_303_SEE_OTHER)
        # --- END MODIFIED ---

# --- Recovery Key Flow Endpoints ---
@router.post("/recover-account", response_model=schemas.Token, summary="Recover Account via Recovery Key")
async def recover_account_with_key(
    recover_in: schemas.PasswordResetRecover,
    db: AsyncSession = Depends(get_db)
):
    """
    Verifies email and recovery key, returns a short-lived token for setting a new password.
    """
    logger.info(f"Account recovery attempt for email: {recover_in.email}")
    developer = await developer_crud.get_developer_by_email(db, email=recover_in.email)

    error_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid email or recovery key.",
    )

    if not developer or not developer.is_verified:
        logger.warning(f"Recovery failed: Developer not found or not verified for email {recover_in.email}.")
        raise error_exception # Don't reveal which part failed

    if not developer.hashed_recovery_key:
        logger.error(f"Recovery failed: Developer {developer.id} has no recovery key hash stored.")
        raise error_exception # Should not happen if generated on registration

    if not security.verify_recovery_key(recover_in.recovery_key, developer.hashed_recovery_key):
        logger.warning(f"Recovery failed: Invalid recovery key provided for developer {developer.id}.")
        raise error_exception

    # Recovery key is valid, issue temporary password-set token
    temp_token_expires = timedelta(minutes=5) # Short expiry
    temp_token = security.create_access_token(
        data={"sub": str(developer.id), "purpose": "password-set"},
        expires_delta=temp_token_expires
    )
    logger.info(f"Recovery key verified for developer {developer.id}. Issuing temporary password-set token.")
    return schemas.Token(access_token=temp_token, token_type="bearer")


@router.post("/set-new-password", summary="Set New Password After Recovery", response_model=Dict[str, str])
async def set_new_password_after_recovery(
    set_in: schemas.PasswordSetNew = Body(...), # Keep embed=True if needed, or remove if not
    # Dependencies last
    db: AsyncSession = Depends(get_db),
    developer_id: int = Depends(security.verify_temp_password_token)
):
    """
    Sets a new password using the temporary token obtained via recovery key flow.
    Invalidates the used recovery key hash.
    Expects the request body to be: {"new_password": "..."}
    """
    logger.info(f"Setting new password for developer ID: {developer_id} after recovery.")
    developer = await developer_crud.get_developer_by_id(db, developer_id=developer_id)
    if not developer:
        # Should not happen if token was valid, but check defensively
        logger.error(f"Set new password failed: Developer {developer_id} not found after token verification.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found.")

    # --- FIXED: Extract plain string from SecretStr before hashing ---
    new_hashed_password = security.hash_password(set_in.new_password.get_secret_value())
    # --- END FIXED ---

    # Update password and invalidate recovery key hash
    developer.hashed_password = new_hashed_password
    developer.hashed_recovery_key = None # Invalidate recovery key after use
    developer.updated_at = datetime.now(timezone.utc)

    try:
        db.add(developer)
        await db.commit()
        logger.info(f"Successfully set new password and invalidated recovery key for developer {developer_id}.")
        return {"message": "Password updated successfully."}
    except Exception as e:
        await db.rollback()
        logger.exception(f"Database error setting new password for developer {developer_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password.")


# --- Placeholder for Email Password Reset Endpoints ---
# @router.post("/request-password-reset") ...
# @router.post("/reset-password") ...
