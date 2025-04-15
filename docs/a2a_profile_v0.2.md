# AgentVault A2A Profile v0.2

This document specifies the Agent-to-Agent (A2A) communication profile implemented by AgentVault components (as of v0.2.x of the libraries/SDK). It defines how clients interact with A2A-compliant agent servers, aligning with concepts from emerging A2A standards like Google's A2A protocol.

## Overview

*   **Protocol:** JSON-RPC 2.0 Specification.
*   **Transport:** HTTP/1.1 or HTTP/2. **HTTPS is REQUIRED** for all communication except potentially during local development targeting `localhost`.
*   **Request Method:** `POST` for all JSON-RPC requests.
*   **Streaming:** Server-Sent Events (SSE) via the `tasks/sendSubscribe` method for real-time updates.
*   **Data Format:** JSON (UTF-8 encoding).
*   **Authentication:** Defined via `authSchemes` in the [Agent Card](concepts.md#agent-card). Supported schemes include `none`, `apiKey`, and `oauth2` (Client Credentials Grant).

## Transport Details

All JSON-RPC requests, including method calls and notifications (if used), MUST be sent using the HTTP `POST` method to the agent's designated A2A endpoint URL (found in the `url` field of its Agent Card).

*   **Request Headers:**
    *   `Content-Type: application/json` is REQUIRED.
    *   Authentication headers (e.g., `X-Api-Key` or `Authorization: Bearer <token>`) MUST be included if required by the agent's `authSchemes`.
*   **Request Body:** Contains the standard JSON-RPC 2.0 request object (see below).
*   **Response Body (Non-Streaming):** Contains the standard JSON-RPC 2.0 response object (either `result` or `error`).
*   **Response Body (Streaming via `tasks/sendSubscribe`):** The server responds with HTTP `200 OK` and `Content-Type: text/event-stream`. The body then contains a stream of Server-Sent Events (see SSE section below).

## Authentication

Refer to the main [Security Considerations](security.md#agent-authentication-client---agent) document for details on how `none`, `apiKey`, and `oauth2` (Client Credentials) schemes are implemented and handled by the `agentvault` client library and expected by servers.

## JSON-RPC 2.0 Structure

All requests and responses adhere to the JSON-RPC 2.0 specification.

**Request Object:**

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": <parameters_object_or_array>,
  "id": <request_id_string_or_number_or_null>
}
```

*   `jsonrpc`: MUST be exactly "2.0".
*   `method`: A string containing the name of the method to be invoked (e.g., "tasks/send").
*   `params`: An optional structured value (object or array) containing parameter values. If omitted, the method is assumed to take no parameters. AgentVault methods use parameter objects (dictionaries).
*   `id`: An identifier established by the Client. If included, the response MUST include the same value. If omitted (for notifications), the server MUST NOT reply. AgentVault methods generally expect an ID.

**Response Object (Success):**

```json
{
  "jsonrpc": "2.0",
  "result": <result_value>,
  "id": <matching_request_id>
}
```

*   `result`: The value returned by the method invocation. Its structure depends on the method called.
*   `id`: Must match the `id` from the Request Object.

**Response Object (Error):**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": <integer>,
    "message": <string>,
    "data": <optional_any>
  },
  "id": <matching_request_id_or_null>
}
```

*   `error`: An object describing the error.
    *   `code`: A Number that indicates the error type that occurred. See [Error Codes](#json-rpc-error-codes).
    *   `message`: A String providing a short description of the error.
    *   `data`: Optional. A Primitive or Structured value containing additional information about the error.
*   `id`: Must match the `id` from the Request Object. If the error occurred before the ID could be determined (e.g., Parse Error), it SHOULD be `null`.

## Standard A2A Methods

These methods form the core of the AgentVault A2A interaction model.

### `tasks/send`

Initiates a new task or sends a subsequent message to an existing task.

*   **Params:** `TaskSendParams` object
    ```json
    // Example: Initiate a new task
    {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "content": "What is the weather in London?"}],
        "metadata": {
          "mcp_context": { /* Optional MCP data */ }
        }
      },
      "webhookUrl": "https://my-client.example.com/webhook/task-updates" // Optional
    }

    // Example: Send subsequent message to existing task
    {
      "id": "task-abc-123",
      "message": {
        "role": "user",
        "parts": [{"type": "text", "content": "What about tomorrow?"}]
      }
    }
    ```
    *   `id` (Optional[str]): Task ID if continuing, omit/null if initiating.
    *   `message` (Message): The message object.
    *   `webhookUrl` (Optional[str]): URL for agent push notifications (if supported).
*   **Result:** `TaskSendResult` object
    ```json
    {
      "id": "task-abc-123" // The ID of the task (new or existing)
    }
    ```

### `tasks/get`

Retrieve the current status and details of a specific task.

*   **Params:** `TaskGetParams` object (or just the `id` field)
    ```json
    {
      "id": "task-abc-123"
    }
    ```
*   **Result:** `Task` object (See `agentvault.models.Task` for full structure)
    ```json
    {
      "id": "task-abc-123",
      "state": "WORKING", // Or COMPLETED, FAILED, etc.
      "createdAt": "2024-04-15T10:00:00Z",
      "updatedAt": "2024-04-15T10:05:30Z",
      "messages": [
        {"role": "user", "parts": [...]},
        {"role": "assistant", "parts": [...]}
      ],
      "artifacts": [
        {"id": "artifact-1", "type": "log", "content": "...", "mediaType": "text/plain"}
      ],
      "metadata": { /* Optional task-level metadata */ }
    }
    ```

### `tasks/cancel`

Request the cancellation of an ongoing task.

*   **Params:** `TaskCancelParams` object (or just the `id` field)
    ```json
    {
      "id": "task-abc-123"
    }
    ```
*   **Result:** `TaskCancelResult` object
    ```json
    {
      "success": true, // Indicates request was accepted, not necessarily completed cancellation
      "message": "Cancellation request received." // Optional
    }
    ```

### `tasks/sendSubscribe`

Subscribe to real-time updates for a task via Server-Sent Events (SSE).

*   **Params:** Object containing the task ID
    ```json
    {
      "id": "task-abc-123"
    }
    ```
*   **Response:** HTTP `200 OK` with `Content-Type: text/event-stream`, followed by SSE stream in the body. **No JSON-RPC `result` field is sent in the initial HTTP response body.**

## Task States (`TaskState` Enum)

The defined states for an A2A task lifecycle:

*   **`SUBMITTED`**: Task received, awaiting execution.
*   **`WORKING`**: Task actively being processed.
*   **`INPUT_REQUIRED`**: Task paused, awaiting further client input (advanced use case).
*   **`COMPLETED`**: Task finished successfully. (Terminal)
*   **`FAILED`**: Task terminated due to an error. (Terminal)
*   **`CANCELED`**: Task canceled by request. (Terminal)

## Server-Sent Events (SSE)

Used for the `tasks/sendSubscribe` stream.

*   **Format:** Standard SSE. Each event consists of `event:` and `data:` lines, terminated by `\n\n`.
    ```sse
    event: <event_type>
    data: <json_payload_string>

    event: <another_event_type>
    data: <another_json_payload_string>

    ```
*   **Event Types (`event:` field):**
    *   `task_status`: Task state change. `data` is JSON of `TaskStatusUpdateEvent`.
    *   `task_message`: New message added. `data` is JSON of `TaskMessageEvent`.
    *   `task_artifact`: Artifact created/updated. `data` is JSON of `TaskArtifactUpdateEvent`.
    *   `error`: Server-side error during streaming. `data` is a JSON object like `{"error": "code", "message": "desc"}`.
*   **Data Payload (`data:` field):** A **single line** containing a JSON string representing the corresponding event model (e.g., `TaskStatusUpdateEvent`, `TaskMessageEvent`, `TaskArtifactUpdateEvent`).

**Example SSE Stream:**

```sse
event: task_status
data: {"taskId": "task-abc-123", "state": "WORKING", "timestamp": "2024-04-15T10:05:00Z", "message": null}

event: task_message
data: {"taskId": "task-abc-123", "message": {"role": "assistant", "parts": [{"type": "text", "content": "Thinking..."}], "metadata": null}, "timestamp": "2024-04-15T10:05:05Z"}

event: task_artifact
data: {"taskId": "task-abc-123", "artifact": {"id": "log-1", "type": "debug_log", "content": "Processing step 1", "url": null, "mediaType": "text/plain", "metadata": null}, "timestamp": "2024-04-15T10:05:10Z"}

event: task_status
data: {"taskId": "task-abc-123", "state": "COMPLETED", "timestamp": "2024-04-15T10:05:15Z", "message": "Task finished successfully."}

```

## JSON-RPC Error Codes

Standard codes should be used where applicable. AgentVault defines some application-specific codes in the `-32000` to `-32099` range.

| Code    | Message             | Meaning                                      |
| :------ | :------------------ | :------------------------------------------- |
| -32700  | Parse error         | Invalid JSON was received by the server.     |
| -32600  | Invalid Request     | The JSON sent is not a valid Request object. |
| -32601  | Method not found    | The method does not exist / is not available.|
| -32602  | Invalid Params      | Invalid method parameter(s).                 |
| -32603  | Internal error      | Internal JSON-RPC error on the server.       |
| -32000  | Agent Server Error  | Generic application error on the agent.      |
| -32001  | Task Not Found      | Specified `task_id` does not exist.          |
| -32002  | Authentication Error| API Key / Token invalid or missing.          |
| -32003  | Authorization Error | Authenticated user cannot perform action.    |
| -32004  | Invalid State       | Operation not allowed in current task state. |
| *others*| *Implementation Defined* | Server may define other -320xx errors.   |

Servers SHOULD include meaningful information in the `message` and optionally the `data` part of the error object.
