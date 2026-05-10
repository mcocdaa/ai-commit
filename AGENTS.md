# AGENTS.md — AI Agent Integration Guide

This document describes how AI agents (Claude Code, Cursor, Aider, etc.) should interact with the ai-commit project.

## Project Overview

ai-commit is a Git `prepare-commit-msg` hook that generates Conventional Commits messages using an OpenAI-compatible API. It reads the staged diff, filters ignored files, abbreviates large diffs, and calls the AI API to produce a commit message.

**Zero external dependencies** — uses only Python standard library (`json`, `urllib`, `subprocess`, `fnmatch`).

## Architecture

### Package Structure

```
prepare_commit_msg_hooks/
├── __init__.py
├── ai_commit_gen.py          # Entry point & orchestration
└── util/
    ├── __init__.py
    ├── api.py                # OpenAI-compatible API client
    ├── config.py             # Configuration loading & constants
    ├── diff_processor.py     # Diff filtering & abbreviation
    ├── git_util.py           # Git subprocess wrappers
    └── gitignore.py          # fnmatch-based ignore pattern matching
```

### Core Script: `ai_commit_gen.py`

Orchestrates the full pipeline. Dependencies: Python 3.9+ standard library only.

**Flow**:
1. `main()` receives `commit_msg_file` and `commit_source` from Git (via pre-commit or direct hook)
2. `config.load_config()` reads config: env vars > project `.ai-commit.json` > global `~/.ai-commit.json`
3. `git_util.get_staged_diff()` fetches `git diff --cached`
4. `config.read_ignore_patterns()` + `diff_processor.filter_diff_by_ignore()` exclude files per `.opencommitignore`
5. `diff_processor.abbreviate_diff()` truncates large file diffs beyond threshold
6. `api.call_ai_api()` sends diff + file summary to OpenAI-compatible chat completions endpoint
7. The generated message is written to `commit_msg_file` (replacing or appending depending on `commit_source`)

### Key Functions

| Module | Function | Purpose |
|---|---|---|
| `util/config.py` | `load_config()` | Reads config with priority: env > project > global |
| `util/config.py` | `read_ignore_patterns()` | Parses `.opencommitignore` file |
| `util/config.py` | `cfg_get(key)` | Returns config value with default fallback |
| `util/git_util.py` | `get_staged_diff()` | Gets `git diff --cached` output |
| `util/git_util.py` | `get_staged_file_stats()` | Gets `+N/-N` line change stats per staged file |
| `util/git_util.py` | `get_branch_name()` | Gets current Git branch name |
| `util/git_util.py` | `find_commit_msg_file()` | Auto-detects `.git/COMMIT_EDITMSG` path |
| `util/git_util.py` | `detect_commit_source()` | Infers commit source from existing message |
| `util/gitignore.py` | `compile_patterns()` | Compiles ignore patterns into a spec |
| `util/gitignore.py` | `is_ignored()` | Checks if a file matches ignore patterns (using `fnmatch`) |
| `util/diff_processor.py` | `filter_diff_by_ignore()` | Removes ignored files from diff |
| `util/diff_processor.py` | `abbreviate_diff()` | Truncates large diffs with summary |
| `util/diff_processor.py` | `build_file_summary()` | Creates `+N/-N` summary per file |
| `util/api.py` | `call_ai_api()` | Sends request to OpenAI-compatible API |
| `ai_commit_gen.py` | `generate_commit_message()` | Orchestrates the full pipeline |
| `ai_commit_gen.py` | `main()` | Entry point: handles commit_source logic, writes message |

### pre-commit Framework Integration

`.pre-commit-hooks.yaml` defines the hook:
- `entry: ai-commit-gen` — Console script installed via `setup.cfg`
- `language: python` — pre-commit manages virtual environment automatically
- `stages: [prepare-commit-msg]` — Only runs at the prepare-commit-msg stage
- `always_run: true` — Runs even with no matching files
- `pass_filenames: false` — Hook receives Git args, not file list

### Debug Output Visibility

pre-commit swallows both stdout and stderr from "Passed" hooks by default. To see debug output during `git commit`, add `verbose: true` to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/mcocdaa/ai-commit.git
    rev: v1.0.0
    hooks:
      - id: ai-commit
        verbose: true
```

Debug log chain: Config → Raw Diff → Ignore Patterns → Filtered Diff → Processed Diff → System Prompt → User Prompt → API Request → API Response → Final Result

### Thinking Mode Control (DeepSeek)

The `thinking` config option controls DeepSeek's reasoning/thinking mode. `true` enables reasoning (model outputs intermediate thinking + final answer), `false` disables it for direct output. The hook sends `{"thinking": {"type": "enabled/disabled"}}` in the API request body accordingly.

## Key Design Decisions

1. **Zero pip dependencies** — `urllib.request` + `json` replace `curl` + `jq`; `subprocess` + `fnmatch` replace bash
2. **Modular package** — Core logic split into `util/` subpackage for maintainability
3. **Graceful degradation** — `return 0` on failure; commit never blocked by AI
4. **fnmatch for ignore** — Uses Python's `fnmatch` instead of bash globbing for cross-platform compatibility
5. **Conventional Commits only** — System prompt enforces the spec strictly
6. **Commit source awareness** — Skips merge/squash/amend, appends for `-m`
7. **Native Windows support** — All subprocess calls use explicit `encoding='utf-8'` to avoid GBK decode errors
8. **Written for AI agents** — Structured to be easily understood and modified by AI coding assistants
9. **Thinking mode control** — DeepSeek reasoning toggle via `thinking: true/false` config, sent as `{"thinking": {"type": "enabled/disabled"}}` in API body

## Modifying the Code

### Adding a New Config Option

1. Add the key + default to `DEFAULTS` dict in `util/config.py`
2. Add the key → env var mapping to `ENV_MAP` dict
3. Add type coercion logic to `_coerce_type()` if needed
4. Use `cfg_get(key)` to read the value anywhere

### Changing the Prompt

Edit the `SYSTEM_PROMPT` constant in `util/config.py`. The prompt must instruct the model to output ONLY the commit message.

### Adding a New Language

Add a mapping to the `LANG_INSTRUCTIONS` dict in `util/config.py`.

### Updating Version

Bump `__version__` in `util/config.py` and `version` in `setup.cfg`.

## Testing

### Run Pytest Suite

```bash
cd test_git
python -m pytest tests/ -v
```

### Direct Test (no pre-commit)

```bash
python -m prepare_commit_msg_hooks.ai_commit_gen .git/COMMIT_EDITMSG
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

Requires `verbose: true` in `.pre-commit-config.yaml` to see debug output.

### Test ignore file

Create `.opencommitignore`:
```
*.md
*.lock
```

## Common Issues

- **Hook not firing**: `pre-commit install --hook-type prepare-commit-msg`
- **API errors**: Enable debug mode (`AI_COMMIT_DEBUG=true`) + `verbose: true` in pre-commit config
- **UnicodeDecodeError on Windows**: All subprocess calls in `util/git_util.py` use explicit `encoding='utf-8'`
- **Python not found**: Ensure Python 3.9+ is in PATH
- **Debug output not visible**: Add `verbose: true` to hook config in `.pre-commit-config.yaml`
- **Empty AI response with DeepSeek**: Set `thinking: false` to disable reasoning mode, or increase `max_output_tokens` to 2048+
- **Windows + pre-commit**: Use `pre-commit run --hook-stage prepare-commit-msg` to test
