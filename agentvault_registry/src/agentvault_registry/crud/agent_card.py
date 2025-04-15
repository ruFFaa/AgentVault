import logging
import uuid
import math
import datetime
import os
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, or_
# --- MODIFIED: Import JSONB and cast ---
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import cast, Text
# --- END MODIFIED ---
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Import local models and schemas with absolute imports
from agentvault_registry import models, schemas
from pydantic import ValidationError as PydanticValidationError


# Import the AgentCard model from the core library for validation
try:
    from agentvault import AgentCard as AgentCardModel
    _agentvault_lib_available = True
except ImportError:
    AgentCardModel = None # type: ignore
    _agentvault_lib_available = False
    logging.warning("Could not import 'agentvault' library. Agent Card validation during CRUD operations will be skipped.")


logger = logging.getLogger(__name__)

# --- Placeholder Data Generation ---
_placeholder_data_cache = {}
def _get_placeholder_items():
    global _placeholder_data_cache
    if not _placeholder_data_cache:
        logger.warning("!!! GENERATING PLACEHOLDER DATA !!!")
        now = datetime.datetime.now(datetime.timezone.utc)
        dev1 = models.Developer(id=1, name="Dev One", is_verified=True)
        dev2 = models.Developer(id=2, name="Dev Two", is_verified=False)
        # --- ADDED: Placeholder with TEE details ---
        tee_card_data = {
            "url": "http://tee-agent.example", "tags": ["tee", "secure"],
            "capabilities": {
                "a2aVersion": "1.0",
                "teeDetails": {
                    "type": "Intel SGX",
                    "attestationEndpoint": "https://attest.example.com"
                }
            }
        }
        # --- END ADDED ---
        items = [
            models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="Weather Agent (Placeholder)",
                description="Provides weather forecasts.", is_active=True,
                created_at=now, updated_at=now, card_data={"url": "http://weather.example", "tags": ["weather", "forecast", "public"]}, developer=dev1
            ),
            models.AgentCard(
                id=uuid.uuid4(), developer_id=2, name="Summarizer Agent (Placeholder)",
                description="Summarizes long texts.", is_active=True,
                created_at=now, updated_at=now, card_data={"url": "http://summarizer.example", "privacyPolicyUrl": "http://summarizer.example/privacy", "tags": ["text", "summarization", "nlp"]}, developer=dev2
            ),
             models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="Inactive Agent (Placeholder)",
                description="This one is inactive.", is_active=False,
                created_at=now, updated_at=now, card_data={"url": "http://inactive.example", "termsOfServiceUrl": "http://inactive.example/terms", "tags": ["internal", "test"]}, developer=dev1
            ),
             models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="Weather Tool (Placeholder)",
                description="Internal weather tool.", is_active=True,
                created_at=now, updated_at=now, card_data={"url": "http://weather-tool.internal", "tags": ["weather", "tool", "internal"]}, developer=dev1
            ),
            # --- ADDED: Placeholder with TEE details ---
            models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="TEE Agent (Placeholder)",
                description="Runs in a TEE.", is_active=True,
                created_at=now, updated_at=now, card_data=tee_card_data, developer=dev1
            ),
            # --- END ADDED ---
        ]
        _placeholder_data_cache = {item.id: item for item in items}
    return _placeholder_data_cache


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
            validated_card_model = AgentCardModel.model_validate(card_create.card_data)
            validated_data = validated_card_model.model_dump(mode='json', by_alias=True) # Use by_alias
            logger.debug("Agent Card data successfully validated against core model.")
        except PydanticValidationError as e:
            logger.error(f"Agent Card validation failed: {e}", exc_info=True)
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

    if os.environ.get("AGENTVAULT_USE_PLACEHOLDERS", "false").lower() == "true":
        logger.warning(f"!!! RETURNING PLACEHOLDER DATA FOR get_agent_card ID: {card_id} !!!")
        placeholder_items = _get_placeholder_items()
        item = placeholder_items.get(card_id)
        if item:
            logger.debug(f"Found placeholder Agent Card: {item.name}")
        else:
            logger.debug(f"Placeholder Agent Card with ID {card_id} not found.")
        return item

    try:
        stmt = (
            select(models.AgentCard)
            .where(models.AgentCard.id == card_id)
            .options(selectinload(models.AgentCard.developer))
        )
        result = await db.execute(stmt)
        db_card = result.scalar_one_or_none()

        if db_card:
            if db_card.developer:
                logger.debug(f"Found Agent Card: {db_card.name} (Developer: {db_card.developer.name})")
            else:
                logger.warning(f"Found Agent Card {db_card.name} but developer relationship was not loaded/found.")
        else:
            logger.debug(f"Agent Card with ID {card_id} not found.")
        return db_card
    except Exception as e:
        logger.error(f"Error fetching Agent Card {card_id}: {e}", exc_info=True)
        return None


async def list_agent_cards(
    db: AsyncSession, skip: int = 0, limit: int = 100, active_only: bool = True,
    search: Optional[str] = None, tags: Optional[List[str]] = None,
    developer_id: Optional[int] = None,
    # --- ADDED: Parameters from previous step ---
    has_tee: Optional[bool] = None,
    tee_type: Optional[str] = None
    # --- END ADDED ---
) -> Tuple[List[models.AgentCard], int]:
    """
    Retrieves a list of Agent Cards with pagination and optional filtering.
    """
    # --- MODIFIED: Updated logging ---
    logger.debug(f"Listing Agent Cards: skip={skip}, limit={limit}, active_only={active_only}, search='{search}', tags={tags}, developer_id={developer_id}, has_tee={has_tee}, tee_type='{tee_type}'")
    # --- END MODIFIED ---

    if os.environ.get("AGENTVAULT_USE_PLACEHOLDERS", "false").lower() == "true":
        logger.warning("!!! RETURNING PLACEHOLDER DATA FOR list_agent_cards !!!")
        placeholder_items_dict = _get_placeholder_items()
        placeholder_items = list(placeholder_items_dict.values())

        # Basic filtering for placeholders
        filtered_items = placeholder_items
        if active_only:
            filtered_items = [item for item in filtered_items if item.is_active]
        if search:
            search_lower = search.lower()
            filtered_items = [
                item for item in filtered_items
                if search_lower in item.name.lower() or (item.description and search_lower in item.description.lower())
            ]
        if tags:
            tags_set = set(tags)
            filtered_items = [
                item for item in filtered_items
                if isinstance(item.card_data.get("tags"), list) and tags_set.issubset(set(item.card_data["tags"]))
            ]
        if developer_id is not None:
            filtered_items = [item for item in filtered_items if item.developer_id == developer_id]
        # --- ADDED: Placeholder TEE filtering ---
        if has_tee is True:
            filtered_items = [item for item in filtered_items if item.card_data.get("capabilities", {}).get("teeDetails") is not None]
        elif has_tee is False:
            filtered_items = [item for item in filtered_items if item.card_data.get("capabilities", {}).get("teeDetails") is None]
        if tee_type:
            tee_type_lower = tee_type.lower()
            filtered_items = [
                item for item in filtered_items
                if item.card_data.get("capabilities", {}).get("teeDetails", {}).get("type", "").lower() == tee_type_lower
            ]
        # --- END ADDED ---

        total_items = len(filtered_items)
        paginated_items = filtered_items[skip : skip + limit]
        return paginated_items, total_items


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
            )
        )
    if tags:
        if isinstance(tags, list) and tags:
            try:
                # Ensure tags are treated as strings for the JSONB contains operator
                base_stmt = base_stmt.where(models.AgentCard.card_data['tags'].astext.cast(JSONB).contains(tags))
                logger.debug(f"Applied tag filter using JSONB contains: {tags}")
            except Exception as json_err:
                logger.warning(f"Could not apply JSONB @> operator for tag filtering (maybe not JSONB or data format issue?): {json_err}. Skipping tag filter.")
    if developer_id is not None:
        base_stmt = base_stmt.where(models.AgentCard.developer_id == developer_id)
        logger.debug(f"Applied developer ID filter: {developer_id}")

    # --- ADDED: TEE Filtering Logic ---
    if has_tee is True:
        logger.debug("Applying filter: has_tee = True")
        # Check if the path exists and is not JSON null
        base_stmt = base_stmt.where(models.AgentCard.card_data['capabilities']['teeDetails'].isnot(None))
    elif has_tee is False:
        logger.debug("Applying filter: has_tee = False")
        # Check if the path does not exist OR is JSON null
        # Using `is_(None)` should handle both cases correctly with JSONB path operators
        base_stmt = base_stmt.where(models.AgentCard.card_data['capabilities']['teeDetails'].is_(None))

    if tee_type:
        logger.debug(f"Applying filter: tee_type = '{tee_type}'")
        # Use the ->> operator to get the value as text for direct comparison
        # This assumes the 'type' field exists if 'teeDetails' exists.
        # Add path existence check if needed: .where(models.AgentCard.card_data['capabilities']['teeDetails'].isnot(None))
        base_stmt = base_stmt.where(
            models.AgentCard.card_data['capabilities']['teeDetails']['type'].astext == tee_type
        )
        # Alternative using cast, might be slightly less efficient:
        # base_stmt = base_stmt.where(
        #     cast(models.AgentCard.card_data['capabilities']['teeDetails']['type'], Text) == tee_type
        # )
    # --- END ADDED ---


    # Get total count matching filters *before* applying limit/offset
    try:
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await db.execute(count_stmt)
        total_items = count_result.scalar_one_or_none() or 0
    except Exception as e:
        logger.error(f"Error counting agent cards: {e}", exc_info=True)
        return [], 0

    logger.debug(f"Total matching agent cards found: {total_items}")

    # Apply ordering, offset, and limit for the final result set
    final_stmt = (
        base_stmt
        .options(selectinload(models.AgentCard.developer))
        .order_by(models.AgentCard.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )

    try:
        result = await db.execute(final_stmt)
        items = list(result.scalars().all())
        logger.debug(f"Returning {len(items)} agent cards for the current page.")
        return items, total_items
    except Exception as e:
        logger.error(f"Error executing agent card list query: {e}", exc_info=True)
        return [], total_items


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

        if not isinstance(card_update.card_data, dict):
            raise ValueError("Provided card_data for update must be a dictionary.")

        # --- MODIFIED: Merge before validation ---
        existing_data = db_card.card_data or {}
        merged_data = {**existing_data, **card_update.card_data}
        # --- END MODIFIED ---

        # Validate the *merged* data
        if not _agentvault_lib_available or AgentCardModel is None:
             logger.warning("Skipping Agent Card validation as 'agentvault' library is not available.")
             validated_data = merged_data # Use merged data directly
        else:
            try:
                # --- MODIFIED: Validate merged_data ---
                validated_card_model = AgentCardModel.model_validate(merged_data)
                validated_data = validated_card_model.model_dump(mode='json', by_alias=True) # Use by_alias
                # --- END MODIFIED ---
                logger.debug("Merged Agent Card data successfully validated.")
            except PydanticValidationError as e: # Catch imported name
                logger.error(f"Merged Agent Card validation failed: {e}", exc_info=True)
                raise ValueError(f"Invalid merged Agent Card data provided for update: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error during merged Agent Card update validation: {e}", exc_info=True)
                raise ValueError(f"Unexpected error validating merged Agent Card data: {e}") from e

        # Update stored data and extracted fields using validated merged data
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
        return db_card


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
