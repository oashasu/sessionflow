"""Tests for core modules - errors, recovery, scanner, parser, sqlite_storage

Targets missing coverage lines:
- errors.py: lines 17, 44, 54, 78
- recovery.py: lines 33-34, 86, 116-118, 137, 142-148, 157-158, 201-202
- scanner.py: lines 38-39, 47-48, 156
- parser.py: lines 17, 54, 137-139, 190-191
- sqlite_storage.py: lines 198-199, 428, 435, 643, 665-675, 679-688, 692-696, 703-748
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# errors.py tests
# ============================================================

class TestSessionFlowError:
    """Test base error class and format_message branches."""

    def test_format_message_with_suggestion(self):
        """format_message returns message + suggestion when suggestion is set."""
        from core.errors import SessionFlowError
        err = SessionFlowError("something broke", suggestion="try this")
        assert "something broke" in str(err)
        assert "try this" in str(err)

    def test_format_message_without_suggestion(self):
        """Line 17: format_message returns bare message when suggestion is None."""
        from core.errors import SessionFlowError
        err = SessionFlowError("something broke")
        assert str(err) == "something broke"
        assert err.suggestion is None

    def test_format_message_empty_suggestion(self):
        """Empty string suggestion is falsy, so message returned without hint."""
        from core.errors import SessionFlowError
        err = SessionFlowError("msg", suggestion="")
        # Empty string is falsy in Python, so the no-suggestion branch is taken
        assert str(err) == "msg"


class TestSessionNotFoundError:
    def test_message_and_suggestion(self):
        from core.errors import SessionNotFoundError
        err = SessionNotFoundError("abc-123")
        assert "abc-123" in str(err)
        assert "sessionflow list" in str(err)


class TestInvalidSessionIdError:
    def test_message_and_suggestion(self):
        from core.errors import InvalidSessionIdError
        err = InvalidSessionIdError("bad-id")
        assert "bad-id" in str(err)
        assert "UUID" in str(err)


class TestDirectoryNotFoundError:
    """Line 44: covers super().__init__ call in DirectoryNotFoundError."""

    def test_message_contains_path(self):
        from core.errors import DirectoryNotFoundError
        err = DirectoryNotFoundError("/no/such/dir")
        assert "/no/such/dir" in str(err)
        assert "sessionflow list" in str(err)


class TestNoActiveSessionError:
    """Line 54: covers super().__init__ call in NoActiveSessionError."""

    def test_message_and_suggestion(self):
        from core.errors import NoActiveSessionError
        err = NoActiveSessionError()
        assert "活跃会话" in str(err)
        assert "sessionflow scan" in str(err)


class TestMultipleMatchError:
    def test_message_shows_matches(self):
        from core.errors import MultipleMatchError
        m1 = MagicMock()
        m1.short_id = "aaa"
        m1.project_name = "proj1"
        m2 = MagicMock()
        m2.short_id = "bbb"
        m2.project_name = "proj2"
        err = MultipleMatchError("ab", [m1, m2])
        msg = str(err)
        assert "2" in msg
        assert "aaa" in msg
        assert "bbb" in msg


class TestJsonlNotFoundError:
    """Line 78: covers super().__init__ call in JsonlNotFoundError."""

    def test_message_contains_session_id(self):
        from core.errors import JsonlNotFoundError
        err = JsonlNotFoundError("sess-42")
        assert "sess-42" in str(err)
        assert "日志文件" in str(err)


class TestSecurityError:
    def test_message_and_suggestion(self):
        from core.errors import SecurityError
        err = SecurityError("path traversal detected")
        assert "path traversal detected" in str(err)
        assert "允许范围" in str(err)


# ============================================================
# recovery.py tests
# ============================================================

class TestValidateSessionId:
    def test_valid_uuid(self):
        from core.recovery import validate_session_id
        assert validate_session_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890") is True

    def test_invalid_uuid(self):
        from core.recovery import validate_session_id
        assert validate_session_id("not-a-uuid") is False

    def test_empty_string(self):
        from core.recovery import validate_session_id
        assert validate_session_id("") is False


class TestValidatePath:
    def test_valid_home_path(self):
        from core.recovery import validate_path
        home = str(Path.home())
        assert validate_path(home) is True

    def test_invalid_path_outside_home(self):
        from core.recovery import validate_path
        # /tmp is outside home on macOS
        assert validate_path("/tmp/some_random_path_xyz") is False

    def test_path_resolution_exception(self):
        """Lines 33-34: exception branch in validate_path."""
        from core.recovery import validate_path
        with patch("core.recovery.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.resolve.side_effect = OSError("permission denied")
            mock_path_cls.return_value = mock_path_instance
            result = validate_path("/some/path")
            assert result is False


class TestGenerateRecoveryCmd:
    def test_valid_tool(self):
        from core.recovery import generate_recovery_cmd
        cmd = generate_recovery_cmd(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            str(Path.home()),
            "claude"
        )
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in cmd

    def test_unknown_tool_falls_back(self):
        """Test fallback when provider raises ValueError."""
        from core.recovery import generate_recovery_cmd
        with patch("core.recovery.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create.side_effect = ValueError("unknown tool")
            mock_factory.return_value = mock_factory_instance
            cmd = generate_recovery_cmd("abc-123", "/some/dir", "unknown_tool")
            assert "claude --resume abc-123" == cmd


class TestRecoverSession:
    def test_invalid_session_id_raises(self):
        from core.recovery import recover_session
        from core.errors import InvalidSessionIdError
        with pytest.raises(InvalidSessionIdError):
            recover_session("bad", "/some/dir")

    def test_nonexistent_cwd_uses_home(self):
        """Line 86: when cwd doesn't exist, fallback to home dir."""
        from core.recovery import recover_session
        with patch("core.recovery.Path") as mock_path_cls, \
             patch("core.recovery.get_factory") as mock_factory, \
             patch("core.recovery.validate_path", return_value=True), \
             patch("core.recovery.generate_recovery_cmd", return_value="cmd"):
            # First call to Path (cwd) - exists() returns False
            mock_cwd_path = MagicMock()
            mock_cwd_path.exists.return_value = False
            # Second call to Path.home() - returns a valid path
            mock_home_path = MagicMock()
            mock_home_path.resolve.return_value = Path("/Users/test")
            # The Path(cwd) call
            mock_path_cls.return_value = mock_cwd_path
            # The Path.home() call during validate_path
            mock_path_cls.home.return_value = mock_home_path

            # Provider mock that raises ValueError to end the flow
            mock_factory_instance = MagicMock()
            mock_factory.return_value = mock_factory_instance
            mock_factory_instance.create.return_value = MagicMock()

            # Make recover_local_session return True
            provider = mock_factory_instance.create.return_value
            provider.recover_local_session.return_value = True

            result = recover_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "/nonexistent")
            assert result is True

    def test_invalid_path_raises_security_error(self):
        from core.recovery import recover_session
        from core.errors import SecurityError
        with patch("core.recovery.validate_path", return_value=False):
            with pytest.raises(SecurityError):
                recover_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "/outside/home")

    def test_provider_value_error_returns_false(self):
        """Lines 116-118: ValueError branch returns False."""
        from core.recovery import recover_session
        with patch("core.recovery.validate_path", return_value=True), \
             patch("core.recovery.Path") as mock_path_cls, \
             patch("core.recovery.get_factory") as mock_factory, \
             patch("core.recovery.generate_recovery_cmd", return_value="cmd"):
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_cls.return_value = mock_path

            mock_factory_instance = MagicMock()
            mock_factory.return_value = mock_factory_instance
            mock_factory_instance.create.side_effect = ValueError("no provider")

            result = recover_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "/valid/dir")
            assert result is False

    def test_recover_with_host(self):
        from core.recovery import recover_session
        mock_host = MagicMock()
        with patch("core.recovery.validate_path", return_value=True), \
             patch("core.recovery.Path") as mock_path_cls, \
             patch("core.recovery.get_factory") as mock_factory, \
             patch("core.recovery.generate_recovery_cmd", return_value="cmd"):
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_cls.return_value = mock_path

            mock_provider = MagicMock()
            mock_provider.recover_remote_session.return_value = True
            mock_factory_instance = MagicMock()
            mock_factory_instance.create.return_value = mock_provider
            mock_factory.return_value = mock_factory_instance

            result = recover_session(
                "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "/valid/dir",
                host=mock_host
            )
            assert result is True
            mock_provider.recover_remote_session.assert_called_once()


class TestOpenSession:
    def test_invalid_session_id_raises(self):
        from core.recovery import open_session
        from core.errors import InvalidSessionIdError
        with pytest.raises(InvalidSessionIdError):
            open_session("bad", "/some/dir")

    def test_nonexistent_cwd_uses_home(self):
        """Lines 137, 142-148: open_session with nonexistent cwd falls back to home."""
        from core.recovery import open_session
        with patch("core.recovery.Path") as mock_path_cls, \
             patch("core.recovery.validate_path", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            mock_cwd = MagicMock()
            mock_cwd.exists.return_value = False
            mock_path_cls.return_value = mock_cwd

            mock_home = MagicMock()
            mock_path_cls.home.return_value = mock_home

            open_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "/nonexistent")
            mock_popen.assert_called_once()

    def test_invalid_path_raises_security_error(self):
        from core.recovery import open_session
        from core.errors import SecurityError
        with patch("core.recovery.validate_path", return_value=False), \
             patch("core.recovery.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_cls.return_value = mock_path
            with pytest.raises(SecurityError):
                open_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "/outside")

    def test_normal_opens_subprocess(self):
        """Lines 142-148: normal path opens subprocess.Popen."""
        from core.recovery import open_session
        with patch("core.recovery.Path") as mock_path_cls, \
             patch("core.recovery.validate_path", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_cls.return_value = mock_path

            open_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "/valid/dir", "claude")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in call_args[0][0]
            assert call_args[1]["start_new_session"] is True


class TestCopyToClipboard:
    """Lines 157-158: covers copy_to_clipboard."""

    def test_calls_pbcopy(self):
        from core.recovery import copy_to_clipboard
        with patch("subprocess.run") as mock_run:
            copy_to_clipboard("hello world")
            mock_run.assert_called_once_with(
                ["pbcopy"], input=b"hello world", check=True
            )


class TestAttachTmuxSession:
    """Lines 201-202: covers tmux attach branch."""

    def test_finds_and_attaches(self):
        from core.recovery import attach_tmux_session
        mock_provider = MagicMock()
        mock_provider.scan_tmux_mappings.return_value = {
            "session-abc": {"tmux_name": "claude-session-abc"}
        }
        mock_provider._attach_tmux.return_value = True

        with patch("core.recovery.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.get_all_enabled.return_value = [mock_provider]
            mock_factory.return_value = mock_factory_instance

            result = attach_tmux_session("session-abc")
            assert result is True
            mock_provider._attach_tmux.assert_called_once_with(
                {"tmux_name": "claude-session-abc"}, None
            )

    def test_no_matching_tmux_session(self):
        from core.recovery import attach_tmux_session
        mock_provider = MagicMock()
        mock_provider.scan_tmux_mappings.return_value = {}

        with patch("core.recovery.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.get_all_enabled.return_value = [mock_provider]
            mock_factory.return_value = mock_factory_instance

            result = attach_tmux_session("nonexistent")
            assert result is False


# ============================================================
# scanner.py tests
# ============================================================

class TestScanSessions:
    def test_tool_name_not_found(self):
        """Lines 38-39: ValueError branch when tool_name provider not found."""
        from core.scanner import scan_sessions
        with patch("core.scanner.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create.side_effect = ValueError("unknown")
            mock_factory.return_value = mock_factory_instance
            result = scan_sessions(tool_name="nonexistent")
            assert result == []

    def test_provider_scan_exception(self):
        """Lines 47-48: generic Exception branch during provider scan."""
        from core.scanner import scan_sessions
        mock_provider = MagicMock()
        mock_provider.scan_sessions.side_effect = RuntimeError("scan failed")
        mock_provider.tool_info.name = "claude"

        with patch("core.scanner.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.get_all_enabled.return_value = [mock_provider]
            mock_factory.return_value = mock_factory_instance
            result = scan_sessions()
            assert result == []

    def test_successful_scan_single_tool(self):
        from core.scanner import scan_sessions
        mock_session = MagicMock()
        mock_provider = MagicMock()
        mock_provider.scan_sessions.return_value = [mock_session]

        with patch("core.scanner.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create.return_value = mock_provider
            mock_factory.return_value = mock_factory_instance
            result = scan_sessions(tool_name="claude")
            assert len(result) == 1


class TestScanAllSessions:
    def test_delegates_to_scan_sessions(self):
        from core.scanner import scan_all_sessions
        with patch("core.scanner.scan_sessions", return_value=["s1"]) as mock_scan:
            result = scan_all_sessions(tool_name="claude")
            assert result == ["s1"]
            mock_scan.assert_called_once_with("claude", None, force_refresh=True)


class TestScanSessionsByTool:
    def test_delegates_to_scan_sessions(self):
        from core.scanner import scan_sessions_by_tool
        with patch("core.scanner.scan_sessions", return_value=["s1"]) as mock_scan:
            result = scan_sessions_by_tool("claude")
            assert result == ["s1"]
            mock_scan.assert_called_once_with(tool_name="claude")


class TestGetActiveSessions:
    def test_filters_by_status(self):
        from core.scanner import get_active_sessions
        s1 = MagicMock()
        s1.meta.status = "busy"
        s2 = MagicMock()
        s2.meta.status = "idle"
        s3 = MagicMock()
        s3.meta.status = "active"

        with patch("core.scanner.scan_sessions", return_value=[s1, s2, s3]):
            result = get_active_sessions()
            assert len(result) == 2


class TestGetSessionsByProject:
    def test_filters_by_project_name(self):
        from core.scanner import get_sessions_by_project
        s1 = MagicMock()
        s1.project_name = "myproject/frontend"
        s2 = MagicMock()
        s2.project_name = "other/backend"

        with patch("core.scanner.scan_sessions", return_value=[s1, s2]):
            result = get_sessions_by_project("myproject")
            assert len(result) == 1


class TestTranslateTopic:
    def test_empty_topic_returns_default(self):
        from core.scanner import translate_topic
        assert translate_topic("") == "无主题"
        assert translate_topic(None) == "无主题"

    def test_known_keywords_translated(self):
        from core.scanner import translate_topic
        result = translate_topic("Build the payment adapter")
        assert "构建" in result

    def test_no_matching_keywords(self):
        from core.scanner import translate_topic
        assert translate_topic("hello world") == "hello world"


class TestScanRemoteSessions:
    """Line 156: covers scan_remote_sessions delegation."""

    def test_delegates_to_scan_sessions(self):
        from core.scanner import scan_remote_sessions
        mock_host = MagicMock()
        with patch("core.scanner.scan_sessions", return_value=["r1"]) as mock_scan:
            result = scan_remote_sessions(mock_host, tool_name="claude")
            assert result == ["r1"]
            mock_scan.assert_called_once_with(tool_name="claude", host=mock_host)


class TestGetAvailableTools:
    def test_returns_tool_list(self):
        from core.scanner import get_available_tools
        with patch("core.scanner.get_factory") as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.discover_available.return_value = ["claude", "codex"]
            mock_factory.return_value = mock_factory_instance
            result = get_available_tools()
            assert "claude" in result


# ============================================================
# parser.py tests
# ============================================================

class TestParseJsonlFile:
    def test_nonexistent_file(self):
        from core.parser import parse_jsonl_file
        result = list(parse_jsonl_file(Path("/nonexistent/file.jsonl")))
        assert result == []

    def test_blank_lines_skipped(self):
        """Line 17: blank line causes continue."""
        from core.parser import parse_jsonl_file
        with patch.object(Path, "exists", return_value=True):
            import io
            content = '{"a": 1}\n\n{"b": 2}\n'
            with patch("builtins.open", return_value=io.StringIO(content)):
                # parse_jsonl_file opens the file directly, so we need to mock open
                pass
        # Use tmp_path for a real file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"a": 1}\n\n{"b": 2}\n')
            f.flush()
            result = list(parse_jsonl_file(Path(f.name)))
        assert len(result) == 2
        assert result[0] == {"a": 1}
        assert result[1] == {"b": 2}
        import os
        os.unlink(f.name)

    def test_invalid_json_line_skipped(self):
        from core.parser import parse_jsonl_file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"valid": true}\nnot json\n{"also": "valid"}\n')
            f.flush()
            result = list(parse_jsonl_file(Path(f.name)))
        assert len(result) == 2
        import os
        os.unlink(f.name)


class TestFindAiTitle:
    def test_custom_title_type(self):
        """Line 54: custom-title branch."""
        from core.parser import find_ai_title
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "custom-title", "customTitle": "My Custom Title"}\n')
            f.flush()
            result = find_ai_title(Path(f.name))
        assert result == "My Custom Title"
        import os
        os.unlink(f.name)

    def test_ai_title_type(self):
        from core.parser import find_ai_title
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "ai-title", "aiTitle": "AI Generated Title"}\n')
            f.flush()
            result = find_ai_title(Path(f.name))
        assert result == "AI Generated Title"
        import os
        os.unlink(f.name)

    def test_no_title_returns_none(self):
        from core.parser import find_ai_title
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "other"}\n')
            f.flush()
            result = find_ai_title(Path(f.name))
        assert result is None
        import os
        os.unlink(f.name)


class TestFindFirstUserMessage:
    def test_content_as_list(self):
        from core.parser import find_first_user_message
        import tempfile
        event = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello from list"}
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = find_first_user_message(Path(f.name))
        assert result == "Hello from list"
        import os
        os.unlink(f.name)

    def test_content_as_string(self):
        from core.parser import find_first_user_message
        import tempfile
        event = {"type": "user", "message": {"content": "Hello string"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = find_first_user_message(Path(f.name))
        assert result == "Hello string"
        import os
        os.unlink(f.name)

    def test_no_user_message_returns_none(self):
        from core.parser import find_first_user_message
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "other"}\n')
            f.flush()
            result = find_first_user_message(Path(f.name))
        assert result is None
        import os
        os.unlink(f.name)

    def test_long_content_truncated(self):
        from core.parser import find_first_user_message
        import tempfile
        event = {"type": "user", "message": {"content": "x" * 500}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = find_first_user_message(Path(f.name))
        assert len(result) == 200
        import os
        os.unlink(f.name)


class TestGetSessionTasks:
    def test_extracts_tasks(self):
        from core.parser import get_session_tasks
        import tempfile
        event = {
            "type": "TaskCreate",
            "task": {"taskId": "t1", "subject": "Do something", "status": "todo"}
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_session_tasks(Path(f.name))
        assert len(result) == 1
        assert result[0]["id"] == "t1"
        import os
        os.unlink(f.name)


class TestGetJsonlSummary:
    def test_user_event_with_list_content(self):
        """Lines 137-139: user message content as list in get_jsonl_summary."""
        from core.parser import get_jsonl_summary
        import tempfile
        event = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "First message"}
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert result["first_user_message"] == "First message"
        assert result["stats"]["user_messages"] == 1
        import os
        os.unlink(f.name)

    def test_task_create_event(self):
        """Lines 190-191: TaskCreate event extraction in get_jsonl_summary."""
        from core.parser import get_jsonl_summary
        import tempfile
        event = {
            "type": "TaskCreate",
            "task": {"taskId": "t1", "subject": "Fix bug", "status": "done"}
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["id"] == "t1"
        import os
        os.unlink(f.name)

    def test_assistant_event_with_tool_use(self):
        from core.parser import get_jsonl_summary
        import tempfile
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read"},
                    {"type": "tool_use", "name": "Edit"},
                    {"type": "tool_use", "name": "Write"},
                    {"type": "tool_use", "name": "Bash"},
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert result["stats"]["tool_calls"] == 4
        assert result["stats"]["read_count"] == 1
        assert result["stats"]["edit_count"] == 1
        assert result["stats"]["write_count"] == 1
        assert result["stats"]["bash_count"] == 1
        import os
        os.unlink(f.name)

    def test_system_event(self):
        from core.parser import get_jsonl_summary
        import tempfile
        event = {"type": "system", "content": "system msg"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert result["stats"]["system_messages"] == 1
        import os
        os.unlink(f.name)

    def test_codex_format_events(self):
        """Test Codex format (response_item) event processing."""
        from core.parser import get_jsonl_summary
        import tempfile
        event = {
            "type": "response_item",
            "payload": {
                "type": "message",
                "content": [
                    {"type": "input_text", "text": "user input"},
                    {"type": "output_text", "text": "assistant output"},
                    {"type": "tool_call", "id": "tc1"},
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert result["stats"]["user_messages"] == 1
        assert result["stats"]["assistant_messages"] == 1
        assert result["stats"]["tool_calls"] == 1
        assert result["first_user_message"] == "user input"
        import os
        os.unlink(f.name)

    def test_codex_session_meta_cwd(self):
        from core.parser import get_jsonl_summary
        import tempfile
        event = {
            "type": "session_meta",
            "payload": {"cwd": "/home/user/project"}
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert result["cwd"] == "/home/user/project"
        import os
        os.unlink(f.name)

    def test_ai_title_and_custom_title(self):
        from core.parser import get_jsonl_summary
        import tempfile
        events = [
            {"type": "ai-title", "aiTitle": "AI Topic"},
            {"type": "custom-title", "customTitle": "Custom Topic"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        # ai-title comes first, so it should be the topic
        assert result["topic"] == "AI Topic"
        assert result["has_ai_title"] is True
        import os
        os.unlink(f.name)

    def test_cwd_from_event(self):
        from core.parser import get_jsonl_summary
        import tempfile
        event = {"type": "other", "cwd": "/some/cwd"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            result = get_jsonl_summary(Path(f.name))
        assert result["cwd"] == "/some/cwd"
        import os
        os.unlink(f.name)


class TestGetJsonlStats:
    def test_counts_event_types(self):
        from core.parser import get_jsonl_stats
        import tempfile
        events = [
            {"type": "tool_use"},
            {"type": "human"},
            {"type": "assistant"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            f.flush()
            result = get_jsonl_stats(Path(f.name))
        assert result["total_events"] == 3
        assert result["tool_calls"] == 1
        assert result["user_messages"] == 1
        assert result["assistant_messages"] == 1
        import os
        os.unlink(f.name)


# ============================================================
# sqlite_storage.py tests
# ============================================================

@pytest.fixture
def sqlite_storage(tmp_path):
    """Create a SQLiteStorage instance backed by a temporary database."""
    from core.sqlite_storage import SQLiteStorage
    with patch("core.sqlite_storage.get_db_path") as mock_path:
        db_path = tmp_path / "test_sessionflow.db"
        mock_path.return_value = db_path
        storage = SQLiteStorage()
        return storage


class TestSQLiteStorageInit:
    def test_creates_database_file(self, sqlite_storage):
        assert sqlite_storage.db_path.exists()

    def test_tables_created(self, sqlite_storage):
        conn = sqlite_storage._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row['name'] for row in cursor.fetchall()}
        conn.close()
        expected = {"tasks", "notes", "bookmarks", "config", "remote_hosts",
                    "requirements", "requirement_session_links", "archived_sessions",
                    "stats_cache", "remote_sessions_cache"}
        assert expected.issubset(tables)


class TestSQLiteMigration:
    """Lines 198-199: migration adds missing requirement_id column."""

    def test_migration_adds_column_if_missing(self, tmp_path):
        """Simulate a pre-migration database and verify migration adds column."""
        import sqlite3
        db_path = tmp_path / "migrate_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'todo',
                priority TEXT DEFAULT 'medium',
                linked_session_id TEXT,
                progress INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

        from core.sqlite_storage import SQLiteStorage
        with patch("core.sqlite_storage.get_db_path", return_value=db_path):
            storage = SQLiteStorage()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "requirement_id" in columns

    def test_migration_skips_if_column_exists(self, sqlite_storage):
        """When column already exists, migration is a no-op."""
        conn = sqlite_storage._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "requirement_id" in columns


class TestSQLiteTasks:
    def test_save_and_load_tasks(self, sqlite_storage):
        from core.storage import Task
        task = Task(id="t1", title="Test Task", description="desc", status="todo",
                    priority="high", progress=50, created_at=1000, updated_at=2000)
        sqlite_storage.save_tasks([task])
        loaded = sqlite_storage.load_tasks()
        assert len(loaded) == 1
        assert loaded[0].id == "t1"
        assert loaded[0].title == "Test Task"

    def test_save_replaces_all(self, sqlite_storage):
        from core.storage import Task
        t1 = Task(id="t1", title="Task 1", created_at=1000, updated_at=1000)
        t2 = Task(id="t2", title="Task 2", created_at=2000, updated_at=2000)
        sqlite_storage.save_tasks([t1, t2])
        sqlite_storage.save_tasks([t1])
        loaded = sqlite_storage.load_tasks()
        assert len(loaded) == 1


class TestSQLiteNotes:
    def test_save_and_load_notes(self, sqlite_storage):
        from core.storage import SessionNote
        note = SessionNote(session_id="s1", text="hello", tags=["tag1", "tag2"],
                           bookmark=True, created_at=1000, updated_at=2000)
        sqlite_storage.save_notes({"s1": note})
        loaded = sqlite_storage.load_notes()
        assert "s1" in loaded
        assert loaded["s1"].text == "hello"
        assert loaded["s1"].tags == ["tag1", "tag2"]
        assert loaded["s1"].bookmark  # SQLite stores as 0/1 int

    def test_empty_tags(self, sqlite_storage):
        from core.storage import SessionNote
        note = SessionNote(session_id="s2", text="no tags", tags=[])
        sqlite_storage.save_notes({"s2": note})
        loaded = sqlite_storage.load_notes()
        assert loaded["s2"].tags == []


class TestSQLiteBookmarks:
    def test_save_and_load_bookmarks(self, sqlite_storage):
        sqlite_storage.save_bookmarks(["s1", "s2", "s3"])
        loaded = sqlite_storage.load_bookmarks()
        assert loaded == ["s1", "s2", "s3"]


class TestSQLiteConfig:
    def test_save_and_load_config(self, sqlite_storage):
        config = {"theme": "dark", "count": 42, "enabled": True}
        sqlite_storage.save_config(config)
        loaded = sqlite_storage.load_config()
        assert loaded["theme"] == "dark"
        assert loaded["count"] == 42
        assert loaded["enabled"] is True

    def test_string_value_loaded_directly(self, sqlite_storage):
        """Config values that are plain strings are loaded as-is (not JSON parsed)."""
        config = {"key": "simple_string"}
        sqlite_storage.save_config(config)
        loaded = sqlite_storage.load_config()
        assert loaded["key"] == "simple_string"


class TestSQLiteRemoteHosts:
    def test_crud_operations(self, sqlite_storage):
        from core.storage import RemoteHostConfig
        host = RemoteHostConfig(
            id="h1", name="server1", hostname="192.168.1.1",
            user="admin", ssh_alias="srv1"
        )
        sqlite_storage.add_remote_host(host)

        loaded = sqlite_storage.get_remote_host("h1")
        assert loaded is not None
        assert loaded.name == "server1"

        all_hosts = sqlite_storage.load_remote_hosts()
        assert len(all_hosts) == 1

        removed = sqlite_storage.remove_remote_host("h1")
        assert removed is True
        assert sqlite_storage.get_remote_host("h1") is None

    def test_remove_nonexistent_host(self, sqlite_storage):
        assert sqlite_storage.remove_remote_host("nonexistent") is False

    def test_get_nonexistent_host(self, sqlite_storage):
        assert sqlite_storage.get_remote_host("nonexistent") is None


class TestSQLiteRequirements:
    def test_crud_operations(self, sqlite_storage):
        from core.storage import Requirement
        req = Requirement(id="REQ-001", title="Build feature X", description="desc",
                          category="feature", status="draft", priority="p1",
                          tags=["frontend"], work_dirs=["/src"], created_at=1000, updated_at=2000)
        sqlite_storage.save_requirements([req])

        loaded = sqlite_storage.load_requirements()
        assert len(loaded) == 1
        assert loaded[0].id == "REQ-001"
        assert loaded[0].tags == ["frontend"]

        found = sqlite_storage.get_requirement("REQ-001")
        assert found is not None
        assert found.title == "Build feature X"

        not_found = sqlite_storage.get_requirement("REQ-999")
        assert not_found is None

    def test_update_requirement(self, sqlite_storage):
        """Line 428: covers the return False path when req not found."""
        from core.storage import Requirement
        req = Requirement(id="REQ-001", title="Original", created_at=1000, updated_at=1000)
        sqlite_storage.save_requirements([req])

        result = sqlite_storage.update_requirement("REQ-001", title="Updated")
        assert result is True
        assert sqlite_storage.get_requirement("REQ-001").title == "Updated"

    def test_update_requirement_not_found(self, sqlite_storage):
        """Line 428: return False when requirement not found."""
        result = sqlite_storage.update_requirement("REQ-999", title="Nope")
        assert result is False

    def test_remove_requirement(self, sqlite_storage):
        from core.storage import Requirement
        req = Requirement(id="REQ-001", title="To remove", created_at=1000, updated_at=1000)
        sqlite_storage.save_requirements([req])

        result = sqlite_storage.remove_requirement("REQ-001")
        assert result is True
        assert sqlite_storage.get_requirement("REQ-001") is None

    def test_remove_requirement_not_found(self, sqlite_storage):
        """Line 435: return False when requirement not found."""
        result = sqlite_storage.remove_requirement("REQ-999")
        assert result is False

    def test_remove_requirement_cleans_links(self, sqlite_storage):
        from core.storage import Requirement, RequirementSessionLink
        req = Requirement(id="REQ-001", title="Req with link", created_at=1000, updated_at=1000)
        sqlite_storage.save_requirements([req])
        link = RequirementSessionLink(
            requirement_id="REQ-001", session_id="s1", role="primary",
            linked_at=1000, notes=""
        )
        sqlite_storage.save_requirement_links([link])

        sqlite_storage.remove_requirement("REQ-001")
        remaining_links = sqlite_storage.load_requirement_links()
        assert len(remaining_links) == 0

    def test_add_requirement(self, sqlite_storage):
        from core.storage import Requirement
        req = Requirement(id="REQ-001", title="Added", created_at=1000, updated_at=1000)
        sqlite_storage.add_requirement(req)
        assert sqlite_storage.get_requirement("REQ-001") is not None


class TestSQLiteRequirementLinks:
    def test_save_load_links(self, sqlite_storage):
        from core.storage import RequirementSessionLink
        link = RequirementSessionLink(
            requirement_id="REQ-001", session_id="s1", role="primary",
            linked_at=1000, notes="test"
        )
        sqlite_storage.save_requirement_links([link])
        loaded = sqlite_storage.load_requirement_links()
        assert len(loaded) == 1
        assert loaded[0].session_id == "s1"

    def test_link_session_to_requirement(self, sqlite_storage):
        from core.storage import RequirementSessionLink
        link = RequirementSessionLink(
            requirement_id="REQ-001", session_id="s1", role="primary",
            linked_at=1000
        )
        sqlite_storage.link_session_to_requirement(link)
        found = sqlite_storage.get_session_requirement("s1")
        assert found is not None
        assert found.requirement_id == "REQ-001"

    def test_link_session_replaces_existing(self, sqlite_storage):
        from core.storage import RequirementSessionLink
        link1 = RequirementSessionLink(requirement_id="REQ-001", session_id="s1", role="primary", linked_at=1000)
        link2 = RequirementSessionLink(requirement_id="REQ-002", session_id="s1", role="secondary", linked_at=2000)
        sqlite_storage.link_session_to_requirement(link1)
        sqlite_storage.link_session_to_requirement(link2)
        found = sqlite_storage.get_session_requirement("s1")
        assert found.requirement_id == "REQ-002"

    def test_unlink_session(self, sqlite_storage):
        from core.storage import RequirementSessionLink
        link = RequirementSessionLink(requirement_id="REQ-001", session_id="s1", linked_at=1000)
        sqlite_storage.link_session_to_requirement(link)
        result = sqlite_storage.unlink_session("s1")
        assert result is True
        assert sqlite_storage.get_session_requirement("s1") is None

    def test_unlink_nonexistent(self, sqlite_storage):
        result = sqlite_storage.unlink_session("nonexistent")
        assert result is False

    def test_get_requirement_sessions(self, sqlite_storage):
        from core.storage import RequirementSessionLink
        links = [
            RequirementSessionLink(requirement_id="REQ-001", session_id="s1", linked_at=1000),
            RequirementSessionLink(requirement_id="REQ-001", session_id="s2", linked_at=2000),
            RequirementSessionLink(requirement_id="REQ-002", session_id="s3", linked_at=3000),
        ]
        sqlite_storage.save_requirement_links(links)
        result = sqlite_storage.get_requirement_sessions("REQ-001")
        assert len(result) == 2


class TestSQLiteArchivedSessions:
    def test_archive_and_restore(self, sqlite_storage):
        archived = sqlite_storage.archive_session(
            "s1", "archived", insight="learned stuff", project_name="proj", topic="test", reason="done"
        )
        assert archived.session_id == "s1"

        found = sqlite_storage.get_archived_session("s1")
        assert found is not None
        assert found.insight == "learned stuff"

        result = sqlite_storage.restore_session("s1")
        assert result is True
        assert sqlite_storage.get_archived_session("s1") is None

    def test_restore_nonexistent(self, sqlite_storage):
        result = sqlite_storage.restore_session("nonexistent")
        assert result is False

    def test_archive_updates_existing(self, sqlite_storage):
        sqlite_storage.archive_session("s1", "archived", insight="first")
        sqlite_storage.archive_session("s1", "trash", reason="moved to trash")
        found = sqlite_storage.get_archived_session("s1")
        assert found.archive_type == "trash"
        assert found.reason == "moved to trash"

    def test_get_archived_by_type(self, sqlite_storage):
        sqlite_storage.archive_session("s1", "archived")
        sqlite_storage.archive_session("s2", "trash")
        sqlite_storage.archive_session("s3", "archived")

        archived = sqlite_storage.get_archived_by_type("archived")
        assert len(archived) == 2
        trash = sqlite_storage.get_archived_by_type("trash")
        assert len(trash) == 1

    def test_delete_trash_session(self, sqlite_storage):
        sqlite_storage.archive_session("s1", "trash")
        result = sqlite_storage.delete_trash_session("s1")
        assert result is True
        assert sqlite_storage.get_archived_session("s1") is None

    def test_delete_trash_session_nonexistent(self, sqlite_storage):
        result = sqlite_storage.delete_trash_session("nonexistent")
        assert result is False

    def test_delete_trash_only_affects_trash_type(self, sqlite_storage):
        sqlite_storage.archive_session("s1", "archived")
        result = sqlite_storage.delete_trash_session("s1")
        assert result is False
        assert sqlite_storage.get_archived_session("s1") is not None

    def test_save_and_load_archived_sessions(self, sqlite_storage):
        from core.storage import ArchivedSession
        sessions = [
            ArchivedSession(session_id="s1", archive_type="archived", archived_at=1000, insight="i1", project_name="p1", topic="t1", reason="r1"),
            ArchivedSession(session_id="s2", archive_type="trash", archived_at=2000, insight="i2", project_name="p2", topic="t2", reason="r2"),
        ]
        sqlite_storage.save_archived_sessions(sessions)
        loaded = sqlite_storage.load_archived_sessions()
        assert len(loaded) == 2


class TestSQLiteStatsCache:
    def test_update_and_get(self, sqlite_storage):
        stats = {"total_events": 10, "tool_calls": 5}
        sqlite_storage.update_stats_cache("s1", stats)
        cached = sqlite_storage.get_cached_stats("s1")
        assert cached == stats

    def test_cache_miss(self, sqlite_storage):
        assert sqlite_storage.get_cached_stats("nonexistent") is None

    def test_expired_cache_returns_none(self, sqlite_storage):
        """Line 643: expired cache TTL check."""
        import time
        stats = {"count": 1}
        # Manually insert with old timestamp
        conn = sqlite_storage._get_conn()
        cursor = conn.cursor()
        old_time = time.time() - 100000  # well over 24h ago
        cursor.execute(
            "INSERT INTO stats_cache (session_id, stats, cached_at) VALUES (?, ?, ?)",
            ("s_old", json.dumps(stats), old_time)
        )
        conn.commit()
        conn.close()

        result = sqlite_storage.get_cached_stats("s_old")
        assert result is None

    def test_save_and_load_stats_cache(self, sqlite_storage):
        cache = {
            "s1": {"stats": {"count": 1}, "cached_at": 1000.0},
            "s2": {"stats": {"count": 2}, "cached_at": 2000.0},
        }
        sqlite_storage.save_stats_cache(cache)
        loaded = sqlite_storage.load_stats_cache()
        assert len(loaded) == 2
        assert loaded["s1"]["stats"]["count"] == 1


class TestSQLiteRemoteSessionsCache:
    """Lines 665-696: remote sessions cache methods."""

    def test_save_and_get(self, sqlite_storage):
        sessions = [{"id": "s1", "name": "session1"}]
        sqlite_storage.save_cached_remote_sessions("host1", sessions)
        cached = sqlite_storage.get_cached_remote_sessions("host1")
        assert cached == sessions

    def test_cache_miss(self, sqlite_storage):
        assert sqlite_storage.get_cached_remote_sessions("nonexistent") is None

    def test_expired_cache_returns_none(self, sqlite_storage):
        """Remote sessions cache TTL expiry."""
        import time
        sessions = [{"id": "s1"}]
        conn = sqlite_storage._get_conn()
        cursor = conn.cursor()
        old_time = time.time() - 100000
        cursor.execute(
            "INSERT INTO remote_sessions_cache (host_id, sessions, cached_at) VALUES (?, ?, ?)",
            ("host_old", json.dumps(sessions), old_time)
        )
        conn.commit()
        conn.close()

        result = sqlite_storage.get_cached_remote_sessions("host_old")
        assert result is None

    def test_clear_cache(self, sqlite_storage):
        sqlite_storage.save_cached_remote_sessions("host1", [{"id": "s1"}])
        sqlite_storage.clear_remote_sessions_cache("host1")
        assert sqlite_storage.get_cached_remote_sessions("host1") is None

    def test_clear_nonexistent_cache(self, sqlite_storage):
        """Clearing a nonexistent cache is a no-op."""
        sqlite_storage.clear_remote_sessions_cache("nonexistent")
        # Should not raise

    def test_overwrite_existing_cache(self, sqlite_storage):
        sqlite_storage.save_cached_remote_sessions("host1", [{"id": "s1"}])
        sqlite_storage.save_cached_remote_sessions("host1", [{"id": "s2"}, {"id": "s3"}])
        cached = sqlite_storage.get_cached_remote_sessions("host1")
        assert len(cached) == 2


class TestSQLiteMigrateFromJson:
    """Lines 703-748: migrate_from_json method."""

    def test_migrate_tasks(self, sqlite_storage):
        from core.storage import Task
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = [
            Task(id="t1", title="Migrated Task", created_at=1000, updated_at=1000)
        ]
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        tasks = sqlite_storage.load_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "Migrated Task"

    def test_migrate_notes(self, sqlite_storage):
        from core.storage import SessionNote
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {
            "s1": SessionNote(session_id="s1", text="note text", tags=["a"])
        }
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        notes = sqlite_storage.load_notes()
        assert "s1" in notes
        assert notes["s1"].text == "note text"

    def test_migrate_bookmarks(self, sqlite_storage):
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = ["s1", "s2"]
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        bookmarks = sqlite_storage.load_bookmarks()
        assert bookmarks == ["s1", "s2"]

    def test_migrate_config(self, sqlite_storage):
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {"theme": "dark", "lang": "zh"}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        config = sqlite_storage.load_config()
        assert config["theme"] == "dark"

    def test_migrate_remote_hosts(self, sqlite_storage):
        from core.storage import RemoteHostConfig
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = [
            RemoteHostConfig(id="h1", name="server", hostname="1.2.3.4", user="admin")
        ]
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        hosts = sqlite_storage.load_remote_hosts()
        assert len(hosts) == 1
        assert hosts[0].name == "server"

    def test_migrate_requirements(self, sqlite_storage):
        from core.storage import Requirement
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = [
            Requirement(id="REQ-001", title="Migrated Req", tags=["t1"], work_dirs=["/src"])
        ]
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        reqs = sqlite_storage.load_requirements()
        assert len(reqs) == 1
        assert reqs[0].title == "Migrated Req"
        assert reqs[0].tags == ["t1"]

    def test_migrate_requirement_links(self, sqlite_storage):
        from core.storage import RequirementSessionLink
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = [
            RequirementSessionLink(requirement_id="REQ-001", session_id="s1", role="primary", linked_at=1000)
        ]
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        links = sqlite_storage.load_requirement_links()
        assert len(links) == 1
        assert links[0].session_id == "s1"

    def test_migrate_archived_sessions(self, sqlite_storage):
        from core.storage import ArchivedSession
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = [
            ArchivedSession(session_id="s1", archive_type="archived", archived_at=1000, insight="done")
        ]
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        archived = sqlite_storage.load_archived_sessions()
        assert len(archived) == 1
        assert archived[0].session_id == "s1"

    def test_migrate_stats_cache(self, sqlite_storage):
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {
            "s1": {"stats": {"count": 42}, "cached_at": 1000.0}
        }

        sqlite_storage.migrate_from_json(mock_json)

        cached = sqlite_storage.get_cached_stats("s1")
        # Stats may be expired if cached_at is in the past, but save_stats_cache was called
        # Let's check the raw DB instead
        conn = sqlite_storage._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT stats FROM stats_cache WHERE session_id = 's1'")
        row = cursor.fetchone()
        conn.close()
        assert row is not None

    def test_migrate_stats_cache_exception(self, sqlite_storage):
        """Line 747-748: exception in load_stats_cache is caught silently."""
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.side_effect = Exception("no stats cache method")

        # Should not raise
        sqlite_storage.migrate_from_json(mock_json)

    def test_migrate_empty_data(self, sqlite_storage):
        """Migration with empty data is a no-op (no data written)."""
        mock_json = MagicMock()
        mock_json.load_tasks.return_value = []
        mock_json.load_notes.return_value = {}
        mock_json.load_bookmarks.return_value = []
        mock_json.load_config.return_value = {}
        mock_json.load_remote_hosts.return_value = []
        mock_json.load_requirements.return_value = []
        mock_json.load_requirement_links.return_value = []
        mock_json.load_archived_sessions.return_value = []
        mock_json.load_stats_cache.return_value = {}

        sqlite_storage.migrate_from_json(mock_json)

        assert sqlite_storage.load_tasks() == []
        assert sqlite_storage.load_bookmarks() == []
        assert sqlite_storage.load_remote_hosts() == []
        assert sqlite_storage.load_archived_sessions() == []


class TestGetDbPath:
    def test_creates_storage_dir(self, tmp_path):
        """get_db_path creates the storage directory if it doesn't exist."""
        from core.sqlite_storage import get_db_path
        target_dir = tmp_path / "nonexistent"
        with patch("core.storage.STORAGE_DIR", target_dir):
            result = get_db_path()
            assert result.parent.exists()
            assert result.name == "sessionflow.db"
