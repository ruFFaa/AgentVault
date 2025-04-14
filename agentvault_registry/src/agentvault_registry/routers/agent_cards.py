import logging
import uuid
import math
import datetime
import os
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# --- MODIFIED: Import APIRouter earlier ---
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
# --- END MODIFIED ---
from pydantic import ValidationError as PydanticValidationError # To catch validation errors

# Import local dependencies with absolute imports
from agentvault_registry import schemas, models, database, security
from agentvault_registry.crud import agent_card

# Import the AgentCard model from the core library for validation
try:
    from agentvault import AgentCard as AgentCardModel
    from agentvault import AgentCardValidationError # Although we catch Pydantic's directly
    _agentvault_lib_available = True
except ImportError:
    AgentCardModel = None # type: ignore
    AgentCardValidationError = Exception # Placeholder
    _agentvault_lib_available = False
    logging.warning("Could not import 'agentvault' library. Agent Card validation during CRUD operations will be skipped.")


logger = logging.getLogger(__name__)

router = APIRouter()

# --- Helper Function to build response dict ---
def _build_agent_card_read_dict(db_card: models.AgentCard) -> dict:
    """Builds the dictionary for AgentCardRead response from the ORM model."""
    if not db_card:
        return {} # Should not happen if called correctly
    # Ensure developer relationship is loaded (get_agent_card should handle this)
    developer_verified = False
    if hasattr(db_card, 'developer') and db_card.developer:
        developer_verified = getattr(db_card.developer, 'is_verified', False)
    else:
        logger.warning(f"Developer relationship not loaded for AgentCard {db_card.id} when building response.")

    return {
        "id": db_card.id,
        "developer_id": db_card.developer_id,
        "card_data": db_card.card_data,
        "name": db_card.name,
        "description": db_card.description,
        "is_active": db_card.is_active,
        "created_at": db_card.created_at,
        "updated_at": db_card.updated_at,
        "developer_is_verified": developer_verified,
    }
# --- End Helper ---


# --- POST /agent-cards ---
@router.post(
    "/",
    response_model=schemas.AgentCardRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new Agent Card",
    description="Submits a new Agent Card associated with the authenticated developer.",
)
async def submit_agent_card(
    card_in: schemas.AgentCardCreate,
    db: AsyncSession = Depends(database.get_db),
    current_developer: models.Developer = Depends(security.get_current_developer),
) -> schemas.AgentCardRead: # Return type hint remains the schema
    """
    Endpoint to submit a new Agent Card.
    Requires developer authentication via the X-Api-Key header.
    Validates the provided `card_data` against the core AgentCard schema.
    """
    logger.info(f"Received request to create agent card from developer ID: {current_developer.id}")
    try:
        db_agent_card = await agent_card.create_agent_card(
            db=db, developer_id=current_developer.id, card_create=card_in
        )
        # Refresh should load relationships if configured correctly,
        # but explicitly reload developer if needed after refresh for safety.
        if db_agent_card and (not hasattr(db_agent_card, 'developer') or not db_agent_card.developer):
             await db.refresh(db_agent_card, attribute_names=['developer'])

        # Build dict manually before returning
        response_dict = _build_agent_card_read_dict(db_agent_card)
        # Pydantic validates the dict when FastAPI returns it based on response_model
        return response_dict # type: ignore # FastAPI handles dict -> schema
    except ValueError as e:
        logger.warning(f"Failed to create agent card due to validation/DB error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to create agent card: {e}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating agent card for developer {current_developer.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the agent card.",
        )


# --- GET /agent-cards ---
@router.get(
    "/",
    response_model=schemas.AgentCardListResponse,
    summary="List Agent Cards",
    description="Retrieves a paginated list of active Agent Cards, optionally filtered by search query, tags, or ownership.",
)
async def list_agent_cards(
    db: AsyncSession = Depends(database.get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination."),
    limit: int = Query(100, ge=1, le=250, description="Maximum number of records to return."),
    active_only: bool = Query(True, description="Filter for active agent cards only."),
    search: Optional[str] = Query(
        None,
        max_length=100, # Limit search term length
        description="Search term to filter by name or description (case-insensitive, max 100 chars)."
    ),
    tags: Optional[List[str]] = Query(
        None,
        description="List of tags to filter by (agents must have ALL specified tags)."
    ),
    # --- ADDED: owned_only parameter and optional developer dependency ---
    owned_only: bool = Query(False, description="If true, only return cards owned by the authenticated developer (requires authentication)."),
    current_developer: Optional[models.Developer] = Depends(security.get_current_developer_optional)
    # --- END ADDED ---
):
    """
    Public endpoint to list and search for Agent Cards.
    Can optionally filter by owned cards if authenticated.
    """
    developer_id_filter: Optional[int] = None
    if owned_only:
        if current_developer is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to list owned agent cards."
            )
        developer_id_filter = current_developer.id
        logger.info(f"Listing agent cards for owner ID: {developer_id_filter}, skip={skip}, limit={limit}, active_only={active_only}, search='{search}', tags={tags}")
    else:
        logger.info(f"Listing public agent cards with skip={skip}, limit={limit}, active_only={active_only}, search='{search}', tags={tags}")

    try:
        items, total_items = await agent_card.list_agent_cards(
            db=db, skip=skip, limit=limit, active_only=active_only, search=search, tags=tags,
            developer_id=developer_id_filter # Pass filter value
        )

        # Calculate pagination details
        current_page = (skip // limit) + 1
        total_pages = math.ceil(total_items / limit) if limit > 0 else 0

        pagination_info = schemas.PaginationInfo(
            total_items=total_items,
            limit=limit,
            offset=skip,
            total_pages=total_pages,
            current_page=current_page,
        )

        # Convert DB models to summary schemas for response
        summaries = [schemas.AgentCardSummary.model_validate(item) for item in items]

        return schemas.AgentCardListResponse(items=summaries, pagination=pagination_info)

    except Exception as e:
        logger.exception("Error listing agent cards")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving agent cards.",
        )


# --- GET /agent-cards/{card_id} ---
@router.get(
    "/{card_id}",
    response_model=schemas.AgentCardRead,
    summary="Get Agent Card by ID",
    description="Retrieves the details of a specific Agent Card by its UUID.",
)
async def get_agent_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(database.get_db),
) -> schemas.AgentCardRead: # Return type hint remains the schema
    """
    Public endpoint to retrieve a specific Agent Card.
    """
    logger.info(f"Fetching agent card with ID: {card_id}")
    # CRUD function now eagerly loads developer
    db_card = await agent_card.get_agent_card(db=db, card_id=card_id)
    if db_card is None:
        logger.warning(f"Agent card with ID {card_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Card not found")

    # Build dict manually before returning
    response_dict = _build_agent_card_read_dict(db_card)
    # Pydantic validates the dict when FastAPI returns it based on response_model
    return response_dict # type: ignore


# --- PUT /agent-cards/{card_id} ---
@router.put(
    "/{card_id}",
    response_model=schemas.AgentCardRead,
    summary="Update an Agent Card",
    description="Updates an existing Agent Card. Requires ownership.",
)
async def update_agent_card(
    card_id: uuid.UUID,
    card_in: schemas.AgentCardUpdate,
    db: AsyncSession = Depends(database.get_db),
    current_developer: models.Developer = Depends(security.get_current_developer),
) -> schemas.AgentCardRead: # Return type hint remains the schema
    """
    Endpoint to update an Agent Card.

    Requires developer authentication and ownership of the card.
    Validates `card_data` if provided.
    """
    logger.info(f"Received request to update agent card {card_id} from developer ID: {current_developer.id}")
    # Fetch card with developer loaded for ownership check and response schema
    db_card = await agent_card.get_agent_card(db=db, card_id=card_id)
    if db_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Card not found")

    # Ownership check
    if db_card.developer_id != current_developer.id:
        logger.warning(f"Developer {current_developer.id} attempted to update agent card {card_id} owned by {db_card.developer_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this agent card")

    try:
        updated_card = await agent_card.update_agent_card(db=db, db_card=db_card, card_update=card_in)

        # Ensure developer relationship is loaded for the response schema
        # Refresh should handle this, but check if needed
        if updated_card and (not hasattr(updated_card, 'developer') or not updated_card.developer):
             logger.info(f"Refreshing developer relationship for updated card {updated_card.id}")
             await db.refresh(updated_card, attribute_names=['developer'])

        # Build dict manually before returning
        response_dict = _build_agent_card_read_dict(updated_card)
        # Pydantic validates the dict when FastAPI returns it based on response_model
        return response_dict # type: ignore
    except ValueError as e:
        logger.warning(f"Failed to update agent card {card_id} due to validation/DB error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to update agent card: {e}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error updating agent card {card_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the agent card.",
        )


# --- DELETE /agent-cards/{card_id} ---
@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an Agent Card",
    description="Marks an Agent Card as inactive (soft delete). Requires ownership.",
)
async def delete_agent_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(database.get_db),
    current_developer: models.Developer = Depends(security.get_current_developer),
):
    """
    Endpoint to soft-delete (deactivate) an Agent Card.

    Requires developer authentication and ownership.
    Returns 204 No Content on success.
    """
    logger.info(f"Received request to deactivate agent card {card_id} from developer ID: {current_developer.id}")
    # Fetch the card first to check ownership (developer relationship is loaded by get_agent_card)
    db_card = await agent_card.get_agent_card(db=db, card_id=card_id)
    if db_card is None:
        # Return 404 even if it existed but belonged to someone else,
        # to avoid leaking information about ownership.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Card not found")

    # Ownership check
    if db_card.developer_id != current_developer.id:
        logger.warning(f"Developer {current_developer.id} attempted to delete agent card {card_id} owned by {db_card.developer_id}")
        # Return 403 if they don't own it
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this agent card")

    # Proceed with soft delete
    success = await agent_card.delete_agent_card(db=db, card_id=card_id)

    if not success:
        # This might happen if the card was deleted between the get and delete calls,
        # or if there was a DB error during the update.
        # Check if it still exists but failed to update
        # Re-fetch to check current state
        check_card = await agent_card.get_agent_card(db=db, card_id=card_id)
        if check_card and check_card.is_active:
             logger.error(f"Failed to deactivate agent card {card_id} due to a database error.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deactivate agent card")
        elif not check_card:
             # If it disappeared, treat as 404 from the start
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Card not found")
        # If it exists and is already inactive, the CRUD function returns True, so this path shouldn't be hit often.

    # Return No Content on successful deactivation
    return Response(status_code=status.HTTP_204_NO_CONTENT)
