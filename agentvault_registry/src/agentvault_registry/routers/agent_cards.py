import logging
import uuid
import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

# Import local dependencies with absolute imports
from agentvault_registry import schemas, models, database, security
from agentvault_registry.crud import agent_card

logger = logging.getLogger(__name__)

router = APIRouter()

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
):
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
        if db_agent_card is None:
            # This case might occur if validation passed but DB commit failed unexpectedly
            # CRUD function now raises ValueError for known issues.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create agent card in database.",
            )
        # Use the schema to format the response from the DB object
        return schemas.AgentCardRead.model_validate(db_agent_card)
    except ValueError as e:
        # Catch validation errors or DB integrity errors raised from CRUD
        logger.warning(f"Failed to create agent card due to validation/DB error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # 422 for validation errors
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
    description="Retrieves a paginated list of active Agent Cards, optionally filtered by search query.",
)
async def list_agent_cards(
    db: AsyncSession = Depends(database.get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination."),
    limit: int = Query(100, ge=1, le=250, description="Maximum number of records to return."),
    active_only: bool = Query(True, description="Filter for active agent cards only."),
    # --- MODIFIED: Added max_length to search parameter ---
    search: Optional[str] = Query(
        None,
        max_length=100, # Limit search term length
        description="Search term to filter by name or description (case-insensitive, max 100 chars)."
    )
    # --- END MODIFIED ---
):
    """
    Public endpoint to list and search for Agent Cards.
    """
    logger.info(f"Listing agent cards with skip={skip}, limit={limit}, active_only={active_only}, search='{search}'")
    try:
        items, total_items = await agent_card.list_agent_cards(
            db=db, skip=skip, limit=limit, active_only=active_only, search=search
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
):
    """
    Public endpoint to retrieve a specific Agent Card.
    """
    logger.info(f"Fetching agent card with ID: {card_id}")
    db_card = await agent_card.get_agent_card(db=db, card_id=card_id)
    if db_card is None:
        logger.warning(f"Agent card with ID {card_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Card not found")
    # Use the schema to format the response
    return schemas.AgentCardRead.model_validate(db_card)


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
):
    """
    Endpoint to update an Agent Card.

    Requires developer authentication and ownership of the card.
    Validates `card_data` if provided.
    """
    logger.info(f"Received request to update agent card {card_id} from developer ID: {current_developer.id}")
    db_card = await agent_card.get_agent_card(db=db, card_id=card_id)
    if db_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Card not found")

    # Ownership check
    if db_card.developer_id != current_developer.id:
        logger.warning(f"Developer {current_developer.id} attempted to update agent card {card_id} owned by {db_card.developer_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this agent card")

    try:
        updated_card = await agent_card.update_agent_card(db=db, db_card=db_card, card_update=card_in)
        if updated_card is None:
             # Should ideally not happen if ValueError is raised correctly from CRUD
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update agent card in database.",
            )
        return schemas.AgentCardRead.model_validate(updated_card)
    except ValueError as e:
        # Catch validation errors or DB errors raised from CRUD
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
    # Fetch the card first to check ownership
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
