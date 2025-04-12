import uuid
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Agent Card Schemas ---

class AgentCardBase(BaseModel):
    """Base schema for Agent Card containing common fields."""
    # These fields are derived from card_data in the DB model but useful in response schemas
    name: str = Field(..., description="Human-readable display name of the agent.")
    description: Optional[str] = Field(None, description="Detailed description of the agent's purpose and functionality.")
    is_active: bool = Field(True, description="Whether the agent card is active and discoverable.")

class AgentCardCreate(BaseModel):
    """Schema for creating a new Agent Card via the API."""
    # Accepts the full JSON payload of the Agent Card
    # Validation against the actual Agent Card schema (from agentvault library)
    # should happen in the CRUD layer or service layer.
    card_data: Dict[str, Any] = Field(
        ...,
        description="The full Agent Card JSON object conforming to the A2A Agent Card schema."
    )

class AgentCardUpdate(BaseModel):
    """Schema for updating an existing Agent Card via the API."""
    # Allows updating the full card data and/or the active status
    card_data: Optional[Dict[str, Any]] = Field(
        None,
        description="The full Agent Card JSON object conforming to the A2A Agent Card schema."
    )
    is_active: Optional[bool] = Field(
        None,
        description="Set the active status of the agent card."
    )

class AgentCardRead(AgentCardBase):
    """Schema for representing a full Agent Card read from the database."""
    id: uuid.UUID = Field(..., description="Unique identifier for the Agent Card record.")
    developer_id: int = Field(..., description="ID of the developer who owns this card.")
    card_data: Dict[str, Any] = Field(..., description="The full Agent Card JSON object.")
    created_at: datetime.datetime = Field(..., description="Timestamp when the card was created.")
    updated_at: datetime.datetime = Field(..., description="Timestamp when the card was last updated.")

    # Enable ORM mode (now from_attributes in Pydantic v2)
    # Allows creating this schema directly from the SQLAlchemy model instance
    model_config = ConfigDict(from_attributes=True)

class AgentCardSummary(BaseModel):
    """Schema for representing a summarized Agent Card in list responses."""
    id: uuid.UUID = Field(..., description="Unique identifier for the Agent Card record.")
    name: str = Field(..., description="Human-readable display name of the agent.")
    description: Optional[str] = Field(None, description="Detailed description of the agent's purpose.")
    # Add other summary fields if needed, e.g., icon_url from card_data

    model_config = ConfigDict(from_attributes=True)


# --- Pagination Schemas ---

class PaginationInfo(BaseModel):
    """Schema for pagination details in list responses."""
    total_items: int = Field(..., description="Total number of items available.")
    limit: int = Field(..., description="Number of items requested per page.")
    offset: int = Field(..., description="Offset of the current page.")
    total_pages: int = Field(..., description="Total number of pages available.")
    current_page: int = Field(..., description="The current page number (1-based).")


# --- List Response Schemas ---

class AgentCardListResponse(BaseModel):
    """Schema for the response when listing Agent Cards."""
    items: List[AgentCardSummary] = Field(..., description="List of agent card summaries for the current page.")
    pagination: PaginationInfo = Field(..., description="Pagination details.")


# --- Developer Schemas (Optional but good practice) ---

class DeveloperCreate(BaseModel):
    """Schema for creating a new developer (e.g., via an admin interface)."""
    name: str = Field(..., min_length=3, max_length=100, description="Unique name for the developer.")

class DeveloperRead(BaseModel):
    """Schema for reading developer information."""
    id: int
    name: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# Maybe add a schema for returning the API key on creation?
class DeveloperCreateResponse(DeveloperRead):
    """Schema for response after creating a developer, including the plain API key."""
    api_key: str = Field(..., description="The generated plain-text API key. Store this securely!")
