"""
Pydantic models representing the structures used in the Agent-to-Agent (A2A) protocol.

Based on common A2A concepts and structures (specific schema version TBD).
Note: This implementation assumes a baseline A2A protocol version.
Future versions may need adjustments based on standard evolution.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
import datetime

# --- Core Enumerations ---

class TaskState(str, Enum):
    """
    Represents the possible states of an A2A task.

    States:
        SUBMITTED: Task received by the agent, awaiting execution.
        WORKING: Task is actively being processed by the agent.
        INPUT_REQUIRED: Task is paused, awaiting further input from the user/client.
        COMPLETED: Task finished successfully.
        FAILED: Task terminated due to an error during execution.
        CANCELED: Task was canceled by user request before completion.
    """
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


# --- Message Parts ---

class TextPart(BaseModel):
    """Represents a plain text part of a message."""
    model_config = ConfigDict(frozen=True) # Parts are typically immutable once created
    type: Literal['text'] = "text"
    content: str = Field(..., description="The plain text content.")

class FilePart(BaseModel):
    """Represents a reference to a file within a message."""
    model_config = ConfigDict(frozen=True)
    type: Literal['file'] = "file"
    url: HttpUrl = Field(..., description="URL pointing to the file content.")
    media_type: Optional[str] = Field(None, alias="mediaType", description="MIME type of the file (e.g., 'image/png', 'application/pdf').")
    filename: Optional[str] = Field(None, description="Original filename, if known.")
    # Add size, checksum etc. if needed

class DataPart(BaseModel):
    """Represents structured data (e.g., JSON) within a message."""
    model_config = ConfigDict(frozen=True)
    type: Literal['data'] = "data"
    content: Dict[str, Any] = Field(..., description="The structured data content (JSON object).")
    media_type: str = Field("application/json", alias="mediaType", description="MIME type of the data, defaults to application/json.")

# Union type for message parts
Part = Union[TextPart, FilePart, DataPart]

# --- Artifacts ---

class Artifact(BaseModel):
    """Represents an artifact generated or consumed by a task."""
    id: str = Field(..., description="Unique identifier for the artifact within the task context.")
    type: str = Field(..., description="Type identifier for the artifact (e.g., 'file', 'log', 'intermediate_result').")
    content: Optional[Any] = Field(None, description="Direct content of the artifact (if small/simple).")
    url: Optional[HttpUrl] = Field(None, description="URL pointing to the artifact content (if large/external).")
    media_type: Optional[str] = Field(None, alias="mediaType", description="MIME type of the artifact content.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata about the artifact.")

    @field_validator('content', 'url')
    @classmethod
    def check_content_or_url(cls, v: Optional[Any], info: Any) -> Optional[Any]:
        """Ensure either content or url is provided, but not both (common pattern)."""
        # This validation logic might need adjustment based on exact schema rules
        # For now, just allowing either or none. More complex validation could enforce one exists.
        # if values.get('content') is not None and values.get('url') is not None:
        #     raise ValueError("Artifact cannot have both 'content' and 'url'.")
        # if values.get('content') is None and values.get('url') is None:
        #     raise ValueError("Artifact must have either 'content' or 'url'.")
        return v

# --- Messages ---

class Message(BaseModel):
    """Represents a single message within an A2A task conversation."""
    model_config = ConfigDict(frozen=True) # Messages are typically immutable
    role: Literal['user', 'assistant', 'system', 'tool'] = Field(..., description="The role of the entity sending the message.")
    parts: List[Part] = Field(..., min_length=1, description="List of message parts comprising the content.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata associated with the message (e.g., timestamps, tool call info, MCP context).")

# --- Task ---

class Task(BaseModel):
    """Represents the state and history of an A2A task."""
    id: str = Field(..., description="Unique identifier for the task.")
    state: TaskState = Field(..., description="The current execution state of the task.")
    created_at: datetime.datetime = Field(..., alias="createdAt", description="Timestamp when the task was created.")
    updated_at: datetime.datetime = Field(..., alias="updatedAt", description="Timestamp when the task was last updated.")
    messages: List[Message] = Field(default_factory=list, description="Chronological list of messages exchanged during the task.")
    artifacts: List[Artifact] = Field(default_factory=list, description="List of artifacts associated with the task.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata associated with the task itself.")

# --- JSON-RPC Style Parameters & Results (for common methods) ---

# Parameters for tasks/send
class TaskSendParams(BaseModel):
    """Parameters for initiating or continuing a task."""
    id: Optional[str] = Field(None, description="Task ID if continuing an existing task, null/omitted if initiating.")
    message: Message = Field(..., description="The message to send to the agent.")
    # Potentially add skill_id, context, etc. here if needed

# Result of tasks/send
class TaskSendResult(BaseModel):
    """Result returned when sending a message to a task."""
    id: str = Field(..., description="The ID of the task (newly created or existing).")
    # Potentially add initial status or confirmation details

# Parameters for tasks/get
class TaskGetParams(BaseModel):
    """Parameters for retrieving task status."""
    id: str = Field(..., description="The ID of the task to retrieve.")

# Result of tasks/get (is the full Task object)
GetTaskResult = Task

# Parameters for tasks/cancel
class TaskCancelParams(BaseModel):
    """Parameters for requesting task cancellation."""
    id: str = Field(..., description="The ID of the task to cancel.")

# Result of tasks/cancel
class TaskCancelResult(BaseModel):
    """Result confirming task cancellation request was received."""
    success: bool = Field(True, description="Indicates if the cancellation request was accepted.")
    message: Optional[str] = Field(None, description="Optional message regarding cancellation.")


# --- Server-Sent Events (SSE) Payloads ---

class TaskStatusUpdateEvent(BaseModel):
    """Event sent via SSE when the task's status changes."""
    # --- ADDED: model_config ---
    model_config = ConfigDict(populate_by_name=True)
    # --- END ADDED ---
    task_id: str = Field(..., alias="taskId", description="The ID of the task being updated.")
    state: TaskState = Field(..., description="The new state of the task.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the status update.")
    message: Optional[str] = Field(None, description="Optional message accompanying the status change (e.g., error details).")

class TaskMessageEvent(BaseModel):
    """Event sent via SSE when a new message is added to the task."""
    # --- ADDED: model_config ---
    model_config = ConfigDict(populate_by_name=True)
    # --- END ADDED ---
    task_id: str = Field(..., alias="taskId", description="The ID of the task.")
    message: Message = Field(..., description="The new message added to the task.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the event.")

class TaskArtifactUpdateEvent(BaseModel):
    """Event sent via SSE when an artifact is created or updated."""
    # --- ADDED: model_config ---
    model_config = ConfigDict(populate_by_name=True)
    # --- END ADDED ---
    task_id: str = Field(..., alias="taskId", description="The ID of the task.")
    artifact: Artifact = Field(..., description="The artifact that was created or updated.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the artifact update.")

#
