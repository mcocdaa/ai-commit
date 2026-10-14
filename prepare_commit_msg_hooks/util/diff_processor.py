"""
Diff processing utilities for ai-commit-gen.

Handles diff abbreviation, filtering by ignore patterns, and file summary.
"""

from __future__ import annotations

import re

from . import config, gitignore

MAX_LINE_LENGTH = 1000
MAX_TOTAL_CHARS = 40000

_DIFF_HEADER_RE = re.compile(
    r'^diff --git (?:a/(.*?)|"a/((?:[^"\\]|\\.)*)") (?:b/(.*)|"b/((?:[^"\\]|\\.)*)")$'
)

_C_ESCAPES: dict[str, int] = {
    "a": 0x07,
    "b": 0x08,
    "f": 0x0C,
    "n": 0x0A,
    "r": 0x0D,
    "t": 0x09,
    "v": 0x0B,
    "\\": ord("\\"),
    '"': ord('"'),
}


def _unquote_git_path(raw: str) -> str:
    """Unescape C-style quoted Git paths (including octal UTF-8 byte sequences)."""
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        raw = raw[1:-1]
    buf = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            octal = raw[i + 1 : i + 4]
            if len(octal) == 3 and all(c in "01234567" for c in octal):
                buf.append(int(octal, 8) & 0xFF)
                i += 4
                continue
            nxt = raw[i + 1]
            if nxt in _C_ESCAPES:
                buf.append(_C_ESCAPES[nxt])
            else:
                buf.extend(nxt.encode("utf-8"))
            i += 2
        else:
            buf.extend(ch.encode("utf-8"))
            i += 1
    return buf.decode("utf-8", errors="replace")


def _parse_diff_git_header(line: str) -> tuple[str, str] | None:
    m = _DIFF_HEADER_RE.match(line)
    if not m:
        return None
    a_unquoted, a_quoted, b_unquoted, b_quoted = m.groups()
    a_path = _unquote_git_path(a_quoted) if a_quoted is not None else (a_unquoted or "")
    b_path = _unquote_git_path(b_quoted) if b_quoted is not None else (b_unquoted or "")
    return a_path, b_path


def _format_abbreviated_file(
    current_file: str,
    current_lines: list[str],
    line_count: int,
    reason: str,
) -> str:
    added = sum(1 for item in current_lines if item.startswith("+") and not item.startswith("+++"))
    removed = sum(
        1 for item in current_lines if item.startswith("-") and not item.startswith("---")
    )
    return "\n".join(
        [
            f"--- a/{current_file}",
            f"+++ b/{current_file}",
            f"@@ ... @@ (abbreviated: +{added}/-{removed} lines, {reason})",
        ]
    )


def abbreviate_diff(
    diff: str,
    max_lines: int,
    max_total_chars: int = MAX_TOTAL_CHARS,
    max_line_length: int = MAX_LINE_LENGTH,
) -> str:
    file_entries: list[tuple[str, list[str], int]] = []
    current_file = ""
    current_lines: list[str] = []
    line_count = 0

    for line in diff.splitlines():
        parsed = _parse_diff_git_header(line)
        if parsed is not None:
            if current_file and current_lines:
                file_entries.append((current_file, current_lines, line_count))
            current_file = parsed[1]
            current_lines = [line]
            line_count = 0
        else:
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                line_count += 1
            if len(line) > max_line_length:
                orig_len = len(line)
                line = f"{line[:max_line_length]}... (line truncated, {orig_len} chars)"
            current_lines.append(line)

    if current_file and current_lines:
        file_entries.append((current_file, current_lines, line_count))

    result_parts: list[str] = []
    total_chars = 0

    for filepath, lines, count in file_entries:
        if count > max_lines:
            block = _format_abbreviated_file(
                filepath,
                lines,
                count,
                f"total {count} lines exceed threshold {max_lines}",
            )
        else:
            block = "\n".join(lines)

        sep_len = 1 if result_parts else 0
        if total_chars + sep_len + len(block) > max_total_chars:
            abbrev_block = _format_abbreviated_file(
                filepath,
                lines,
                count,
                f"total diff budget {max_total_chars} chars exceeded",
            )
            if total_chars + sep_len + len(abbrev_block) <= max_total_chars:
                result_parts.append(abbrev_block)
                total_chars += sep_len + len(abbrev_block)
            else:
                remaining = max_total_chars - total_chars - sep_len
                notice = "... (diff truncated due to max_total_chars budget)"
                if remaining >= len(notice):
                    result_parts.append(notice)
                elif not result_parts and max_total_chars > 0:
                    result_parts.append(block[:max_total_chars])
                break
        else:
            result_parts.append(block)
            total_chars += sep_len + len(block)

    return "\n".join(result_parts)


def filter_diff_by_ignore(diff: str, spec: gitignore.GitIgnoreSpec) -> str:
    result_parts: list[str] = []
    current_file = ""
    skip = False
    current_lines: list[str] = []

    for line in diff.splitlines():
        parsed = _parse_diff_git_header(line)
        if parsed is not None:
            if current_file and not skip and current_lines:
                result_parts.extend(current_lines)

            current_file = parsed[1]
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
        if filepath.startswith('"') and filepath.endswith('"'):
            filepath = _unquote_git_path(filepath)

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
