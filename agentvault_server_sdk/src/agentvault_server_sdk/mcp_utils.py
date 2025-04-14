"""
Utilities for safely extracting Model Context Protocol (MCP) data
from A2A messages on the server-side.
"""

import logging
from typing import Optional, Dict, Any

# Import core types from the agentvault library
try:
    from agentvault.models import Message
    _AGENTVAULT_IMPORTED = True
except ImportError:
    logging.getLogger(__name__).error("Failed to import Message model from 'agentvault'. MCP utils may not function correctly.")
    # Define placeholder if import fails
    class Message: # type: ignore
        metadata: Optional[Dict[str, Any]] = None
    _AGENTVAULT_IMPORTED = False

logger = logging.getLogger(__name__)

def get_mcp_context(message: Message) -> Optional[Dict[str, Any]]:
    """
    Safely extracts the MCP context dictionary from an A2A Message object.

    Checks for the presence and correct type of `message.metadata` and
    the `mcp_context` key within it.

    Args:
        message: The A2A Message object to extract context from.

    Returns:
        The MCP context dictionary if found and valid, otherwise None.
    """
    if not hasattr(message, 'metadata') or message.metadata is None:
        logger.debug("Message has no metadata attribute or metadata is None.")
        return None

    if not isinstance(message.metadata, dict):
        logger.warning(f"Message metadata is not a dictionary (type: {type(message.metadata)}). Cannot extract MCP context.")
        return None

    mcp_context = message.metadata.get('mcp_context')

    if mcp_context is None:
        logger.debug("Metadata found, but 'mcp_context' key is not present.")
        return None

    if not isinstance(mcp_context, dict):
        logger.warning(f"'mcp_context' found in metadata, but it is not a dictionary (type: {type(mcp_context)}).")
        return None

    logger.debug("Successfully extracted MCP context dictionary from message metadata.")
    return mcp_context
