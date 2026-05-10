# AGENTS.md — AI Agent Integration Guide

This document describes how AI agents (Claude Code, Cursor, Aider, etc.) should interact with the ai-commit project.

## Project Overview

ai-commit is a Git `prepare-commit-msg` hook that generates Conventional Commits messages using an OpenAI-compatible API. It reads the staged diff, filters ignored files, abbreviates large diffs, and calls the AI API to produce a commit message.

**Zero external dependencies** — the entire core logic is a single Python file using only standard library modules.

## Architecture

### Core Script: `ai_commit_gen.py`

Single-file core logic. Dependencies: Python 3.9+ standard library only.

**Flow**:
1. `main()` receives `commit_msg_file` and `commit_source` from Git (via pre-commit or direct hook)
2. `load_config()` reads config from env vars > project `.ai-commit.json` > global `~/.ai-commit.json`
3. `get_staged_diff()` fetches `git diff --cached`
4. `read_ignore_patterns()` + `filter_diff_by_ignore()` exclude files per `.opencommitignore`
5. `abbreviate_diff()` truncates large file diffs beyond threshold
6. `call_ai_api()` sends diff + file summary to OpenAI-compatible chat completions endpoint (via `urllib.request`)
7. The generated message is written to `commit_msg_file` (replacing or appending depending on `commit_source`)

### Key Functions

| Function | Purpose |
|---|---|
| `load_config()` | Reads config with priority: env > project > global |
| `read_ignore_patterns()` | Parses `.opencommitignore` file |
| `is_ignored()` | Checks if a file matches ignore patterns (using `fnmatch`) |
| `get_staged_diff()` | Gets `git diff --cached` output |
| `abbreviate_diff()` | Truncates large diffs with summary |
| `filter_diff_by_ignore()` | Removes ignored files from diff |
| `build_file_summary()` | Creates `+N/-N` summary per file |
| `call_ai_api()` | Sends request to OpenAI-compatible API |
| `generate_commit_message()` | Orchestrates the full pipeline |
| `main()` | Entry point: handles commit_source logic, writes message |

### pre-commit Framework Integration

`.pre-commit-hooks.yaml` defines the hook:
- `stages: [prepare-commit-msg]` — Only runs at the prepare-commit-msg stage
- `language: python` — pre-commit manages virtual environment automatically
- `always_run: true` — Runs even with no matching files
- `pass_filenames: false` — Hook receives Git args, not file list

## Key Design Decisions

1. **Single-file core** — `ai_commit_gen.py` is self-contained for easy distribution
2. **Zero pip dependencies** — `urllib.request` + `json` replace `curl` + `jq`
3. **Graceful degradation** — `return 0` on failure; commit never blocked by AI
4. **fnmatch for ignore** — Uses Python's `fnmatch` instead of bash globbing
5. **Conventional Commits only** — System prompt enforces the spec strictly
6. **Commit source awareness** — Skips merge/squash/amend, appends for `-m`
7. **Native Windows support** — No bash/WSL dependency

## Modifying the Code

### Adding a New Config Option

1. Add the key + default to `DEFAULTS` dict
2. Add the key → env var mapping to `ENV_MAP` dict
3. Add type coercion logic to `_coerce_type()` if needed
4. Use `cfg_get(key)` to read the value anywhere

### Changing the Prompt

Edit the `SYSTEM_PROMPT` constant at module level. The prompt must instruct the model to output ONLY the commit message.

### Adding a New Language

Add a mapping to the `LANG_INSTRUCTIONS` dict.

## Testing

### Direct Test (no pre-commit)

```bash
python ai_commit_gen.py .git/COMMIT_EDITMSG
```

### Test with pre-commit Framework

```bash
pip install pre-commit
pre-commit install --hook-type prepare-commit-msg
echo "test" > test.txt && git add test.txt
git commit -m "test: trigger"
```

### Test debug mode

```bash
AI_COMMIT_DEBUG=true git commit
```

### Test ignore file

Create `.opencommitignore`:
```
*.md
*.lock
```

## Common Issues

- **Hook not firing**: `pre-commit install --hook-type prepare-commit-msg`
- **API errors**: Enable debug mode (`AI_COMMIT_DEBUG=true`)
- **Python not found**: Ensure Python 3.9+ is in PATH
- **Windows + pre-commit**: Use `pre-commit run --hook-stage prepare-commit-msg` to test
