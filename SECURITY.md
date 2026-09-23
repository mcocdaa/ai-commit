# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## API Key Security

`ai-commit` interacts with external AI APIs using API keys:
- **Never commit your API keys** to Git repositories.
- Use the `AI_COMMIT_API_KEY` environment variable or global `~/.ai-commit.json` configuration file.
- Project-level `.ai-commit.json` files are automatically included in `.gitignore` to prevent accidental commits.

## Reporting a Vulnerability

If you discover a potential security vulnerability in `ai-commit`:
1. Please do **not** disclose it publicly via GitHub issues.
2. Open a private security advisory on GitHub or contact the maintainers directly.
3. Include detailed steps to reproduce the issue.
