import uuid
import datetime
# --- MODIFIED: Added EmailStr, SecretStr, Literal ---
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, EmailStr, SecretStr
# --- END MODIFIED ---

# Import local models for type checking
# from . import models # No longer needed here

# --- Developer Schemas (Define before AgentCardRead) ---

# --- ADDED: DeveloperCreate Schema ---
class DeveloperCreate(BaseModel):
    """Schema for creating a new developer."""
    name: str = Field(..., min_length=3, max_length=100, description="Unique name for the developer.")
    email: EmailStr = Field(..., description="Developer's email address.")
    password: SecretStr = Field(..., description="Developer's chosen password.")
# --- END ADDED ---

class DeveloperRead(BaseModel):
    """Schema for reading developer information."""
    id: int
    name: str
    # --- ADDED: email field ---
    email: EmailStr = Field(..., description="Developer's email address.")
    # --- END ADDED ---
    created_at: datetime.datetime
    is_verified: bool = Field(..., description="Indicates if the developer is verified.")

    model_config = ConfigDict(from_attributes=True)

# --- ADDED: Auth Related Schemas ---
class Token(BaseModel):
    """Schema for access token response."""
    access_token: str
    token_type: Literal["bearer"] = "bearer"

class RegistrationResponse(BaseModel):
    """Schema for the response after successful registration."""
    message: str
    recovery_keys: List[str] = Field(..., description="Generated recovery keys. Store these securely!")

class PasswordResetRequest(BaseModel):
    """Schema for requesting a password reset email."""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Schema for confirming password reset using a token."""
    token: str = Field(..., description="The password reset token received via email.")
    new_password: SecretStr = Field(..., description="The new password for the account.")

class PasswordResetRecover(BaseModel):
    """Schema for initiating password reset using a recovery key."""
    email: EmailStr = Field(..., description="The email address associated with the account.")
    recovery_key: str = Field(..., description="One of the recovery keys provided during registration.")

class PasswordSetNew(BaseModel):
    """Schema for setting a new password after recovery key validation."""
    # --- MODIFIED FOR DEBUGGING: Use str instead of SecretStr ---
    new_password: str = Field(..., description="The new password for the account.")
    # --- END MODIFIED ---
# --- END ADDED ---

# --- ADDED: API Key Schemas ---
class ApiKeyRead(BaseModel):
    """Schema for reading details about a developer's API key (excluding the key itself)."""
    id: int # Added ID for potential future management needs
    key_prefix: str = Field(..., description="The non-secret prefix of the API key (e.g., 'avreg_').")
    description: Optional[str] = Field(None, description="User-provided description for the key.")
    is_active: bool = Field(..., description="Whether the API key is currently active.")
    created_at: datetime.datetime = Field(..., description="Timestamp when the key was created.")
    last_used_at: Optional[datetime.datetime] = Field(None, description="Timestamp when the key was last used (if tracked).")

    model_config = ConfigDict(from_attributes=True)

class NewApiKeyResponse(BaseModel):
    """Schema for the response when a new API key is generated."""
    plain_api_key: str = Field(..., description="The full, plain-text API key. Store this securely, it will not be shown again.")
    api_key_info: ApiKeyRead = Field(..., description="Metadata about the newly created key.")
# --- END ADDED ---


# --- Agent Card Schemas ---

class AgentCardBase(BaseModel):
    """Base schema for Agent Card containing common fields."""
    name: str = Field(..., description="Human-readable display name of the agent.")
    description: Optional[str] = Field(None, description="Detailed description of the agent's purpose and functionality.")
    is_active: bool = Field(True, description="Whether the agent card is active and discoverable.")

class AgentCardCreate(BaseModel):
    """Schema for creating a new Agent Card via the API."""
    card_data: Dict[str, Any] = Field(
        ...,
        description="The full Agent Card JSON object conforming to the A2A Agent Card schema."
    )

class AgentCardUpdate(BaseModel):
    """Schema for updating an existing Agent Card via the API."""
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
    # --- MODIFIED: Reverted to developer_id and added developer_is_verified ---
    developer_id: int = Field(..., description="ID of the developer who owns this card.")
    developer_is_verified: bool = Field(..., description="Indicates if the developer owning this card is verified.")
    # --- END MODIFIED ---
    card_data: Dict[str, Any] = Field(..., description="The full Agent Card JSON object.")
    created_at: datetime.datetime = Field(..., description="Timestamp when the card was created.")
    updated_at: datetime.datetime = Field(..., description="Timestamp when the card was last updated.")
    # --- REMOVED: developer: DeveloperRead field ---
    # developer: DeveloperRead = Field(..., description="Details of the developer owning this card.")
    # --- END REMOVED ---


    # Enable ORM mode (now from_attributes=True)
    model_config = ConfigDict(from_attributes=True)


class AgentCardSummary(BaseModel):
    """Schema for representing a summarized Agent Card in list responses."""
    id: uuid.UUID = Field(..., description="Unique identifier for the Agent Card record.")
    name: str = Field(..., description="Human-readable display name of the agent.")
    description: Optional[str] = Field(None, description="Detailed description of the agent's purpose.")

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


# --- Developer Schemas (Moved earlier) ---
# class DeveloperRead defined above

# --- REMOVED: Old DeveloperCreateResponse ---
# class DeveloperCreateResponse(DeveloperRead):
#     """Schema for response after creating a developer, including the plain API key."""
#     api_key: str = Field(..., description="The generated plain-text API key. Store this securely!")
# --- END REMOVED ---

# --- Validation Schemas ---
class AgentCardValidationRequest(BaseModel):
    """Schema for requesting validation of Agent Card data."""
    card_data: Dict[str, Any] = Field(
        ...,
        description="The Agent Card JSON object to validate."
    )

class AgentCardValidationResponse(BaseModel):
    """Schema for the response of an Agent Card validation request."""
    is_valid: bool = Field(..., description="Indicates whether the provided card data is valid according to the schema.")
    detail: Optional[str] = Field(None, description="Provides details about validation errors if is_valid is False.")
    validated_card_data: Optional[Dict[str, Any]] = Field(None, description="The validated and potentially normalized card data if is_valid is True (optional).")
