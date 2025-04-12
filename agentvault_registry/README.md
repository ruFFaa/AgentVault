# AgentVault Registry Backend API (`agentvault-registry`)

This directory contains the source code for the AgentVault Central Registry Backend API.

**Purpose:**

This FastAPI application serves as the **discovery hub** for the AgentVault ecosystem. Its sole purpose is to store and serve standardized Agent Card metadata.

**Key Features:**

*   Provides a RESTful API for managing Agent Cards:
    *   Developer submission, update, and deletion of cards (authenticated).
    *   Public discovery via listing, searching, and retrieving individual cards.
*   Validates submitted Agent Cards against the official A2A schema.
*   Handles basic developer authentication via API keys (managed internally).
*   Uses PostgreSQL for data persistence and Alembic for migrations.

**IMPORTANT:** This service **does not** execute agents, handle user API keys (other than developer keys for registry access), or proxy A2A communication. It is purely a metadata catalog.

**API Documentation:**

Once the service is running, interactive API documentation (Swagger UI and ReDoc) is typically available at `/docs` and `/redoc` respectively.

**Deployment (Conceptual):**

This API is designed to be hosted as a standard web service (e.g., using Docker, deployed to a VM, PaaS, or serverless platform) behind a reverse proxy (like Nginx or Traefik) handling HTTPS termination and potentially load balancing. It requires a connection to a PostgreSQL database. A CDN should be placed in front for caching public GET requests.

**Development:**

See the main project `README.md` for contribution guidelines and development setup. Requires Python, Poetry, and a local PostgreSQL instance.

1.  Install dependencies: `poetry install --with dev`
2.  Set up `.env` file with `DATABASE_URL`.
3.  Run migrations: `alembic upgrade head`
4.  Run the development server: `uvicorn agentvault_registry.main:app --reload --host 0.0.0.0 --port 8000` (adjust port if needed)

Tests are located in `agentvault_registry/tests/registry_api/`.
