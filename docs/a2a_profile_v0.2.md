# AgentVault A2A Profile v0.2

This document specifies the Agent-to-Agent (A2A) communication profile implemented by AgentVault components (as of v0.2.x of the libraries/SDK). It defines how clients interact with A2A-compliant agent servers.

## Overview

*   **Protocol:** JSON-RPC 2.0
*   **Transport:** HTTP/1.1 or HTTP/2 (HTTPS REQUIRED for non-localhost communication)
*   **Request Method:** Primarily `POST` for all JSON-RPC requests, including `tasks/sendSubscribe`.
*   **Streaming:** Server-Sent Events (SSE) for real-time updates (`tasks/sendSubscribe`).
*   **Data Format:** JSON

## Transport

All JSON-RPC requests are sent using the HTTP `POST` method to the agent's A2A endpoint URL specified in its Agent Card (`url` field).

Responses to standard JSON-RPC requests are returned in the HTTP response body.

For streaming updates via `tasks/sendSubscribe`, the server responds with HTTP `200 OK` and a `Content-Type: text/event-stream` header, followed by the SSE stream in the response body.

HTTPS is mandatory for all communication except potentially during local development targeting `localhost`.

## Authentication

Agents declare their supported authentication methods in their Agent Card (`authSchemes`). Clients MUST support at least one of the declared schemes. The `agentvault` library currently supports the following client-side implementations:

*   **`none`:** No authentication is performed. The client sends the request without any specific authentication headers.
*   **`apiKey`:**
    *   The client retrieves the appropriate API key using the `KeyManager` (based on the `service_identifier` in the Agent Card or an override).
    *   The client includes the key in the `X-Api-Key` HTTP header.
    *   The server is responsible for validating this key.
*   **`oauth2` (Client Credentials Grant):**
    *   The Agent Card MUST provide a valid `tokenUrl` and optionally `scopes`.
    *   The client uses `KeyManager` to retrieve the `clientId` and `clientSecret` associated with the agent's `service_identifier`.
    *   The client makes a `POST` request to the `tokenUrl` with `grant_type=client_credentials`, `client_id`, `client_secret`, and optionally `scope`.
    *   The client extracts the `access_token` from the token endpoint's JSON response.
    *   The client includes the token in the `Authorization: Bearer <access_token>` HTTP header for subsequent requests to the agent's A2A endpoint.
    *   The client library performs basic in-memory caching of the obtained token based on its `expires_in` value (if provided).
    *   The agent server is responsible for validating the received Bearer token.

## JSON-RPC Methods

All methods follow the JSON-RPC 2.0 specification.

### `tasks/send`

*   **Purpose:** Initiates a new task or sends a subsequent message to an existing task. Can optionally register a webhook for push notifications if the agent supports it.
*   **Params:** `TaskSendParams` model
    *   `id` (Optional[str]): Task ID if continuing an existing task, `null` or omitted if initiating.
    *   `message` (Message): The message object to send.
    *   `webhookUrl` (Optional[str]): URL for the agent to send push notifications to (if supported by the agent).
    *   *(Other fields like `sessionId`, `historyLength` might be added based on spec evolution)*
*   **Result:** `TaskSendResult` model
    *   `id` (str): The ID of the task (newly created or existing).

### `tasks/get`

*   **Purpose:** Retrieve the current status, message history, and artifacts of a specific task.
*   **Params:** `TaskGetParams` model (or simply `{"id": "task-id"}`)
    *   `id` (str): The ID of the task to retrieve.
    *   *(Optional parameters like `historyLength` might be added)*
*   **Result:** `Task` model - Contains the full task state (`id`, `state`, `createdAt`, `updatedAt`, `messages`, `artifacts`, `metadata`).

### `tasks/cancel`

*   **Purpose:** Request the cancellation of an ongoing task.
*   **Params:** `TaskCancelParams` model (or simply `{"id": "task-id"}`)
    *   `id` (str): The ID of the task to cancel.
*   **Result:** `TaskCancelResult` model
    *   `success` (bool): Indicates if the cancellation request was accepted by the agent (doesn't guarantee immediate termination).
    *   `message` (Optional[str]): Optional message from the agent regarding cancellation.

### `tasks/sendSubscribe`

*   **Purpose:** Subscribe to real-time updates for a task via Server-Sent Events (SSE).
*   **Params:** `TaskIdParams` model (or simply `{"id": "task-id"}`)
    *   `id` (str): The ID of the task to subscribe to.
*   **Response:**
    *   Initial HTTP `200 OK` with `Content-Type: text/event-stream`.
    *   Followed by a stream of SSE messages in the response body (see SSE section below).
    *   The connection remains open until the task reaches a terminal state or is closed by either party.

## Task States (`TaskState` Enum)

Defines the lifecycle of an A2A task:

*   **`SUBMITTED`**: Task received by the agent, awaiting execution.
*   **`WORKING`**: Task is actively being processed by the agent.
*   **`INPUT_REQUIRED`**: Task is paused, awaiting further input from the user/client (support for handling this state might vary).
*   **`COMPLETED`**: Task finished successfully. (Terminal State)
*   **`FAILED`**: Task terminated due to an error during execution. (Terminal State)
*   **`CANCELED`**: Task was canceled by user request before completion. (Terminal State)

## Server-Sent Events (SSE)

Used by the `tasks/sendSubscribe` method for streaming updates.

*   **Format:** Standard SSE format. Each message consists of lines like `field: value`, followed by an empty line (`\n\n`).
    ```sse
    event: <event_type>
    data: <json_payload>

    event: <another_event_type>
    data: <another_json_payload>

    ```
*   **Event Types (`event:` field):**
    *   `task_status`: Indicates a change in the task's overall state.
    *   `task_message`: Indicates a new message has been added to the task's history (usually from the agent or a tool).
    *   `task_artifact`: Indicates a new artifact has been created or updated for the task.
    *   `error`: Indicates an error occurred on the server side during streaming (distinct from JSON-RPC errors).
*   **Data Payload (`data:` field):** A JSON string representing the corresponding Pydantic model:
    *   `event: task_status` -> `data: TaskStatusUpdateEvent` JSON
    *   `event: task_message` -> `data: TaskMessageEvent` JSON
    *   `event: task_artifact` -> `data: TaskArtifactUpdateEvent` JSON
    *   `event: error` -> `data: {"error": "...", "message": "...", ...}` JSON (structure may vary)

## JSON-RPC Errors

Standard JSON-RPC 2.0 error objects are returned within the JSON response body when a request cannot be fulfilled normally.

*   **Structure:**
    ```json
    {
      "jsonrpc": "2.0",
      "error": {
        "code": <integer>,
        "message": <string>,
        "data": <optional_any>
      },
      "id": <request_id_or_null>
    }
    ```
*   **Common Codes Used:**
    *   `-32700`: Parse Error (Invalid JSON received).
    *   `-32600`: Invalid Request (JSON is not a valid Request object).
    *   `-32601`: Method Not Found.
    *   `-32602`: Invalid Params (Invalid method parameters).
    *   `-32603`: Internal Error (Server-side error not covered by others).
    *   `-32000`: Generic Application Error (Used by SDK for agent logic errors).
    *   `-32001`: Task Not Found (Custom application error).
    *   *(Others may be defined)*
