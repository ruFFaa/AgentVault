import logging
import uuid
import math
from typing import Optional, List, Dict, Any, Tuple

# --- MODIFIED: Import select ---
from sqlalchemy import select, func, or_
# --- END MODIFIED ---
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
# --- MODIFIED: Import selectinload ---
from sqlalchemy.orm import selectinload
# --- END MODIFIED ---
from pydantic import ValidationError as PydanticValidationError # To catch validation errors

# Import local models and schemas with absolute imports
from agentvault_registry import models, schemas

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


async def create_agent_card(
    db: AsyncSession, developer_id: int, card_create: schemas.AgentCardCreate
) -> Optional[models.AgentCard]:
    """
    Creates a new Agent Card record in the database after validating the card data.

    Args:
        db: The SQLAlchemy async session.
        developer_id: The ID of the developer owning this card.
        card_create: The Pydantic schema containing the raw card data.

    Returns:
        The created AgentCard database object, or None if validation or DB operation fails.
    """
    logger.info(f"Attempting to create Agent Card for developer ID: {developer_id}")

    # 1. Validate the input card_data against the canonical AgentCard model
    if not _agentvault_lib_available or AgentCardModel is None:
        logger.warning("Skipping Agent Card validation as 'agentvault' library is not available.")
        validated_data = card_create.card_data # Use raw data if validation skipped
    else:
        try:
            # Validate the structure using the model from the core library
            validated_card_model = AgentCardModel.model_validate(card_create.card_data)
            # Use the validated data (dict representation) for storage and extraction
            validated_data = validated_card_model.model_dump(mode='json')
            logger.debug("Agent Card data successfully validated against core model.")
        except PydanticValidationError as e:
            logger.error(f"Agent Card validation failed: {e}", exc_info=True)
            # Raise a ValueError that can be caught by the API layer to return 400/422
            raise ValueError(f"Invalid Agent Card data provided: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error during Agent Card validation: {e}", exc_info=True)
             raise ValueError(f"Unexpected error validating Agent Card data: {e}") from e

    # 2. Extract required fields for direct storage and indexing
    try:
        name = validated_data.get("name")
        description = validated_data.get("description")
        if not name:
            raise ValueError("Validated card data is missing the required 'name' field.")
    except Exception as e:
        logger.error(f"Failed to extract required fields (name, description) from validated card data: {e}", exc_info=True)
        raise ValueError(f"Could not extract required fields from card data: {e}") from e

    # 3. Create the database model instance
    db_agent_card = models.AgentCard(
        developer_id=developer_id,
        card_data=validated_data, # Store the full (validated) JSON
        name=name,
        description=description,
        is_active=True # Default to active on creation
    )

    # 4. Add, commit, refresh
    db.add(db_agent_card)
    try:
        await db.commit()
        await db.refresh(db_agent_card)
        logger.info(f"Successfully created Agent Card '{name}' with ID: {db_agent_card.id}")
        return db_agent_card
    except IntegrityError as e:
        await db.rollback()
        # This could happen if UUID somehow conflicts, though unlikely.
        # Or if there are other DB constraints violated.
        logger.error(f"Database integrity error creating agent card '{name}': {e}", exc_info=True)
        raise ValueError(f"Database error creating agent card: {e}") from e # Re-raise for API layer
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected database error creating agent card '{name}': {e}", exc_info=True)
        raise ValueError(f"Unexpected database error: {e}") from e


async def get_agent_card(db: AsyncSession, card_id: uuid.UUID) -> Optional[models.AgentCard]:
    """
    Retrieves a single Agent Card by its UUID, eagerly loading the developer relationship.

    Args:
        db: The SQLAlchemy async session.
        card_id: The UUID of the agent card to retrieve.

    Returns:
        The AgentCard database object with the developer loaded if found, otherwise None.
    """
    logger.debug(f"Fetching Agent Card with ID: {card_id}, eagerly loading developer.")
    try:
        # --- MODIFIED: Use select with options(selectinload(...)) ---
        stmt = (
            select(models.AgentCard)
            .where(models.AgentCard.id == card_id)
            .options(selectinload(models.AgentCard.developer))
        )
        result = await db.execute(stmt)
        db_card = result.scalar_one_or_none()
        # --- END MODIFIED ---

        if db_card:
            # --- MODIFIED: Log if developer was loaded (optional debug) ---
            if db_card.developer:
                logger.debug(f"Found Agent Card: {db_card.name} (Developer: {db_card.developer.name})")
            else:
                # This case shouldn't happen with eager loading unless the FK is somehow null or invalid
                logger.warning(f"Found Agent Card {db_card.name} but developer relationship was not loaded/found.")
            # --- END MODIFIED ---
        else:
            logger.debug(f"Agent Card with ID {card_id} not found.")
        return db_card
    except Exception as e:
        logger.error(f"Error fetching Agent Card {card_id}: {e}", exc_info=True)
        return None


async def list_agent_cards(
    db: AsyncSession, skip: int = 0, limit: int = 100, active_only: bool = True, search: Optional[str] = None
) -> Tuple[List[models.AgentCard], int]:
    """
    Retrieves a list of Agent Cards with pagination and optional filtering.

    Args:
        db: The SQLAlchemy async session.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return.
        active_only: If True, only return cards where is_active is True.
        search: Optional search string to filter by name or description (case-insensitive).

    Returns:
        A tuple containing a list of AgentCard database objects and the total count
        of matching items before pagination.
    """
    logger.debug(f"Listing Agent Cards: skip={skip}, limit={limit}, active_only={active_only}, search='{search}'")

    # Base statement
    base_stmt = select(models.AgentCard)

    # Apply filters
    if active_only:
        base_stmt = base_stmt.where(models.AgentCard.is_active == True)
    if search:
        search_term = f"%{search}%"
        base_stmt = base_stmt.where(
            or_(
                models.AgentCard.name.ilike(search_term),
                models.AgentCard.description.ilike(search_term)
                # Add more searchable fields from card_data if needed using JSON operators
            )
        )

    # Get total count matching filters *before* applying limit/offset
    try:
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await db.execute(count_stmt)
        total_items = count_result.scalar_one_or_none() or 0 # Handle potential None if table is empty
    except Exception as e:
        logger.error(f"Error counting agent cards: {e}", exc_info=True)
        return [], 0 # Return empty on count error

    logger.debug(f"Total matching agent cards found: {total_items}")

    # Apply ordering, offset, and limit for the final result set
    final_stmt = base_stmt.order_by(models.AgentCard.updated_at.desc()).offset(skip).limit(limit)

    try:
        result = await db.execute(final_stmt)
        items = list(result.scalars().all()) # Use list() to ensure iteration if needed
        logger.debug(f"Returning {len(items)} agent cards for the current page.")
        return items, total_items
    except Exception as e:
        logger.error(f"Error executing agent card list query: {e}", exc_info=True)
        return [], total_items # Return empty list but potentially correct count


async def update_agent_card(
    db: AsyncSession, db_card: models.AgentCard, card_update: schemas.AgentCardUpdate
) -> Optional[models.AgentCard]:
    """
    Updates an existing Agent Card record.

    Args:
        db: The SQLAlchemy async session.
        db_card: The existing AgentCard database object to update.
        card_update: The Pydantic schema containing update data.

    Returns:
        The updated AgentCard database object, or None if validation/DB error occurs.
    """
    logger.info(f"Attempting to update Agent Card ID: {db_card.id}")
    update_data_provided = False

    # 1. Update card_data if provided
    if card_update.card_data is not None:
        update_data_provided = True
        logger.debug(f"Updating card_data for Agent Card ID: {db_card.id}")
        # Validate the new data
        if not _agentvault_lib_available or AgentCardModel is None:
             logger.warning("Skipping Agent Card validation as 'agentvault' library is not available.")
             validated_data = card_update.card_data
        else:
            try:
                validated_card_model = AgentCardModel.model_validate(card_update.card_data)
                validated_data = validated_card_model.model_dump(mode='json')
                logger.debug("Updated Agent Card data successfully validated.")
            except PydanticValidationError as e:
                logger.error(f"Updated Agent Card validation failed: {e}", exc_info=True)
                raise ValueError(f"Invalid Agent Card data provided for update: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error during Agent Card update validation: {e}", exc_info=True)
                raise ValueError(f"Unexpected error validating updated Agent Card data: {e}") from e

        # Update stored data and extracted fields
        db_card.card_data = validated_data
        try:
            db_card.name = validated_data.get("name")
            db_card.description = validated_data.get("description")
            if not db_card.name:
                 raise ValueError("Validated card data for update is missing the required 'name' field.")
        except Exception as e:
            logger.error(f"Failed to extract required fields from updated card data: {e}", exc_info=True)
            raise ValueError(f"Could not extract required fields from updated card data: {e}") from e

    # 2. Update is_active status if provided
    if card_update.is_active is not None:
        if db_card.is_active != card_update.is_active:
             update_data_provided = True
             logger.debug(f"Updating is_active status for Agent Card ID {db_card.id} to {card_update.is_active}")
             db_card.is_active = card_update.is_active

    # 3. Commit changes if any were made
    if update_data_provided:
        try:
            db.add(db_card) # Add to session to track changes
            await db.commit()
            await db.refresh(db_card)
            logger.info(f"Successfully updated Agent Card ID: {db_card.id}")
            return db_card
        except Exception as e:
            await db.rollback()
            logger.error(f"Database error updating agent card {db_card.id}: {e}", exc_info=True)
            raise ValueError(f"Database error updating agent card: {e}") from e
    else:
        logger.debug(f"No update data provided for Agent Card ID: {db_card.id}. Returning existing object.")
        return db_card # Return the original object if no changes were made


async def delete_agent_card(db: AsyncSession, card_id: uuid.UUID) -> bool:
    """
    Soft deletes an Agent Card by setting its 'is_active' flag to False.

    Args:
        db: The SQLAlchemy async session.
        card_id: The UUID of the agent card to soft delete.

    Returns:
        True if the card was found and marked inactive, False otherwise.
    """
    logger.info(f"Attempting to soft delete (deactivate) Agent Card ID: {card_id}")
    db_card = await get_agent_card(db, card_id)

    if db_card:
        if not db_card.is_active:
            logger.warning(f"Agent Card {card_id} is already inactive.")
            return True # Idempotent: already in desired state

        db_card.is_active = False
        try:
            db.add(db_card)
            await db.commit()
            await db.refresh(db_card)
            logger.info(f"Successfully deactivated Agent Card ID: {card_id}")
            return True
        except Exception as e:
            await db.rollback()
            logger.error(f"Database error deactivating agent card {card_id}: {e}", exc_info=True)
            return False # Indicate failure
    else:
        logger.warning(f"Agent Card {card_id} not found for deactivation.")
        return False # Indicate not found

# --- Hard Delete (Alternative - Not Used by Default) ---
# async def hard_delete_agent_card(db: AsyncSession, card_id: uuid.UUID) -> bool:
#     """
#     Permanently deletes an Agent Card from the database. Use with caution!
#     """
#     logger.warning(f"Attempting to HARD DELETE Agent Card ID: {card_id}")
#     stmt = delete(models.AgentCard).where(models.AgentCard.id == card_id)
#     try:
#         result = await db.execute(stmt)
#         await db.commit()
#         deleted_count = result.rowcount
#         if deleted_count > 0:
#             logger.info(f"Successfully hard deleted {deleted_count} Agent Card record(s) with ID: {card_id}")
#             return True
#         else:
#             logger.warning(f"No Agent Card found with ID {card_id} to hard delete.")
#             return False
#     except Exception as e:
#         await db.rollback()
#         logger.error(f"Database error hard deleting agent card {card_id}: {e}", exc_info=True)
#         return False
