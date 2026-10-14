"""
Git utility functions for ai-commit-gen.

Provides subprocess wrappers for common git operations used by the hook.
"""

from __future__ import annotations

import os
import subprocess

SCISSORS_LINE = "# ------------------------ >8 ------------------------"


class GitError(RuntimeError):
    pass


def cmd_output(*cmd: str, retcode: int | None = 0) -> str:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if retcode is not None and proc.returncode != retcode:
        raise GitError(
            f"Command '{' '.join(cmd)}' returned {proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout


def git_root() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "."


def get_staged_diff() -> str:
    try:
        return subprocess.check_output(
            ["git", "diff", "--cached", "--diff-filter=ACMR", "--unified=3"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_staged_file_stats() -> str:
    try:
        return subprocess.check_output(
            ["git", "diff", "--cached", "--numstat"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_branch_name() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def added_files() -> set[str]:
    return set(cmd_output("git", "diff", "--staged", "--name-only", "--diff-filter=A").splitlines())


def find_commit_msg_file() -> str:
    candidates = [".git/COMMIT_EDITMSG"]
    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-dir"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
        if git_dir:
            candidates.insert(0, os.path.join(git_dir, "COMMIT_EDITMSG"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""


def parse_commit_editmsg(content: str) -> tuple[str, str]:
    """
    Split COMMIT_EDITMSG content into (clean_user_message, comment_and_scissors_block).

    Any line starting with '#' and everything at or below the Git scissors line
    ('# ------------------------ >8 ------------------------') are treated as the
    trailing Git comment/verbose-diff block rather than user message content.
    """
    user_lines: list[str] = []
    comment_lines: list[str] = []
    in_scissors = False

    for line in content.splitlines():
        if not in_scissors and line.strip() == SCISSORS_LINE:
            in_scissors = True
        if in_scissors or line.startswith("#"):
            comment_lines.append(line)
        else:
            user_lines.append(line)

    return "\n".join(user_lines).strip(), "\n".join(comment_lines)


def detect_commit_source(commit_msg_file: str) -> str:
    try:
        with open(commit_msg_file, "r", encoding="utf-8") as f:
            content = f.read()
        user_msg, _ = parse_commit_editmsg(content)
        if user_msg:
            return "message"
    except OSError:
        pass
    return ""
