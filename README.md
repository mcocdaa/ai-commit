# ai-commit

AI-powered Git commit message generator hook. Generates [Conventional Commits](https://www.conventionalcommits.org/) messages using any OpenAI-compatible API.

**Zero external dependencies** — uses only Python standard library (`json`, `urllib`, `subprocess`, `fnmatch`).

## Features

- Generates Conventional Commits format messages from your staged diff
- Works with any OpenAI-compatible API (DeepSeek, OpenAI, etc.)
- **Zero external dependencies** — pure Python standard library
- Respects `.opencommitignore` for excluding files from diff analysis
- Abbreviates large diffs (configurable threshold, default 1000 lines)
- Multi-language support (en, zh, zh-TW, ja, ko)
- Graceful degradation: if AI fails, your commit still proceeds
- `git commit` → AI generates the full message
- `git commit -m "aaa"` → AI appends details after your message "aaa"
- Native Windows support (no WSL required)
- Debug mode with full pipeline visibility (`verbose: true` in pre-commit config)

## Quick Start

### Via pre-commit Framework (Recommended)

1. Install [pre-commit](https://pre-commit.com/): `pip install pre-commit`
2. Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/mcocdaa/ai-commit.git
    rev: v1.0.0
    hooks:
      - id: ai-commit
```

3. Install the hook:

```bash
pre-commit install --hook-type prepare-commit-msg
```

### Local / Testing

For local development or testing without a published repo:

```yaml
repos:
  - repo: /path/to/ai-commit
    hooks:
      - id: ai-commit
```

Or use `repo: .` if the hook files are in your project root.

## Configuration

Create `.ai-commit.json` in your project root (or `~/.ai-commit.json` for global):

```json
{
  "api_key": "",
  "api_base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-flash",
  "max_diff_lines": 1000,
  "max_input_tokens": 4096,
  "max_output_tokens": 500,
  "debug": false,
  "language": "en",
  "ignore_file": ".opencommitignore"
}
```

### Config Priority

Environment variables > project `.ai-commit.json` > global `~/.ai-commit.json`

| Config Key | Env Variable | Default |
|---|---|---|
| `api_key` | `AI_COMMIT_API_KEY` | `""` |
| `api_base_url` | `AI_COMMIT_API_BASE_URL` | `https://api.deepseek.com` |
| `model` | `AI_COMMIT_MODEL` | `deepseek-v4-flash` |
| `max_diff_lines` | `AI_COMMIT_MAX_DIFF_LINES` | `1000` |
| `max_input_tokens` | `AI_COMMIT_MAX_INPUT_TOKENS` | `4096` |
| `max_output_tokens` | `AI_COMMIT_MAX_OUTPUT_TOKENS` | `500` |
| `debug` | `AI_COMMIT_DEBUG` | `false` |
| `language` | `AI_COMMIT_LANGUAGE` | `en` |
| `ignore_file` | `AI_COMMIT_IGNORE_FILE` | `.opencommitignore` |

### API Key Security

- **Recommended**: Set `AI_COMMIT_API_KEY` environment variable
- **Per-project**: Use `.ai-commit.json` (auto-added to `.gitignore`)
- **Global**: Use `~/.ai-commit.json` with restricted permissions
- **Never** commit API keys to version control

### .opencommitignore

Exclude files from diff analysis:

```
*.md
package-lock.json
dist/
```

### Debug Mode

Set `debug: true` in `.ai-commit.json` or `AI_COMMIT_DEBUG=true` env var. To see debug output during `git commit`, add `verbose: true` to the hook config:

```yaml
repos:
  - repo: https://github.com/mcocdaa/ai-commit.git
    rev: v1.0.0
    hooks:
      - id: ai-commit
        verbose: true
```

## Dependencies

- **Python 3.9+** — No pip packages required
- **Git** — Obviously

## File Structure

```
ai-commit/
├── prepare_commit_msg_hooks/
│   ├── __init__.py
│   ├── ai_commit_gen.py       # Entry point & orchestration
│   └── util/
│       ├── __init__.py
│       ├── api.py             # OpenAI-compatible API client
│       ├── config.py          # Configuration & constants
│       ├── diff_processor.py  # Diff filtering & abbreviation
│       ├── git_util.py        # Git subprocess wrappers
│       └── gitignore.py       # fnmatch-based ignore patterns
├── .pre-commit-hooks.yaml     # pre-commit framework hook definition
├── setup.cfg                  # Package metadata & entry points
├── setup.py                   # Editable install stub
├── tests/
│   └── test_ai_commit_gen.py  # Pytest test suite (22 tests)
├── README.md                  # This file
├── AGENTS.md                  # AI agent integration guide
├── LICENSE                    # MIT License
└── .ai-commit.json            # Configuration (gitignored)
```

## How It Works

1. The `prepare-commit-msg` hook is triggered by Git before the editor opens
2. The script reads staged diff via `git diff --cached`
3. Files matching `.opencommitignore` patterns are excluded
4. Large diffs (per `max_diff_lines`) are abbreviated
5. The diff + file summary is sent to the OpenAI-compatible chat completions API
6. The generated commit message is written to the commit message file
7. If `git commit -m "..."` was used, AI appends after your message
8. If AI fails for any reason, the commit proceeds normally

## License

MIT
