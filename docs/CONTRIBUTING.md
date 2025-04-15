# Contributing to AgentVault

First off, thank you for considering contributing to AgentVault! It's people like you that make open source great. Your contributions help build a robust and interoperable ecosystem for AI agents.

Please take a moment to review this document in order to make the contribution process easy and effective for everyone involved.

## Getting Started

1.  **Fork the Repository:** Start by forking the main [AgentVault repository](https://github.com/SecureAgentTools/AgentVault) on GitHub.
2.  **Clone Your Fork:** Clone your forked repository to your local machine.
    ```bash
    git clone https://github.com/YOUR-USERNAME/AgentVault.git
    cd AgentVault
    ```
3.  **Install Prerequisites:** Ensure you have [Git](https://git-scm.com/) and a compatible Python version (3.10 or 3.11) installed.
4.  **Install Poetry:** If you don't have Poetry installed, follow the instructions on the [official Poetry website](https://python-poetry.org/docs/#installation). Poetry is used for dependency management and packaging across the monorepo.
5.  **Set up Virtual Environment & Install Dependencies:** Navigate to the project root (`AgentVault/`) and run:
    ```bash
    poetry install --with dev
    ```
    This command performs several crucial steps:
    *   Reads the `pyproject.toml` files within each component package (`agentvault_library`, `agentvault_cli`, etc.).
    *   Resolves all dependencies across the entire workspace, ensuring compatibility.
    *   Creates a single virtual environment (usually `.venv/` in the project root) for the whole project.
    *   Installs all production *and* development dependencies (like `pytest`, `httpx`, `mkdocs`, `ruff`) into this shared virtual environment.
6.  **Activate Virtual Environment:** Before running any commands, tests, or development servers, activate the virtual environment:
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
    Your command prompt should now indicate you are inside the `(.venv)` environment.

## Development Workflow

1.  **Find/Create an Issue:** Look for existing issues or create a new one on GitHub to discuss the bug or feature you want to work on. This helps coordinate efforts.
2.  **Branching:** Create a descriptive feature branch off the `main` branch:
    ```bash
    git checkout main
    git pull origin main # Ensure your main is up-to-date
    git checkout -b feat/my-new-feature # Or fix/resolve-issue-123
    ```
3.  **Coding:**
    *   Make your changes within the relevant component directory (e.g., `agentvault_library/src/agentvault/`, `agentvault_cli/src/agentvault_cli/`).
    *   Follow existing code style and patterns. We aim for clean, readable, and type-hinted Python code.
    *   Ensure new functions, classes, and modules have appropriate docstrings.
4.  **Testing:**
    *   **Write Tests:** Add new unit or integration tests for your changes within the corresponding component's `tests/` directory.
    *   **Run Tests:** Navigate to the component's directory (e.g., `cd agentvault_library`) and run `pytest`. Ensure all tests pass, including your new ones.
    *   **Run All Tests (Optional):** From the project root, you can run `pytest` to execute tests for all components (ensure `pytest.ini` at the root is configured correctly).
5.  **Linting & Formatting:** (Tooling setup TBD - e.g., Black, Ruff) Run the project's code formatter and linter to ensure consistency.
6.  **Documentation:** If your changes affect user-facing behavior, APIs, or architecture, update the relevant documentation pages in the `/docs` directory. Build the docs locally (`mkdocs serve` from the root) to preview your changes.
7.  **Committing:** Write clear, concise commit messages using conventional commit style (e.g., `feat(sdk): Add helper for SSE events`, `fix(cli): Correct handling of --output-artifacts`, `docs(library): Improve KeyManager examples`). Reference the relevant GitHub issue number (e.g., `feat(registry): Implement tag filtering (#42)`).
8.  **Pull Request:**
    *   Push your feature branch to your fork: `git push origin feat/my-new-feature`
    *   Go to the main AgentVault repository on GitHub and open a Pull Request (PR) from your branch to the `main` branch.
    *   Provide a clear title and description for your PR, explaining the changes and linking to the relevant issue(s).
    *   Ensure all automated checks (CI workflows like tests and dependency audits) pass on your PR. Address any failures.
    *   Engage in the code review process if feedback is provided.

## Code Style

*(Placeholder: This section will be updated once specific tools like Black/Ruff are enforced via pre-commit hooks or CI.)*

Generally, adhere to PEP 8 guidelines and follow the style of the existing codebase. Use type hints extensively.

## Testing

*   **Unit Tests:** Focus on testing individual functions and classes in isolation. Place these in the relevant component's `tests/` directory (e.g., `agentvault_library/tests/library/`).
*   **Integration Tests:** Test the interaction between different parts of a component or between components (e.g., CLI using the Library against a mock server). Place these in appropriate subdirectories within `tests/`.
*   **Coverage:** Aim for high test coverage for new code. *(Coverage reporting setup TBD)*.
*   **Running Tests:** Activate the virtual environment and run `pytest` from the component directory or the project root.

## Dependency Security

This project uses `pip-audit` via a GitHub Actions workflow (`.github/workflows/dependency_audit.yml`) to automatically check for known vulnerabilities in project dependencies based on the `poetry.lock` files.

*   **Workflow:** Triggers on pushes/PRs to `main`. Audits each component separately.
*   **Reviewing Audits:** Check the "Actions" tab on GitHub for the "Security Dependency Audit" results. Failures indicate known vulnerabilities.
*   **Updating Dependencies:** Use `poetry update <package_name>` within a component directory to update specific dependencies, or `poetry update` to update all allowed by `pyproject.toml`. Always re-run `poetry lock` and commit the updated lock file. Re-run tests thoroughly after updates.

## Reporting Issues & Security Vulnerabilities

*   **Bugs & Feature Requests:** Please check existing [GitHub Issues](https://github.com/SecureAgentTools/AgentVault/issues) first. If your issue isn't there, open a new one with detailed information.
*   **Security Vulnerabilities:** **DO NOT** report security issues publicly. Please follow the instructions in our [Security Policy (security_policy.md)](security_policy.md).

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

Thank you for contributing to AgentVault!
