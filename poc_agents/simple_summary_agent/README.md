# Simple Summary Agent

An agent that generates summaries of text using a local LLM via LM Studio's OpenAI-compatible endpoint.

## Overview

This agent demonstrates integration with a local LLM (bartowski/meta-llama-3.1-8b-instruct) through LM Studio. It receives text input and returns a concise summary, handling potentially longer processing times gracefully.

## Prerequisites

- LM Studio running with `bartowski/meta-llama-3.1-8b-instruct` loaded
- LM Studio server started on port 1234
- Docker for containerization
- AgentVault SDK

## Configuration

Create a `.env` file with the following variables:

```env
LOCAL_API_BASE_URL=http://host.docker.internal:1234/v1
WRAPPER_MODEL_NAME=bartowski/meta-llama-3.1-8b-instruct
SYSTEM_PROMPT=You are a helpful assistant that specializes in creating concise summaries of text. When given a text, provide a clear, accurate, and concise summary that captures the main points.
LLM_TIMEOUT_SECONDS=120
LOG_LEVEL=INFO
```

## Building and Running

### Build the Docker image

From the AgentVault monorepo root:

```bash
docker build --no-cache -t simple-summary-agent -f ./poc_agents/simple_summary_agent/Dockerfile .
```

### Run the container

```bash
docker run -d -p 8003:8003 --name simple-summary-agent --env-file ./poc_agents/simple_summary_agent/.env simple-summary-agent:latest
```

## Testing

Use the agentvault_cli to test the agent:

```bash
agentvault_cli run --agent http://localhost:8003/agent-card.json --input "Paste a long paragraph of text here that you want summarized..."
```

## API Endpoints

- `GET /`: Health check
- `GET /agent-card.json`: Agent metadata
- `POST /a2a`: A2A API endpoint

## Development

To run locally for development:

```bash
cd poc_agents/simple_summary_agent
poetry install
poetry run uvicorn simple_summary_agent.main:app --reload --port 8003
```

## Features

- **OpenAI-compatible API integration**: Works with LM Studio's endpoint
- **Configurable parameters**: Adjust max_tokens, temperature, and system prompt
- **Timeout handling**: Properly handles longer LLM processing times
- **Error handling**: Gracefully manages network errors and LLM issues

## Author

Raphael Jeziorny <AgentVault@proton.me>
