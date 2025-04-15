# Developer Guide: Registry API (`agentvault_registry`)

The AgentVault Registry provides a central RESTful API service for discovering and managing Agent Cards. Developers interact with it to publish their agents, while clients (like the `agentvault_cli` or other applications) use it to find agents.

## API Base Path

All registry API endpoints are prefixed with `/api/v1`. The full URL depends on where the registry is deployed (e.g., `http://localhost:8000/api/v1` for local development, or the production URL).

## Authentication

*   **Developer Authentication:** Endpoints related to managing agent cards (creating, updating, deleting) require developer authentication. This is handled via an API key specific to the developer, provided in the `X-Api-Key` HTTP header. Keys are obtained from registry administrators (process TBD).
*   **Public Access:** Endpoints for discovering agents (listing/searching, getting details by ID, validating cards) generally do not require authentication.
*   **Exception:** The `GET /agent-cards/` endpoint requires authentication *only* if the `owned_only=true` query parameter is used.

## Common Error Responses

The API uses standard HTTP status codes. Common errors include:

*   **`401 Unauthorized`:** Returned if a required `X-Api-Key` header is missing or invalid for a protected endpoint, or if the key is invalid when using `owned_only=true`.
*   **`403 Forbidden`:** Returned if a valid `X-Api-Key` was provided, but the authenticated developer does not have permission for the requested action (e.g., attempting to modify or delete another developer's Agent Card).
*   **`404 Not Found`:** Returned if the requested resource (e.g., an Agent Card with a specific UUID) does not exist.
*   **`422 Unprocessable Entity`:** Returned if the request body (e.g., for `POST` or `PUT`) fails validation. This commonly occurs if the submitted `card_data` does not conform to the Agent Card schema defined in the `agentvault` library, or if other required fields in the request schema are missing/invalid. The response `detail` field usually contains specific information about the validation errors from Pydantic.
*   **`500 Internal Server Error`:** Returned for unexpected errors on the server (e.g., database connection issue, unhandled exception in the API logic). Check server logs for details.

## API Endpoints

### Agent Cards (`/agent-cards`)

#### `POST /`

*   **Summary:** Submit a new Agent Card.
*   **Description:** Submits a new Agent Card associated with the authenticated developer. The provided `card_data` is validated against the canonical `agentvault.models.AgentCard` schema. The `name` and `description` fields are automatically extracted from `card_data` for indexing.
*   **Authentication:** Required (`X-Api-Key`).
*   **Request Body:** `schemas.AgentCardCreate`
    ```json
    {
      "card_data": {
        "schemaVersion": "1.0",
        "humanReadableId": "your-org/your-agent",
        "agentVersion": "1.1.0",
        "name": "My Awesome Agent",
        "description": "This agent does amazing things.",
        "url": "https://my-agent.example.com/a2a",
        "provider": { "name": "My Org" },
        "capabilities": { "a2aVersion": "1.0" },
        "authSchemes": [ { "scheme": "apiKey", "service_identifier": "my-agent-service" } ]
        // ... other valid Agent Card fields ...
      }
    }
    ```
*   **Success Response (201 Created):** `schemas.AgentCardRead` - Returns the full details of the newly created card record, including its generated UUID (`id`), timestamps, and the `developer_is_verified` status inherited from the owner.
    ```json
    {
      "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "developer_id": 15,
      "developer_is_verified": false, // Example value
      "card_data": { /* ... submitted card_data ... */ },
      "name": "My Awesome Agent",
      "description": "This agent does amazing things.",
      "is_active": true,
      "created_at": "2024-04-15T12:00:00Z",
      "updated_at": "2024-04-15T12:00:00Z"
    }
    ```
*   **Errors:** 401, 403, 422 (e.g., invalid `card_data`, missing required fields like `name`), 500.

#### `GET /`

*   **Summary:** List Agent Cards.
*   **Description:** Retrieves a paginated list of Agent Cards, with options for filtering. By default, only active cards (`is_active=true`) are returned.
*   **Authentication:** Optional. Required *only* if `owned_only=true`.
*   **Query Parameters:**
    *   `skip` (int, default: 0, min: 0): Offset for pagination.
    *   `limit` (int, default: 100, min: 1, max: 250): Max items per page.
    *   `active_only` (bool, default: true): Set to `false` to include inactive cards.
    *   `search` (str, optional, max_length: 100): Case-insensitive search term applied to indexed `name` and `description` fields.
    *   `tags` (list[str], optional): Filter by tags present in `card_data.tags`. Provide the parameter multiple times for AND logic (e.g., `?tags=weather&tags=forecast`). Requires agents to have *all* specified tags. Uses JSONB containment.
    *   `has_tee` (bool, optional): Filter by TEE support declaration (`card_data.capabilities.teeDetails` existence).
    *   `tee_type` (str, optional, max_length: 50): Filter by specific TEE type string (`card_data.capabilities.teeDetails.type`). Case-insensitive match.
    *   `owned_only` (bool, default: false): If `true`, requires `X-Api-Key` header and returns only cards owned by the authenticated developer.
*   **Success Response (200 OK):** `schemas.AgentCardListResponse`
    ```json
    {
      "items": [
        {
          "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
          "name": "My Awesome Agent",
          "description": "This agent does amazing things."
        },
        // ... other AgentCardSummary objects ...
      ],
      "pagination": {
        "total_items": 150,
        "limit": 100,
        "offset": 0,
        "total_pages": 2,
        "current_page": 1
      }
    }
    ```
*   **Errors:** 401 (if `owned_only=true` and auth fails), 500.

#### `GET /{card_id}`

*   **Summary:** Get Agent Card by ID.
*   **Description:** Retrieves the full details of a specific Agent Card by its UUID. Includes the `developer_is_verified` status.
*   **Authentication:** Public.
*   **Path Parameter:**
    *   `card_id` (UUID): The unique ID of the agent card (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`).
*   **Success Response (200 OK):** `schemas.AgentCardRead` (Similar structure to the `POST /` success response).
*   **Errors:** 404 (if ID not found), 500.

#### `PUT /{card_id}`

*   **Summary:** Update an Agent Card.
*   **Description:** Updates an existing Agent Card. Only the authenticated owner of the card can perform this action. Fields not included in the request body (`card_data`, `is_active`) are left unchanged. If `card_data` is provided, it is validated against the schema, and the `name`/`description` fields in the database are updated accordingly.
*   **Authentication:** Required (`X-Api-Key`, must match card owner).
*   **Path Parameter:**
    *   `card_id` (UUID): The ID of the agent card to update.
*   **Request Body:** `schemas.AgentCardUpdate`
    ```json
    {
      // Example: Update only card_data
      "card_data": { /* ... complete new card data ... */ }
    }
    ```
    ```json
    {
      // Example: Update only active status
      "is_active": false
    }
    ```
    ```json
    {
      // Example: Update both
      "card_data": { /* ... complete new card data ... */ },
      "is_active": true
    }
    ```
*   **Success Response (200 OK):** `schemas.AgentCardRead` - Returns the full details of the updated card record.
*   **Errors:** 401, 403 (if not owner), 404, 422 (if `card_data` is provided and invalid), 500.

#### `DELETE /{card_id}`

*   **Summary:** Deactivate an Agent Card (Soft Delete).
*   **Description:** Marks an Agent Card as inactive (`is_active = false`). This is a soft delete; the record remains but is typically excluded from public listings via the `active_only=true` default filter. Only the owner can deactivate.
*   **Authentication:** Required (`X-Api-Key`, must match card owner).
*   **Path Parameter:**
    *   `card_id` (UUID): The ID of the agent card to deactivate.
*   **Success Response:** `204 No Content` (Empty body).
*   **Errors:** 401, 403 (if not owner), 404, 500.

### Utilities (`/utils`)

#### `POST /validate-card`

*   **Summary:** Validate Agent Card Data.
*   **Description:** Validates provided JSON data against the official `agentvault.models.AgentCard` schema without registering or storing it. Useful for developers checking their `agent-card.json` before submission.
*   **Authentication:** Public.
*   **Request Body:** `schemas.AgentCardValidationRequest`
    ```json
    {
      "card_data": {
        "schemaVersion": "1.0",
        "name": "Agent to Validate",
        // ... other card fields ...
      }
    }
    ```
*   **Success Response (200 OK):** `schemas.AgentCardValidationResponse`
    *   *If Valid:*
        ```json
        {
          "is_valid": true,
          "detail": null,
          "validated_card_data": { /* ... validated/normalized card data ... */ }
        }
        ```
    *   *If Invalid:*
        ```json
        {
          "is_valid": false,
          "detail": "Validation Error: Field required [type=missing, loc=('humanReadableId',), ...]",
          "validated_card_data": null
        }
        ```
*   **Errors:** 422 (if the request body itself is invalid, e.g., missing `card_data`), 500.
