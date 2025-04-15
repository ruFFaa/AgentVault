# Developer Guide: Registry API (`agentvault_registry`)

The AgentVault Registry provides a central RESTful API service for discovering and managing Agent Cards. Developers interact with it to publish their agents, while clients (like the `agentvault_cli` or other applications) use it to find agents.

## API Base Path

All registry API endpoints are prefixed with `/api/v1`. The full URL depends on where the registry is deployed (e.g., `http://localhost:8000/api/v1` for local development).

## Authentication

Endpoints related to managing agent cards (creating, updating, deleting) require developer authentication. This is handled via an API key specific to the developer, provided in the `X-Api-Key` HTTP header.

Public endpoints (listing/searching agents, getting details by ID, validating cards) do not require authentication, although some filtering options (like `owned_only=true` on the list endpoint) *do* require authentication to identify the owner.

## Common Error Responses

*   **`401 Unauthorized`:** Invalid or missing `X-Api-Key` header provided for a protected endpoint, or when required for a specific filter like `owned_only=true`.
*   **`403 Forbidden`:** A valid `X-Api-Key` was provided, but the authenticated developer does not have permission for the requested action (e.g., attempting to modify or delete another developer's Agent Card).
*   **`404 Not Found`:** The requested resource (e.g., an Agent Card with a specific UUID) does not exist.
*   **`422 Unprocessable Entity`:** The request body (e.g., for `POST` or `PUT`) failed validation. This commonly occurs if the submitted `card_data` does not conform to the Agent Card schema or if other required fields in the request schema are missing/invalid. The response `detail` field usually contains specific information about the validation errors.
*   **`500 Internal Server Error`:** An unexpected error occurred on the server (e.g., database connection issue, unhandled exception in the API logic).

## API Endpoints

### Agent Cards (`/agent-cards`)

#### `POST /`

*   **Summary:** Submit a new Agent Card
*   **Description:** Submits a new Agent Card associated with the authenticated developer. The provided `card_data` is validated against the canonical Agent Card schema.
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
*   **Success Response (201 Created):** `schemas.AgentCardRead` - Returns the full details of the newly created card record, including its generated UUID (`id`), timestamps, and the `developer_is_verified` status.
    ```json
    {
      "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "developer_id": 15,
      "developer_is_verified": false,
      "card_data": { /* ... submitted card_data ... */ },
      "name": "My Awesome Agent",
      "description": "This agent does amazing things.",
      "is_active": true,
      "created_at": "2024-04-15T12:00:00Z",
      "updated_at": "2024-04-15T12:00:00Z"
    }
    ```
*   **Errors:** 401, 403, 422 (e.g., invalid `card_data`, duplicate `humanReadableId` if enforced), 500.

#### `GET /`

*   **Summary:** List Agent Cards
*   **Description:** Retrieves a paginated list of Agent Cards, with options for filtering. By default, only active cards are returned.
*   **Authentication:** Optional. Required only if `owned_only=true`.
*   **Query Parameters:**
    *   `skip` (int, default: 0): Offset for pagination (e.g., `?skip=20`).
    *   `limit` (int, default: 100, max: 250): Max items per page (e.g., `?limit=50`).
    *   `active_only` (bool, default: true): Set to `false` to include inactive cards (e.g., `?active_only=false`).
    *   `search` (str, optional): Case-insensitive search term applied to `name` and `description` (e.g., `?search=weather`).
    *   `tags` (list[str], optional): Filter by tags. Provide the parameter multiple times for AND logic (e.g., `?tags=weather&tags=forecast`). Requires agents to have *all* specified tags in `card_data.tags`.
    *   `has_tee` (bool, optional): Filter by TEE support declaration (e.g., `?has_tee=true`).
    *   `tee_type` (str, optional): Filter by specific TEE type string (e.g., `?tee_type=Intel SGX`).
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

*   **Summary:** Get Agent Card by ID
*   **Description:** Retrieves the full details of a specific Agent Card by its UUID.
*   **Authentication:** Public.
*   **Path Parameter:**
    *   `card_id` (UUID): The unique ID of the agent card (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`).
*   **Success Response (200 OK):** `schemas.AgentCardRead` (Similar structure to the `POST /` success response). Includes `card_data` and `developer_is_verified`.
*   **Errors:** 404 (if ID not found), 500.

#### `PUT /{card_id}`

*   **Summary:** Update an Agent Card
*   **Description:** Updates an existing Agent Card. Only the authenticated owner of the card can perform this action. Fields not included in the request body are left unchanged. If `card_data` is provided, it *replaces* the existing card data entirely after validation.
*   **Authentication:** Required (`X-Api-Key`, must match card owner).
*   **Path Parameter:**
    *   `card_id` (UUID): The ID of the agent card to update.
*   **Request Body:** `schemas.AgentCardUpdate`
    ```json
    {
      "card_data": { /* ... complete new card data ... */ },
      "is_active": false // Optional: Deactivate the card
    }
    ```
    *Note:* You only need to include the fields you want to change (`card_data` or `is_active`).
*   **Success Response (200 OK):** `schemas.AgentCardRead` - Returns the full details of the updated card record.
*   **Errors:** 401, 403 (if not owner), 404, 422 (if `card_data` is provided and invalid), 500.

#### `DELETE /{card_id}`

*   **Summary:** Deactivate an Agent Card
*   **Description:** Marks an Agent Card as inactive (`is_active = false`). This is a soft delete; the record remains but is typically excluded from public listings. Only the owner can deactivate.
*   **Authentication:** Required (`X-Api-Key`, must match card owner).
*   **Path Parameter:**
    *   `card_id` (UUID): The ID of the agent card to deactivate.
*   **Success Response:** `204 No Content` (Empty body).
*   **Errors:** 401, 403 (if not owner), 404, 500.

### Utilities (`/utils`)

#### `POST /validate-card`

*   **Summary:** Validate Agent Card Data
*   **Description:** Validates provided JSON data against the official AgentVault Agent Card schema without registering or storing it. Useful for developers checking their `agent-card.json` before submission.
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
