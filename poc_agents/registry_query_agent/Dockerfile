# --- Base Stage ---
    FROM python:3.11-slim-bookworm AS base

    # Set environment variables consistently
    ENV PYTHONUNBUFFERED=1 \
        PYTHONDONTWRITEBYTECODE=1 \
        PIP_NO_CACHE_DIR=off \
        PIP_DISABLE_PIP_VERSION_CHECK=on \
        PIP_DEFAULT_TIMEOUT=100 \
        POETRY_VERSION=1.8.3 \
        POETRY_HOME="/opt/poetry" \
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=true \
        POETRY_NO_INTERACTION=1 \
        VENV_PATH="/app/.venv"
    
    # Add Poetry installation directory and venv bin to PATH
    ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"
    
    # Install Poetry globally
    RUN pip install --no-cache-dir poetry==$POETRY_VERSION
    
    # --- Builder Stage ---
    FROM base AS builder
    
    WORKDIR /app
    
    # Copy all necessary source code from the monorepo root context (.)
    COPY agentvault_library /app/agentvault_library
    COPY agentvault_server_sdk /app/agentvault_server_sdk
    COPY poc_agents/registry_query_agent /app/poc_agents/registry_query_agent
    
    # Change to the agent directory
    WORKDIR /app/poc_agents/registry_query_agent
    
    # Use Poetry to install in a virtual environment
    RUN poetry install --no-interaction --no-ansi --only main
    
    # --- Final Stage ---
    FROM python:3.11-slim-bookworm AS final
    
    WORKDIR /app
    
    # Set required runtime ENV variables
    ENV PATH="/app/.venv/bin:$PATH" \
        PYTHONUNBUFFERED=1 \
        PYTHONDONTWRITEBYTECODE=1
    
    # Copy the virtual environment created by poetry install from the builder stage
    COPY --from=builder /app/poc_agents/registry_query_agent/.venv /app/.venv
    
    # Copy only the necessary application code from the builder stage
    COPY --from=builder /app/agentvault_library /app/agentvault_library
    COPY --from=builder /app/agentvault_server_sdk /app/agentvault_server_sdk
    COPY --from=builder /app/poc_agents/registry_query_agent /app/poc_agents/registry_query_agent
    
    # Copy agent-card.json (from build context, not from builder)
    COPY ./poc_agents/registry_query_agent/agent-card.json /app/agent-card.json
    
    # Create a non-root user for security
    RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser && \
        chown -R appuser:appgroup /app
    
    # Switch to the non-root user
    USER appuser
    
    # Expose the application port
    EXPOSE 8001
    
    # Command to run the application
    CMD ["uvicorn", "registry_query_agent.main:app", "--host", "0.0.0.0", "--port", "8001"]
    