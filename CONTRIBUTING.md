# Contributing to AgentVault

First off, thank you for considering contributing to AgentVault! We welcome contributions from the community to help make this project better.

## How Can I Contribute?

*   **Reporting Bugs:** If you find a bug, please open an issue on our GitHub repository, providing as much detail as possible (component, steps to reproduce, expected vs. actual behavior, environment details).
*   **Suggesting Enhancements:** Open an issue to discuss new features or improvements. Please provide context and rationale for your suggestion.
*   **Pull Requests:** If you'd like to contribute code or documentation fixes/improvements, please follow the process below.

## Development Setup

Please refer to the main project `README.md` and the README files within each component directory (`agentvault_library/`, `agentvault_registry/`, `agentvault_cli/`) for specific setup instructions. Generally, you will need:

1.  Python >= 3.10, < 3.12
2.  Poetry
3.  Git
4.  Access to a PostgreSQL database (for `agentvault-registry` development)

Install dependencies for all components using Poetry from the project root:
```bash
# Ensure Poetry is configured for in-project virtual environments (optional but recommended)
# poetry config virtualenvs.in-project true

# Install for all components
cd agentvault_library && poetry install --sync --with dev --all-extras && cd ..
cd agentvault_registry && poetry install --sync --with dev && cd ..
cd agentvault_cli && poetry install --sync --with dev && cd ..

# Activate the environment (example for bash/zsh)
# source .venv/bin/activate
```

## Pull Request Process

1.  **Fork the Repository:** Create your own fork of the main AgentVault repository on GitHub.
2.  **Create a Branch:** Create a new branch in your fork for your feature or bug fix (e.g., `git checkout -b feature/my-new-feature` or `git checkout -b fix/issue-123`).
3.  **Make Changes:** Implement your changes, adhering to the coding style (see below).
4.  **Add Tests:** Ensure you add relevant unit or integration tests for any new code or bug fixes. Maintain or improve test coverage.
5.  **Run Tests:** Ensure all tests pass locally (`pytest` in the relevant component directory or project root).
6.  **Linting/Formatting:** Ensure your code conforms to the project's style guidelines (e.g., run `ruff format .` and `ruff check .` from the project root).
7.  **Commit Changes:** Commit your changes with clear and concise commit messages. Reference the relevant issue number if applicable (e.g., `feat: Implement feature X (closes #123)`).
8.  **Push to Your Fork:** Push your branch to your fork on GitHub (`git push origin feature/my-new-feature`).
9.  **Submit a Pull Request:** Open a Pull Request from your branch to the `main` branch of the official AgentVault repository. Provide a clear description of your changes in the PR.

## Coding Style

*   We aim to follow standard Python best practices (PEP 8).
*   We use `ruff` for linting and formatting. Please run `ruff format .` and `ruff check . --fix` before submitting a PR. Configuration is in `pyproject.toml` (or will be added).
*   Use clear variable and function names.
*   Add docstrings to new modules, classes, and functions.
*   Add type hints to your code.

## Dependency Management & Security

*   **Adding Dependencies:** If your contribution requires adding new dependencies, please discuss this in the relevant issue or PR first. Add the dependency using `poetry add <package>` within the appropriate component directory (`agentvault_library`, `agentvault_registry`, `agentvault_cli`).
*   **Security Scanning:** We use automated tools (like `pip-audit` and/or GitHub Dependabot) to scan for known vulnerabilities in our dependencies (See REQ-SEC-DEP-001).
*   **Updating Dependencies:**
    *   Pull requests should generally include updates to dependencies if newer, compatible versions are available, especially if they address security vulnerabilities. Run `poetry update` within the relevant component directory.
    *   If a vulnerability is found in a dependency by our scanning tools:
        *   We prioritize fixing High/Critical severity issues promptly.
        *   We will attempt to update to a non-vulnerable version.
        *   If a direct update is not possible (e.g., due to breaking changes), we will assess the risk and potentially pin the dependency while seeking alternatives or contributing fixes upstream.
        *   Contributors are encouraged to help identify and test updates for vulnerable dependencies.

## Code of Conduct

Please note that this project is released with a Contributor Code of Conduct. By participating in this project you agree to abide by its terms. (Link to `CODE_OF_CONDUCT.md` - *to be created*)

---
Thank you for contributing!
