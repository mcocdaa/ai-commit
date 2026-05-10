"""
Diff processing utilities for ai-commit-gen.

Handles diff abbreviation, filtering by ignore patterns, and file summary.
"""

import re
from collections.abc import Iterable

from . import config
from . import gitignore


def abbreviate_diff(diff: str, max_lines: int) -> str:
    result_parts: list[str] = []
    current_file = ""
    current_lines: list[str] = []
    line_count = 0

    for line in diff.splitlines():
        m = re.match(r"^diff --git a/(.*) b/(.*)", line)
        if m:
            if current_file and current_lines:
                if line_count > max_lines:
                    added = sum(1 for l in current_lines if l.startswith("+") and not l.startswith("+++"))
                    removed = sum(1 for l in current_lines if l.startswith("-") and not l.startswith("---"))
                    result_parts.append(f"--- a/{current_file}")
                    result_parts.append(f"+++ b/{current_file}")
                    result_parts.append(
                        f"@@ ... @@ (abbreviated: +{added}/-{removed} lines, "
                        f"total {line_count} lines exceed threshold {max_lines})"
                    )
                else:
                    result_parts.extend(current_lines)

            current_file = m.group(2)
            current_lines = [line]
            line_count = 0
        else:
            current_lines.append(line)
            if line.startswith("+") or line.startswith("-"):
                if not line.startswith("+++") and not line.startswith("---"):
                    line_count += 1

    if current_file and current_lines:
        if line_count > max_lines:
            added = sum(1 for l in current_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in current_lines if l.startswith("-") and not l.startswith("---"))
            result_parts.append(f"--- a/{current_file}")
            result_parts.append(f"+++ b/{current_file}")
            result_parts.append(
                f"@@ ... @@ (abbreviated: +{added}/-{removed} lines, "
                f"total {line_count} lines exceed threshold {max_lines})"
            )
        else:
            result_parts.extend(current_lines)

    return "\n".join(result_parts)


def filter_diff_by_ignore(diff: str, spec: gitignore.GitIgnoreSpec) -> str:
    result_parts: list[str] = []
    current_file = ""
    skip = False
    current_lines: list[str] = []

    for line in diff.splitlines():
        m = re.match(r"^diff --git a/(.*) b/(.*)", line)
        if m:
            if current_file and not skip and current_lines:
                result_parts.extend(current_lines)

            current_file = m.group(2)
            skip = spec.is_ignored(current_file)
            if skip:
                config._debug(f"Ignoring file: {current_file}")
            current_lines = [line]
        else:
            if not skip:
                current_lines.append(line)

    if current_file and not skip and current_lines:
        result_parts.extend(current_lines)

    return "\n".join(result_parts)


def build_file_summary(stats: str, spec: gitignore.GitIgnoreSpec) -> str:
    if not stats:
        return ""

    lines: list[str] = []
    max_lines = config.cfg_get("max_diff_lines")

    for entry in stats.splitlines():
        parts = entry.split("\t")
        if len(parts) != 3:
            continue
        added_s, removed_s, filepath = parts

        if spec.is_ignored(filepath):
            continue

        if added_s == "-" and removed_s == "-":
            lines.append(f"  (binary) {filepath}")
        else:
            try:
                total = int(added_s) + int(removed_s)
            except ValueError:
                continue
            if total > max_lines:
                lines.append(f"  (+{added_s}/-{removed_s}, abbreviated) {filepath}")
            else:
                lines.append(f"  (+{added_s}/-{removed_s}) {filepath}")

    return "\n".join(lines)
