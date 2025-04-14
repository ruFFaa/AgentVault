import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status
import pydantic

# Import local schemas
from agentvault_registry import schemas

# Import the AgentCard model from the core library for validation
try:
    from agentvault import AgentCard as AgentCardModel
    _agentvault_lib_available = True
except ImportError:
    AgentCardModel = None # type: ignore
    _agentvault_lib_available = False
    logging.warning("Could not import 'agentvault' library. Agent Card validation endpoint will skip validation.")


logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/validate-card",
    response_model=schemas.AgentCardValidationResponse,
    summary="Validate Agent Card Data",
    description="Validates the provided JSON data against the official AgentVault Agent Card schema.",
    tags=["Utilities"] # Add a tag for grouping in OpenAPI docs
)
async def validate_agent_card(
    request: schemas.AgentCardValidationRequest
) -> schemas.AgentCardValidationResponse:
    """
    Validates Agent Card JSON data.

    - **request**: The request body containing the `card_data` dictionary.
    """
    logger.info("Received request to validate agent card data.")

    if not _agentvault_lib_available or AgentCardModel is None:
        logger.warning("Skipping validation as core 'agentvault' library is unavailable.")
        return schemas.AgentCardValidationResponse(
            is_valid=True, # Treat as valid if we can't check
            detail="Validation skipped: Core library not available.",
            validated_card_data=request.card_data # Return original data
        )

    try:
        # Attempt to validate using the core library's model
        validated_card = AgentCardModel.model_validate(request.card_data)
        logger.info("Agent card data validation successful.")
        # Return success with the validated (potentially normalized) data
        return schemas.AgentCardValidationResponse(
            is_valid=True,
            validated_card_data=validated_card.model_dump(mode='json', by_alias=True)
        )
    except pydantic.ValidationError as e:
        logger.warning(f"Agent card data validation failed: {e}")
        # Return failure with detailed validation errors
        return schemas.AgentCardValidationResponse(
            is_valid=False,
            detail=str(e) # Pydantic's error string is usually informative
        )
    except Exception as e:
        logger.exception("Unexpected error during agent card validation.")
        # Return failure for unexpected errors
        return schemas.AgentCardValidationResponse(
            is_valid=False,
            detail=f"An unexpected error occurred during validation: {type(e).__name__}"
        )
