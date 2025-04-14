# AgentVault Server SDK (`agentvault-server-sdk`)

This directory contains the source code for the `agentvault-server-sdk`, a Python library designed to simplify the development of A2A-compliant agents for the AgentVault ecosystem.

**(Placeholder - More details will be added as the SDK is developed)**

**Purpose:**

*   Provide base classes and utilities for handling A2A protocol requests (JSON-RPC/SSE).
*   Integrate seamlessly with web frameworks like FastAPI.
*   Offer helpers for managing task state and generating A2A events.
*   Simplify agent packaging for deployment (e.g., Dockerfile generation).

**Installation:**

```bash
# This package is typically used as a dependency when building an agent.
# Install locally for development (from the agentvault_server_sdk directory):
# pip install -e ".[dev]"
```

**Basic Usage (Conceptual):**

```python
# (Example - Actual implementation TBD)
from fastapi import FastAPI
from agentvault_server_sdk import BaseA2AAgent, create_a2a_router
from agentvault.models import Message, Task, TaskState # Import from core library

class MySimpleAgent(BaseA2AAgent):
    async def handle_task_send(self, task_id: str | None, message: Message) -> str:
        # Process initial message or subsequent message
        new_task_id = task_id or "task-" + secrets.token_hex(4)
        print(f"Received message for task {new_task_id}: {message.parts[0].content}")
        # ... start background processing ...
        # Update task state (using SDK helpers TBD)
        return new_task_id # Return task ID

    async def handle_task_get(self, task_id: str) -> Task:
        # Retrieve and return task state (using SDK helpers TBD)
        pass

    async def handle_task_cancel(self, task_id: str) -> bool:
        # Handle cancellation request
        pass

    async def handle_subscribe_request(self, task_id: str) -> AsyncGenerator[A2AEvent, None]:
        # Yield events (Status, Message, Artifact) as they happen
        # (using SDK helpers TBD)
        pass

# --- FastAPI Integration ---
my_agent = MySimpleAgent()
a2a_router = create_a2a_router(agent=my_agent) # Pass agent instance

app = FastAPI()
app.include_router(a2a_router, prefix="/a2a") # Mount the A2A endpoint

# Run with: uvicorn main:app --reload
```
