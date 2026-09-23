# Contributing to ai-commit

Thank you for your interest in contributing to `ai-commit`!

## Principles

1. **Zero External Dependencies**: The runtime code must only use Python standard library modules (`json`, `urllib`, `subprocess`, `re`, etc.). No pip dependencies allowed in runtime.
2. **Conventional Commits**: All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.
3. **Cross-Platform Compatibility**: Code must work smoothly on Linux, macOS, and Windows (with explicit UTF-8 encoding handling).
4. **Python Compatibility**: Must support Python 3.9 through Python 3.13+.

## Development Workflow

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/mcocdaa/ai-commit.git
   cd ai-commit
   ```

2. Set up a virtual environment and install test dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   pip install pytest ruff
   ```

3. Run tests and linter:
   ```bash
   pytest tests/ -v
   ruff check .
   ```

4. Format code and ensure tests pass before submitting a Pull Request.
