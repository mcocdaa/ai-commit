"""
Gitignore-style pattern matching using only Python standard library.

Implements the .gitignore pattern specification:
- https://git-scm.com/docs/gitignore

Supports: *, ?, [...], **, leading /, trailing /, ! negation
"""

import re
from collections.abc import Iterable


def _glob_segment_to_regex(segment: str) -> str:
    i = 0
    n = len(segment)
    result: list[str] = []

    while i < n:
        ch = segment[i]

        if ch == '*':
            if i + 1 < n and segment[i + 1] == '*':
                j = i + 2
                while j < n and segment[j] == '*':
                    j += 1
                i = j
                result.append('.*')
            else:
                result.append('[^/]*')
                i += 1

        elif ch == '?':
            result.append('[^/]')
            i += 1

        elif ch == '[':
            j = i + 1
            if j < n and segment[j] == ']':
                j += 1
            while j < n and segment[j] != ']':
                j += 1
            if j >= n:
                result.append(re.escape('['))
                i += 1
            else:
                bracket_expr = segment[i:j + 1]
                negated = len(bracket_expr) >= 3 and bracket_expr[1] == '!'
                inner = bracket_expr[1:-1]
                if inner == '!':
                    result.append(re.escape(bracket_expr))
                else:
                    if '/' in inner:
                        inner_expr = ''
                        k = 1
                        while k < len(inner):
                            if inner[k] == '/':
                                inner_expr += '/'
                            elif k + 2 < len(inner) and inner[k] == '-' and inner[k + 1] != ']':
                                inner_expr += inner[k]
                            else:
                                inner_expr += re.escape(inner[k])
                            k += 1
                        result.append(f'[{"".join(inner_expr)}]')
                    else:
                        result.append(bracket_expr)
                i = j + 1

        else:
            result.append(re.escape(ch))
            i += 1

    return ''.join(result)


def _pattern_to_regex(pattern: str) -> tuple[str, bool, bool] | None:
    """
    Convert a single gitignore pattern to (regex, is_negated, is_dir_only).

    Returns None if the pattern should be skipped (blank, comment, single '/').
    """
    if pattern.endswith('\\ '):
        pattern = pattern.lstrip()
    else:
        pattern = pattern.strip()

    if not pattern or pattern.startswith('#'):
        return None

    if pattern == '/':
        return None

    is_negated = pattern.startswith('!')
    if is_negated:
        pattern = pattern[1:]

    is_dir_only = pattern.endswith('/')
    if is_dir_only:
        pattern = pattern[:-1]

    is_rooted = pattern.startswith('/')
    if is_rooted:
        pattern = pattern[1:]

    has_slash = '/' in pattern

    if has_slash or is_rooted:
        segments = pattern.split('/')
    else:
        segments = ['**', pattern]

    regex_parts: list[str] = ['^']
    skip_next_slash = False

    for idx, seg in enumerate(segments):
        if not skip_next_slash and idx > 0:
            regex_parts.append('/')
        skip_next_slash = False

        if seg == '**':
            if idx == 0:
                regex_parts.append('(?:.*/)*')
                skip_next_slash = True
            elif idx == len(segments) - 1:
                regex_parts.append('.*')
            else:
                regex_parts.append('(?:.*/)*')
                skip_next_slash = True
        else:
            regex_parts.append(_glob_segment_to_regex(seg))

    if is_dir_only:
        regex_parts.append('(?:/.*)?$')
    else:
        regex_parts.append('$')

    return ''.join(regex_parts), is_negated, is_dir_only


class GitIgnoreSpec:
    """
    Compiled set of gitignore-style patterns for matching file paths.
    """

    def __init__(self, patterns: Iterable[str]) -> None:
        self._include: list[re.Pattern] = []
        self._exclude: list[re.Pattern] = []

        for pat in patterns:
            result = _pattern_to_regex(pat)
            if result is None:
                continue
            regex_str, is_negated, is_dir_only = result
            compiled = re.compile(regex_str)
            if is_negated:
                self._include.append(compiled)
            else:
                self._exclude.append(compiled)

    def is_ignored(self, filepath: str) -> bool:
        ignored = False
        for pattern in self._exclude:
            if pattern.match(filepath):
                ignored = True
                break
        for pattern in self._include:
            if pattern.match(filepath):
                ignored = False
                break
        return ignored


def compile_patterns(patterns: Iterable[str]) -> GitIgnoreSpec:
    return GitIgnoreSpec(patterns)
