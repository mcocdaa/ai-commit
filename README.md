<div align="center">

# ai-commit

Zero-dependency Git prepare-commit-msg hook for Conventional Commits via any OpenAI-compatible API.

[![CI](https://github.com/mcocdaa/ai-commit/actions/workflows/ci.yml/badge.svg)](https://github.com/mcocdaa/ai-commit/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/mcocdaa/ai-commit?color=blue&label=latest%20release)](https://github.com/mcocdaa/ai-commit/releases/latest)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits)](https://conventionalcommits.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](README.md) · [简体中文](README_CN.md)

<img src="docs/assets/demo_commit.gif" alt="ai-commit demo" width="840">

</div>

## ✨ Highlights

- **Zero Third-Party Dependencies** — Powered strictly by the Python 3.9+ standard library (`json`, `urllib`, `subprocess`, `fnmatch`) with no external `pip` packages required.
- **Seamless `prepare-commit-msg` Workflow** — Generates full [Conventional Commits](https://www.conventionalcommits.org/) messages on `git commit`, or appends structured details when you run `git commit -m "summary"`.
- **Smart Diff Compression & `.opencommitignore` Filtering** — Automatically excludes lockfiles, minified bundles, and custom `.opencommitignore` patterns while truncating oversized diffs to stay within token budgets.
- **Universal OpenAI-Compatible Support** — Works out of the box with DeepSeek, OpenAI, Ollama, vLLM, and any `/v1/chat/completions` endpoint.
- **Multi-Language Output** — Supports commit generation in English (`en`), Simplified/Traditional Chinese (`zh`, `zh-TW`), Japanese (`ja`), and Korean (`ko`).
- **Graceful Fallback** — Never blocks your Git workflow; if the network or API fails, your commit proceeds normally.

## 🚀 Quick Start

### 1. Configure `pre-commit`

Add `ai-commit` to your `.pre-commit-config.yaml` and install the `prepare-commit-msg` hook:

```yaml
repos:
  - repo: https://github.com/mcocdaa/ai-commit.git
    rev: v1.0.0  # Run `pre-commit autoupdate` for the latest release
    hooks:
      - id: ai-commit
```

```bash
pip install pre-commit
pre-commit install --hook-type prepare-commit-msg
```

### 2. Set Your API Key & Commit

```bash
export AI_COMMIT_API_KEY="sk-..."
git add -A && git commit
```

## ⚙️ Configuration

Configure via environment variables, project `.ai-commit.json`, or global `~/.ai-commit.json` (precedence: `ENV` > `./.ai-commit.json` > `~/.ai-commit.json`):

| Environment Variable | `.ai-commit.json` Key | Default | Description |
| :--- | :--- | :--- | :--- |
| `AI_COMMIT_API_KEY` | `api_key` | `""` | API key for the OpenAI-compatible provider |
| `AI_COMMIT_API_BASE_URL` | `api_base_url` | `https://api.deepseek.com` | Base URL for chat completions API |
| `AI_COMMIT_MODEL` | `model` | `deepseek-v4-flash` | Model identifier used for generation |
| `AI_COMMIT_LANGUAGE` | `language` | `en` | Output language (`en`, `zh`, `zh-TW`, `ja`, `ko`) |
| `AI_COMMIT_MAX_DIFF_LINES` | `max_diff_lines` | `1000` | Max diff lines per file before abbreviation |
| `AI_COMMIT_MAX_OUTPUT_TOKENS` | `max_output_tokens` | `2048` | Max tokens for generated response |
| `AI_COMMIT_IGNORE_FILE` | `ignore_file` | `.opencommitignore` | Ignore file for excluding paths from diff analysis |
| `AI_COMMIT_THINKING` | `thinking` | `false` | Enable/disable reasoning mode on DeepSeek models |
| `AI_COMMIT_DEBUG` | `debug` | `false` | Print diagnostic pipeline logs to `stderr` |

<details>
<summary><b>Advanced Configuration & Troubleshooting</b></summary>

### Example `.ai-commit.json`

```json
{
  "api_base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-flash",
  "max_diff_lines": 1000,
  "language": "en",
  "ignore_file": ".opencommitignore",
  "thinking": false
}
```

### Custom Ignore Rules (`.opencommitignore`)

Lockfiles (`uv.lock`, `package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`) and `*.min.js` / `*.min.css` are ignored by default. Add custom `.gitignore`-style patterns in `.opencommitignore`:

```gitignore
*.md
dist/
fixtures/*.json
```

### Debugging & Pre-Commit Hook Stages

- **Verbose Hook Output**: Set `AI_COMMIT_DEBUG=true` and add `verbose: true` under `- id: ai-commit` in `.pre-commit-config.yaml` to inspect diff filtering and API payloads.
- **Avoid Duplicate Hook Runs**: If you use both `pre-commit` and `prepare-commit-msg` hooks, add `default_stages: [pre-commit]` at the top of `.pre-commit-config.yaml`.

</details>

## 📄 License

Released under the [MIT License](LICENSE).
