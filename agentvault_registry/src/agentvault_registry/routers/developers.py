import logging
# --- MODIFIED: Added List, Optional, Annotated ---
from typing import List, Optional, Annotated
# --- END MODIFIED ---

# --- MODIFIED: Added Body, Path, Response ---
from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Response
# --- END MODIFIED ---
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports (will be needed later)
from agentvault_registry import schemas, models, security
from agentvault_registry.database import get_db
from agentvault_registry.crud import developer as developer_crud

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/developers",
    tags=["Developers"],
    # Apply JWT authentication to all routes in this router
    dependencies=[Depends(security.get_current_developer)]
)

# --- Endpoints will be added here based on REQ-AUTH-008 ---

@router.get("/me", response_model=schemas.DeveloperRead, summary="Get Current Developer Info")
async def read_users_me(
    current_developer: Annotated[models.Developer, Depends(security.get_current_developer)] # Use Annotated
):
    """Returns the information for the currently authenticated developer."""
    # The dependency already fetches and validates the developer
    return current_developer

# --- ADDED: API Key Management Endpoints ---
@router.post(
    "/me/apikeys",
    response_model=schemas.NewApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new programmatic API Key"
)
async def create_new_api_key(
    description: Optional[str] = Body(None, embed=True, description="Optional description for the API key."), # Use Body for optional field
    db: AsyncSession = Depends(get_db),
    current_developer: models.Developer = Depends(security.get_current_developer)
):
    """
    Generates a new programmatic API key (prefixed with 'avreg_') associated
    with the authenticated developer. The plain text key is returned ONLY once.
    """
    logger.info(f"Request to create new API key for developer ID: {current_developer.id}")
    plain_key = security.generate_secure_api_key()
    hashed_key = security.hash_api_key(plain_key)
    prefix = plain_key.split("_")[0] + "_"

    db_api_key = await developer_crud.create_api_key(
        db=db,
        developer_id=current_developer.id,
        prefix=prefix,
        hashed_key=hashed_key,
        description=description
    )

    if not db_api_key:
        logger.error(f"Failed to save new API key to database for developer {current_developer.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key."
        )

    # Validate the created object before returning
    api_key_info = schemas.ApiKeyRead.model_validate(db_api_key)

    return schemas.NewApiKeyResponse(
        plain_api_key=plain_key,
        api_key_info=api_key_info
    )

@router.get(
    "/me/apikeys",
    response_model=List[schemas.ApiKeyRead],
    summary="List active programmatic API Keys"
)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_developer: models.Developer = Depends(security.get_current_developer)
):
    """
    Retrieves a list of active programmatic API keys for the authenticated developer.
    """
    logger.info(f"Request to list API keys for developer ID: {current_developer.id}")
    db_keys = await developer_crud.get_active_api_keys_for_developer(
        db=db, developer_id=current_developer.id
    )
    # Pydantic will automatically validate the list during response serialization
    return db_keys

@router.delete(
    "/me/apikeys/{key_id}", # Use integer ID from ApiKeyRead schema
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate (delete) a programmatic API Key"
)
async def delete_api_key(
    key_id: int = Path(..., description="The integer ID of the API key to deactivate."),
    db: AsyncSession = Depends(get_db),
    current_developer: models.Developer = Depends(security.get_current_developer)
):
    """
    Deactivates (soft deletes) a specific programmatic API key owned by the
    authenticated developer.
    """
    logger.info(f"Request to deactivate API key ID: {key_id} for developer ID: {current_developer.id}")
    success = await developer_crud.deactivate_api_key(
        db=db,
        developer_id=current_developer.id,
        api_key_id=key_id # Pass integer ID
    )
    if not success:
        # CRUD function handles logging details, just raise 404 here
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found or not owned by the current user."
        )
    # Return No Content on success
    return Response(status_code=status.HTTP_204_NO_CONTENT)
# --- END ADDED ---

logger.info("Developer router initialized.") # Removed (endpoints pending)
