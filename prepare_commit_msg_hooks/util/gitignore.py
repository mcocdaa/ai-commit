"""
Gitignore-style pattern matching using only Python standard library.

Implements the .gitignore pattern specification:
- https://git-scm.com/docs/gitignore

Supports: *, ?, [...], **, leading /, trailing /, ! negation
"""

from __future__ import annotations

import re
from collections.abc import Iterable


def _glob_segment_to_regex(segment: str) -> str:
    i = 0
    n = len(segment)
    result: list[str] = []

    while i < n:
        ch = segment[i]

        if ch == "*":
            if i + 1 < n and segment[i + 1] == "*":
                j = i + 2
                while j < n and segment[j] == "*":
                    j += 1
                i = j
                result.append(".*")
            else:
                result.append("[^/]*")
                i += 1

        elif ch == "?":
            result.append("[^/]")
            i += 1

        elif ch == "\\":
            if i + 1 < n:
                result.append(re.escape(segment[i + 1]))
                i += 2
            else:
                result.append(re.escape("\\"))
                i += 1

        elif ch == "[":
            j = i + 1
            if j < n and segment[j] == "]":
                j += 1
            while j < n and segment[j] != "]":
                j += 1
            if j >= n:
                result.append(re.escape("["))
                i += 1
            else:
                bracket_expr = segment[i : j + 1]
                negated = len(bracket_expr) >= 3 and bracket_expr[1] == "!"
                inner = bracket_expr[1:-1]
                if inner == "!":
                    result.append(re.escape(bracket_expr))
                else:
                    if negated:
                        inner = inner[1:]
                        prefix = "^/"
                    else:
                        prefix = ""
                    if "/" in inner:
                        inner_expr = ""
                        k = 0
                        while k < len(inner):
                            if inner[k] == "/":
                                inner_expr += "/"
                            elif k + 2 < len(inner) and inner[k] == "-" and inner[k + 1] != "]":
                                inner_expr += inner[k]
                            else:
                                inner_expr += re.escape(inner[k])
                            k += 1
                        result.append(f"[{prefix}{''.join(inner_expr)}]")
                    else:
                        result.append(f"[{prefix}{inner}]")
                i = j + 1

        else:
            result.append(re.escape(ch))
            i += 1

    return "".join(result)


def _strip_unescaped_trailing_spaces(pattern: str) -> str:
    pattern = pattern.rstrip("\r\n")
    end = len(pattern)
    while end > 0 and pattern[end - 1] in (" ", "\t"):
        backslashes = 0
        k = end - 1
        while k > 0 and pattern[k - 1] == "\\":
            backslashes += 1
            k -= 1
        if backslashes % 2 == 1:
            break
        end -= 1
    return pattern[:end].lstrip()


def _pattern_to_regex(pattern: str) -> tuple[str, bool, bool] | None:
    """
    Convert a single gitignore pattern to (regex, is_negated, is_dir_only).

    Returns None if the pattern should be skipped (blank, comment, single '/').
    """
    pattern = _strip_unescaped_trailing_spaces(pattern)

    if not pattern or pattern.startswith("#"):
        return None

    if pattern == "/":
        return None

    is_negated = pattern.startswith("!")
    if is_negated:
        pattern = pattern[1:]

    is_dir_only = pattern.endswith("/")
    if is_dir_only:
        pattern = pattern[:-1]

    is_rooted = pattern.startswith("/")
    if is_rooted:
        pattern = pattern[1:]

    has_slash = "/" in pattern

    if has_slash or is_rooted:
        segments = pattern.split("/")
    else:
        segments = ["**", pattern]

    regex_parts: list[str] = ["^"]
    skip_next_slash = False

    for idx, seg in enumerate(segments):
        if not skip_next_slash and idx > 0:
            regex_parts.append("/")
        skip_next_slash = False

        if seg == "**":
            if idx == 0:
                regex_parts.append("(?:.*/)*")
                skip_next_slash = True
            elif idx == len(segments) - 1:
                regex_parts.append(".*")
            else:
                regex_parts.append("(?:.*/)*")
                skip_next_slash = True
        else:
            regex_parts.append(_glob_segment_to_regex(seg))

    if is_dir_only:
        regex_parts.append("(?:/.*)?$")
    else:
        regex_parts.append("$")

    return "".join(regex_parts), is_negated, is_dir_only


class GitIgnoreSpec:
    """
    Compiled set of gitignore-style patterns for matching file paths.
    """

    def __init__(self, patterns: Iterable[str]) -> None:
        self._rules: list[tuple[re.Pattern[str], bool]] = []

        for pat in patterns:
            result = _pattern_to_regex(pat)
            if result is None:
                continue
            regex_str, is_negated, _ = result
            compiled = re.compile(regex_str)
            self._rules.append((compiled, is_negated))

    def is_ignored(self, filepath: str) -> bool:
        ignored = False
        for pattern, is_negated in self._rules:
            if pattern.match(filepath):
                ignored = not is_negated
        return ignored


def compile_patterns(patterns: Iterable[str]) -> GitIgnoreSpec:
    return GitIgnoreSpec(patterns)
