import uuid
import datetime
# --- MODIFIED: Added Optional ---
from typing import List, Dict, Any, Optional
# --- END MODIFIED ---

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Index,
    # --- MODIFIED: Added unique=True for email token ---
    UUID as SQLUUID, func, UniqueConstraint
    # --- END MODIFIED ---
)
# --- MODIFIED: Import mapped_column and relationship directly if not already ---
# --- MODIFIED: Added DateTime ---
from sqlalchemy.orm import relationship, Mapped, mapped_column, selectinload # Added selectinload, DateTime
# --- END MODIFIED ---


# Import the Base class from database setup
from .database import Base

# --- Developer Model ---
class Developer(Base):
    """SQLAlchemy model for agent developers."""
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    # --- ADDED: New fields for email/password auth ---
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    verification_token_expires: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hashed_recovery_key: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Hash of one representative key
    # --- END ADDED ---
    # --- REMOVED: Old api_key_hash ---
    # api_key_hash: Mapped[str] = mapped_column(String, nullable=False)
    # --- END REMOVED ---
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True) # Ensure index=True
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship to AgentCard (one-to-many)
    agent_cards: Mapped[List["AgentCard"]] = relationship(
        "AgentCard", back_populates="developer", cascade="all, delete-orphan"
    )
    # --- ADDED: Relationship to DeveloperApiKey ---
    api_keys: Mapped[List["DeveloperApiKey"]] = relationship(
        "DeveloperApiKey", back_populates="developer", cascade="all, delete-orphan"
    )
    # --- END ADDED ---

    def __repr__(self):
        # --- MODIFIED: Add email and is_verified to repr ---
        return f"<Developer(id={self.id}, name='{self.name}', email='{self.email}', verified={self.is_verified})>"
        # --- END MODIFIED ---


# --- AgentCard Model ---
class AgentCard(Base):
    """SQLAlchemy model for storing Agent Card metadata."""
    __tablename__ = "agent_cards"

    # Using UUID for the primary key
    id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Foreign key to the developer who owns this card
    developer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("developers.id"), nullable=False, index=True
    )
    # Store the full Agent Card JSON data
    # JSONB is generally preferred in PostgreSQL for performance if available
    # SQLAlchemy's JSON type maps appropriately based on dialect
    card_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Extracted fields for easier querying and indexing
    # Ensure these fields are populated correctly in CRUD operations
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String, index=True, nullable=True) # Allow nullable description
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship back to Developer (many-to-one)
    developer: Mapped["Developer"] = relationship("Developer", back_populates="agent_cards")

    # Explicit indexes (optional if index=True used on columns, but good for clarity)
    # Note: Indexes on `name` and `description` might benefit from specific types
    # like `text_pattern_ops` in PostgreSQL for LIKE queries, configured via postgresql_using='gin' or similar.
    # A GIN index on `card_data` could be useful for deep JSON searches later.
    __table_args__ = (
        Index("ix_agent_cards_name", "name"),
        Index("ix_agent_cards_description", "description"), # Indexing description
        Index("ix_agent_cards_is_active", "is_active"),
        # Example GIN index for PostgreSQL (requires specific dialect setup):
        # Index('ix_agent_cards_card_data_gin', card_data, postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<AgentCard(id={self.id}, name='{self.name}', developer_id={self.developer_id})>"

# --- ADDED: DeveloperApiKey Model ---
class DeveloperApiKey(Base):
    """SQLAlchemy model for storing developer-specific programmatic API keys."""
    __tablename__ = "developer_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(Integer, ForeignKey("developers.id"), nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False, index=True) # e.g., "avreg_"
    hashed_key: Mapped[str] = mapped_column(String, nullable=False, unique=True) # Hash of the full key
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True) # User-provided description

    developer: Mapped["Developer"] = relationship("Developer", back_populates="api_keys")

    def __repr__(self):
        return f"<DeveloperApiKey(id={self.id}, developer_id={self.developer_id}, prefix='{self.key_prefix}', active={self.is_active})>"
# --- END ADDED ---
