"""
AI-powered Git commit message generator hook for pre-commit.

Zero external dependencies - uses only Python standard library.
"""

import argparse
import os
import sys

from .util import api
from .util import config
from .util import diff_processor
from .util import git_util
from .util import gitignore


def generate_commit_message() -> str | None:
    config.load_config()

    api_key = config.cfg_get("api_key")
    if not api_key:
        config._error("API key not configured. Set AI_COMMIT_API_KEY env var or add 'api_key' to .ai-commit.json")
        config._error("Project config: .ai-commit.json | Global config: ~/.ai-commit.json")
        return None

    raw_diff = git_util.get_staged_diff()
    if not raw_diff:
        config._debug("No staged changes found")
        return None

    patterns = config.read_ignore_patterns()
    config._debug(f"Ignore patterns: {patterns}")

    spec = gitignore.compile_patterns(patterns)

    filtered_diff = diff_processor.filter_diff_by_ignore(raw_diff, spec)
    if not filtered_diff:
        config._debug(f"All files ignored by {config.cfg_get('ignore_file')}")
        return None

    stats = git_util.get_staged_file_stats()
    file_summary = diff_processor.build_file_summary(stats, spec)

    processed_diff = diff_processor.abbreviate_diff(filtered_diff, config.cfg_get("max_diff_lines"))

    config._debug(f"Processed diff length: {len(processed_diff)}")
    if file_summary:
        config._debug(f"File summary:\n{file_summary}")

    try:
        return api.call_ai_api(processed_diff, file_summary)
    except Exception as exc:
        config._debug(f"AI API call failed: {exc}")
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-commit-gen",
        description="Generate AI-powered Conventional Commits messages for pre-commit prepare-commit-msg hook",
    )
    parser.add_argument(
        'commit_msg_file',
        nargs='?',
        default='',
        help='Path to the commit message file (COMMIT_EDITMSG)',
    )
    parser.add_argument(
        'commit_source',
        nargs='?',
        default='',
        help='Commit source: message, merge, squash, amend, or empty',
    )
    args = parser.parse_args(argv)

    commit_msg_file = args.commit_msg_file
    commit_source = args.commit_source

    if not commit_msg_file:
        commit_msg_file = git_util.find_commit_msg_file()
        if not commit_msg_file:
            config._error("Usage: ai-commit-gen <commit-msg-file> [commit-source]")
            config._error("Auto-detection failed - no COMMIT_EDITMSG found")
            return 1
        config._debug(f"Auto-detected commit msg file: {commit_msg_file}")
        if not commit_source:
            commit_source = git_util.detect_commit_source(commit_msg_file)

    if not os.path.isfile(commit_msg_file):
        config._error(f"Commit message file not found: {commit_msg_file}")
        return 1

    if commit_source in ("merge", "squash", "amend"):
        config._debug(f"Skipping for {commit_source} commit")
        return 0

    ai_msg = generate_commit_message()
    if not ai_msg:
        config._log("AI generation failed or no changes, proceeding without AI message")
        return 0

    try:
        with open(commit_msg_file, "r", encoding="utf-8") as f:
            existing_msg = f.read()
    except OSError:
        existing_msg = ""

    existing_lines = [
        line for line in existing_msg.splitlines()
        if not line.startswith("#")
    ]
    existing_msg_clean = "\n".join(existing_lines).strip()

    if existing_msg_clean and commit_source == "message":
        combined = f"{existing_msg_clean}\n\n{ai_msg}"
        with open(commit_msg_file, "w", encoding="utf-8") as f:
            f.write(combined + "\n")
        config._log("AI message appended after your -m message")
    elif existing_msg_clean and not commit_source:
        combined = f"{existing_msg_clean}\n\n{ai_msg}"
        with open(commit_msg_file, "w", encoding="utf-8") as f:
            f.write(combined + "\n")
        config._log("AI message appended after existing message")
    else:
        with open(commit_msg_file, "w", encoding="utf-8") as f:
            f.write(ai_msg + "\n")
        config._log("AI message generated (edit in editor to adjust)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
