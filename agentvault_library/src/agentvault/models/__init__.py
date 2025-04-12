# Pydantic models for AgentVault Library

# Expose the core Agent Card models for easier import
from .agent_card import (
    AgentProvider,
    AgentSkill,
    AgentAuthentication,
    AgentCapabilities,
    AgentCard
)

# Expose the core A2A protocol models
from .a2a_protocol import (
    TaskState,
    TextPart,
    FilePart,
    DataPart,
    Part,
    Artifact,
    Message,
    Task,
    TaskSendParams,
    TaskSendResult,
    TaskGetParams,
    GetTaskResult,       # Alias for Task
    TaskCancelParams,
    TaskCancelResult,
    TaskStatusUpdateEvent,
    TaskMessageEvent,
    TaskArtifactUpdateEvent,
)


__all__ = [
    # Agent Card Models
    "AgentProvider",
    "AgentSkill",
    "AgentAuthentication",
    "AgentCapabilities",
    "AgentCard",
    # A2A Protocol Models
    "TaskState",
    "TextPart",
    "FilePart",
    "DataPart",
    "Part",
    "Artifact",
    "Message",
    "Task",
    "TaskSendParams",
    "TaskSendResult",
    "TaskGetParams",
    "GetTaskResult",
    "TaskCancelParams",
    "TaskCancelResult",
    "TaskStatusUpdateEvent",
    "TaskMessageEvent",
    "TaskArtifactUpdateEvent",
]
#
