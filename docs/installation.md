# Installation Guide

This guide covers how to install the different parts of the AgentVault ecosystem, depending on your needs.

## 1. Installing for Usage (CLI & Client Library)

If you want to use the AgentVault CLI to interact with agents or use the `agentvault` client library in your own Python projects, install directly from PyPI.

**Prerequisites:**

*   Python 3.10 or 3.11 installed.
*   `pip` (Python's package installer).

**Installation Options:**

*   **CLI Only:**
    ```bash
    pip install agentvault-cli
    ```
    *To include optional OS Keyring support for secure credential storage:*
    ```bash
    pip install "agentvault-cli[os_keyring]"
    ```

*   **Client Library Only (`agentvault`):**
    ```bash
    pip install agentvault
    ```
    *To include optional OS Keyring support:*
    ```bash
    pip install "agentvault[os_keyring]"
    ```

*   **Server SDK Only (`agentvault-server-sdk`):**
    *(Note: This also installs the `agentvault` client library as a dependency)*
    ```bash
    pip install agentvault-server-sdk
    ```

**Verification (CLI):**

After installing the CLI, check that the command is available:

```bash
agentvault_cli --version
```

**Connecting to the Public Registry:**

You can use the installed CLI or library with the publicly hosted registry:

*   **URL:** `https://agentvault-registry-api.onrender.com`
*   **Usage:**
    *   Set the environment variable: `export AGENTVAULT_REGISTRY_URL=https://agentvault-registry-api.onrender.com` (Linux/macOS) or `set AGENTVAULT_REGISTRY_URL=https://agentvault-registry-api.onrender.com` (Windows Cmd) or `$env:AGENTVAULT_REGISTRY_URL='https://agentvault-registry-api.onrender.com'` (PowerShell).
    *   Or use the `--registry` flag with CLI commands: `agentvault_cli discover --registry https://agentvault-registry-api.onrender.com`
*   **Note (Cold Start):** This instance runs on Render's free tier. If it hasn't received traffic recently, it might take **up to 60 seconds** to respond to the first request while it "wakes up". Subsequent requests will be faster. You can send a simple request like `curl https://agentvault-registry-api.onrender.com/health` to wake it up before running commands if needed.

## 2. Setting up for Development (Contributing or Running from Source)

If you want to contribute to AgentVault, run components locally from the source code (like the registry), or use features not yet released on PyPI, follow these steps. This sets up the entire monorepo.

**Prerequisites:**

*   Git
*   Python 3.10 or 3.11
*   [Poetry](https://python-poetry.org/docs/#installation) (Python dependency management and packaging tool)
*   **PostgreSQL Server** (Required *only* if running the `agentvault_registry` locally).

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SecureAgentTools/AgentVault.git
    cd AgentVault
    ```

2.  **Install Dependencies (including Development Tools):** Navigate to the project root (`AgentVault/`) and use Poetry to install all dependencies for all workspace packages:
    ```bash
    # Installs production AND development dependencies (pytest, httpx, mkdocs, etc.)
    poetry install --with dev

    # To include optional OS Keyring support for development:
    # poetry install --with dev --extras os_keyring
    ```
    *   This command reads the `pyproject.toml` files in each component directory (`agentvault_library`, `agentvault_cli`, etc.).
    *   It resolves all dependencies across the workspace.
    *   It installs everything into a single virtual environment located in the project root (usually `.venv/`).

3.  **Activate Virtual Environment:** Before running any commands or tests from source, activate the environment created by Poetry:
    *   **Linux/macOS (bash/zsh):**
        ```bash
        source .venv/bin/activate
        ```
    *   **Windows (PowerShell):**
        ```powershell
        .\.venv\Scripts\Activate.ps1
        ```
    *   **Windows (Command Prompt):**
        ```cmd
        .\.venv\Scripts\activate.bat
        ```
    You should see `(.venv)` appear at the beginning of your command prompt line.

4.  **Verify Installation:** You can now run commands from different components, e.g.:
    ```bash
    # Check CLI version (running from source)
    agentvault_cli --version
    # Run library tests
    pytest agentvault_library/tests/
    # Check docs tool
    mkdocs --version
    ```

## 3. Running the Registry (Local Development)

To run the `agentvault_registry` API locally (e.g., for testing agents or the CLI against it):

1.  **Complete Development Setup:** Follow the steps in section 2 above. Ensure you have a running **PostgreSQL** server accessible.
2.  **Navigate:**
    ```bash
    cd agentvault_registry
    ```
3.  **Configure Database & Secrets:**
    *   Copy `.env.example` to `.env` (if it exists) or create a `.env` file in the `agentvault_registry/` directory.
    *   Set the `DATABASE_URL` environment variable in the `.env` file to point to your local PostgreSQL instance (ensure it uses the `asyncpg` driver, e.g., `postgresql+asyncpg://user:pass@host:port/dbname`).
    *   Set the `API_KEY_SECRET` environment variable in the `.env` file (generate a strong secret, e.g., `openssl rand -hex 32`).
4.  **Database Setup:**
    *   Ensure your PostgreSQL server is running and the specified database exists.
    *   Run database migrations using Alembic (make sure your virtual environment is activated):
        ```bash
        # Run from the agentvault_registry/ directory
        alembic upgrade head
        ```
5.  **Run the Server:** Use Uvicorn (which was installed as part of development dependencies):
    ```bash
    # Run from the agentvault_registry/ directory
    uvicorn agentvault_registry.main:app --reload --host 0.0.0.0 --port 8000
    ```
    *   `--reload`: Automatically restarts the server when code changes.
    *   `--host 0.0.0.0`: Makes the server accessible from other devices on your network (use `127.0.0.1` for localhost only).
    *   `--port 8000`: The default port.

The registry API should now be running at `http://localhost:8000`. You can access the API docs at `http://localhost:8000/docs`.
