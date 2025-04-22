```markdown
# Model Context Protocol (MCP) - AgentVault Profile

## Introduction

The AgentVault Agent-to-Agent (A2A) protocol defines the core mechanisms for secure communication, task management, and event streaming between agents. However, many complex agent interactions require more than just the primary message content. Agents often need additional **context** to perform their tasks effectively. This could include:

*   User profile information
*   Relevant snippets from previous interactions
*   Metadata about the environment
*   References to external files or data artifacts
*   Schema definitions for expected inputs/outputs
*   Tool descriptions and schemas

The **Model Context Protocol (MCP)** is designed to be the standardized way to provide this richer context within the AgentVault ecosystem. It is *not* a separate transport protocol but rather a defined structure for embedding context *within* standard A2A messages.

## Current Status

**Evolving Specification:** It's important to note that the formal MCP specification is still evolving within the broader AI agent community. The implementation within AgentVault currently represents a **basic, conceptual profile** based on common needs observed during development.

**Implementation:** The core `agentvault` library provides utilities (`agentvault.mcp_utils`) for formatting and validating a basic MCP structure, and the `agentvault-server-sdk` provides helpers for extracting it on the agent side. Future versions of AgentVault will align with and potentially contribute to more formalized MCP standards as they emerge.

## Transport Mechanism

MCP context is transported within the `metadata` field of standard A2A `Message` objects (defined in `agentvault.models`). Specifically, the formatted MCP payload is expected under the key `"mcp_context"`.

```json
{
  "role": "user",
  "parts": [
    { "type": "text", "content": "Refactor the attached Python script." }
    // Potentially other parts like FilePart referencing the script
  ],
  "metadata": {
    "timestamp": "...",
    "client_request_id": "...",
    // MCP context is embedded here:
    "mcp_context": {
       // ... MCP payload structure ...
    }
  }
}
```

## Conceptual Structure (Based on Current Implementation)

The current implementation in `agentvault.mcp_utils` defines a basic structure using Pydantic models as placeholders.

1.  **`MCPContext` (Root Object):**
    *   The top-level container for the context.
    *   Currently defined with a single primary field:
        *   `items`: A dictionary where keys are unique identifiers/names for context items, and values are `MCPItem` objects.

2.  **`MCPItem` (Individual Context Piece):**
    *   Represents a single piece of contextual information.
    *   Fields:
        *   `id` (Optional `str`): A unique identifier for this specific item within the context payload.
        *   `mediaType` (Optional `str`): The MIME type of the `content` if applicable (e.g., "text/plain", "application/json", "text/csv").
        *   `content` (Optional `Any`): The actual contextual data itself (e.g., a string, dictionary, list). Used for embedding smaller pieces of context directly.
        *   `ref` (Optional `str`): A reference (e.g., a URL, artifact ID) pointing to external context information, often used for larger data.
        *   `metadata` (Optional `Dict[str, Any]`): Additional key-value metadata specific to this context item.

**Example `mcp_context` Payload:**

```json
"mcp_context": {
  "items": {
    "user_profile": {
      "mediaType": "application/json",
      "content": {
        "user_id": "usr_123",
        "preferences": {"theme": "dark"},
        "permissions": ["read", "write"]
      },
      "metadata": {"source": "internal_db"}
    },
    "target_document": {
      "mediaType": "application/pdf",
      "ref": "s3://my-bucket/documents/report.pdf",
      "metadata": {"version": "1.2"}
    },
    "system_instruction_override": {
        "mediaType": "text/plain",
        "content": "Focus specifically on the financial results section.",
        "id": "instr-001"
    }
  }
}
```

## Client-Side Usage (AgentVault Library)

The `agentvault.client.AgentVaultClient` provides optional parameters in its `initiate_task` and `send_message` methods to include MCP context:

```python
# Example using agentvault library
from agentvault import AgentVaultClient, KeyManager, Message, TextPart, agent_card_utils
from agentvault.models import AgentCard # Assuming AgentCard is available

# Assume agent_card, key_manager are loaded/initialized
client = AgentVaultClient()
initial_message = Message(role="user", parts=[TextPart(content="Analyze this data.")])

# Define the context payload
mcp_payload = {
    "items": {
        "data_reference": {
            "ref": "https://data.example.com/dataset.csv",
            "mediaType": "text/csv"
        },
        "analysis_params": {
            "content": {"mode": "deep", "output_format": "json"},
            "mediaType": "application/json"
        }
    }
}

try:
    # Pass the payload to initiate_task
    task_id = await client.initiate_task(
        agent_card=agent_card,
        initial_message=initial_message,
        key_manager=key_manager,
        mcp_context=mcp_payload # Pass the context dictionary here
    )
    print(f"Task initiated with MCP context, ID: {task_id}")

    # ... handle subsequent events ...

except Exception as e:
    print(f"Error: {e}")

```

The client library uses `agentvault.mcp_utils.format_mcp_context` internally to perform basic validation against the placeholder Pydantic models and embed the formatted context into `message.metadata["mcp_context"]` before sending the request.

## Server-Side Usage (AgentVault Server SDK)

Agents built using the `agentvault-server-sdk` can easily extract the MCP context from incoming messages using the provided utility function:

```python
# Example within an AgentVault SDK Agent method
from agentvault_server_sdk import BaseA2AAgent
from agentvault_server_sdk.mcp_utils import get_mcp_context
from agentvault.models import Message # Assuming Message is available

class MyAgent(BaseA2AAgent):
    # ... other methods ...

    async def handle_task_send(self, task_id: Optional[str], message: Message) -> str:
        # Extract MCP context
        mcp_data = get_mcp_context(message)

        if mcp_data:
            print(f"Received MCP context for task {task_id or 'new'}: {mcp_data}")
            # Access specific items
            user_profile = mcp_data.get("items", {}).get("user_profile")
            if user_profile and user_profile.get("content"):
                user_id = user_profile["content"].get("user_id")
                print(f"User ID from MCP: {user_id}")
            # ... process context items ...
        else:
            print(f"No valid MCP context found in message for task {task_id or 'new'}.")

        # ... rest of task handling logic ...
        new_task_id = f"task-{uuid.uuid4().hex[:6]}"
        # ... store task state, start background work etc ...
        return new_task_id

```

The `get_mcp_context` function safely checks for the presence and type of `message.metadata` and the `"mcp_context"` key, returning the dictionary if found, or `None` otherwise.

## Future Directions

As MCP standards solidify, AgentVault plans to:

*   Adopt or contribute to official schema definitions.
*   Enhance validation logic in `mcp_utils`.
*   Potentially provide more structured ways to interact with specific MCP item types within the SDK.

The current implementation provides a flexible placeholder mechanism for passing structured context alongside core A2A messages.
```
