# Query And Log Agent

An orchestrator agent that demonstrates agent-to-agent communication by querying one agent and logging results with another.

## Overview

This agent showcases multi-agent workflows in the AgentVault framework. It orchestrates a two-step process:
1. Takes a search term and queries the Registry Query Agent
2. Logs the search term and the first result with the Task Logger Agent

## Prerequisites

- Registry Query Agent running on port 8001
- Task Logger Agent running on port 8002
- AgentVault client library installed
- Docker for containerization

## Configuration

Create a `.env` file with the following variables:

```env
# Agent URLs - use these for local development/testing
REGISTRY_QUERY_AGENT_URL=http://host.docker.internal:8001/agent-card.json
TASK_LOGGER_AGENT_URL=http://host.docker.internal:8002/agent-card.json

# Alternative: Use IDs if agents are registered
# REGISTRY_QUERY_AGENT_ID=local-poc/registry-query
# TASK_LOGGER_AGENT_ID=local-poc/task-logger

LOG_LEVEL=INFO
```

## Building and Running

### Build the Docker image

From the AgentVault monorepo root:

```bash
docker build --no-cache -t query-and-log-agent -f ./poc_agents/query_and_log_agent/Dockerfile .
```

### Run the container

```bash
docker run -d -p 8004:8004 --name query-and-log-agent --env-file ./poc_agents/query_and_log_agent/.env query-and-log-agent:latest
```

## Testing

Use the agentvault_cli to test the orchestrator:

```bash
agentvault_cli run --agent http://localhost:8004/agent-card.json --input "weather"
```

This will:
1. Send "weather" to the Registry Query Agent
2. Receive a response from the agent (currently powered by LLM)
3. Log both the search term and the response to the database via Task Logger Agent
4. Return a confirmation message

Verify in the database:
```sql
SELECT * FROM agent_logs WHERE message LIKE '%weather%' ORDER BY timestamp DESC;
```

## API Endpoints

- `GET /`: Health check
- `GET /agent-card.json`: Agent metadata
- `POST /a2a`: A2A API endpoint

## Development

To run locally for development:

```bash
cd poc_agents/query_and_log_agent
poetry install
poetry run uvicorn query_and_log_agent.main:app --reload --port 8004
```

## Features

- **Multi-agent orchestration**: Demonstrates agent-to-agent communication
- **Workflow management**: Handles sequential agent interactions
- **Error handling**: Gracefully manages failures in multi-step processes
- **Async task execution**: Non-blocking communication with multiple agents

## Author

Raphael Jeziorny <AgentVault@proton.me>
