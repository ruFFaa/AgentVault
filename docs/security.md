# AgentVault Security Considerations

> **Note:** For the official security policy and vulnerability reporting process, please see the [Security Policy](security_policy.md) document.

This document details the security mechanisms, considerations, and best practices within the AgentVault ecosystem. Security is fundamental to enabling trustworthy interactions between agents and protecting user/developer credentials.

## Authentication

Authentication verifies the identity of the communicating parties. AgentVault employs different mechanisms for client-to-agent and developer-to-registry interactions.

### 1. Client-to-Agent Authentication (A2A)

Agents declare how clients should authenticate in their `AgentCard` (`authSchemes`). The `agentvault` library supports:

*   **`none`:** No authentication. Use only for public, non-sensitive agents.
*   **`apiKey`:** Client sends a pre-shared secret in `X-Api-Key`. Requires secure key management on both client (`KeyManager`) and server (agent implementation).
*   **`oauth2` (Client Credentials Grant):** Client uses its ID/Secret (managed by `KeyManager`) to get a Bearer token from the agent's `/token` endpoint. The client sends this token in the `Authorization: Bearer <token>` header for A2A requests. The `AgentVaultClient` handles token fetching/caching. The agent server must implement the `/token` endpoint and validate Bearer tokens at its `/a2a` endpoint.
*   **`bearer`:** Client sends a pre-obtained Bearer token. Token lifecycle management is external to AgentVault library. Agent server must validate the token.

*(Refer to the [A2A Profile](a2a_profile_v0.2.md) for more detail)*

### 2. Developer-to-Registry Authentication

The registry uses a multi-faceted approach for developers managing their agents:

*   **Account Creation:** Developers register using **email and password**. Passwords are **hashed using bcrypt** (`passlib`) before storage. Email verification is required.
*   **Login (JWT):** Successful login (`POST /auth/login`) returns a **JSON Web Token (JWT)** signed using a server-side secret (`API_KEY_SECRET` from config). This JWT acts as a session token.
*   **Authenticated Requests (JWT):** Developers include the JWT in the `Authorization: Bearer <token>` header for subsequent requests to protected endpoints (e.g., managing agent cards, API keys, using the agent builder). The registry API verifies the token's signature and expiry.
*   **Account Recovery (Recovery Keys):** During registration, **single-use recovery keys** are generated. One representative key's **hash (using bcrypt)** is stored. If a developer loses their password, they can use their email and one of the *plain text* recovery keys (which they stored securely offline) via `POST /auth/recover-account`. The server verifies the key against the stored hash. If valid, it issues a very short-lived JWT specifically for setting a new password (`POST /auth/set-new-password`). The recovery key hash is then invalidated in the database.
*   **Programmatic API Keys:**
    *   **Purpose:** For non-interactive use (scripts, CI/CD) to manage agent cards.
    *   **Generation:** Developers generate these keys via the Developer Portal UI or `POST /developers/me/apikeys`. The full key (e.g., `avreg_...`) is shown **only once**.
    *   **Storage:** The **hash** of the full key (using `passlib` with bcrypt) and the non-secret prefix (`avreg_`) are stored in the `developer_api_keys` database table.
    *   **Verification:** For requests using the `X-Api-Key` header, the registry API finds potential keys based on the prefix, then uses `passlib.verify()` to check the provided plain key against the stored hashes for active keys belonging to the developer associated with the prefix match (lookup logic might need optimization for scale).

**Security Implications:**

*   JWTs provide standard session management but require secure handling of the `API_KEY_SECRET` on the server.
*   Recovery keys provide a fallback but *must* be stored securely by the developer; losing them means losing account access if password reset fails. Hashing the stored key prevents direct compromise from database leaks.
*   Programmatic API keys offer convenience for automation but must be treated as sensitive secrets by the developer. Hashing provides database-level protection.

## Credential Management (`KeyManager` - Client Side)

*(This section remains largely the same as before, emphasizing keyring usage)*

The `agentvault` library's `KeyManager` provides a unified way for clients (like the CLI) to manage credentials needed for agent authentication.

*   **Secure Storage:** Strongly recommends using the OS Keyring (`--keyring` or `--oauth-configure` options in CLI `config set`) for storing sensitive API keys and OAuth secrets.
*   **Alternative Sources:** Supports loading from environment variables and `.env`/`.json` files, but users must ensure appropriate security for these methods.
*   **Abstraction:** Client code interacts with `KeyManager` without needing to know the storage location.

## Transport Security

*   **HTTPS is MANDATORY** for all communication with the AgentVault Registry API and any A2A agent endpoint not run on `localhost`.

## Data Validation

*   **Pydantic:** Used extensively for request/response validation in the registry API, server SDK, and core library models, preventing malformed data issues.
*   **Registry:** Validates submitted `card_data` against the canonical `agentvault.models.AgentCard` schema.

## Rate Limiting

*   **Registry:** Implements basic IP-based rate limiting (`slowapi`).
*   **Agents:** Agent developers should implement their own rate limiting.

## Trusted Execution Environments (TEE)

*   **Current Status:** Declarative only. Agent Cards can specify TEE usage, and the registry supports filtering based on this.
*   **Future Work:** Automated attestation verification is planned.

## Dependency Security

*   **Auditing:** Automated checks via GitHub Actions (`pip-audit`).
*   **Updates:** Regular updates are crucial.

## Reporting Vulnerabilities

Please report suspected security vulnerabilities privately according to the [Security Policy](security_policy.md).
