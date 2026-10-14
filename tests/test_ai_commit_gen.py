"""Tests for ai_commit_gen module."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prepare_commit_msg_hooks import ai_commit_gen
from prepare_commit_msg_hooks.util import (
    api,
    config,
    diff_processor,
    git_util,
    gitignore,
)
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

    def test_sequential_negation_reignore(self):
        spec = gitignore.compile_patterns(["*.log", "!important.log", "important.log"])
        assert spec.is_ignored("important.log") is True

        spec2 = gitignore.compile_patterns(["!important.log", "*.log"])
        assert spec2.is_ignored("important.log") is True

        spec3 = gitignore.compile_patterns(["logs/*", "!logs/keep.log", "logs/secret.log"])
        assert spec3.is_ignored("logs/other.log") is True
        assert spec3.is_ignored("logs/keep.log") is False
        assert spec3.is_ignored("logs/secret.log") is True

    def test_escaped_trailing_space(self):
        spec = gitignore.compile_patterns([r"trailing\ "])
        assert spec.is_ignored("trailing ") is True
        assert spec.is_ignored("trailing") is False

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

    def test_bracket_negation(self):
        spec = gitignore.compile_patterns(["*[!0-9].txt"])
        assert spec.is_ignored("abc.txt") is True
        assert spec.is_ignored("123.txt") is False


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

    def test_long_single_line_truncated(self):
        long_line = "+" + ("x" * 2500)
        diff = f"diff --git a/bundle.js b/bundle.js\n--- a/bundle.js\n+++ b/bundle.js\n@@ -1 +1 @@\n{long_line}"
        result = diff_processor.abbreviate_diff(diff, 1000)
        assert "line truncated" in result
        assert len(result) < 1500

    def test_global_total_chars_budget(self):
        parts = []
        for idx in range(10):
            parts.append(f"diff --git a/f{idx}.py b/f{idx}.py")
            for line_no in range(50):
                parts.append(f"+file_{idx}_line_{line_no}_{'a' * 60}")
        diff = "\n".join(parts)
        result = diff_processor.abbreviate_diff(diff, 1000, max_total_chars=5000)
        assert len(result) <= 5000
        assert "abbreviated" in result


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

    def test_quoted_space_and_octal_non_ascii_paths(self):
        # "\344\270\255\346\226\207.md" is Git's octal C-escaped representation of "中文.md"
        diff = (
            'diff --git "a/docs/my notes.md" "b/docs/my notes.md"\n'
            '--- "a/docs/my notes.md"\n'
            '+++ "b/docs/my notes.md"\n'
            "@@ -1 +1 @@\n-old\n+new\n"
            'diff --git "a/docs/\\344\\270\\255\\346\\226\\207.md" "b/docs/\\344\\270\\255\\346\\226\\207.md"\n'
            '--- "a/docs/\\344\\270\\255\\346\\226\\207.md"\n'
            '+++ "b/docs/\\344\\270\\255\\346\\226\\207.md"\n'
            "@@ -1 +1 @@\n-old\n+new\n"
            'diff --git "a/src/keep file.py" "b/src/keep file.py"\n'
            '--- "a/src/keep file.py"\n'
            '+++ "b/src/keep file.py"\n'
            "@@ -1 +1 @@\n-old\n+new"
        )
        spec = gitignore.compile_patterns(["*.md"])
        result = diff_processor.filter_diff_by_ignore(diff, spec)
        assert "my notes.md" not in result
        assert "344" not in result
        assert "keep file.py" in result


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
    def test_returns_path_when_file_exists(self, tmp_path):
        commit_msg = tmp_path / "COMMIT_EDITMSG"
        commit_msg.write_text("test commit")
        with patch("subprocess.check_output", return_value=str(tmp_path)):
            result = git_util.find_commit_msg_file()
            assert result == str(commit_msg)

    def test_returns_empty_when_not_found(self):
        with patch("os.path.isfile", return_value=False):
            result = git_util.find_commit_msg_file()
            assert result == ""


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

    def test_comments_and_scissors_only_not_detected_as_message(self, tmp_path):
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(
            "\n# Please enter the commit message\n"
            "# ------------------------ >8 ------------------------\n"
            "diff --git a/foo.py b/foo.py\n"
            "+added line\n",
            encoding="utf-8",
        )
        assert git_util.detect_commit_source(str(msg_file)) == ""


class TestMainHookBehavior:
    def test_amend_three_args_skips_without_crash_or_overwrite(self, tmp_path):
        msg_file = tmp_path / "COMMIT_EDITMSG"
        original_content = "feat: existing commit message to amend\n"
        msg_file.write_text(original_content, encoding="utf-8")

        with patch("prepare_commit_msg_hooks.ai_commit_gen.generate_commit_message") as mock_gen:
            ret = ai_commit_gen.main([str(msg_file), "commit", "HEAD"])
            assert ret == 0
            mock_gen.assert_not_called()

        assert msg_file.read_text(encoding="utf-8") == original_content

    def test_verbose_commit_scissors_preserved_without_diff_leak(self, tmp_path):
        msg_file = tmp_path / "COMMIT_EDITMSG"
        verbose_template = (
            "\n"
            "# Please enter the commit message for your changes.\n"
            "# On branch main\n"
            "# ------------------------ >8 ------------------------\n"
            "# Do not modify or remove the line above.\n"
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1,2 @@\n"
            " print('hello')\n"
            "+print('world')\n"
        )
        msg_file.write_text(verbose_template, encoding="utf-8")

        with patch(
            "prepare_commit_msg_hooks.ai_commit_gen.generate_commit_message",
            return_value="feat(app): add world greeting",
        ):
            ret = ai_commit_gen.main([str(msg_file)])
            assert ret == 0

        written = msg_file.read_text(encoding="utf-8")
        user_msg, trailer = git_util.parse_commit_editmsg(written)
        assert user_msg == "feat(app): add world greeting"
        assert "diff --git" not in user_msg
        assert "# ------------------------ >8 ------------------------" in trailer
        assert "+print('world')" in trailer


class TestApiThinkStrippingAndHeaders:
    def test_strips_think_tags_and_sends_user_agent(self, monkeypatch):
        monkeypatch.setitem(config._cfg, "api_key", "test-key")
        monkeypatch.setitem(config._cfg, "api_base_url", "https://api.openai.com/v1")
        monkeypatch.setitem(config._cfg, "model", "deepseek-r1")
        monkeypatch.setitem(config._cfg, "max_output_tokens", 512)
        monkeypatch.setitem(config._cfg, "thinking", False)

        fake_resp_body = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "<think>\nAnalyzing staged changes...\n</think>\n```text\nfix(parser): handle quoted paths\n```"
                        }
                    }
                ]
            }
        ).encode("utf-8")

        captured_req = {}

        def fake_urlopen(req, timeout=30):
            captured_req["req"] = req
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_resp_body
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__exit__.return_value = False
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            msg = api.call_ai_api("diff --git a/a.py b/a.py\n+pass", "  (+1/-0) a.py")

        assert msg == "fix(parser): handle quoted paths"
        assert "<think>" not in msg
        req = captured_req["req"]
        assert req.get_header("User-agent") == "ai-commit/1.0"
        sent_payload = json.loads(req.data.decode("utf-8"))
        # Non-deepseek.com endpoint with thinking=False must not receive proprietary "thinking" field
        assert "thinking" not in sent_payload

    def test_falls_back_to_reasoning_content(self, monkeypatch):
        monkeypatch.setitem(config._cfg, "api_key", "test-key")
        monkeypatch.setitem(config._cfg, "api_base_url", "https://api.deepseek.com")
        monkeypatch.setitem(config._cfg, "model", "deepseek-reasoner")
        monkeypatch.setitem(config._cfg, "max_output_tokens", 512)
        monkeypatch.setitem(config._cfg, "thinking", True)

        fake_resp_body = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "<think>only thoughts</think>",
                            "reasoning_content": "<think>step 1</think>\nchore: update lockfile ignore list",
                        }
                    }
                ]
            }
        ).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_resp_body
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            msg = api.call_ai_api("diff --git a/a.py b/a.py\n+pass", "")

        assert msg == "chore: update lockfile ignore list"


class TestConfigAndIgnoreLoading:
    def test_read_ignore_patterns_preserves_escaped_trailing_space_and_defaults(
        self, tmp_path, monkeypatch
    ):
        ignore_file = tmp_path / ".opencommitignore"
        ignore_file.write_text("# comment\nspace_file\\ \ncustom.lock  \n", encoding="utf-8")
        monkeypatch.setitem(config._cfg, "ignore_file", ".opencommitignore")
        with patch("prepare_commit_msg_hooks.util.config._git_root", return_value=str(tmp_path)):
            patterns = config.read_ignore_patterns()

        assert "uv.lock" in patterns
        assert "package-lock.json" in patterns
        assert "space_file\\ " in patterns
        spec = gitignore.compile_patterns(patterns)
        assert spec.is_ignored("uv.lock") is True
        assert spec.is_ignored("space_file ") is True
        assert spec.is_ignored("space_file") is False
        assert spec.is_ignored("custom.lock") is True

    def test_load_config_handles_non_dict_json_and_early_debug(self, tmp_path, monkeypatch):
        bad_cfg = tmp_path / ".ai-commit.json"
        bad_cfg.write_text('["not", "a", "dict"]', encoding="utf-8")
        monkeypatch.setenv("AI_COMMIT_DEBUG", "true")
        stderr_buf = io.StringIO()
        with (
            patch("prepare_commit_msg_hooks.util.config._git_root", return_value=str(tmp_path)),
            patch("os.path.expanduser", return_value=str(tmp_path / "nonexistent_home")),
            patch("sys.stderr", stderr_buf),
        ):
            config.load_config()

        assert config.cfg_get("debug") is True
        assert "root JSON value must be an object" in stderr_buf.getvalue()
