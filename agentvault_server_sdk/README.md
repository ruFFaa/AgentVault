# AgentVault Server SDK

This package provides base classes, utilities, and tools to help developers build [Agent-to-Agent (A2A) protocol](link-to-a2a-spec-later) compliant agents within the AgentVault ecosystem.

## Overview

The core component is the `BaseA2AAgent` abstract class, which defines the interface agent implementations must adhere to. The SDK also provides FastAPI integration helpers (`create_a2a_router`) to easily expose an agent implementation as a standard A2A JSON-RPC endpoint.

## Packager Utility (`agentvault-sdk package`)

To simplify deployment, the SDK includes a command-line utility to generate standardized Docker packaging artifacts for your agent project.

**Purpose:** Creates a `Dockerfile`, a `.dockerignore` file, and copies necessary configuration files (like `requirements.txt` and `agent-card.json`) into an output directory, ready for building a container image.

**Usage:**

```bash
agentvault-sdk package [OPTIONS]
```

**Options:**

*   `--output-dir DIRECTORY` / `-o DIRECTORY`: **(Required)** Directory to write Dockerfile and other artifacts.
*   `--entrypoint TEXT`: **(Required)** Python import path to the FastAPI app instance (e.g., `my_agent.main:app`).
*   `--python TEXT`: Python version for the base image tag (e.g., 3.10, 3.11). [default: 3.11]
*   `--suffix TEXT`: Suffix for the python base image (e.g., slim-bookworm, alpine). [default: slim-bookworm]
*   `--port INTEGER`: Port the application will listen on inside the container. [default: 8000]
*   `--requirements PATH` / `-r PATH`: Path to the requirements.txt file. If not provided, it looks for `./requirements.txt` in the current directory and copies it if found. A warning is issued if the SDK dependency seems missing.
*   `--agent-card PATH` / `-c PATH`: Path to the agent-card.json file. If provided, it will be copied into the output directory.
*   `--app-dir TEXT`: Directory inside the container where the application code will reside. [default: /app]
*   `--help`: Show this message and exit.

**Example:**

```bash
# Assuming your agent code is in ./src and FastAPI app is in src/my_agent/main.py
# and you have ./requirements.txt and ./agent-card.json

agentvault-sdk package \
    --output-dir ./agent_build \
    --entrypoint my_agent.main:app \
    --agent-card ./agent-card.json \
    --python 3.11
```

**Generated Files:**

Running the command creates the specified output directory (e.g., `./agent_build`) containing:

*   `Dockerfile`: A multi-stage Dockerfile optimized for Python applications.
*   `.dockerignore`: A standard file listing patterns to exclude from the build context.
*   `requirements.txt` (if source found/provided): A copy of your requirements file.
*   `agent-card.json` (if `--agent-card` provided): A copy of your agent card file.

**Building and Running the Image:**

After generating the files, navigate to your project root (where your agent source code and the output directory are) and run:

```bash
# Build the image (replace 'my-agent-image:latest' with your desired tag)
docker build -t my-agent-image:latest -f ./agent_build/Dockerfile .

# Run the container
docker run -d -p 8000:8000 --name my-running-agent my-agent-image:latest
```
*(Adjust the `-p` flag if you used a different port)*

## Future Directions

*   Integration with specific deployment platforms.
*   More sophisticated dependency analysis.
*   Advanced configuration options for Dockerfile generation.
