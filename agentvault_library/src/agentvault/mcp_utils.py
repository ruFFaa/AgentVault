"""
Utilities for handling Model Context Protocol (MCP) data formatting.

Note: The MCP specification is still evolving. This implementation provides
a basic structure and validation mechanism based on common needs.
It assumes the input context data is already structured appropriately
for embedding. Future versions may involve more complex parsing and mapping.
"""

import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Basic MCP Pydantic Models (Example Structure) ---
# These models represent a potential structure for MCP context.
# They might need significant refinement based on the finalized MCP spec.
# Note: This is a placeholder structure for Phase 1.

class MCPItem(BaseModel):
    """Represents a single item within the MCP context."""
    # Using Any allows flexibility for initial implementation
    id: Optional[str] = Field(None, description="Optional unique identifier for this item within the context.")
    media_type: Optional[str] = Field(None, alias="mediaType", description="MIME type of the content, if applicable.")
    content: Optional[Any] = Field(None, description="The actual content of the item (e.g., text, dict, list).")
    ref: Optional[str] = Field(None, description="Reference to another item or artifact (e.g., a file URL or artifact ID).")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata specific to this item.")

    # Basic validation example: Ensure either content or ref is present if not just metadata
    # @field_validator('*', mode='before') # Example - more complex validation can be added
    # def check_content_or_ref(cls, v, info):
    #     values = info.data
    #     if values.get('content') is None and values.get('ref') is None and values.get('metadata') is None:
    #          raise ValueError("MCPItem must have 'content', 'ref', or 'metadata'.")
    #     return v

class MCPContext(BaseModel):
    """Represents the overall MCP context payload."""
    # Using a dictionary allows named context items. A List[MCPItem] is another option.
    items: Dict[str, MCPItem] = Field(default_factory=dict, description="A dictionary of context items, keyed by a unique name or ID.")
    # You could add global metadata here as well
    # global_metadata: Optional[Dict[str, Any]] = None

# --- Formatting Function ---

def format_mcp_context(context_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validates and formats the input dictionary according to the MCPContext model.

    For this initial version, it primarily validates the structure using Pydantic
    and returns the dictionary representation if valid. Future versions should
    align with the official MCP specification.

    Args:
        context_data: A dictionary intended to represent the MCP context.

    Returns:
        A dictionary representing the validated MCP context payload, ready for
        JSON serialization, or None if validation fails.
    """
    if not isinstance(context_data, dict):
        logger.error("MCP context data must be a dictionary.")
        return None

    try:
        # Validate the input data against the MCPContext model
        # For now, we assume the input dict *is* the MCPContext structure
        # A more robust implementation would parse context_data and build MCPContext
        # Example: If context_data was {'my_text': 'abc', 'my_file': {'ref': 'url://...'}}
        # you would map it to MCPContext(items={'my_text': MCPItem(content='abc'), ...})
        # For simplicity now, we validate if the input *already matches* MCPContext structure.
        # Let's assume the input `context_data` directly represents the `MCPContext` fields.
        mcp_model = MCPContext.model_validate(context_data)

        # Return the dictionary representation of the validated model
        # Using exclude_unset=True can keep the payload cleaner if defaults weren't provided
        return mcp_model.model_dump(mode='json', exclude_unset=True, by_alias=True)

    except Exception as e: # Catch Pydantic ValidationError and others
        logger.error(f"Failed to validate or format MCP context data: {e}", exc_info=True)
        logger.debug(f"Invalid MCP context data received: {context_data}")
        return None
