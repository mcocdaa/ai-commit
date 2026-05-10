"""Tests for ai_commit_gen module."""

import os
import sys
import json
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prepare_commit_msg_hooks.util import config
from prepare_commit_msg_hooks.util import diff_processor
from prepare_commit_msg_hooks.util import git_util
from prepare_commit_msg_hooks.util import gitignore

from prepare_commit_msg_hooks.util.config import (
    DEFAULTS,
    _coerce_type,
)


class TestCoerceType:
    def test_int_keys(self):
        assert _coerce_type("max_diff_lines", "500") == 500
        assert _coerce_type("max_diff_lines", "invalid") == DEFAULTS["max_diff_lines"]

    def test_debug_key(self):
        assert _coerce_type("debug", "true") is True
        assert _coerce_type("debug", "false") is False
        assert _coerce_type("debug", True) is True

    def test_string_key(self):
        assert _coerce_type("language", "zh") == "zh"


class TestGitIgnore:
    def test_exact_match(self):
        spec = gitignore.compile_patterns(["*.md"])
        assert spec.is_ignored("test.md") is True

    def test_basename_match(self):
        spec = gitignore.compile_patterns(["*.pyc"])
        assert spec.is_ignored("some/deep/path/test.pyc") is True

    def test_no_match(self):
        spec = gitignore.compile_patterns(["*.md", "*.txt"])
        assert spec.is_ignored("src/main.py") is False

    def test_empty_patterns(self):
        spec = gitignore.compile_patterns([])
        assert spec.is_ignored("any/file.py") is False

    def test_directory_pattern(self):
        spec = gitignore.compile_patterns(["dist/"])
        assert spec.is_ignored("dist/bundle.js") is True

    def test_negation(self):
        spec = gitignore.compile_patterns(["*.log", "!important.log"])
        assert spec.is_ignored("error.log") is True
        assert spec.is_ignored("important.log") is False

    def test_anchored_pattern(self):
        spec = gitignore.compile_patterns(["/src/test.py"])
        assert spec.is_ignored("src/test.py") is True
        assert spec.is_ignored("other/src/test.py") is False

    def test_double_asterisk(self):
        spec = gitignore.compile_patterns(["a/**/b.py"])
        assert spec.is_ignored("a/b.py") is True
        assert spec.is_ignored("a/x/b.py") is True
        assert spec.is_ignored("a/x/y/b.py") is True
        assert spec.is_ignored("x/a/b.py") is False

    def test_comment_skipped(self):
        spec = gitignore.compile_patterns(["# this is a comment", "*.md"])
        assert spec.is_ignored("test.md") is True


class TestAbbreviateDiff:
    def test_small_diff_passes_through(self):
        diff = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new"
        result = diff_processor.abbreviate_diff(diff, 10)
        assert "old" in result
        assert "new" in result

    def test_large_diff_abbreviated(self):
        lines = ["diff --git a/big.py b/big.py"]
        for i in range(2000):
            lines.append(f"+line_{i}")
        diff = "\n".join(lines)
        result = diff_processor.abbreviate_diff(diff, 1000)
        assert "abbreviated" in result
        assert "+2000" in result


class TestFilterDiffByIgnore:
    def test_filters_ignored_file(self):
        diff = (
            "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
            "@@ -1,1 +1,1 @@\n-old\n+new\n"
            "diff --git a/src/main.py b/src/main.py\n--- a/src/main.py\n+++ b/src/main.py\n"
            "@@ -1,1 +1,1 @@\n-old\n+new"
        )
        spec = gitignore.compile_patterns(["*.md"])
        result = diff_processor.filter_diff_by_ignore(diff, spec)
        assert "README.md" not in result
        assert "main.py" in result

    def test_no_patterns_returns_all(self):
        diff = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new"
        spec = gitignore.compile_patterns([])
        assert diff_processor.filter_diff_by_ignore(diff, spec) == diff


class TestBuildFileSummary:
    def test_basic_summary(self, monkeypatch):
        monkeypatch.setitem(config._cfg, "max_diff_lines", 1000)
        stats = "1\t0\tsrc/main.py"
        spec = gitignore.compile_patterns([])
        result = diff_processor.build_file_summary(stats, spec)
        assert "(+1/-0)" in result
        assert "src/main.py" in result

    def test_ignored_file_skipped(self, monkeypatch):
        monkeypatch.setitem(config._cfg, "max_diff_lines", 1000)
        stats = "1\t0\tREADME.md"
        spec = gitignore.compile_patterns(["*.md"])
        result = diff_processor.build_file_summary(stats, spec)
        assert result == ""

    def test_binary_file(self, monkeypatch):
        monkeypatch.setitem(config._cfg, "max_diff_lines", 1000)
        stats = "-\t-\timage.png"
        spec = gitignore.compile_patterns([])
        result = diff_processor.build_file_summary(stats, spec)
        assert "(binary)" in result


class TestFindCommitMsgFile:
    def test_returns_valid_path_in_repo(self):
        result = git_util.find_commit_msg_file()
        assert result != ""
        assert "COMMIT_EDITMSG" in result


class TestDetectCommitSource:
    def test_detects_message(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test: commit message")
            f.flush()
            result = git_util.detect_commit_source(f.name)
        os.unlink(f.name)
        assert result == "message"

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            f.flush()
            result = git_util.detect_commit_source(f.name)
        os.unlink(f.name)
        assert result == ""
