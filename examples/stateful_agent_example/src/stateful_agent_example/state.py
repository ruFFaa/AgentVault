"""
Defines custom TaskContext for the stateful agent example.
"""
import asyncio
from dataclasses import dataclass, field
from typing import List

# Import SDK base context and core models
from agentvault_server_sdk.state import TaskContext
from agentvault.models import Message

@dataclass
class ChatTaskContext(TaskContext):
    """Extends TaskContext to store chat history and an event signal."""
    history: List[Message] = field(default_factory=list)
    # Event to signal new message arrival to the background processing task
    new_message_event: asyncio.Event = field(default_factory=asyncio.Event)
    # Event to signal cancellation request
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
