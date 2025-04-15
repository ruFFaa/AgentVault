# AgentVault Security Considerations

Security is a core principle of the AgentVault project. This document outlines the current security features and considerations.

## Authentication

How clients prove their identity to agents, and how developers prove their identity to the registry.

### Agent Authentication (Client -> Agent)

Agents declare their supported authentication methods in their `AgentCard` via the `authSchemes` field. The client (`agentvault_library`) currently supports:

*   **`apiKey`:** The client sends a secret API key, typically in the `X-Api-Key` header. The `KeyManager` helps clients store and retrieve these keys securely. The agent server is responsible for validating this key against its own store.
*   **`oauth2` (Client Credentials Grant):** The client uses a pre-configured Client ID and Client Secret (managed via `KeyManager`) to obtain a Bearer token from the `tokenUrl` specified in the Agent Card. The client then sends this token in the `Authorization: Bearer <token>` header. The agent server is responsible for validating the Bearer token (e.g., via introspection or using JWT validation if applicable).
*   **`none`:** No authentication is required. Suitable for public, informational agents.
*   **`bearer`:** (Supported by model, client logic TBD) Assumes the client already possesses a Bearer token and sends it in the `Authorization` header. The mechanism for obtaining this token is outside the scope of the basic A2A interaction itself.

### Registry Authentication (Developer -> Registry)

*   **API Key:** The `agentvault_registry` uses a simple API key mechanism for developers managing their Agent Cards.
    *   Keys are generated securely (`avreg_` prefix + `secrets.token_urlsafe`).
    *   Keys are hashed using `bcrypt` (`passlib`) before being stored in the database (`Developer.api_key_hash`).
    *   Incoming requests to protected registry endpoints (e.g., POST/PUT/DELETE on `/agent-cards/`) must include the plain text key in the `X-Api-Key` header.
    *   The registry verifies the provided key against the stored hash using `passlib.verify`.
    *   **Note:** This relies on iterating through developer hashes, which is not suitable for very large scale but acceptable for initial phases.

## Key Management (Client-Side)

*   The `agentvault_library` provides the `KeyManager` class to abstract credential storage for clients.
*   **Sources:** It loads API keys and OAuth credentials from:
    1.  Key Files (`.env` or `.json`) - Highest priority.
    2.  Environment Variables (`AGENTVAULT_KEY_*`, `AGENTVAULT_OAUTH_*`).
    3.  OS Keyring (optional, requires `keyring` package and backend).
*   **Security:** Storing keys directly in files or environment variables carries risks. Using the OS Keyring (`--keyring` flag in CLI `config set`) is the most secure option provided by the library, leveraging system-level secure storage.

## Trusted Execution Environments (TEE)

*   **Concept:** TEEs offer hardware-level isolation to protect code and data during execution.
*   **AgentVault Support:**
    *   Agents can *declare* their use of a TEE in their Agent Card via the `capabilities.teeDetails` field.
    *   This field includes the TEE type (`type`) and optionally an `attestationEndpoint` URL and `publicKey`.
    *   The registry allows filtering agents based on TEE support (`has_tee`, `tee_type`).
*   **Current Status:** This is currently a *declarative* feature. AgentVault components do not yet *enforce* or *verify* TEE attestations automatically during A2A communication. Implementing client-side attestation verification and secure channel establishment based on TEE details is a significant future enhancement.
*   **Profile:** See [TEE Profile](tee_profile.md) (placeholder link).

## General Considerations

*   **Transport Security:** Always use HTTPS for Registry API calls and A2A agent interactions unless strictly in a trusted local development environment. Agent Card URLs should enforce HTTPS.
*   **Input Validation:** Both the Registry and Agent implementations rely heavily on Pydantic for validating incoming data against defined schemas.
*   **Rate Limiting:** The Registry API implements basic rate limiting using `slowapi`. Agent implementations should consider adding their own rate limiting.
*   **Dependency Security:** Use tools like `pip-audit` or Dependabot to monitor dependencies for known vulnerabilities.

*(This document will be updated as security features evolve.)*
