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
*   Includes basic rate limiting to prevent abuse.

**IMPORTANT:** This service **does not** execute agents, handle user API keys (other than developer keys for registry access), or proxy A2A communication. It is purely a metadata catalog.

**API Documentation:**

Once the service is running, interactive API documentation (Swagger UI and ReDoc) is typically available at `/docs` and `/redoc` respectively.

**Deployment (Conceptual):**

This API is designed to be hosted as a standard web service (e.g., using Docker, deployed to a VM, PaaS, or serverless platform) behind a reverse proxy (like Nginx or Traefik) handling HTTPS termination and potentially load balancing. It requires a connection to a PostgreSQL database. A CDN should be placed in front for caching public GET requests.

**Operational Monitoring (Deployment)**

Deployers of the AgentVault Registry API are responsible for implementing appropriate monitoring and alerting. Recommended practices include:

*   **Uptime Monitoring:** Use an external monitoring service (e.g., UptimeRobot, Better Uptime, cloud provider native tools) to periodically check the `/health` endpoint for availability. Configure alerts for downtime.
*   **Logging:** Ensure the deployment environment captures standard output (stdout) and standard error (stderr) from the Uvicorn/FastAPI process. Aggregate these logs using a centralized logging platform (e.g., ELK Stack, Grafana Loki, AWS CloudWatch Logs, Google Cloud Logging) for easier searching, analysis, and alerting.
*   **Alerting:** Configure alerts based on:
    *   Uptime check failures (API unresponsive).
    *   Significant increases in error logs (e.g., HTTP 5xx responses, database connection errors, unhandled exceptions).
    *   Resource utilization thresholds (CPU, memory, disk) if applicable to the hosting environment.
*   **Rate Limit Monitoring:** Monitor logs for excessive `429 Too Many Requests` responses, which might indicate legitimate high traffic or potential abuse attempts.

**Database Backup & Recovery (Deployment)**

Regular backups of the PostgreSQL database are crucial. Deployers are responsible for implementing a robust backup strategy. Common approaches include:

*   **Managed Databases:** Utilize the automated backup and point-in-time recovery features provided by managed database services (e.g., AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL).
*   **Self-Hosted Databases:** Implement automated `pg_dump` backups using cron or other scheduling tools. Ensure backups are stored securely, ideally in a separate location (e.g., cloud storage). Define a clear retention policy.
*   **Testing:** Periodically test the database restore process from backups to verify their integrity and the recovery procedure.

**Development:**

See the main project `README.md` for contribution guidelines and development setup. Requires Python, Poetry, and a local PostgreSQL instance.

1.  Ensure the root `.venv` is created and activated (see main README troubleshooting).
2.  Set up `.env` file in this directory (`agentvault_registry/`) with `DATABASE_URL` and `API_KEY_SECRET`.
3.  Run migrations: `alembic upgrade head`
4.  Run the development server: `uvicorn agentvault_registry.main:app --reload --host 0.0.0.0 --port 8000` (adjust port if needed)

Tests are located in `agentvault_registry/tests/registry_api/`.
