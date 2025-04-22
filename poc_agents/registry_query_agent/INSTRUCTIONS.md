# Instructions for Registry Query Agent

Congratulations! You've successfully generated the boilerplate code for your AgentVault agent: `Registry Query Agent`.

This package contains:

*   `src/registry_query_agent/`: The Python source code for your agent.
    *   `main.py`: FastAPI application setup.
    *   `agent.py`: Core agent logic (inherits from `BaseA2AAgent` or wraps ADK).
    *   
*   `tests/`: Basic pytest structure (add your agent-specific tests here!).
*   `pyproject.toml`: Project metadata and dependencies managed by Poetry.
*   `requirements.txt`: Pinned dependencies for Docker build (generated from `pyproject.toml`).
*   `agent-card.json`: Metadata describing your agent for discovery.
*   `Dockerfile`: For building a container image of your agent.
*   `.gitignore`: Standard ignore file.
*   `.env.example`: **IMPORTANT:** Example environment variables needed to run your agent.
*   `INSTRUCTIONS.md`: This file.

## Next Steps:

**1. Configure Environment Variables:**

*   **Crucial Step:** Your agent needs credentials or configuration to connect to its backend LLM (local_openai_compatible) and potentially for its own authentication.
*   Copy the `.env.example` file to a new file named `.env` in the same directory:
    ```bash
    cp .env.example .env
    ```
*   **Edit the `.env` file:** Open the new `.env` file in a text editor.
*   **Fill in the required values:** Look for the section corresponding to `local_openai_compatible` and replace the placeholder values (like `"sk-..."` or `"YOUR_GOOGLE_API_KEY"`) with your **actual API keys or configuration**.

*   **Save the `.env` file.** **NEVER commit your `.env` file (containing secrets) to Git.** The included `.gitignore` should prevent this.

**2. Build the Docker Image:**

*   Make sure you have [Docker](https://docs.docker.com/get-docker/) installed and running.
*   Open your terminal in this directory (where the `Dockerfile` is).
*   Run the build command (replace `registry-query-agent` with your preferred image tag):
    ```bash
    docker build -t registry-query-agent:latest .
    ```

**3. Run the Agent Container:**

*   Run the container, making sure to pass the environment variables from your `.env` file and map the correct port:
    ```bash
    docker run -d --env-file .env -p 8001:8001 --name registry-query-agent registry-query-agent:latest
    ```
    *   `-d`: Run in detached mode (background).
    *   `--env-file .env`: Securely passes the variables from your `.env` file to the container.
    *   `-p 8001:8001`: Maps the port inside the container to the same port on your host machine.
    *   `--name ...`: Assigns a convenient name to the running container.

**4. Verify the Agent is Running:**

*   Check the container logs: `docker logs registry-query-agent`
*   Access the root endpoint in your browser or with `curl`: `http://localhost:8001/`
*   Access the agent card: `http://localhost:8001/agent-card.json`

**5. Interact with your Agent:**

*   Use the AgentVault CLI (`agentvault_cli run`) or the AgentVault Client Library (`agentvault`) to interact with your agent's A2A endpoint:
    *   **A2A Endpoint URL:** `http://localhost:8001/a2a`
    *   **Agent Reference:** You can use the URL `http://localhost:8001/agent-card.json` or the local file path `agent-card.json`.
    *   **Example CLI command:**
        ```bash
        agentvault run --agent http://localhost:8001/agent-card.json --input "Your prompt here"
        ```


**6. (Optional) Publish to Registry:**

*   If you want others to discover your agent, you can publish its `agent-card.json` to an AgentVault Registry.
*   **Update the `url` field** in `agent-card.json` to point to the **publicly accessible URL** where your agent will be deployed (e.g., `https://your-deployed-agent.com/a2a`), not `localhost`.
*   Use the AgentVault Developer Portal UI (if available on the registry) or the registry's API (requires a Developer API Key) to submit your updated `agent-card.json`.

**7. Develop Further:**

*   Modify the agent logic in `src/registry_query_agent/agent.py`.
*   Add tests in `tests/`.
*   Update dependencies in `pyproject.toml` and regenerate `requirements.txt` (`poetry lock && poetry export -f requirements.txt --output requirements.txt --without-hashes`).
*   Rebuild your Docker image after making changes.

Happy agent building!
