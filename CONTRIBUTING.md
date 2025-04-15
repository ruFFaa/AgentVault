# Contributing to AgentVault

First off, thank you for considering contributing to AgentVault! It's people like you that make open source great.

Please take a moment to review this document in order to make the contribution process easy and effective for everyone involved.

## Getting Started

1.  **Fork the Repository:** Start by forking the main AgentVault repository on GitHub.
2.  **Clone Your Fork:** Clone your forked repository to your local machine.
    ```bash
    git clone https://github.com/YOUR-USERNAME/AgentVault.git
    cd AgentVault
    ```
3.  **Install Poetry:** If you don't have Poetry installed, follow the instructions on the [official Poetry website](https://python-poetry.org/docs/#installation).
4.  **Set up Virtual Environment & Install Dependencies:** Navigate to the project root (`AgentVault/`) and run:
    ```bash
    poetry install --with dev
    ```
    This command will create a virtual environment (usually `.venv/` in the root) and install all production and development dependencies for all components defined in the workspace.
5.  **Activate Virtual Environment:**
    *   PowerShell: `.\.venv\Scripts\Activate.ps1`
    *   Bash/Zsh: `source .venv/bin/activate`
    *   Cmd.exe: `.\.venv\Scripts\activate.bat`

## Development Workflow

*   **Branching:** Create a new branch for your feature or bugfix off the `main` branch (e.g., `git checkout -b feat/add-new-widget` or `git checkout -b fix/resolve-issue-123`).
*   **Coding:** Make your changes within the relevant component directory (e.g., `agentvault_library/`, `agentvault_cli/`). Follow existing code style and patterns.
*   **Testing:** Run tests for the component you modified. Navigate to the component's directory and run `pytest`. To run all tests for the entire project from the root, you might need further configuration or a helper script (TBD).
    ```bash
    cd agentvault_library # Example
    pytest tests/
    ```
*   **Committing:** Write clear and concise commit messages. Reference related issues if applicable (e.g., `feat(registry): Add search by tag (#42)`).
*   **Pull Request:** Push your branch to your fork and open a Pull Request against the main AgentVault repository's `main` branch. Provide a clear description of your changes.

## Code Style

*(Placeholder: Define code style guidelines later - e.g., using Black, Ruff, isort)*

## Testing

*(Placeholder: Add more details about running specific test types or coverage)*

Ensure all relevant tests pass before submitting a pull request. New features should ideally include new tests.

## Dependency Security

This project uses `pip-audit` via a GitHub Actions workflow (`.github/workflows/dependency_audit.yml`) to automatically check for known vulnerabilities in project dependencies.

*   **How it Works:** The workflow triggers on pushes and pull requests to the `main` branch. It installs dependencies based on the `poetry.lock` files across the monorepo (generating a temporary consolidated lock file) and runs `pip-audit`.
*   **Reviewing Audits:** Check the "Actions" tab on GitHub for the results of the "Security Dependency Audit" workflow.
*   **Updating Dependencies:** Periodically, dependencies should be updated to patch vulnerabilities and get new features. This can typically be done using `poetry update` within specific component directories or carefully at the root level. Always re-run tests after updating dependencies.

## Reporting Issues

If you encounter a bug or have a feature request, please check the existing issues on GitHub first. If it hasn't been reported, feel free to open a new issue, providing as much detail as possible.

Thank you for contributing!
