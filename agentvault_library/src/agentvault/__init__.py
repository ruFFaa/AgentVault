# AgentVault Core Library
# Provides client implementations for A2A/MCP protocols and secure key management.

__version__ = "0.1.0"

# Import core components for easier access
# (These imports will initially fail until the files are created)
try:
    from .exceptions import (
        AgentVaultError, AgentCardError, AgentCardValidationError, AgentCardFetchError,
        A2AError, A2AConnectionError, A2AAuthenticationError, A2ARemoteAgentError,
        A2ATimeoutError, A2AMessageError, KeyManagementError
    )
    from .key_manager import KeyManager
    from .agent_card_utils import (
        parse_agent_card_from_dict, load_agent_card_from_file, fetch_agent_card_from_url
    )
    from .client import AgentVaultClient
    from .models.agent_card import AgentCard # Expose main model
    from .models.a2a_protocol import Message, TextPart, FilePart, DataPart # Expose core message parts
except ImportError:
    # Allow init to load even if submodules aren't created yet during setup
    pass

# Explicitly define __all__ later once components exist
__all__ = [
    # Add class/function names here as they are implemented
    # "AgentVaultClient", "KeyManager", "AgentCard", ...
]
