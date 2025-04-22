# Task Logger Agent

An agent that logs messages to a PostgreSQL database with timestamps.

## Overview

This agent demonstrates database interaction in the AgentVault framework. It receives text messages and logs them along with timestamps into a PostgreSQL database table (`agent_logs`).

## Prerequisites

- PostgreSQL database running and accessible
- Docker for containerization
- AgentVault SDK

## Database Setup

The agent will automatically create the required table if it doesn't exist:

```sql
CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    message TEXT
);
```

## Configuration

Create a `.env` file with the following variables:

```env
DATABASE_HOST=host.docker.internal  # For Docker container
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
DATABASE_NAME=agentvault_dev
LOG_LEVEL=INFO
```

## Building and Running

### Build the Docker image

From the AgentVault monorepo root:

```bash
docker build --no-cache -t task-logger-agent -f ./poc_agents/task_logger_agent/Dockerfile .
```

### Run the container

```bash
docker run -d -p 8002:8002 --name task-logger-agent --env-file ./poc_agents/task_logger_agent/.env task-logger-agent:latest
```

## Testing

Use the agentvault_cli to test the agent:

```bash
agentvault_cli run --agent http://localhost:8002/agent-card.json --input "Test message to log"
```

Verify the message appears in your PostgreSQL database:

```sql
SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT 1;
```

## API Endpoints

- `GET /`: Health check
- `GET /agent-card.json`: Agent metadata
- `POST /a2a`: A2A API endpoint

## Development

To run locally for development:

```bash
cd poc_agents/task_logger_agent
poetry install
poetry run uvicorn task_logger_agent.main:app --reload --port 8002
```

## Author

Raphael Jeziorny <AgentVault@proton.me>
