# Stage 1: Build environment with dependencies
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app # Use /app consistently

# Prevent writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Keep python output unbuffered
ENV PYTHONUNBUFFERED 1

# Install Poetry
ENV POETRY_HOME="/opt/poetry"
ENV POETRY_VERSION="1.8.3"
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"
ENV PATH="${POETRY_HOME}/bin:${PATH}"

# Copy all source code needed first
COPY ./agentvault_library /app/agentvault_library
COPY ./agentvault_registry /app/agentvault_registry

# --- MODIFIED: Generate lock and export MAIN dependencies only ---
WORKDIR /app/agentvault_registry
RUN poetry lock --no-interaction
RUN poetry export --without-hashes -o requirements.txt
# --- END MODIFIED ---

# Create wheels directory
RUN mkdir /wheels

# --- MODIFIED: Install MAIN dependencies from requirements.txt ---
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir -r requirements.txt -w /wheels
# --- END MODIFIED ---

# --- MODIFIED: Build wheels for local path deps and project ---
WORKDIR /app/agentvault_library
RUN poetry build --format wheel -n -v && cp dist/*.whl /wheels/
WORKDIR /app/agentvault_registry
RUN poetry build --format wheel -n -v && cp dist/*.whl /wheels/
# --- END MODIFIED ---

# --- ADDED: Install DEV dependencies separately into the wheels dir ---
# This avoids exporting them, potentially bypassing the problematic export step
RUN poetry export --group dev --without-hashes -o requirements-dev.txt && \
    pip wheel --no-cache-dir -r requirements-dev.txt -w /wheels
# --- END ADDED ---


# Stage 2: Final application image
FROM python:3.11-slim-bookworm AS final

WORKDIR /app

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

# Create and activate a runtime virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the wheels from the builder stage
COPY --from=builder /wheels /wheels

# Install all wheels using pip into the virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/*.whl

# Copy necessary non-code assets for the registry
COPY ./agentvault_registry/alembic.ini /app/alembic.ini
COPY ./agentvault_registry/alembic /app/alembic
# We DO NOT copy ./src anymore, it's installed via the wheel

# Change ownership of potentially needed runtime dirs (like alembic versions)
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Command to run the application using Uvicorn
# Runs migrations first, then starts server using the installed package entry point
# Need to ensure alembic and uvicorn are found in the venv PATH
CMD ["sh", "-c", "alembic upgrade head && uvicorn agentvault_registry.main:app --host 0.0.0.0 --port 8000"]
