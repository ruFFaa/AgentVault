# AgentVault Server SDK
# Provides base classes and utilities for building A2A agents.

__version__ = "0.1.0"

# Expose key components
try:
    from .agent import BaseA2AAgent
    from .fastapi_integration import create_a2a_router
except ImportError:
    # Allow init to load even if submodules aren't fully created yet
    pass

__all__ = [
    "BaseA2AAgent",
    "create_a2a_router",
]
