import logging
import uuid
import math
import datetime
import os
from typing import Optional, List, Dict, Any, Tuple

# --- MODIFIED: Import JSONB and cast, and_ ---
from sqlalchemy import select, func, or_, cast, Text, and_
# --- END MODIFIED ---
# --- MODIFIED: Import JSONB ---
from sqlalchemy.dialects.postgresql import JSONB
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
        dev1 = models.Developer(id=1, name="Dev One", email="dev1@example.com", hashed_password="hash1", is_verified=True)
        dev2 = models.Developer(id=2, name="Dev Two", email="dev2@example.com", hashed_password="hash2", is_verified=False)
        tee_card_data = {
            "url": "http://tee-agent.example", "tags": ["tee", "secure"], "name": "TEE Agent", "description": "Desc",
            "schemaVersion": "1.0", "humanReadableId": "dev1/tee", "agentVersion": "1.0", "provider": {"name": "Dev One"},
            "capabilities": {
                "a2aVersion": "1.0",
                "teeDetails": {
                    "type": "Intel SGX",
                    "attestationEndpoint": "https://attest.example.com"
                }
            },
            "authSchemes": [{"scheme": "none"}]
        }
        items = [
            models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="Weather Agent (Placeholder)",
                description="Provides weather forecasts.", is_active=True,
                created_at=now, updated_at=now, card_data={"url": "http://weather.example", "tags": ["weather", "forecast", "public"], "name": "Weather Agent (Placeholder)", "description": "Provides weather forecasts.", "schemaVersion": "1.0", "humanReadableId": "dev1/weather", "agentVersion": "1.0", "provider": {"name": "Dev One"}, "capabilities": {"a2aVersion": "1.0"}, "authSchemes": [{"scheme": "none"}]}, developer=dev1
            ),
            models.AgentCard(
                id=uuid.uuid4(), developer_id=2, name="Summarizer Agent (Placeholder)",
                description="Summarizes long texts.", is_active=True,
                created_at=now, updated_at=now, card_data={"url": "http://summarizer.example", "privacyPolicyUrl": "http://summarizer.example/privacy", "tags": ["text", "summarization", "nlp"], "name": "Summarizer Agent (Placeholder)", "description": "Summarizes long texts.", "schemaVersion": "1.0", "humanReadableId": "dev2/summarizer", "agentVersion": "1.0", "provider": {"name": "Dev Two"}, "capabilities": {"a2aVersion": "1.0"}, "authSchemes": [{"scheme": "none"}]}, developer=dev2
            ),
             models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="Inactive Agent (Placeholder)",
                description="This one is inactive.", is_active=False,
                created_at=now, updated_at=now, card_data={"url": "http://inactive.example", "termsOfServiceUrl": "http://inactive.example/terms", "tags": ["internal", "test"], "name": "Inactive Agent (Placeholder)", "description": "This one is inactive.", "schemaVersion": "1.0", "humanReadableId": "dev1/inactive", "agentVersion": "1.0", "provider": {"name": "Dev One"}, "capabilities": {"a2aVersion": "1.0"}, "authSchemes": [{"scheme": "none"}]}, developer=dev1
            ),
             models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="Weather Tool (Placeholder)",
                description="Internal weather tool.", is_active=True,
                created_at=now, updated_at=now, card_data={"url": "http://weather-tool.internal", "tags": ["weather", "tool", "internal"], "name": "Weather Tool (Placeholder)", "description": "Internal weather tool.", "schemaVersion": "1.0", "humanReadableId": "dev1/weather-tool", "agentVersion": "1.0", "provider": {"name": "Dev One"}, "capabilities": {"a2aVersion": "1.0"}, "authSchemes": [{"scheme": "none"}]}, developer=dev1
            ),
            models.AgentCard(
                id=uuid.uuid4(), developer_id=1, name="TEE Agent (Placeholder)",
                description="Runs in a TEE.", is_active=True,
                created_at=now, updated_at=now, card_data=tee_card_data, developer=dev1
            ),
        ]
        _placeholder_data_cache = {item.id: item for item in items}
        for item in items:
             if item.card_data and isinstance(item.card_data, dict) and item.card_data.get("humanReadableId"):
                 _placeholder_data_cache[item.card_data["humanReadableId"]] = item

    return _placeholder_data_cache


async def create_agent_card(
    db: AsyncSession, developer_id: int, card_create: schemas.AgentCardCreate
) -> Optional[models.AgentCard]:
    """
    Creates a new Agent Card record in the database after validating the card data.
    """
    logger.info(f"Attempting to create Agent Card for developer ID: {developer_id}")

    if not _agentvault_lib_available or AgentCardModel is None:
        logger.warning("Skipping Agent Card validation as 'agentvault' library is not available.")
        validated_data = card_create.card_data
    else:
        try:
            validated_card_model = AgentCardModel.model_validate(card_create.card_data)
            validated_data = validated_card_model.model_dump(mode='json', by_alias=True)
            logger.debug("Agent Card data successfully validated against core model.")
        except PydanticValidationError as e:
            logger.error(f"Agent Card validation failed: {e}", exc_info=True)
            raise ValueError(f"Invalid Agent Card data provided: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error during Agent Card validation: {e}", exc_info=True)
             raise ValueError(f"Unexpected error validating Agent Card data: {e}") from e

    try:
        name = validated_data.get("name")
        description = validated_data.get("description")
        if not name:
            raise ValueError("Validated card data is missing the required 'name' field.")
    except Exception as e:
        logger.error(f"Failed to extract required fields (name, description) from validated card data: {e}", exc_info=True)
        raise ValueError(f"Could not extract required fields from card data: {e}") from e

    db_agent_card = models.AgentCard(
        developer_id=developer_id,
        card_data=validated_data,
        name=name,
        description=description,
        is_active=True
    )

    db.add(db_agent_card)
    try:
        await db.commit()
        await db.refresh(db_agent_card)
        logger.info(f"Successfully created Agent Card '{name}' with ID: {db_agent_card.id}")
        return db_agent_card
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating agent card '{name}': {e}", exc_info=True)
        raise ValueError(f"Database error creating agent card: {e}") from e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected database error creating agent card '{name}': {e}", exc_info=True)
        raise ValueError(f"Unexpected database error: {e}") from e


async def get_agent_card(db: AsyncSession, card_id: uuid.UUID) -> Optional[models.AgentCard]:
    """
    Retrieves a single Agent Card by its UUID, eagerly loading the developer relationship.
    """
    logger.debug(f"Fetching Agent Card with ID: {card_id}, eagerly loading developer.")

    if os.environ.get("AGENTVAULT_USE_PLACEHOLDERS", "false").lower() == "true":
        logger.warning(f"!!! RETURNING PLACEHOLDER DATA FOR get_agent_card ID: {card_id} !!!")
        placeholder_items = _get_placeholder_items()
        item = placeholder_items.get(card_id)
        if item: logger.debug(f"Found placeholder Agent Card: {item.name}")
        else: logger.debug(f"Placeholder Agent Card with ID {card_id} not found.")
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
            if db_card.developer: logger.debug(f"Found Agent Card: {db_card.name} (Developer: {db_card.developer.name})")
            else: logger.warning(f"Found Agent Card {db_card.name} but developer relationship was not loaded/found.")
        else: logger.debug(f"Agent Card with ID {card_id} not found.")
        return db_card
    except Exception as e:
        logger.error(f"Error fetching Agent Card {card_id}: {e}", exc_info=True)
        return None

# --- ADDED: get_agent_card_by_human_readable_id ---
async def get_agent_card_by_human_readable_id(db: AsyncSession, human_readable_id: str) -> Optional[models.AgentCard]:
    """
    Retrieves a single Agent Card by its humanReadableId stored within the card_data JSONB field.
    """
    logger.debug(f"Fetching Agent Card by humanReadableId: {human_readable_id}")

    if os.environ.get("AGENTVAULT_USE_PLACEHOLDERS", "false").lower() == "true":
        logger.warning(f"!!! RETURNING PLACEHOLDER DATA FOR get_agent_card_by_human_readable_id: {human_readable_id} !!!")
        placeholder_items = _get_placeholder_items()
        item = placeholder_items.get(human_readable_id) # Use ID as key in placeholder
        if item: logger.debug(f"Found placeholder Agent Card by human ID: {item.name}")
        else: logger.debug(f"Placeholder Agent Card with human ID {human_readable_id} not found.")
        return item

    # --- MODIFIED: Implement actual query ---
    try:
        # Query using JSONB path operator ->> to extract text and compare
        stmt = (
            select(models.AgentCard)
            .where(models.AgentCard.card_data['humanReadableId'].astext == human_readable_id)
            .options(selectinload(models.AgentCard.developer)) # Eager load developer
        )
        result = await db.execute(stmt)
        db_card = result.scalar_one_or_none()

        if db_card:
            logger.debug(f"Found Agent Card by humanReadableId: {db_card.name} (ID: {db_card.id})")
        else:
            logger.debug(f"Agent Card with humanReadableId '{human_readable_id}' not found.")
        return db_card
    except Exception as e:
        # Catch potential errors if card_data isn't JSONB or path doesn't exist
        logger.error(f"Error fetching Agent Card by humanReadableId '{human_readable_id}': {e}", exc_info=True)
        return None
    # --- END MODIFIED ---
# --- END ADDED ---


async def list_agent_cards(
    db: AsyncSession, skip: int = 0, limit: int = 100, active_only: bool = True,
    search: Optional[str] = None, tags: Optional[List[str]] = None,
    developer_id: Optional[int] = None,
    has_tee: Optional[bool] = None,
    tee_type: Optional[str] = None
) -> Tuple[List[models.AgentCard], int]:
    """
    Retrieves a list of Agent Cards with pagination and optional filtering.
    """
    logger.debug(f"Listing Agent Cards: skip={skip}, limit={limit}, active_only={active_only}, search='{search}', tags={tags}, developer_id={developer_id}, has_tee={has_tee}, tee_type='{tee_type}'")

    if os.environ.get("AGENTVAULT_USE_PLACEHOLDERS", "false").lower() == "true":
        logger.warning("!!! RETURNING PLACEHOLDER DATA FOR list_agent_cards !!!")
        placeholder_items_dict = _get_placeholder_items()
        placeholder_items = list(placeholder_items_dict.values())

        # Basic filtering for placeholders
        filtered_items = placeholder_items
        if active_only: filtered_items = [item for item in filtered_items if item.is_active]
        if search:
            search_lower = search.lower()
            filtered_items = [item for item in filtered_items if search_lower in item.name.lower() or (item.description and search_lower in item.description.lower())]
        if tags:
            tags_set = set(tag.lower() for tag in tags) # Case-insensitive tag check
            filtered_items = [item for item in filtered_items if isinstance(item.card_data.get("tags"), list) and tags_set.issubset(set(t.lower() for t in item.card_data["tags"]))]
        if developer_id is not None: filtered_items = [item for item in filtered_items if item.developer_id == developer_id]
        if has_tee is True: filtered_items = [item for item in filtered_items if item.card_data.get("capabilities", {}).get("teeDetails") is not None]
        elif has_tee is False: filtered_items = [item for item in filtered_items if item.card_data.get("capabilities", {}).get("teeDetails") is None]
        if tee_type:
            tee_type_lower = tee_type.lower()
            filtered_items = [item for item in filtered_items if item.card_data.get("capabilities", {}).get("teeDetails", {}).get("type", "").lower() == tee_type_lower]

        total_items = len(filtered_items)
        paginated_items = filtered_items[skip : skip + limit]
        return paginated_items, total_items


    # Base statement
    base_stmt = select(models.AgentCard)
    count_stmt_base = select(func.count()).select_from(models.AgentCard) # Base for counting

    # Apply filters to both statements
    filters = []
    if active_only: filters.append(models.AgentCard.is_active == True)
    if search:
        search_term = f"%{search}%"
        filters.append(or_(models.AgentCard.name.ilike(search_term), models.AgentCard.description.ilike(search_term)))
    if tags:
        if isinstance(tags, list) and tags:
            try:
                # Ensure tags are treated as strings for the JSONB contains operator
                filters.append(models.AgentCard.card_data['tags'].astext.cast(JSONB).contains(tags))
                logger.debug(f"Applied tag filter using JSONB contains: {tags}")
            except Exception as json_err:
                logger.warning(f"Could not apply JSONB @> operator for tag filtering (maybe not JSONB or data format issue?): {json_err}. Skipping tag filter.")
    if developer_id is not None: filters.append(models.AgentCard.developer_id == developer_id)
    if has_tee is True: filters.append(models.AgentCard.card_data['capabilities']['teeDetails'].isnot(None))
    elif has_tee is False: filters.append(models.AgentCard.card_data['capabilities']['teeDetails'].is_(None))
    if tee_type: filters.append(models.AgentCard.card_data['capabilities']['teeDetails']['type'].astext == tee_type)

    if filters:
        base_stmt = base_stmt.where(and_(*filters))
        count_stmt_base = count_stmt_base.where(and_(*filters))

    # Get total count
    try:
        count_result = await db.execute(count_stmt_base)
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
    """
    logger.info(f"Attempting to update Agent Card ID: {db_card.id}")
    update_data_provided = False

    if card_update.card_data is not None:
        update_data_provided = True
        logger.debug(f"Updating card_data for Agent Card ID: {db_card.id}")
        if not isinstance(card_update.card_data, dict): raise ValueError("Provided card_data for update must be a dictionary.")

        existing_data = db_card.card_data or {}
        merged_data = {**existing_data, **card_update.card_data}

        if not _agentvault_lib_available or AgentCardModel is None:
             logger.warning("Skipping Agent Card validation as 'agentvault' library is not available.")
             validated_data = merged_data
        else:
            try:
                validated_card_model = AgentCardModel.model_validate(merged_data)
                validated_data = validated_card_model.model_dump(mode='json', by_alias=True)
                logger.debug("Merged Agent Card data successfully validated.")
            except PydanticValidationError as e:
                logger.error(f"Merged Agent Card validation failed: {e}", exc_info=True)
                raise ValueError(f"Invalid merged Agent Card data provided for update: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error during merged Agent Card update validation: {e}", exc_info=True)
                raise ValueError(f"Unexpected error validating merged Agent Card data: {e}") from e

        db_card.card_data = validated_data
        try:
            db_card.name = validated_data.get("name")
            db_card.description = validated_data.get("description")
            if not db_card.name: raise ValueError("Validated card data for update is missing the required 'name' field.")
        except Exception as e:
            logger.error(f"Failed to extract required fields from updated card data: {e}", exc_info=True)
            raise ValueError(f"Could not extract required fields from updated card data: {e}") from e

    if card_update.is_active is not None:
        if db_card.is_active != card_update.is_active:
             update_data_provided = True
             logger.debug(f"Updating is_active status for Agent Card ID {db_card.id} to {card_update.is_active}")
             db_card.is_active = card_update.is_active

    if update_data_provided:
        try:
            db.add(db_card)
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
    """
    logger.info(f"Attempting to soft delete (deactivate) Agent Card ID: {card_id}")
    db_card = await get_agent_card(db, card_id) # Reuse existing get function

    if db_card:
        if not db_card.is_active:
            logger.warning(f"Agent Card {card_id} is already inactive.")
            return True

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
            return False
    else:
        logger.warning(f"Agent Card {card_id} not found for deactivation.")
        return False
