# AgentVault Server SDK
# Provides base classes and utilities for building A2A agents.

__version__ = "0.1.0"

# Expose key components
try:
    from .agent import BaseA2AAgent
    from .fastapi_integration import create_a2a_router
    # --- REMOVED: Exception imports ---
except ImportError as e:
    # Allow init to load even if submodules aren't fully created yet
    import logging
    logging.getLogger(__name__).warning(f"Import error during SDK init: {e}", exc_info=False)
    pass

# --- REMOVED: Exceptions from __all__ ---
__all__ = [
    "BaseA2AAgent",
    "create_a2a_router",
]
