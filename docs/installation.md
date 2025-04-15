# Installation Guide

This guide covers how to install the different parts of the AgentVault ecosystem.

## 1. Installing the CLI (`agentvault_cli`)

This is the primary tool for end-users and developers interacting with the registry and agents.

**Prerequisites:**

*   Python 3.10 or 3.11 installed.
*   `pip` (Python's package installer).

**Installation from PyPI (Recommended):**

Once published, you can install the CLI directly using pip:

```bash
pip install agentvault-cli
```

To include optional OS Keyring support for secure credential storage:

```bash
pip install "agentvault-cli[os_keyring]"
```

**Verification:**

After installation, check that the command is available:

```bash
agentvault_cli --version
```

## 2. Setting up the Development Environment (for Contributors)

If you want to contribute to AgentVault or run components locally from source, follow these steps:

**Prerequisites:**

*   Git
*   Python 3.10 or 3.11
*   [Poetry](https://python-poetry.org/docs/#installation) (Python dependency management and packaging tool)

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SecureAgentTools/AgentVault.git
    cd AgentVault
    ```

2.  **Install Dependencies:** Navigate to the project root (`AgentVault/`) and use Poetry to install all dependencies for all workspace packages, including development dependencies:
    ```bash
    poetry install --with dev
    ```
    *   This command reads the `pyproject.toml` files in each component directory (`agentvault_library`, `agentvault_cli`, etc.).
    *   It resolves all dependencies across the workspace.
    *   It installs everything into a single virtual environment located in the project root (usually `.venv/`).
    *   The `--with dev` flag ensures development tools (like `pytest`, `httpx` for testing, `mkdocs` for docs) are also installed.

3.  **Activate Virtual Environment:** Before running any commands or tests, activate the environment created by Poetry:
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
    agentvault_cli --version
    pytest agentvault_library/tests/
    mkdocs --version
    ```

## 3. Installing Libraries (`agentvault`, `agentvault-server-sdk`)

If you only need to use the client library or the server SDK in your own Python project (without the CLI or registry), you can install them individually from PyPI.

**Client Library (`agentvault`):**

```bash
pip install agentvault
```

With optional OS Keyring support:

```bash
pip install "agentvault[os_keyring]"
```

**Server SDK (`agentvault-server-sdk`):**

```bash
pip install agentvault-server-sdk
```

*(Note: The Server SDK depends on the `agentvault` library, so pip will install both).*

## 4. Running the Registry (Local Development)

To run the `agentvault_registry` API locally (e.g., for testing agents or the CLI against it):

1.  **Complete Development Setup:** Follow the steps in section 2 above.
2.  **Navigate:**
    ```bash
    cd agentvault_registry
    ```
3.  **Configure Database & Secrets:**
    *   Copy `.env.example` to `.env` (if it exists) or create a `.env` file.
    *   Set the `DATABASE_URL` environment variable in the `.env` file to point to your local PostgreSQL instance (ensure it uses the `asyncpg` driver, e.g., `postgresql+asyncpg://user:pass@host:port/dbname`).
    *   Set the `API_KEY_SECRET` environment variable in the `.env` file (generate a strong secret, e.g., `openssl rand -hex 32`).
4.  **Database Setup:**
    *   Ensure your PostgreSQL server is running and the specified database exists.
    *   Run database migrations using Alembic (make sure your virtual environment is activated):
        ```bash
        alembic upgrade head
        ```
5.  **Run the Server:** Use Uvicorn (which was installed as part of FastAPI dependencies):
    ```bash
    uvicorn agentvault_registry.main:app --reload --host 0.0.0.0 --port 8000
    ```
    *   `--reload`: Automatically restarts the server when code changes.
    *   `--host 0.0.0.0`: Makes the server accessible from other devices on your network (use `127.0.0.1` for localhost only).
    *   `--port 8000`: The default port.

The registry API should now be running at `http://localhost:8000`. You can access the API docs at `http://localhost:8000/docs`.
