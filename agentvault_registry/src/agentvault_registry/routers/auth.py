import logging
import secrets
from datetime import datetime, timedelta, timezone
# --- MODIFIED: Added Annotated, Dict ---
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
    response_model=schemas.RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new developer account"
)
async def register_developer(
    # --- MODIFIED: Inject BackgroundTasks ---
    background_tasks: BackgroundTasks,
    # --- END MODIFIED ---
    developer_in: schemas.DeveloperCreate = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handles new developer registration.
    - Checks if email already exists.
    - Hashes password and recovery key.
    - Generates verification token.
    - Creates developer record in DB.
    - Sends verification email in the background.
    - Returns success message and **plain text recovery keys**.
    """
    logger.info(f"Registration attempt for email: {developer_in.email}")
    existing_developer = await developer_crud.get_developer_by_email(db, email=developer_in.email)
    if existing_developer:
        logger.warning(f"Registration failed: Email '{developer_in.email}' already registered.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    # Hash password
    hashed_password = security.hash_password(developer_in.password.get_secret_value())

    # Generate and hash recovery keys
    plain_recovery_keys = security.generate_recovery_keys()
    # --- CORRECTED LINE (Ensure this is applied) ---
    print(f"DEBUG auth.py: Type before hash: {type(plain_recovery_keys[0])}, Value: {plain_recovery_keys[0]!r}")
    hashed_recovery = security.hash_recovery_key(plain_recovery_keys[0]) # Hash only the first key
    # --- END CORRECTED LINE ---

    # Generate verification token and expiry
    verification_token = secrets.token_urlsafe(32)
    # --- MODIFIED: Use setting for expiry ---
    
    expiry_time = datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    # --- END MODIFIED ---

    # Prepare developer data for CRUD
    developer_data = models.Developer(
        name=developer_in.name,
        email=developer_in.email,
        hashed_password=hashed_password,
        hashed_recovery_key=hashed_recovery,
        is_verified=False,
        email_verification_token=verification_token,
        verification_token_expires=expiry_time
    )

    try:
        # Create developer in DB (assuming CRUD function exists)
        created_developer = await developer_crud.create_developer_with_hashed_details(
            db=db, developer_data=developer_data
        )
        if not created_developer: # Should not happen if no exception, but check
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create developer record.")

    except IntegrityError: # Catch potential race condition or unique constraint violation (e.g., name)
        logger.warning(f"Registration conflict for name '{developer_in.name}' or email '{developer_in.email}'.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists.",
        )
    except Exception as e:
        logger.exception(f"Unexpected error during developer creation for email {developer_in.email}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during registration.")

    # --- MODIFIED: Send verification email in background ---
    try:
        background_tasks.add_task(
            send_verification_email,
            to_email=created_developer.email,
            username=created_developer.name,
            token=verification_token
        )
        logger.info(f"Verification email task added for {created_developer.email}")
    except Exception as e:
        # Log error but don't fail registration if email sending fails initially
        logger.error(f"Failed to add verification email task for {created_developer.email}: {e}", exc_info=True)
    # --- END MODIFIED ---


    return schemas.RegistrationResponse(
        message="Registration successful. Please check your email to verify your account.",
        recovery_keys=plain_recovery_keys # Return plain keys ONCE
    )


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

    if not developer.is_verified:
         logger.warning(f"Login failed: Developer email {form_data.username} not verified.")
         # Provide slightly different message for unverified user for better UX, but still 401
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, # Still 401, but different detail
            detail="Email address not verified. Please check your inbox.",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
