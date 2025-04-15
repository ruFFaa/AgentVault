# AgentVault Server SDK
# Provides base classes and utilities for building A2A agents.

__version__ = "0.1.0"

# Expose key components
try:
    from .agent import BaseA2AAgent
    # --- MODIFIED: Import create_a2a_router and a2a_method ---
    from .fastapi_integration import create_a2a_router, a2a_method
    # --- END MODIFIED ---
    # --- ADDED: Import exceptions ---
    from .exceptions import AgentServerError, TaskNotFoundError, InvalidStateTransitionError, AgentProcessingError, ConfigurationError
    # --- END ADDED ---
    # --- ADDED: Import state management ---
    from .state import BaseTaskStore, InMemoryTaskStore, TaskContext
    # --- END ADDED ---
except ImportError as e:
    # Allow init to load even if submodules aren't fully created yet
    import logging
    logging.getLogger(__name__).warning(f"Import error during SDK init: {e}", exc_info=False)
    # Define placeholders if needed for basic loading, though functionality will be broken
    BaseA2AAgent = None # type: ignore
    create_a2a_router = None # type: ignore
    a2a_method = None # type: ignore
    AgentServerError = Exception # type: ignore
    TaskNotFoundError = Exception # type: ignore
    InvalidStateTransitionError = Exception # type: ignore
    AgentProcessingError = Exception # type: ignore
    ConfigurationError = Exception # type: ignore
    BaseTaskStore = None # type: ignore
    InMemoryTaskStore = None # type: ignore
    TaskContext = None # type: ignore
    pass

# --- MODIFIED: Update __all__ ---
__all__ = [
    "BaseA2AAgent",
    "create_a2a_router",
    "a2a_method",
    "AgentServerError",
    "TaskNotFoundError",
    "InvalidStateTransitionError",
    "AgentProcessingError",
    "ConfigurationError",
    "BaseTaskStore",
    "InMemoryTaskStore",
    "TaskContext",
]
# --- END MODIFIED ---
