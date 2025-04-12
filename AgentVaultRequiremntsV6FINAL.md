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
        *   Set package name: `agentvault`. Version: `0.1.0`. Description: "Core Python client library for A2A protocol, MCP, and secure local key management.". Author: [{ name = "Raphael Zbiniew Jeziorny", email = "AgentVault@proton.me" }]. License: Apache-2.0. Python: `>=3.10,<3.12`.
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


Additions lets call it Phase1.1
Understood, boss. You want a consolidated list of just the **new requirements** we've added based on our discussion about security, ethics, community, legal, operations, and technical refinements, formatted similarly to the original requirements doc.

Here is that consolidated list:

---

**`AgentVault` - Phase 1 Additions Requirements (Responsible Practices & Refinements)**

**Section: Enhanced Security & Trust**

*   **REQ-SEC-DEP-001: Integrate Automated Dependency Scanning**
    *   **Component:** CI/CD (Affects all components indirectly)
    *   **Type:** ci_cd_integration
    *   **Goal:** Add automated checks for known vulnerabilities in project dependencies.
    *   **Details:** Integrate `pip-audit` or GitHub Dependabot into the CI workflow. Configure it to scan `poetry.lock` files for all components (`agentvault_library`, `agentvault_registry`, `agentvault_cli`). Fail the build on high/critical severity vulnerabilities.
    *   **Files:** CI configuration files (e.g., `.github/workflows/ci.yml`)

*   **REQ-SEC-DEP-002: Document Dependency Update Policy**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Define how vulnerable dependencies are handled.
    *   **Details:** Add a section to `CONTRIBUTING.md` outlining the scanning process, prioritization (critical/high), update attempts, risk assessment, and contributor expectations regarding dependency updates.
    *   **Files:** `CONTRIBUTING.md`

*   **REQ-SEC-DISC-001: Create SECURITY.md File**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Establish a clear process for responsible vulnerability disclosure.
    *   **Details:** Create `SECURITY.md` outlining the scope, preferred reporting methods (GitHub Private Reporting / dedicated email), information to include, response expectations, and a safe harbor statement.
    *   **Files:** `SECURITY.md`

*   **REQ-REG-SEC-001: Implement Rate Limiting**
    *   **Component:** `agentvault-registry`
    *   **Type:** function_impl
    *   **Goal:** Protect the registry API against abuse.
    *   **Details:** Add `slowapi` dependency. Configure and apply `Limiter` middleware in `main.py`. Use remote IP as the default key. Consider different limits for public vs. authenticated endpoints.
    *   **Files:** `agentvault_registry/pyproject.toml`, `agentvault_registry/src/agentvault_registry/main.py`

*   **REQ-REG-SEC-002: Enhance Query Parameter Validation**
    *   **Component:** `agentvault-registry`
    *   **Type:** function_impl
    *   **Goal:** Prevent overly long search queries.
    *   **Details:** In `routers/agent_cards.py`, add `max_length` validation (e.g., 100) to the `search` query parameter in the `list_agent_cards` endpoint using `fastapi.Query`.
    *   **Files:** `agentvault_registry/src/agentvault_registry/routers/agent_cards.py`

*   **REQ-DOC-SEC-001: Enhance README Security Section**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Increase user awareness of the trust model and risks.
    *   **Details:** Expand the "Security Model" section in the main `README.md`. Add a "Trusting Remote Agents" subsection. Emphasize user responsibility, checking provider policies. Link to `SECURITY.md`, `REGISTRY_POLICY.md`, `TERMS_OF_SERVICE.md`, `PRIVACY_POLICY.md`.
    *   **Files:** `README.md`

*   **REQ-CLI-SEC-001: Add CLI Warning for New Agents (Optional - Phase 1.5)**
    *   **Component:** `agentvault-cli`
    *   **Type:** cli_command_enhancement
    *   **Goal:** Warn users before running unknown agents for the first time.
    *   **Details:** (Deferred slightly) Modify `run` command. Implement simple storage for known agent IDs. Check ID before running. If unknown, display warning about trust and require confirmation (`click.confirm` or `--yes` flag). Add ID to known list upon confirmation.
    *   **Files:** `agentvault_cli/src/agentvault_cli/commands/run.py`

**Section: Ethical Considerations & Registry Governance**

*   **REQ-ETHICS-REG-001: Create Registry Policy Document**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Define the scope, rules, and vetting level of the registry.
    *   **Details:** Create `REGISTRY_POLICY.md`. Define purpose (discovery only), submission rules, vetting process (minimal/automated), content guidelines (summary), reporting mechanism for problematic cards, and enforcement actions (deactivation). Include disclaimers.
    *   **Files:** `REGISTRY_POLICY.md`

**Section: Community & Contribution**

*   **REQ-COMMUNITY-COC-001: Create Code of Conduct**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Foster a positive and inclusive community environment.
    *   **Details:** Create `CODE_OF_CONDUCT.md`. Adopt standard text (e.g., Contributor Covenant v2.1). Fill in project name and reporting contact email.
    *   **Files:** `CODE_OF_CONDUCT.md`

*   **REQ-COMMUNITY-CONTRIB-001: Enhance Contribution Guidelines**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Provide clear instructions for contributors.
    *   **Details:** Update `CONTRIBUTING.md`. Link to `CODE_OF_CONDUCT.md`. Briefly mention current governance model. Refine sections on setup, PR process, coding style, and dependency management.
    *   **Files:** `CONTRIBUTING.md`

**Section: Legal & Compliance**

*   **REQ-LEGAL-LIC-DEPS-001: Document Dependency License Check (Internal/README)**
    *   **Component:** Documentation (Project Root / Internal)
    *   **Type:** documentation
    *   **Goal:** Ensure license compatibility of dependencies.
    *   **Details:** Perform license review using tools/manual checks. Add statement to root `README.md` confirming compatibility review. Optionally generate and store/track a detailed dependency license list.
    *   **Files:** `README.md`, (Optional) `DEPENDENCY_LICENSES.md`

*   **REQ-LEGAL-REG-TOS-001: Create Registry Terms of Service**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Define legal terms for using the registry API.
    *   **Details:** Create `TERMS_OF_SERVICE.md`. Include sections on service definition, developer accounts/keys, submissions, prohibited use, **disclaimers (especially regarding third-party agents)**, IP, termination, liability limits, governing law, changes, contact. **Requires legal review.**
    *   **Files:** `TERMS_OF_SERVICE.md`

*   **REQ-LEGAL-REG-PP-001: Create Registry Privacy Policy**
    *   **Component:** Documentation (Project Root)
    *   **Type:** documentation
    *   **Goal:** Inform users how data is handled by the registry API.
    *   **Details:** Create `PRIVACY_POLICY.md`. Include sections on data controller, information collected (developer info, logs), usage, sharing, security, retention, user rights (GDPR), international transfers, children's privacy, policy updates, contact. **Requires legal review.**
    *   **Files:** `PRIVACY_POLICY.md`

**Section: Operational Aspects (Registry)**

*   **REQ-OPS-MONITOR-001: Document Monitoring & Alerting Strategy**
    *   **Component:** Documentation (`agentvault_registry/README.md`)
    *   **Type:** documentation
    *   **Goal:** Guide deployers on monitoring the registry service.
    *   **Details:** Add section to registry README recommending uptime checks (`/health`), centralized logging, and alerting based on errors/downtime. Emphasize deployer responsibility.
    *   **Files:** `agentvault_registry/README.md`

*   **REQ-OPS-BACKUP-001: Document Backup & Recovery Strategy**
    *   **Component:** Documentation (`agentvault_registry/README.md`)
    *   **Type:** documentation
    *   **Goal:** Guide deployers on backing up registry data.
    *   **Details:** Add section to registry README recommending regular, automated database backups (managed service features or `pg_dump`), secure off-site storage, and periodic restore testing. Emphasize deployer responsibility.
    *   **Files:** `agentvault_registry/README.md`

**Section: Technical Refinements (Library & Protocols)**

*   **REQ-TECH-A2AVERSION-001: Document A2A Protocol Versioning Approach**
    *   **Component:** Documentation (`agentvault_library/README.md`), Code Comments
    *   **Type:** documentation
    *   **Goal:** Clarify current protocol scope and future plans.
    *   **Details:** Add notes to library README and comments in `client.py`/`models/a2a_protocol.py` stating the baseline version used and the need for future handling of different versions based on `AgentCard.capabilities.a2aVersion`.
    *   **Files:** `agentvault_library/README.md`, `agentvault_library/src/agentvault/client.py`, `agentvault_library/src/agentvault/models/a2a_protocol.py`

*   **REQ-TECH-MCP-001: Document MCP Implementation Status & Future**
    *   **Component:** Documentation (`agentvault_library/README.md`), Code Comments
    *   **Type:** documentation
    *   **Goal:** Clarify current MCP handling and future plans.
    *   **Details:** Add notes to library README and comments in `mcp_utils.py`/`client.py` explaining the current basic metadata embedding and the plan to align with the finalized MCP specification later.
    *   **Files:** `agentvault_library/README.md`, `agentvault_library/src/agentvault/mcp_utils.py`, `agentvault_library/src/agentvault/client.py`

*   **REQ-TECH-CLIENTCONFIG-001: Document Client Configuration as Future Enhancement**
    *   **Component:** Documentation (`agentvault_library/README.md`, `agentvault_cli/README.md`)
    *   **Type:** documentation
    *   **Goal:** Note potential future client configuration options.
    *   **Details:** Add notes to library and CLI READMEs mentioning the possibility of a future user configuration file (`config.toml`) for defaults (registry URL, timeouts).
    *   **Files:** `agentvault_library/README.md`, `agentvault_cli/README.md`

---

This list covers all the additions we discussed and implemented or planned for documentation. Ready to proceed with **REQ-LIB-A2ACLIENT-002: Implement `initiate_task` Method**?



Current Implementation Status (Phase 1.1 Additions):

Based on our recent steps and your commits, we have successfully implemented the following requirements from the "Phase 1 Additions" list:

    REQ-SEC-DISC-001: SECURITY.md created.

    REQ-SEC-DEP-002: CONTRIBUTING.md created/updated with dependency policy.

    REQ-REG-SEC-001: Rate limiting added to registry API (slowapi).

    REQ-REG-SEC-002: Search query parameter validation added to registry API.

    REQ-ETHICS-REG-001: REGISTRY_POLICY.md created.

    REQ-COMMUNITY-COC-001: CODE_OF_CONDUCT.md created.

    REQ-COMMUNITY-CONTRIB-001: CONTRIBUTING.md enhanced (linking CoC).

    REQ-LEGAL-REG-TOS-001: TERMS_OF_SERVICE.md created (draft).

    REQ-LEGAL-REG-PP-001: PRIVACY_POLICY.md created (draft).

    REQ-DOC-LINK-001: Root README.md updated with links to new policy files.

    REQ-OPS-MONITOR-001: Monitoring strategy documented in registry README.md.

    REQ-OPS-BACKUP-001: Backup strategy documented in registry README.md.

    REQ-TECH-A2AVERSION-001: A2A versioning documented in library README.md and code comments.

    REQ-TECH-MCP-001: MCP status documented in library README.md and code comments.

    REQ-TECH-CLIENTCONFIG-001: Client config documented as future enhancement in library and CLI README.md.