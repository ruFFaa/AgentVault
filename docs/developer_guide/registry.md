# Developer Guide: Registry API (`agentvault_registry`)

The AgentVault Registry provides a central RESTful API service for discovering and managing Agent Cards. Developers interact with it to publish their agents, while clients (like the `agentvault_cli` or other applications) use it to find agents.

## API Base Path

All registry API endpoints are prefixed with `/api/v1`. The full URL depends on where the registry is deployed (e.g., `http://localhost:8000/api/v1` for local development).

## Authentication

Endpoints related to managing agent cards (creating, updating, deleting) require developer authentication. This is handled via an API key specific to the developer.

*   **Header:** `X-Api-Key`
*   **Value:** The plain-text API key provided to the developer upon registration (or potentially through a future developer portal).

Public endpoints (like listing/searching agents, getting details by ID, validating cards) do not require authentication, although some filtering options (like `owned_only`) might require it.

## Common Error Responses

*   **401 Unauthorized:** Invalid API Key provided.
*   **403 Forbidden:** Valid API Key provided, but the developer does not have permission for the action (e.g., modifying another developer's card), or the `X-Api-Key` header was missing entirely for a protected endpoint.
*   **404 Not Found:** The requested resource (e.g., Agent Card with a specific ID) does not exist.
*   **422 Unprocessable Entity:** The request body failed validation (e.g., invalid Agent Card data during submission/update, missing required fields). The response `detail` usually contains specific validation error messages.
*   **500 Internal Server Error:** An unexpected error occurred on the server.

## API Endpoints

### Agent Cards (`/agent-cards`)

#### `POST /`

*   **Purpose:** Submit a new Agent Card to the registry.
*   **Authentication:** Required (`X-Api-Key`).
*   **Request Body:** `schemas.AgentCardCreate`
    *   `card_data` (dict): The complete Agent Card JSON object. This data is validated against the canonical `agentvault.models.AgentCard` schema before storage.
*   **Success Response (201 Created):** `schemas.AgentCardRead` - Returns the full details of the newly created card record, including its generated UUID (`id`) and timestamps.
*   **Errors:** 401, 403, 422 (if `card_data` is invalid), 500.

#### `GET /`

*   **Purpose:** List and search for registered Agent Cards.
*   **Authentication:** Optional. Required only if `owned_only=true`.
*   **Query Parameters:**
    *   `skip` (int, default: 0): Offset for pagination.
    *   `limit` (int, default: 100, max: 250): Max items per page.
    *   `active_only` (bool, default: true): Filter for active cards.
    *   `search` (str, optional): Case-insensitive search term applied to `name` and `description`.
    *   `tags` (list[str], optional): Filter by tags. Returns cards containing *all* specified tags within their `card_data['tags']` list. (e.g., `?tags=weather&tags=forecast`)
    *   `owned_only` (bool, default: false): If `true`, returns only cards owned by the authenticated developer (requires `X-Api-Key`).
*   **Success Response (200 OK):** `schemas.AgentCardListResponse` - Contains a list of `AgentCardSummary` objects for the current page and `PaginationInfo`.
*   **Errors:** 401 (if `owned_only=true` and auth fails), 500.

#### `GET /{card_id}`

*   **Purpose:** Retrieve the full details of a specific Agent Card.
*   **Authentication:** Public.
*   **Path Parameter:**
    *   `card_id` (UUID): The unique ID of the agent card.
*   **Success Response (200 OK):** `schemas.AgentCardRead` - Contains the full card record, including the `card_data` JSON object and the `developer_is_verified` status.
*   **Errors:** 404 (if ID not found), 500.

#### `PUT /{card_id}`

*   **Purpose:** Update an existing Agent Card. Only the owner can update.
*   **Authentication:** Required (`X-Api-Key`, must match card owner).
*   **Path Parameter:**
    *   `card_id` (UUID): The unique ID of the agent card to update.
*   **Request Body:** `schemas.AgentCardUpdate`
    *   `card_data` (Optional[dict]): The *complete*, new Agent Card JSON object. If provided, it replaces the existing `card_data` entirely after validation.
    *   `is_active` (Optional[bool]): Set the active status of the card.
*   **Success Response (200 OK):** `schemas.AgentCardRead` - Returns the full details of the updated card record.
*   **Errors:** 401, 403 (if not owner), 404, 422 (if `card_data` is invalid), 500.

#### `DELETE /{card_id}`

*   **Purpose:** Deactivate (soft delete) an Agent Card. Only the owner can deactivate.
*   **Authentication:** Required (`X-Api-Key`, must match card owner).
*   **Path Parameter:**
    *   `card_id` (UUID): The unique ID of the agent card to deactivate.
*   **Success Response:** `204 No Content`.
*   **Errors:** 401, 403 (if not owner), 404, 500.

### Utilities (`/utils`)

#### `POST /validate-card`

*   **Purpose:** Validate Agent Card data against the official schema without registering it.
*   **Authentication:** Public.
*   **Request Body:** `schemas.AgentCardValidationRequest`
    *   `card_data` (dict): The Agent Card JSON object to validate.
*   **Success Response (200 OK):** `schemas.AgentCardValidationResponse`
    *   `is_valid` (bool): True if the data conforms to the schema, False otherwise.
    *   `detail` (Optional[str]): Contains validation error details if `is_valid` is False.
    *   `validated_card_data` (Optional[dict]): The validated (and potentially normalized) card data if `is_valid` is True.
*   **Errors:** 422 (if the request body itself is invalid), 500.
