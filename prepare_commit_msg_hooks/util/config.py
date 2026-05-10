"""
Configuration constants and loading for ai-commit-gen.

Configuration is loaded from (in order of precedence, later wins):
1. Default values
2. ~/.ai-commit.json (global)
3. .ai-commit.json (project root)
4. Environment variables
"""

import json
import os
import subprocess
import sys

__version__ = "1.0.0"

DEFAULTS = {
    "api_key": "",
    "api_base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "max_diff_lines": 1000,
    "max_output_tokens": 2048,
    "debug": False,
    "language": "en",
    "ignore_file": ".opencommitignore",
    "thinking": False,
}

ENV_MAP = {
    "api_key": "AI_COMMIT_API_KEY",
    "api_base_url": "AI_COMMIT_API_BASE_URL",
    "model": "AI_COMMIT_MODEL",
    "max_diff_lines": "AI_COMMIT_MAX_DIFF_LINES",
    "max_output_tokens": "AI_COMMIT_MAX_OUTPUT_TOKENS",
    "debug": "AI_COMMIT_DEBUG",
    "language": "AI_COMMIT_LANGUAGE",
    "ignore_file": "AI_COMMIT_IGNORE_FILE",
    "thinking": "AI_COMMIT_THINKING",
}

LANG_INSTRUCTIONS = {
    "zh": "Write the commit message in Chinese (Simplified).",
    "zh-CN": "Write the commit message in Chinese (Simplified).",
    "zh-TW": "Write the commit message in Traditional Chinese.",
    "ja": "Write the commit message in Japanese.",
    "japanese": "Write the commit message in Japanese.",
    "ko": "Write the commit message in Korean.",
    "korean": "Write the commit message in Korean.",
    "en": "Write the commit message in English.",
    "english": "Write the commit message in English.",
}

SYSTEM_PROMPT = """\
You are an expert at writing Git commit messages following the Conventional Commits specification.

Rules:
1. Format: <type>[optional scope]: <description>
2. Types: feat, fix, refactor, docs, style, test, chore, perf, ci, build, revert
3. Subject line: imperative mood, lowercase, no period, max 72 characters
4. Optional body: explain WHAT and WHY (not HOW), wrap at 80 characters
5. Optional footer: breaking changes as "BREAKING CHANGE:", issue refs
6. Do NOT add Co-authored-by or AI attribution lines
7. Be concise and accurate - describe the actual changes
8. If multiple types of changes, use the most significant one as the main type"""


_cfg: dict = {}


def cfg_get(key: str):
    return _cfg.get(key, DEFAULTS.get(key))


def _debug(msg: str) -> None:
    if cfg_get("debug"):
        print(f"[ai-commit DEBUG] {msg}", file=sys.stderr)


def _log(msg: str) -> None:
    print(f"[ai-commit] {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    print(f"[ai-commit ERROR] {msg}", file=sys.stderr)


def _coerce_type(key: str, raw):
    if key in ("max_diff_lines", "max_output_tokens"):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return DEFAULTS[key]
    if key == "debug" or key == "thinking":
        return raw in ("true", "True", "1", True)
    return raw


def _git_root() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "."


def load_config() -> None:
    global _cfg
    _cfg = dict(DEFAULTS)

    project_root = _git_root()
    candidates = [
        os.path.join(os.path.expanduser("~"), ".ai-commit.json"),
        os.path.join(project_root, ".ai-commit.json"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if k in _cfg:
                        _cfg[k] = _coerce_type(k, v)
            except (json.JSONDecodeError, OSError) as exc:
                _debug(f"Failed to read {path}: {exc}")

    for key, env_var in ENV_MAP.items():
        val = os.environ.get(env_var)
        if val is not None:
            _cfg[key] = _coerce_type(key, val)

    _debug(
        f"Config loaded: model={cfg_get('model')}, "
        f"max_diff_lines={cfg_get('max_diff_lines')}, "
        f"debug={cfg_get('debug')}, language={cfg_get('language')}"
    )
    _debug(f"API base URL: {cfg_get('api_base_url')}")
    _debug(f"Ignore file: {cfg_get('ignore_file')}")
    _debug(f"Thinking mode: {cfg_get('thinking')}")


def read_ignore_patterns() -> list[str]:
    project_root = _git_root()
    ignore_path = os.path.join(project_root, cfg_get("ignore_file"))
    patterns: list[str] = []

    if os.path.isfile(ignore_path):
        with open(ignore_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)

    return patterns
