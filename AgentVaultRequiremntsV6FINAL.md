You are absolutely right to push for completeness and adherence to naming conventions from the start! My apologies for the oversight and any remaining internal references. Let's completely finalize the Phase 1 requirements using **`AgentVault`** as the overall project name and **`agentvault`** as the library package name, ensuring all paths, imports, and descriptions reflect this consistently.

Here is the **final, complete, double-checked, hyper-detailed requirements specification for Phase 1**, with consistent naming and ready for the WorkflowA2A.

---

**`AgentVault` - Phase 1 Hyper-Detailed Requirements (Final V3 - Consistent Naming)**

**(Target for Direct Code Generation via WorkflowA2A)**

**Project Name:** AgentVault
**Project Goal:** Develop an open-source ecosystem consisting of a Python library (`agentvault`), a central discovery registry (backend API only), and a CLI reference client (`agentvault-cli`) to enable users to securely discover and interact with remote AI agents using their own locally managed API keys, leveraging A2A/MCP protocols and adhering to global data privacy best practices.
**Phase 1 Scope:** Core Python Library (`agentvault`), Registry Backend API (`agentvault-registry`), CLI Client (`agentvault-cli`). (Web UIs & Local Agent Execution are OUT OF SCOPE).
**Core Technologies:** Python >=3.10, Poetry, FastAPI, SQLAlchemy, PostgreSQL, Alembic, Pydantic, httpx, click/typer, pytest.
**Key Protocols:** Agent2Agent (A2A - based on provided `a2a.json.txt` schema), Model Context Protocol (MCP - target latest stable/draft).
**Licensing:** Apache 2.0 (or MIT).
**Repository Structure (Monorepo Example):**
```
agentvault/
├── agentvault_library/        # Component 1: Core Library
│   ├── src/agentvault/        # Library source code
│   ├── tests/library/         # Library tests
│   ├── docs/                  # Library docs (optional subdir)
│   ├── pyproject.toml
│   ├── README.md
│   └── LICENSE
├── agentvault_registry/       # Component 2: Registry Backend API
│   ├── src/agentvault_registry/ # API source code
│   ├── tests/registry_api/    # API tests
│   ├── alembic/               # DB Migrations
│   ├── pyproject.toml
│   ├── README.md
│   └── LICENSE
├── agentvault_cli/            # Component 3: CLI Client
│   ├── src/agentvault_cli/    # CLI source code
│   ├── tests/cli/             # CLI tests
│   ├── pyproject.toml
│   ├── README.md
│   └── LICENSE
├── docs/                      # Overall Project Docs (optional top-level)
├── .gitignore                 # Top-level gitignore
└── README.md                  # Overall project README
```

---
**Component 1: Core Library (`agentvault`)**
Location: `agentvault_library/`
Package Name: `agentvault`
Source Root: `src/agentvault/`
Tests Root: `tests/library/`
---

**1.1 Foundational Setup**

*   **REQ-LIB-SETUP-001: Initialize Library with Poetry**
    *   **Component:** library
    *   **Type:** config_update
    *   **Goal:** Create `agentvault_library/pyproject.toml` and basic directory structure.
    *   **Details:**
        *   Run `poetry init` within `agentvault_library/` (or generate file manually).
        *   Set package name: `agentvault`. Version: `0.1.0`. Description: "Core Python client library for A2A protocol, MCP, and secure local key management.". Author: [Your Name/Email]. License: Apache-2.0. Python: `>=3.10,<3.12`.
        *   Package structure: `packages = [{include = "agentvault", from = "src"}]`.
        *   Core Dependencies: `python = ">=3.10,<3.12"`, `httpx = {extras = ["http2", "brotli"], version = ">=0.27,<0.28"}`, `pydantic = ">=2.0,<3.0"`, `python-dotenv = ">=1.0,<2.0"`.
        *   Optional Dependency Group: `keyring = { version = ">=24,<25", optional = true }` -> Add `[tool.poetry.extras] os_keyring = ["keyring"]`.
        *   Dev Dependencies: `pytest = ">=8.0,<9.0"`, `pytest-asyncio = ">=0.23,<0.24"`, `pytest-mock = ">=3.12,<4.0"`, `respx = ">=0.20,<0.21"`.
        *   Create directories: `agentvault_library/src/agentvault/`, `agentvault_library/src/agentvault/models/`, `agentvault_library/src/agentvault/protocols/`, `agentvault_library/tests/library/`.
        *   Create empty files: `src/agentvault/__init__.py`, `src/agentvault/models/__init__.py`, `src/agentvault/protocols/__init__.py`, `tests/__init__.py`, `tests/library/__init__.py`, `README.md`, `.gitignore` (Python/Poetry defaults).
        *   Include `LICENSE` file (Apache 2.0).
    *   **Files:** `agentvault_library/pyproject.toml`, `agentvault_library/LICENSE`, `agentvault_library/README.md`, `agentvault_library/.gitignore`, `agentvault_library/src/agentvault/__init__.py`, `agentvault_library/src/agentvault/models/__init__.py`, `agentvault_library/src/agentvault/protocols/__init__.py`, `agentvault_library/tests/__init__.py`, `agentvault_library/tests/library/__init__.py`

*   **REQ-LIB-SETUP-002: Define Custom Exception Hierarchy**
    *   **Component:** library
    *   **Type:** class_impl
    *   **Goal:** Create base exception classes for the library.
    *   **Details:**
        *   Create file `src/agentvault/exceptions.py`.
        *   Define base `AgentVaultError(Exception)`.
        *   Define subclasses: `AgentCardError(AgentVaultError)`, `AgentCardValidationError(AgentCardError)`, `AgentCardFetchError(AgentCardError)`, `A2AError(AgentVaultError)`, `A2AConnectionError(A2AError)`, `A2AAuthenticationError(A2AError)`, `A2ARemoteAgentError(A2AError)` (store status_code, response_body), `A2ATimeoutError(A2AConnectionError)`, `A2AMessageError(A2AError)`, `KeyManagementError(AgentVaultError)`.
    *   **Files:** `src/agentvault/exceptions.py`

**1.2 Agent Card & A2A Protocol Model Definition**

*   **REQ-LIB-ACARD-001: Define Agent Card Pydantic Model**
    *   **Component:** library
    *   **Type:** class_impl
    *   **Goal:** Create Pydantic models for A2A Agent Card structure.
    *   **Details:** Create `src/agentvault/models/agent_card.py`. Define Pydantic models (`AgentProvider`, `AgentSkill`, `AgentAuthentication`, `AgentCapabilities`, `AgentCard`) **exactly** mirroring the structures from `a2a.json.txt`'s `$defs`. Use Pydantic types, validation. Reference schema version in comments.
    *   **Files:** `src/agentvault/models/agent_card.py`, `src/agentvault/models/__init__.py`.

*   **REQ-LIB-A2AMODEL-001: Define Internal A2A Protocol Pydantic Models**
    *   **Component:** library
    *   **Type:** class_impl
    *   **Goal:** Create Pydantic models for A2A request/response/event structures.
    *   **Details:** Create `src/agentvault/models/a2a_protocol.py`. Define Pydantic models **exactly** mirroring structures from `a2a.json.txt`'s `$defs` (e.g., `TaskState` Enum, `TaskStatus`, `Part` Union, `Artifact`, `Task`, `Message`, `SendTaskRequest`, `TaskStatusUpdateEvent`, etc.).
    *   **Files:** `src/agentvault/models/a2a_protocol.py`, `src/agentvault/models/__init__.py`.

**1.3 Agent Card Handling Implementation & Tests**

*   **REQ-LIB-ACARD-002: Implement Agent Card Parsing/Validation Logic**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement functions to load and validate Agent Cards.
    *   **Details:** Create `src/agentvault/agent_card_utils.py`. Import models, exceptions, `httpx`, `pydantic`, etc. Implement `parse_agent_card_from_dict(Dict) -> AgentCard`, `load_agent_card_from_file(Path) -> AgentCard`, `async fetch_agent_card_from_url(str) -> AgentCard`. Handle validation, file I/O, network errors using custom exceptions.
    *   **Files:** `src/agentvault/agent_card_utils.py`

*   **REQ-LIB-ACARD-003: Write Unit Tests for Agent Card Handling**
    *   **Component:** library
    *   **Type:** unit_test
    *   **Goal:** Test parsing and validation.
    *   **Details:** Create `tests/library/test_agent_card_utils.py`. Use `pytest`, `respx`, `mock_open`. Test all three functions covering success, validation errors, file errors, network errors. Verify correct exceptions raised.
    *   **Files:** `tests/library/test_agent_card_utils.py`

**1.4 Secure Local Key Management Implementation & Tests**

*   **REQ-LIB-KEY-001: Implement KeyManager Class Structure**
    *   **Component:** library
    *   **Type:** class_impl
    *   **Goal:** Define the KeyManager class.
    *   **Details:** Create `src/agentvault/key_manager.py`. Define `KeyManager` class. `__init__(key_file_path=None, use_env_vars=True, use_keyring=False, env_prefix="AGENTVAULT_KEY_")`. Store config, init `_keys: Dict`. Call loading methods in priority order (File > Env > Keyring). Define methods `load_env`, `load_file`, `_load_keyring_key`, `get_key`, optional `set_key_in_keyring`.
    *   **Files:** `src/agentvault/key_manager.py`

*   **REQ-LIB-KEY-002: Implement KeyManager Env Var Loading**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement `load_env`.
    *   **Details:** Implement `KeyManager.load_env`. Iterate `os.environ` using `self.env_prefix`. Extract `SERVICE_ID`. Store in `self._keys` if not already present. Log service IDs.
    *   **Files:** `src/agentvault/key_manager.py`

*   **REQ-LIB-KEY-003: Implement KeyManager File Loading**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement `load_file`.
    *   **Details:** Implement `KeyManager.load_file`. Check path. Handle errors. Support `.env` (dotenv) and `.json`. Store keys (lowercase IDs) in `self._keys`, overwriting lower priority sources.
    *   **Files:** `src/agentvault/key_manager.py`

*   **REQ-LIB-KEY-004: Implement KeyManager Keyring Integration (Optional)**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement keyring methods.
    *   **Details:** Add optional `keyring` dep/extra. In `__init__`, check flag & import. Implement `set_key_in_keyring` (`keyring.set_password`), `_load_keyring_key` (`keyring.get_password`). Use service name `agentvault`. Handle errors.
    *   **Files:** `src/agentvault/key_manager.py`, `agentvault_library/pyproject.toml`

*   **REQ-LIB-KEY-005: Implement KeyManager `get_key` Method**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement primary key retrieval.
    *   **Details:** Implement `KeyManager.get_key`. Checks `self._keys`. If not found & keyring enabled, calls `_load_keyring_key`. Returns key or `None`.
    *   **Files:** `src/agentvault/key_manager.py`

*   **REQ-LIB-KEY-006: Write Unit Tests for KeyManager**
    *   **Component:** library
    *   **Type:** unit_test
    *   **Goal:** Test key loading/retrieval.
    *   **Details:** Create `tests/library/test_key_manager.py`. Use `monkeypatch`, `mock_open`, patch `keyring`. Test `__init__`, loading methods (env, file formats, errors, priority), keyring methods, `get_key`.
    *   **Files:** `tests/library/test_key_manager.py`

**1.5 A2A Client Implementation & Tests**

*   **REQ-LIB-A2ACLIENT-001: Define `AgentVaultClient` Class Structure**
    *   **Component:** library
    *   **Type:** class_impl
    *   **Goal:** Define main class for A2A interactions.
    *   **Details:** Create `src/agentvault/client.py`. Import dependencies (`httpx`, `asyncio`, typing, models, exceptions, `KeyManager`). Define `AgentVaultClient`. `__init__`. Define async methods (`initiate_task`, `send_message`, `receive_messages`, `get_task_status`, `terminate_task`). Implement `close()`, `__aenter__`, `__aexit__`. Implement `_get_auth_headers` (handles `apiKey` scheme). Implement `_make_request` (wraps `httpx`, raises specific `A2AError` subclasses).
    *   **Files:** `src/agentvault/client.py`

*   **REQ-LIB-A2ACLIENT-002: Implement `initiate_task` Method**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement task initiation via `tasks/send`.
    *   **Details:** Implement `async initiate_task(self, agent_card: AgentCard, initial_message: Message, key_manager: KeyManager, mcp_context: Optional[Dict] = None) -> str`. Get auth headers. Format/embed `mcp_context`. Construct `TaskSendParams` with `message=initial_message`. Construct `SendTaskRequest`. POST via `_make_request` to `agent_card.url`. Parse `SendTaskResponse` -> extract `result.id`. Validate. Return Task ID. Handle exceptions.
    *   **Files:** `src/agentvault/client.py`

*   **REQ-LIB-A2ACLIENT-003: Implement `send_message` Method**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement sending subsequent messages via `tasks/send`.
    *   **Details:** Implement `async send_message(self, agent_card: AgentCard, task_id: str, message: Message, key_manager: KeyManager, mcp_context: Optional[Dict] = None) -> bool`. Get auth headers. Format/embed `mcp_context`. Construct `TaskSendParams` with `id`, `message`. Construct `SendTaskRequest`. POST via `_make_request`. Return `True` or catch exceptions->`False`.
    *   **Files:** `src/agentvault/client.py`

*   **REQ-LIB-A2ACLIENT-004: Implement `receive_messages` Method (SSE Focus)**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement receiving messages via `tasks/sendSubscribe` or `tasks/resubscribe`.
    *   **Details:** Implement `async receive_messages(self, agent_card: AgentCard, task_id: str, key_manager: KeyManager) -> AsyncGenerator[Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent], None]`. Get auth headers. Determine SSE endpoint/method (assume POST to `agent_card.url` with method `tasks/sendSubscribe`). Construct request payload. Use `self._http_client.stream('POST', ...)`. Process SSE stream line by line (`aiter_lines`). Parse `event.data` JSON. Validate against event Pydantic models. `yield` validated event object. Handle stream lifecycle/errors robustly (raise `A2AConnectionError`/`A2AMessageError`).
    *   **Files:** `src/agentvault/client.py`

*   **REQ-LIB-A2ACLIENT-005: Implement `get_task_status` and `terminate_task` Methods**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Implement `tasks/get` and `tasks/cancel`.
    *   **Details:** Implement `async get_task_status(...) -> Task`: Construct `GetTaskRequest`, call `_make_request`, parse `GetTaskResponse`, return `result`. Implement `async terminate_task(...) -> bool`: Construct `CancelTaskRequest`, call `_make_request`, parse `CancelTaskResponse`, return `True` if no error.
    *   **Files:** `src/agentvault/client.py`

*   **REQ-LIB-A2ACLIENT-006: Write Unit Tests for `AgentVaultClient`**
    *   **Component:** library
    *   **Type:** unit_test
    *   **Goal:** Test A2A client logic.
    *   **Details:** Create `tests/library/test_client.py`. Use `respx`. Mock `KeyManager`. Test all public methods. Verify correct JSON-RPC requests (payloads, methods, URLs, headers). Mock responses (success, errors, SSE events). Assert return values/exceptions. Test context manager. Test auth logic.
    *   **Files:** `tests/library/test_client.py`

**1.6 MCP Implementation & Tests**

*   **REQ-LIB-MCP-001: Implement MCP Context Formatting Utility**
    *   **Component:** library
    *   **Type:** function_impl
    *   **Goal:** Internal logic to format context dict into MCP JSON.
    *   **Details:** Create `src/agentvault/mcp_utils.py`. Define MCP Pydantic models. Implement `format_mcp_context(context_data: Dict) -> Optional[Dict]`: Maps/validates input dict -> MCP models -> output dict. Returns `None` on error. Modify `AgentVaultClient` methods to call this and embed result in `message.metadata['mcp_context']`.
    *   **Files:** `src/agentvault/mcp_utils.py`, `src/agentvault/client.py`

*   **REQ-LIB-MCP-002: Write Unit Tests for MCP Formatting**
    *   **Component:** library
    *   **Type:** unit_test
    *   **Goal:** Test MCP formatting.
    *   **Details:** Create `tests/library/test_mcp_utils.py`. Test `format_mcp_context` with valid/invalid inputs. Verify output structure/exceptions.
    *   **Files:** `tests/library/test_mcp_utils.py`

**1.7 Library Packaging & Documentation**

*   **REQ-LIB-PKG-001: Finalize `agentvault/pyproject.toml`** (Review before release).
*   **REQ-LIB-DOC-001: Generate API Documentation (Sphinx)**
    *   **Component:** library
    *   **Type:** documentation
    *   **Goal:** Create API docs.
    *   **Details:** Setup Sphinx in `agentvault_library/docs/` (or top-level `docs/library/`). Config `conf.py`. Ensure clear docstrings. Build HTML.
    *   **Files:** Documentation files, Source docstrings.
*   **REQ-LIB-DOC-002: Write User Guides & Tutorials (MkDocs/Sphinx)**
    *   **Component:** library
    *   **Type:** documentation
    *   **Goal:** Provide usage guides.
    *   **Details:** Guides: Install, Quickstart, Key Mgmt, Finding Agents, A2A Workflow, Errors, Security/Trust Model.
    *   **Files:** Documentation files.
*   **REQ-LIB-LIC-001: Ensure License Compliance** (Apache 2.0/MIT).
*   **REQ-LIB-TEST-001: Achieve Test Coverage Target** (>85%).

---
**Component 2: Central Agent Registry Backend API (`agentvault-registry`)**
Location: `agentvault_registry/`
Package Name: `agentvault-registry-api`
Source Root: `src/agentvault_registry/`
Tests Root: `tests/registry_api/`
---

**2.1 Foundational Setup**

*   **REQ-REG-SETUP-001: Initialize API Project with Poetry**
    *   **Component:** registry_api
    *   **Type:** config_update
    *   **Goal:** Create `pyproject.toml` and structure.
    *   **Details:** Package `agentvault-registry-api`. Deps: `fastapi`, `uvicorn[standard]`, `SQLAlchemy`, `psycopg2-binary` (or `asyncpg`), `alembic`, `pydantic`, `pydantic-settings`, `passlib[bcrypt]`, `python-dotenv`. Dev Deps: `pytest`, `pytest-asyncio`, `httpx`. Structure: `src/agentvault_registry/`, `tests/registry_api/`, `alembic/`. Files: `README.md`, `.gitignore`, `LICENSE`.
    *   **Files:** `agentvault_registry/pyproject.toml`, etc.
*   **REQ-REG-SETUP-002: Implement FastAPI App Setup & Config**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** Create `main.py` app, load config.
    *   **Details:** Create `src/agentvault_registry/main.py` (`FastAPI` instance). Create `src/agentvault_registry/config.py` (load `DATABASE_URL`, `ALLOWED_ORIGINS`, `LOG_LEVEL`, `API_KEY_SECRET` via `pydantic-settings`). Configure CORS.
    *   **Files:** `src/agentvault_registry/main.py`, `src/agentvault_registry/config.py`, `agentvault_registry/.env.example`
*   **REQ-REG-SETUP-003: Implement Database Setup & Session**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** Configure SQLAlchemy.
    *   **Details:** Create `src/agentvault_registry/database.py`. Engine, `SessionLocal`, `Base`. Implement `get_db` dependency.
    *   **Files:** `src/agentvault_registry/database.py`
*   **REQ-REG-SETUP-004: Define Core DB Models (Developers, AgentCards)**
    *   **Component:** registry_api
    *   **Type:** class_impl
    *   **Goal:** Define SQLAlchemy models.
    *   **Details:** Create `src/agentvault_registry/models.py`. `Developer` (id, name, api_key_hash). `AgentCard` (id/UUID, developer_id FK, card_data JSONB, name indexed, description indexed, is_active bool indexed, timestamps).
    *   **Files:** `src/agentvault_registry/models.py`
*   **REQ-REG-SETUP-005: Setup Alembic for Migrations**
    *   **Component:** registry_api
    *   **Type:** config_update
    *   **Goal:** Configure Alembic.
    *   **Details:** `alembic init alembic`. Modify `.ini` (URL from env). Modify `env.py` (import Base/models, set metadata).
    *   **Files:** `agentvault_registry/alembic.ini`, `agentvault_registry/alembic/env.py`
*   **REQ-REG-SETUP-006: Create Initial Alembic Migration**
    *   **Component:** registry_api
    *   **Type:** db_migration
    *   **Goal:** Generate initial migration script.
    *   **Details:** `alembic revision --autogenerate`. Review script for table creation.
    *   **Files:** `agentvault_registry/alembic/versions/<rev_id>....py`

**2.2 Developer Authentication API**

*   **REQ-REG-AUTH-001: Implement API Key Utils (Hashing, Generation)**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** Secure key handling utils.
    *   **Details:** Create `src/agentvault_registry/security.py`. Use `passlib` (`verify_api_key`, `hash_api_key`). Use `secrets` (`generate_secure_api_key`).
    *   **Files:** `src/agentvault_registry/security.py`
*   **REQ-REG-AUTH-002: Implement Developer CRUD (Internal)**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** Functions to manage developer records (for admin use).
    *   **Details:** Create `src/agentvault_registry/crud/developer.py`. Implement `create_developer(db, name)` -> returns `(Developer, plain_key)`. Implement `get_developer_by_plain_api_key(db, plain_key)` -> iterates, verifies hash, returns `Developer` or `None`.
    *   **Files:** `src/agentvault_registry/crud/developer.py`
*   **REQ-REG-AUTH-003: Implement API Key Authentication Dependency**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** FastAPI dependency to verify `X-Api-Key` header.
    *   **Details:** In `security.py`: Define `api_key_header = APIKeyHeader(...)`. Implement `async get_current_developer(key=Depends(api_key_header), db=Depends(get_db))`: Calls `crud.get_developer_by_plain_api_key`. Raises 401/403. Returns `Developer`.
    *   **Files:** `src/agentvault_registry/security.py`, `src/agentvault_registry/crud/developer.py`

**2.3 Agent Card API Endpoints**

*   **REQ-REG-APIIMPL-001: Define API Schemas (Pydantic)**
    *   **Component:** registry_api
    *   **Type:** class_impl
    *   **Goal:** Request/response models.
    *   **Details:** Create `src/agentvault_registry/schemas.py`. Define `AgentCardCreate` (accepts Dict), `AgentCardUpdate`, `AgentCardRead` (represents full card), `AgentCardSummary` (id, name, desc), `AgentCardListResponse` (items, pagination).
    *   **Files:** `src/agentvault_registry/schemas.py`
*   **REQ-REG-APIIMPL-002: Implement Agent Card CRUD Logic**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** DB interaction functions.
    *   **Details:** Create `src/agentvault_registry/crud/agent_card.py`. Implement `create_agent_card` (validate input against `AgentCard` model from `agentvault` library or mirrored schema, save), `get_agent_card`, `list_agent_cards` (with filtering/pagination), `update_agent_card`, `delete_agent_card` (soft delete).
    *   **Files:** `src/agentvault_registry/crud/agent_card.py`
*   **REQ-REG-APIIMPL-003: Implement API Router & Endpoints**
    *   **Component:** registry_api
    *   **Type:** function_impl
    *   **Goal:** FastAPI router implementation.
    *   **Details:** Create `src/agentvault_registry/routers/agent_cards.py`. Use `APIRouter`. Implement endpoints: `POST /` (auth), `PUT /{id}` (auth), `GET /{id}` (public), `GET /` (public, with filters/pagination), `DELETE /{id}` (auth). Use `Depends(get_current_developer)`. Call CRUD. Handle ownership, validation, errors (400-500). Return schemas/status codes. Include router in `main.py`.
    *   **Files:** `src/agentvault_registry/routers/agent_cards.py`, `src/agentvault_registry/main.py`
*   **REQ-REG-APIIMPL-004: Write API Integration Tests**
    *   **Component:** registry_api
    *   **Type:** integration_test
    *   **Goal:** Test live API endpoints.
    *   **Details:** Create `tests/registry_api/test_agent_cards_api.py`. Use `pytest`, `httpx.AsyncClient(app=...)`. Setup test DB. Test all endpoints, success/error cases, auth, filtering, pagination. Validate responses.
    *   **Files:** `tests/registry_api/test_agent_cards_api.py`, `tests/registry_api/conftest.py`.

---
**Component 3: CLI Reference Client (`agentvault-cli`)**
Location: `agentvault_cli/`
Package Name: `agentvault-cli`
Source Root: `src/agentvault_cli/`
Tests Root: `tests/cli/`
Dependency: `agentvault` (Core Library)
---

**3.1 Foundational Setup**

*   **REQ-CLI-SETUP-001: Initialize CLI Project with Poetry**
    *   **Component:** cli
    *   **Type:** config_update
    *   **Goal:** Create `pyproject.toml` and structure.
    *   **Details:** Package `agentvault-cli`. Deps: `click`, `httpx`, `rich`, `agentvault = {path = "../agentvault_library", develop = true}`. Dev Deps: `pytest`, `pytest-mock`. Entry point: `agentvault_cli = "agentvault_cli.main:cli"`. Structure/Files as before.
    *   **Files:** `agentvault_cli/pyproject.toml`, etc.
*   **REQ-CLI-SETUP-002: Implement Main CLI Entry Point (Click)**
    *   **Component:** cli
    *   **Type:** function_impl
    *   **Goal:** Setup main `click` group.
    *   **Details:** Create `src/agentvault_cli/main.py`. Define `@click.group() def cli(): ...`. Import and add command groups (`config`, `discover`, `run`). Implement `if __name__ == "__main__"` block.
    *   **Files:** `src/agentvault_cli/main.py`
*   **REQ-CLI-SETUP-003: Implement Basic Utility/Error Handling**
    *   **Component:** cli
    *   **Type:** function_impl
    *   **Goal:** Helper functions for console output.
    *   **Details:** Create `src/agentvault_cli/utils.py`. Use `click.secho`, `click.echo`. Use `rich.table.Table` for `display_table`.
    *   **Files:** `src/agentvault_cli/utils.py`

**3.2 Key Management Commands**

*   **REQ-CLI-KEY-001: Implement `config` Command Group**
    *   **Component:** cli
    *   **Type:** function_impl
    *   **Goal:** Create `config` subcommand group.
    *   **Details:** Create `src/agentvault_cli/commands/config.py`. Define `@click.group()`. Add to `main.cli`.
    *   **Files:** `src/agentvault_cli/commands/config.py`, `src/agentvault_cli/main.py`, `src/agentvault_cli/commands/__init__.py`
*   **REQ-CLI-KEY-002: Implement `config set` Command (Guidance & Keyring)**
    *   **Component:** cli
    *   **Type:** cli_command
    *   **Goal:** Guide user or set key in keyring.
    *   **Details:** In `config.py`: `@config.command('set')`. Args: `service_id`. Options: `--env`, `--file <path>`, `--keyring`. Prompt for key only if `--keyring` used. If `--env`/`--file`, print instructions. If `--keyring`, `import agentvault.KeyManager`. Call `manager.set_key_in_keyring`. Print success/error.
    *   **Files:** `src/agentvault_cli/commands/config.py`
*   **REQ-CLI-KEY-003: Implement `config get` Command**
    *   **Component:** cli
    *   **Type:** cli_command
    *   **Goal:** Show key source.
    *   **Details:** In `config.py`: `@config.command('get')`. Args: `service_id`. `import agentvault.KeyManager`. Instantiate. Call `manager.get_key`. Determine source (requires `KeyManager` enhancement). Print source or "Not found".
    *   **Files:** `src/agentvault_cli/commands/config.py` (Requires KeyManager enhancement)
*   **REQ-CLI-KEY-004: Implement `config list` Command**
    *   **Component:** cli
    *   **Type:** cli_command
    *   **Goal:** List potentially configured services.
    *   **Details:** In `config.py`: `@config.command('list')`. `import agentvault.KeyManager`. Instantiate. Print keys found in `manager._keys` and their source (Env/File).
    *   **Files:** `src/agentvault_cli/commands/config.py`

**3.3 Agent Discovery Command**

*   **REQ-CLI-DISC-001: Implement `discover` Command**
    *   **Component:** cli
    *   **Type:** cli_command
    *   **Goal:** Search registry API.
    *   **Details:** In `src/agentvault_cli/commands/discover.py`: Define `@cli.command('discover')`. Args: `search_query` (optional). Options: `--registry <url>`, `--limit`, `--offset`. Use `httpx` to call registry `GET /api/v1/agent-cards` with params. Parse `AgentCardListResponse`. Use `utils.display_table`. Show pagination. Handle errors. Add to `main.cli`.
    *   **Files:** `src/agentvault_cli/commands/discover.py`, `src/agentvault_cli/main.py`.

**3.4 Task Execution Command**

*   **REQ-CLI-RUN-001: Implement `run` Command Structure & Agent Loading**
    *   **Component:** cli
    *   **Type:** cli_command
    *   **Goal:** Setup `run` command, load Agent Card.
    *   **Details:** In `src/agentvault_cli/commands/run.py`: Define `@cli.command('run')` async. Options: `--agent <id|url|file>`, `--input <text|@filepath>`, `--context-file <path>`, `--registry <url>`, `--key-service <id>`, `--auth-key <value>` (insecure). Import `agentvault.agent_card_utils`, `agentvault.exceptions`. Determine agent source. Load Agent Card using library functions (`fetch_agent_card_from_url`, `load_agent_card_from_file`) or registry API call if ID. Store `AgentCard` model. Handle errors. Add command to `main.cli`.
    *   **Files:** `src/agentvault_cli/commands/run.py`, `src/agentvault_cli/main.py`.
*   **REQ-CLI-RUN-002: Implement Key/Context Loading for `run`**
    *   **Component:** cli
    *   **Type:** function_impl
    *   **Goal:** Load keys/context in `run` command.
    *   **Details:** Inside `run`: `import agentvault.KeyManager`. Instantiate. Determine `service_identifier` from card `authSchemes` or `--key-service`. Handle `--auth-key` override. If `--context-file`, read file, parse JSON, store as `mcp_context` dict.
    *   **Files:** `src/agentvault_cli/commands/run.py`
*   **REQ-CLI-RUN-003: Implement A2A Interaction Logic for `run`**
    *   **Component:** cli
    *   **Type:** function_impl
    *   **Goal:** Use library client to run task and display results.
    *   **Details:** Inside `run`: `import agentvault.AgentVaultClient`, `agentvault.models.a2a_protocol as a2a_models`. Use `async with AgentVaultClient() as client:`. Structure input as `a2a_models.Message` with `a2a_models.TextPart`. Call `await client.initiate_task(..., initial_message=...)`. Handle exceptions. Print Task ID. Use `async for event in client.receive_messages(...)`: Print formatted status (`TaskStatusUpdateEvent`) / artifacts (`TaskArtifactUpdateEvent`, extract text/data). Handle completion/error. Add Ctrl+C handler -> `client.terminate_task`.
    *   **Files:** `src/agentvault_cli/commands/run.py`

**3.5 CLI Testing**

*   **REQ-CLI-TEST-001: Write Tests for CLI Commands**
    *   **Component:** cli
    *   **Type:** unit_test
    *   **Goal:** Verify CLI logic by mocking library.
    *   **Details:** Create `tests/cli/test_*.py` files. Use `click.testing.CliRunner`. Patch imports from `agentvault`. Invoke commands. Assert calls to library mocks, exit codes, output. Test arg parsing, error handling.
    *   **Files:** `tests/cli/*`

---

This revised document consistently uses `AgentVault` for the project and `agentvault` for the library name/package, updating paths and imports accordingly. It should now be complete and ready for you to start requesting code generation using Plate A for specific `REQ-` items.