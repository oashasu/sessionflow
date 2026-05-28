"""CLI命令额外测试 - 覆盖cli_main.py中未测试的命令路径"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from argparse import Namespace
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入cli.main模块（避免被__init__.py中的main函数遮蔽）
import importlib
cli_main = importlib.import_module('cli.main')
from core import (
    Task, SessionNote, Requirement, RequirementSessionLink,
    ArchivedSession, RemoteHostConfig,
)
from core.errors import SessionNotFoundError, MultipleMatchError


@pytest.fixture(autouse=True)
def _restore_rich_state():
    """保存并恢复USE_RICH和console状态，防止测试污染"""
    orig_rich = cli_main.USE_RICH
    orig_console = cli_main.console
    yield
    cli_main.USE_RICH = orig_rich
    cli_main.console = orig_console


# ========== Fixtures ==========

def _make_session(session_id="test-sess-001", project="proj", status="idle",
                  topic="topic", log_path=None, duration=120, cwd="/tmp/proj"):
    """创建mock session"""
    s = MagicMock()
    s.meta.session_id = session_id
    s.meta.status = status
    s.meta.updated_at = 1000
    s.meta.cwd = cwd
    s.project_name = project
    s.topic = topic
    s.log_path = log_path
    s.duration_seconds = duration
    s.short_id = session_id[:8]
    s.recovery_cmd = f"claude --resume {session_id}"
    return s


def _make_args(**kwargs):
    """创建Namespace参数"""
    defaults = {
        "all": False, "limit": 50, "project": None, "status": None,
        "tool": "all", "verbose": False, "remote": False, "host_id": None,
        "session_id": "test-sess-001", "select_first": False, "copy": False,
        "text": None, "tags": None, "clear": False, "task_cmd": "list",
        "task_id": None, "task_id_pos": None, "title": None, "session": None,
        "priority": None, "field": None, "value": None, "set_progress": None,
        "bookmark_cmd": "list", "host_cmd": "list", "req_cmd": "list",
        "req_id": None, "title_explicit": None, "category": None,
        "description": None, "work_dirs": None, "insight": None,
        "reason": None, "force": False, "name": None, "hostname": None,
        "user": "claude", "alias": None, "role": None, "notes": None,
        "lines": 50, "list": False,
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


# ========== find_session 测试 ==========

class TestFindSession:
    """测试find_session函数"""

    def test_exact_match(self):
        session = _make_session("abc-123-def")
        result = cli_main.find_session("abc-123-def", [session])
        assert result is session

    def test_prefix_match_single(self):
        session = _make_session("abcdefgh-1234-5678")
        result = cli_main.find_session("abcdefgh", [session])
        assert result is session

    def test_prefix_match_multiple_select_first(self):
        s1 = _make_session("abcdefgh-1111")
        s2 = _make_session("abcdefgh-2222")
        result = cli_main.find_session("abcdefgh", [s1, s2], select_first=True)
        assert result is s1

    def test_prefix_match_multiple_no_select(self):
        s1 = _make_session("abcdefgh-1111")
        s2 = _make_session("abcdefgh-2222")
        with pytest.raises(MultipleMatchError):
            cli_main.find_session("abcdefgh", [s1, s2])

    def test_not_found(self):
        session = _make_session("abc-123")
        with pytest.raises(SessionNotFoundError):
            cli_main.find_session("zzz", [session])

    def test_short_id_below_4_chars(self):
        """少于4位不做前缀匹配"""
        session = _make_session("abcdefgh-1234")
        with pytest.raises(SessionNotFoundError):
            cli_main.find_session("abc", [session])


# ========== print_table 测试 ==========

class TestPrintTable:
    """测试print_table函数"""

    def test_plain_text_output(self, capsys):
        cli_main.USE_RICH = False
        cli_main.console = None
        cli_main.print_table("Title", [["a", "b"]], ["H1", "H2"])
        out = capsys.readouterr().out
        assert "Title" in out
        assert "H1" in out
        assert "a" in out


# ========== cmd_scan 测试 ==========

class TestCmdScan:
    """测试cmd_scan"""

    @patch("cli.main.scan_sessions")
    def test_scan_active(self, mock_scan, capsys):
        mock_scan.return_value = [_make_session()]
        args = _make_args(all=False, limit=20)
        cli_main.cmd_scan(args)
        out = capsys.readouterr().out
        assert "扫描完成" in out
        assert "活跃" in out

    @patch("cli.main.scan_all_sessions")
    def test_scan_all(self, mock_scan, capsys):
        mock_scan.return_value = [_make_session(), _make_session("s2")]
        args = _make_args(all=True, limit=20)
        cli_main.cmd_scan(args)
        out = capsys.readouterr().out
        assert "含历史" in out


# ========== cmd_status 测试 ==========

class TestCmdStatus:
    """测试cmd_status"""

    @patch("cli.main.SessionService")
    def test_no_active_sessions(self, mock_service_class, capsys):
        mock_service = mock_service_class.return_value
        mock_service.get_active.return_value = []
        args = _make_args()
        cli_main.cmd_status(args)
        out = capsys.readouterr().out
        assert "当前无活跃会话" in out

    @patch("cli.main.SessionService")
    def test_with_active_sessions(self, mock_service_class, capsys):
        mock_service = mock_service_class.return_value
        mock_service.get_active.return_value = [
            {'short_id': 'test-id', 'project_name': 'test/project'}
        ]
        args = _make_args()
        cli_main.cmd_status(args)
        out = capsys.readouterr().out
        assert "当前活跃会话" in out


# ========== cmd_recover 测试 ==========

class TestCmdRecover:
    """测试cmd_recover"""

    @patch("cli.main.scan_sessions")
    @patch("cli.main.generate_recovery_cmd", return_value="claude --resume abc")
    def test_recover_all(self, mock_gen, mock_scan, capsys):
        mock_scan.return_value = [_make_session()]
        args = _make_args(session_id=None, limit=10)
        cli_main.cmd_recover(args)
        out = capsys.readouterr().out
        assert "所有会话恢复链接" in out

    @patch("cli.main.scan_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.generate_recovery_cmd", return_value="claude --resume abc")
    def test_recover_specific(self, mock_gen, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        args = _make_args(session_id="test-sess", limit=10)
        cli_main.cmd_recover(args)
        out = capsys.readouterr().out
        assert "claude --resume" in out

    @patch("cli.main.scan_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("bad"))
    def test_recover_not_found(self, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        args = _make_args(session_id="bad", limit=10)
        result = cli_main.cmd_recover(args)
        assert result == 1


# ========== cmd_view 测试 ==========

class TestCmdView:
    """测试cmd_view"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    def test_not_found(self, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        args = _make_args(session_id="x")
        result = cli_main.cmd_view(args)
        assert result == 1

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_no_log_path(self, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path=None)
        mock_scan.return_value = [_make_session()]
        args = _make_args()
        cli_main.cmd_view(args)
        out = capsys.readouterr().out
        assert "没有对话历史记录" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.parse_jsonl_file")
    def test_user_event_string_content(self, mock_parse, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/test.jsonl")
        mock_scan.return_value = [_make_session()]
        mock_parse.return_value = [
            {"type": "user", "message": {"content": "hello world"}},
        ]
        args = _make_args(lines=10)
        cli_main.cmd_view(args)
        out = capsys.readouterr().out
        assert "用户: hello world" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.parse_jsonl_file")
    def test_user_event_list_content(self, mock_parse, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/test.jsonl")
        mock_scan.return_value = [_make_session()]
        mock_parse.return_value = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "list content"}]}},
        ]
        args = _make_args(lines=10)
        cli_main.cmd_view(args)
        out = capsys.readouterr().out
        assert "list content" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.parse_jsonl_file")
    def test_assistant_text_event(self, mock_parse, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/test.jsonl")
        mock_scan.return_value = [_make_session()]
        mock_parse.return_value = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "reply"}]}},
        ]
        args = _make_args(lines=10)
        cli_main.cmd_view(args)
        out = capsys.readouterr().out
        assert "Claude: reply" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.parse_jsonl_file")
    def test_assistant_tool_use_event(self, mock_parse, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/test.jsonl")
        mock_scan.return_value = [_make_session()]
        mock_parse.return_value = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
        ]
        args = _make_args(lines=10)
        cli_main.cmd_view(args)
        out = capsys.readouterr().out
        assert "工具: Bash" in out


# ========== cmd_tasks 测试 ==========

class TestCmdTasks:
    """测试cmd_tasks"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    def test_not_found(self, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_tasks(_make_args())
        assert result == 1

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_no_log_path(self, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path=None)
        mock_scan.return_value = []
        cli_main.cmd_tasks(_make_args())
        out = capsys.readouterr().out
        assert "没有任务记录" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_session_tasks")
    def test_no_tasks(self, mock_tasks, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/t.jsonl")
        mock_scan.return_value = []
        mock_tasks.return_value = []
        cli_main.cmd_tasks(_make_args())
        out = capsys.readouterr().out
        assert "没有任务" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_session_tasks")
    def test_with_tasks(self, mock_tasks, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/t.jsonl")
        mock_scan.return_value = []
        mock_tasks.return_value = [
            {"status": "done", "subject": "task1"},
            {"status": "in_progress", "subject": "task2"},
            {"status": "pending", "subject": "task3"},
        ]
        cli_main.cmd_tasks(_make_args())
        out = capsys.readouterr().out
        assert "[x]" in out
        assert "[~]" in out
        assert "[ ]" in out


# ========== cmd_stats 测试 ==========

class TestCmdStats:
    """测试cmd_stats"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    def test_not_found(self, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_stats(_make_args())
        assert result == 1

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_no_log_path(self, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path=None)
        mock_scan.return_value = []
        cli_main.cmd_stats(_make_args())
        out = capsys.readouterr().out
        assert "没有统计数据" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_jsonl_summary")
    def test_plain_output(self, mock_summary, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session(log_path="/tmp/t.jsonl")
        mock_scan.return_value = []
        mock_summary.return_value = {
            "stats": {
                "total_events": 100, "user_messages": 30, "assistant_messages": 40,
                "tool_calls": 50, "read_count": 10, "edit_count": 5,
                "write_count": 3, "bash_count": 2,
            }
        }
        cli_main.USE_RICH = False
        cli_main.console = None
        cli_main.cmd_stats(_make_args())
        out = capsys.readouterr().out
        assert "总事件数: 100" in out
        assert "用户消息: 30" in out


# ========== cmd_note 测试 ==========

class TestCmdNote:
    """测试cmd_note"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    @patch("cli.main.get_storage")
    def test_not_found(self, mock_store, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_note(_make_args())
        assert result == 1

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_add_note(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_notes.return_value = {}
        mock_store.return_value = storage
        args = _make_args(text="my note", tags="tag1,tag2")
        cli_main.cmd_note(args)
        out = capsys.readouterr().out
        assert "已为会话" in out
        storage.save_notes.assert_called_once()

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_clear_note_exists(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_notes.return_value = {"test-sess-001": MagicMock()}
        mock_store.return_value = storage
        args = _make_args(clear=True)
        cli_main.cmd_note(args)
        out = capsys.readouterr().out
        assert "已清除" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_clear_note_not_exists(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_notes.return_value = {}
        mock_store.return_value = storage
        args = _make_args(clear=True)
        cli_main.cmd_note(args)
        out = capsys.readouterr().out
        assert "没有备注" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_show_note(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        note = MagicMock()
        note.text = "test note"
        note.tags = ["t1", "t2"]
        storage = MagicMock()
        storage.load_notes.return_value = {"test-sess-001": note}
        mock_store.return_value = storage
        cli_main.cmd_note(_make_args())
        out = capsys.readouterr().out
        assert "test note" in out
        assert "t1" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_show_note_no_tags(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        note = MagicMock()
        note.text = "test"
        note.tags = None
        storage = MagicMock()
        storage.load_notes.return_value = {"test-sess-001": note}
        mock_store.return_value = storage
        cli_main.cmd_note(_make_args())
        out = capsys.readouterr().out
        assert "test" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_show_no_note(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_notes.return_value = {}
        mock_store.return_value = storage
        cli_main.cmd_note(_make_args())
        out = capsys.readouterr().out
        assert "没有备注" in out


# ========== cmd_task 测试 ==========

class TestCmdTask:
    """测试cmd_task"""

    @patch("cli.main.get_storage")
    def test_add_task(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_cmd="add", title="new task", priority="high")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已创建任务" in out
        storage.save_tasks.assert_called_once()

    @patch("cli.main.get_storage")
    def test_add_task_with_session(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        with patch("cli.main.scan_all_sessions") as mock_scan, \
             patch("cli.main.find_session") as mock_find:
            mock_find.return_value = _make_session()
            args = _make_args(task_cmd="add", title="task", session="test-sess")
            cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已创建任务" in out

    @patch("cli.main.get_storage")
    def test_add_task_session_not_found(self, mock_store):
        storage = MagicMock()
        mock_store.return_value = storage
        with patch("cli.main.scan_all_sessions") as mock_scan, \
             patch("cli.main.find_session", side_effect=SessionNotFoundError("x")):
            args = _make_args(task_cmd="add", title="task", session="bad")
            result = cli_main.cmd_task(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_list_tasks(self, mock_store, capsys):
        task = Task.create("test", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="list")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "任务列表" in out

    @patch("cli.main.get_storage")
    def test_list_tasks_filter_by_session(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        task.linked_session_id = "sess-123"
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="list", session="sess")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "任务列表" in out

    @patch("cli.main.get_storage")
    def test_list_tasks_filter_by_status(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        task.status = "done"
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="list", status="done")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "任务列表" in out

    @patch("cli.main.get_storage")
    def test_edit_task(self, mock_store, capsys):
        task = Task.create("old title", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="edit", task_id=task.id, field="title", value="new title")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已更新任务" in out

    @patch("cli.main.get_storage")
    def test_edit_task_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_cmd="edit", task_id="nonexist", field="title", value="v")
        result = cli_main.cmd_task(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_edit_task_description(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="edit", task_id=task.id, field="description", value="desc")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已更新" in out

    @patch("cli.main.get_storage")
    def test_edit_task_status(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="edit", task_id=task.id, field="status", value="done")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已更新" in out

    @patch("cli.main.get_storage")
    def test_edit_task_priority(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="edit", task_id=task.id, field="priority", value="high")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已更新" in out

    @patch("cli.main.get_storage")
    def test_edit_task_progress(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="edit", task_id=task.id, field="progress", value="50")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已更新" in out

    @patch("cli.main.get_storage")
    def test_done_task(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="done", task_id=task.id)
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已完成" in out

    @patch("cli.main.get_storage")
    def test_done_task_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_cmd="done", task_id="nonexist")
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "未找到" in out

    @patch("cli.main.get_storage")
    def test_delete_task(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_cmd="delete", task_id=task.id)
        cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已删除" in out

    @patch("cli.main.get_storage")
    def test_delete_task_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_cmd="delete", task_id="nonexist")
        result = cli_main.cmd_task(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_link_task(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        with patch("cli.main.scan_all_sessions") as mock_scan, \
             patch("cli.main.find_session") as mock_find:
            mock_find.return_value = _make_session()
            args = _make_args(task_cmd="link", task_id=task.id, session_id="test-sess")
            cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "已将任务" in out

    @patch("cli.main.get_storage")
    def test_link_task_session_not_found(self, mock_store):
        storage = MagicMock()
        mock_store.return_value = storage
        with patch("cli.main.scan_all_sessions") as mock_scan, \
             patch("cli.main.find_session", side_effect=SessionNotFoundError("x")):
            args = _make_args(task_cmd="link", task_id="t", session_id="bad")
            result = cli_main.cmd_task(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_link_task_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        with patch("cli.main.scan_all_sessions") as mock_scan, \
             patch("cli.main.find_session") as mock_find:
            mock_find.return_value = _make_session()
            args = _make_args(task_cmd="link", task_id="nonexist", session_id="test-sess")
            cli_main.cmd_task(args)
        out = capsys.readouterr().out
        assert "未找到" in out


# ========== cmd_progress 测试 ==========

class TestCmdProgress:
    """测试cmd_progress"""

    @patch("cli.main.get_storage")
    def test_show_single_task(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        task.progress = 50
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_id=task.id, set_progress=None)
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "50%" in out

    @patch("cli.main.get_storage")
    def test_show_single_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_id="nonexist", set_progress=None)
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "未找到" in out

    @patch("cli.main.get_storage")
    def test_set_progress(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_id=None, set_progress=[task.id, "75"])
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "已设置" in out
        assert "75%" in out

    @patch("cli.main.get_storage")
    def test_set_progress_100_marks_done(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_id=None, set_progress=[task.id, "100"])
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "100%" in out

    @patch("cli.main.get_storage")
    def test_set_progress_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_id=None, set_progress=["nonexist", "50"])
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "未找到" in out

    @patch("cli.main.get_storage")
    def test_show_all_progress(self, mock_store, capsys):
        task = Task.create("t", priority="medium")
        task.progress = 30
        storage = MagicMock()
        storage.load_tasks.return_value = [task]
        mock_store.return_value = storage
        args = _make_args(task_id=None, set_progress=None)
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "进度概览" in out
        assert "平均进度" in out

    @patch("cli.main.get_storage")
    def test_show_all_no_tasks(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_tasks.return_value = []
        mock_store.return_value = storage
        args = _make_args(task_id=None, set_progress=None)
        cli_main.cmd_progress(args)
        out = capsys.readouterr().out
        assert "没有任务" in out


# ========== cmd_bookmark 测试 ==========

class TestCmdBookmark:
    """测试cmd_bookmark"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_add_bookmark(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_bookmarks.return_value = []
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="add", session_id="test-sess")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "已收藏" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_add_bookmark_already_exists(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_bookmarks.return_value = ["test-sess-001"]
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="add", session_id="test-sess")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "已在收藏列表中" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    @patch("cli.main.get_storage")
    def test_add_bookmark_not_found(self, mock_store, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        args = _make_args(bookmark_cmd="add", session_id="bad")
        result = cli_main.cmd_bookmark(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_remove_bookmark(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_bookmarks.return_value = ["test-sess-001"]
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="remove", session_id="test-sess")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "已移除收藏" in out

    @patch("cli.main.get_storage")
    def test_remove_bookmark_not_in_list(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_bookmarks.return_value = ["other-sess"]
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="remove", session_id="test-sess")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "未在收藏列表中" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.get_storage")
    def test_list_bookmarks_empty(self, mock_store, mock_scan, capsys):
        mock_scan.return_value = []
        storage = MagicMock()
        storage.load_bookmarks.return_value = []
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="list")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "收藏列表为空" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.get_storage")
    def test_list_bookmarks_with_expired(self, mock_store, mock_scan, capsys):
        mock_scan.return_value = []  # no sessions found = expired
        storage = MagicMock()
        storage.load_bookmarks.return_value = ["expired-sess-123"]
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="list")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "已过期" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.get_storage")
    def test_list_bookmarks_with_active(self, mock_store, mock_scan, capsys):
        session = _make_session("test-sess-001")
        mock_scan.return_value = [session]
        storage = MagicMock()
        storage.load_bookmarks.return_value = ["test-sess-001"]
        mock_store.return_value = storage
        args = _make_args(bookmark_cmd="list")
        cli_main.cmd_bookmark(args)
        out = capsys.readouterr().out
        assert "proj" in out


# ========== cmd_host 测试 ==========

class TestCmdHost:
    """测试cmd_host"""

    @patch("cli.main.get_storage")
    def test_add_host(self, mock_store, capsys):
        storage = MagicMock()
        mock_store.return_value = storage
        args = _make_args(host_cmd="add", name="srv1", hostname="1.2.3.4",
                          user="test", alias="myhost")
        cli_main.cmd_host(args)
        out = capsys.readouterr().out
        assert "已添加远程主机" in out
        assert "SSH别名" in out

    @patch("cli.main.get_storage")
    def test_add_host_no_alias(self, mock_store, capsys):
        storage = MagicMock()
        mock_store.return_value = storage
        args = _make_args(host_cmd="add", name="srv1", hostname="1.2.3.4",
                          user="test", alias=None)
        cli_main.cmd_host(args)
        out = capsys.readouterr().out
        assert "已添加远程主机" in out

    @patch("cli.main.get_storage")
    def test_list_hosts(self, mock_store, capsys):
        host = RemoteHostConfig.create(name="srv", hostname="1.2.3.4", user="u")
        storage = MagicMock()
        storage.load_remote_hosts.return_value = [host]
        mock_store.return_value = storage
        args = _make_args(host_cmd="list")
        cli_main.cmd_host(args)
        out = capsys.readouterr().out
        assert "远程主机" in out

    @patch("cli.main.get_storage")
    def test_list_hosts_empty(self, mock_store, capsys):
        storage = MagicMock()
        storage.load_remote_hosts.return_value = []
        mock_store.return_value = storage
        args = _make_args(host_cmd="list")
        cli_main.cmd_host(args)
        out = capsys.readouterr().out
        assert "没有配置远程主机" in out

    @patch("cli.main.get_storage")
    def test_remove_host(self, mock_store, capsys):
        storage = MagicMock()
        storage.remove_remote_host.return_value = True
        mock_store.return_value = storage
        args = _make_args(host_cmd="remove", host_id="h1")
        cli_main.cmd_host(args)
        out = capsys.readouterr().out
        assert "已移除" in out

    @patch("cli.main.get_storage")
    def test_remove_host_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.remove_remote_host.return_value = False
        mock_store.return_value = storage
        args = _make_args(host_cmd="remove", host_id="h1")
        result = cli_main.cmd_host(args)
        assert result == 1

    @patch("cli.main.get_factory")
    @patch("cli.main.get_storage")
    def test_scan_host(self, mock_store, mock_factory, capsys):
        host_config = RemoteHostConfig.create(name="srv", hostname="1.2.3.4", user="u")
        storage = MagicMock()
        storage.get_remote_host.return_value = host_config
        mock_store.return_value = storage
        provider = MagicMock()
        provider.scan_sessions.return_value = [_make_session()]
        provider.scan_tmux_mappings.return_value = {}
        mock_factory.return_value.create.return_value = provider
        args = _make_args(host_cmd="scan", host_id="h1", limit=20)
        cli_main.cmd_host(args)
        out = capsys.readouterr().out
        assert "扫描远程主机" in out

    @patch("cli.main.get_storage")
    def test_scan_host_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.get_remote_host.return_value = None
        mock_store.return_value = storage
        args = _make_args(host_cmd="scan", host_id="h1")
        result = cli_main.cmd_host(args)
        assert result == 1


# ========== cmd_req 测试 ==========

class TestCmdReq:
    """测试cmd_req"""

    @patch("cli.main.RequirementService")
    def test_add_req(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        req = Requirement.create("new req")
        mock_service.create.return_value = req
        args = _make_args(req_cmd="add", req_id="new req", title_explicit=None,
                          category="feature", priority="p1", description="desc",
                          tags="t1,t2", work_dirs="/a,/b")
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "已创建需求" in out

    @patch("cli.main.RequirementService")
    def test_add_req_with_explicit_title(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        req = Requirement.create("explicit title")
        mock_service.create.return_value = req
        args = _make_args(req_cmd="add", req_id=None, title_explicit="explicit title",
                          category=None, priority=None, description=None,
                          tags=None, work_dirs=None)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "已创建需求" in out

    def test_add_req_no_title(self, capsys):
        args = _make_args(req_cmd="add", req_id=None, title_explicit=None)
        result = cli_main.cmd_req(args)
        assert result == 1

    @patch("cli.main.RequirementService")
    def test_list_reqs(self, mock_req_service, capsys):
        req = Requirement.create("test req")
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.list.return_value = [req]
        args = _make_args(req_cmd="list", status=None, priority=None, category=None)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "需求列表" in out

    @patch("cli.main.RequirementService")
    def test_list_reqs_filter_status(self, mock_req_service, capsys):
        req = Requirement.create("r")
        req.status = "active"
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.list.return_value = [req]
        args = _make_args(req_cmd="list", status="active", priority=None, category=None)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "需求列表" in out

    @patch("cli.main.RequirementService")
    def test_list_reqs_filter_priority(self, mock_req_service, capsys):
        req = Requirement.create("r")
        req.priority = "p1"
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.list.return_value = [req]
        args = _make_args(req_cmd="list", status=None, priority="p1,p2", category=None)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "需求列表" in out

    @patch("cli.main.RequirementService")
    def test_list_reqs_filter_category(self, mock_req_service, capsys):
        req = Requirement.create("r")
        req.category = "bug"
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.list.return_value = [req]
        args = _make_args(req_cmd="list", status=None, priority=None, category="bug")
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "需求列表" in out

    @patch("cli.main.RequirementService")
    def test_list_reqs_empty(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.list.return_value = []
        args = _make_args(req_cmd="list", status=None, priority=None, category=None)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "没有需求" in out

    @patch("cli.main.RequirementService")
    def test_show_req(self, mock_req_service, capsys):
        req = Requirement.create("test req")
        req.description = "desc"
        req.tags = ["t1"]
        req.work_dirs = ["/a"]
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.get_detail.return_value = req
        mock_service.get_linked_sessions.return_value = []
        args = _make_args(req_cmd="show", req_id=req.id)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "test req" in out
        assert "desc" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.RequirementService")
    def test_show_req_with_links(self, mock_req_service, mock_scan, capsys):
        req = Requirement.create("r")
        link = RequirementSessionLink.create(req.id, "sess-001", role="primary", notes="")
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.get_detail.return_value = req
        mock_service.get_linked_sessions.return_value = [link]
        mock_scan.return_value = [_make_session()]
        args = _make_args(req_cmd="show", req_id=req.id)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "关联会话" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.get_storage")
    @patch("cli.main.RequirementService")
    def test_show_req_with_expired_link(self, mock_req_service, mock_store, mock_scan, capsys):
        req = Requirement.create("r")
        link = RequirementSessionLink.create(req.id, "expired-sess", role="reference", notes="")
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.get_detail.return_value = req
        storage = MagicMock()
        mock_store.return_value = storage
        storage.get_requirement_sessions.return_value = [link]
        mock_scan.return_value = []  # session not found = expired
        args = _make_args(req_cmd="show", req_id=req.id)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "已过期" in out

    @patch("cli.main.RequirementService")
    def test_show_req_no_links(self, mock_req_service, capsys):
        req = Requirement.create("r")
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.get_detail.return_value = req
        mock_service.get_linked_sessions.return_value = []
        args = _make_args(req_cmd="show", req_id=req.id)
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "暂无关联会话" in out

    @patch("cli.main.RequirementService")
    def test_show_req_not_found(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.get_detail.return_value = None
        args = _make_args(req_cmd="show", req_id="nonexist")
        result = cli_main.cmd_req(args)
        assert result == 1

    @patch("cli.main.RequirementService")
    def test_edit_req(self, mock_req_service, capsys):
        req = Requirement.create("r")
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.update.return_value = True
        mock_service.get_detail.return_value = req
        args = _make_args(req_cmd="edit", req_id="req1", status="active",
                          priority="p1", category="bug", description="new desc")
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "已更新需求" in out

    @patch("cli.main.RequirementService")
    def test_edit_req_not_found(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.update.return_value = False
        args = _make_args(req_cmd="edit", req_id="nonexist", status="active",
                          priority=None, category=None, description=None)
        result = cli_main.cmd_req(args)
        assert result == 1

    @patch("cli.main.RequirementService")
    def test_done_req(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.complete.return_value = True
        args = _make_args(req_cmd="done", req_id="req1")
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "已完成需求" in out

    @patch("cli.main.RequirementService")
    def test_done_req_not_found(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.complete.return_value = False
        args = _make_args(req_cmd="done", req_id="nonexist")
        result = cli_main.cmd_req(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_archive_req(self, mock_store, capsys):
        storage = MagicMock()
        mock_store.return_value = storage
        storage.update_requirement.return_value = True
        args = _make_args(req_cmd="archive", req_id="req1")
        cli_main.cmd_req(args)
        out = capsys.readouterr().out
        assert "已归档需求" in out

    @patch("cli.main.get_storage")
    def test_archive_req_not_found(self, mock_store, capsys):
        storage = MagicMock()
        mock_store.return_value = storage
        storage.update_requirement.return_value = False
        args = _make_args(req_cmd="archive", req_id="nonexist")
        result = cli_main.cmd_req(args)
        assert result == 1


# ========== cmd_link 测试 ==========

class TestCmdLink:
    """测试cmd_link"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    def test_session_not_found(self, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_link(_make_args(session_id="bad", req_id="r1"))
        assert result == 1

    @patch("cli.main.RequirementService")
    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_req_not_found(self, mock_find, mock_scan, mock_req_service, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.get_detail.return_value = None
        result = cli_main.cmd_link(_make_args(session_id="s1", req_id="bad"))
        assert result == 1

    @patch("cli.main.RequirementService")
    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_link_success(self, mock_find, mock_scan, mock_req_service, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        req = Requirement.create("r")
        mock_service.get_detail.return_value = req
        link = RequirementSessionLink.create(req.id, "sess-001", role="primary", notes="n")
        mock_service.link_session.return_value = link
        args = _make_args(session_id="s1", req_id=req.id, role="primary", notes="n")
        cli_main.cmd_link(args)
        out = capsys.readouterr().out
        assert "已关联会话" in out


# ========== cmd_unlink 测试 ==========

class TestCmdUnlink:
    """测试cmd_unlink"""

    @patch("cli.main.RequirementService")
    def test_unlink_success(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.unlink_session.return_value = True
        cli_main.cmd_unlink(_make_args(session_id="test-sess"))
        out = capsys.readouterr().out
        assert "已解除" in out

    @patch("cli.main.RequirementService")
    def test_unlink_not_linked(self, mock_req_service, capsys):
        mock_service = MagicMock()
        mock_req_service.return_value = mock_service
        mock_service.unlink_session.return_value = False
        cli_main.cmd_unlink(_make_args(session_id="test-sess"))
        out = capsys.readouterr().out
        assert "未关联" in out


# ========== cmd_which_req 测试 ==========

class TestCmdWhichReq:
    """测试cmd_which_req"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    def test_session_not_found(self, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_which_req(_make_args())
        assert result == 1

    @patch("cli.main.MatchingService")
    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_no_link(self, mock_find, mock_scan, mock_matching_service, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        mock_service = MagicMock()
        mock_matching_service.return_value = mock_service
        mock_service.get_session_requirement.return_value = {'linked': False}
        cli_main.cmd_which_req(_make_args())
        out = capsys.readouterr().out
        assert "未关联" in out

    @patch("cli.main.MatchingService")
    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_has_link_with_notes(self, mock_find, mock_scan, mock_matching_service, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        mock_service = MagicMock()
        mock_matching_service.return_value = mock_service
        mock_service.get_session_requirement.return_value = {
            'linked': True,
            'requirement_id': 'req-1',
            'requirement_title': 'Test Req',
            'role': 'primary',
            'notes': 'important',
        }
        cli_main.cmd_which_req(_make_args())
        out = capsys.readouterr().out
        assert "关联到需求" in out
        assert "important" in out

    @patch("cli.main.MatchingService")
    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    def test_link_to_deleted_req(self, mock_find, mock_scan, mock_matching_service, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        mock_service = MagicMock()
        mock_matching_service.return_value = mock_service
        mock_service.get_session_requirement.return_value = {
            'linked': True,
            'requirement_id': 'deleted-req',
            'deleted': True,
        }
        cli_main.cmd_which_req(_make_args())
        out = capsys.readouterr().out
        assert "已删除的需求" in out


# ========== cmd_archive 测试 ==========

class TestCmdArchive:
    """测试cmd_archive"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    @patch("cli.main.get_storage")
    def test_not_found(self, mock_store, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_archive(_make_args())
        assert result == 1

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_archive_success(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        mock_store.return_value = storage
        args = _make_args(insight="learned something", reason="done")
        cli_main.cmd_archive(args)
        out = capsys.readouterr().out
        assert "已归档" in out
        assert "learned something" in out

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_archive_no_insight(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        mock_store.return_value = storage
        args = _make_args(insight=None, reason=None)
        cli_main.cmd_archive(args)
        out = capsys.readouterr().out
        assert "已归档" in out


# ========== cmd_restore 测试 ==========

class TestCmdRestore:
    """测试cmd_restore"""

    @patch("cli.main.get_storage")
    def test_restore_exact(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001", archive_type="archived", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = archived
        storage.restore_session.return_value = True
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001")
        cli_main.cmd_restore(args)
        out = capsys.readouterr().out
        assert "已恢复" in out

    @patch("cli.main.get_storage")
    def test_restore_prefix_match(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001-abcdef", archive_type="trash", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = None
        storage.load_archived_sessions.return_value = [archived]
        storage.restore_session.return_value = True
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001")
        cli_main.cmd_restore(args)
        out = capsys.readouterr().out
        assert "已恢复" in out

    @patch("cli.main.get_storage")
    def test_restore_prefix_multiple_match(self, mock_store, capsys):
        a1 = ArchivedSession(session_id="sess-001-aaa", archive_type="archived", archived_at=1000)
        a2 = ArchivedSession(session_id="sess-001-bbb", archive_type="archived", archived_at=2000)
        storage = MagicMock()
        storage.get_archived_session.return_value = None
        storage.load_archived_sessions.return_value = [a1, a2]
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001")
        result = cli_main.cmd_restore(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_restore_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.get_archived_session.return_value = None
        storage.load_archived_sessions.return_value = []
        mock_store.return_value = storage
        args = _make_args(session_id="nonexist")
        result = cli_main.cmd_restore(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_restore_failure(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001", archive_type="archived", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = archived
        storage.restore_session.return_value = False
        mock_store.return_value = storage
        cli_main.cmd_restore(_make_args(session_id="sess-001"))
        out = capsys.readouterr().out
        assert "恢复失败" in out


# ========== cmd_trash 测试 ==========

class TestCmdTrash:
    """测试cmd_trash"""

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session", side_effect=SessionNotFoundError("x"))
    @patch("cli.main.get_storage")
    def test_not_found(self, mock_store, mock_find, mock_scan, capsys):
        mock_scan.return_value = []
        result = cli_main.cmd_trash(_make_args())
        assert result == 1

    @patch("cli.main.scan_all_sessions")
    @patch("cli.main.find_session")
    @patch("cli.main.get_storage")
    def test_trash_success(self, mock_store, mock_find, mock_scan, capsys):
        mock_find.return_value = _make_session()
        mock_scan.return_value = []
        storage = MagicMock()
        mock_store.return_value = storage
        cli_main.cmd_trash(_make_args())
        out = capsys.readouterr().out
        assert "放入废纸篓" in out

    @patch("cli.main.get_storage")
    def test_list_trash_empty(self, mock_store, capsys):
        storage = MagicMock()
        storage.get_archived_by_type.return_value = []
        mock_store.return_value = storage
        args = _make_args(list=True)
        cli_main.cmd_trash(args)
        out = capsys.readouterr().out
        assert "废纸篓为空" in out

    @patch("cli.main.get_storage")
    def test_list_trash_with_items(self, mock_store, capsys):
        a = ArchivedSession(
            session_id="sess-001", archive_type="trash",
            archived_at=1700000000000, project_name="proj"
        )
        storage = MagicMock()
        storage.get_archived_by_type.return_value = [a]
        mock_store.return_value = storage
        args = _make_args(list=True)
        cli_main.cmd_trash(args)
        out = capsys.readouterr().out
        assert "废纸篓内容" in out


# ========== cmd_delete 测试 ==========

class TestCmdDelete:
    """测试cmd_delete"""

    @patch("cli.main.get_storage")
    def test_delete_exact_match(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001", archive_type="trash", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = archived
        storage.delete_trash_session.return_value = True
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001", force=True)
        cli_main.cmd_delete(args)
        out = capsys.readouterr().out
        assert "已永久删除" in out

    @patch("cli.main.get_storage")
    def test_delete_prefix_match(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001-abc", archive_type="trash", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = None
        storage.load_archived_sessions.return_value = [archived]
        storage.delete_trash_session.return_value = True
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001", force=True)
        cli_main.cmd_delete(args)
        out = capsys.readouterr().out
        assert "已永久删除" in out

    @patch("cli.main.get_storage")
    def test_delete_not_in_trash_type(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001", archive_type="archived", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = archived
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001", force=True)
        result = cli_main.cmd_delete(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_delete_no_force(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001", archive_type="trash", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = archived
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001", force=False)
        result = cli_main.cmd_delete(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_delete_not_found(self, mock_store, capsys):
        storage = MagicMock()
        storage.get_archived_session.return_value = None
        storage.load_archived_sessions.return_value = []
        mock_store.return_value = storage
        args = _make_args(session_id="nonexist", force=True)
        result = cli_main.cmd_delete(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_delete_prefix_multiple_match(self, mock_store, capsys):
        a1 = ArchivedSession(session_id="sess-001-aaa", archive_type="trash", archived_at=1000)
        a2 = ArchivedSession(session_id="sess-001-bbb", archive_type="trash", archived_at=2000)
        storage = MagicMock()
        storage.get_archived_session.return_value = None
        storage.load_archived_sessions.return_value = [a1, a2]
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001", force=True)
        result = cli_main.cmd_delete(args)
        assert result == 1

    @patch("cli.main.get_storage")
    def test_delete_failure(self, mock_store, capsys):
        archived = ArchivedSession(
            session_id="sess-001", archive_type="trash", archived_at=1000
        )
        storage = MagicMock()
        storage.get_archived_session.return_value = archived
        storage.delete_trash_session.return_value = False
        mock_store.return_value = storage
        args = _make_args(session_id="sess-001", force=True)
        cli_main.cmd_delete(args)
        out = capsys.readouterr().out
        assert "删除失败" in out


# ========== main() 测试 ==========

class TestMain:
    """测试main函数"""

    def test_no_command(self, capsys):
        with patch("sys.argv", ["sessionflow"]):
            result = cli_main.main()
        assert result is None or result == 0

    def test_scan_command(self, capsys):
        with patch("sys.argv", ["sessionflow", "scan"]), \
             patch("cli.main.cmd_scan") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_list_command(self, capsys):
        with patch("sys.argv", ["sessionflow", "list"]), \
             patch("cli.main.cmd_list") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_open_command(self, capsys):
        with patch("sys.argv", ["sessionflow", "open", "abc"]), \
             patch("cli.main.cmd_open") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_status_command(self):
        with patch("sys.argv", ["sessionflow", "status"]), \
             patch("cli.main.cmd_status") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_recover_command(self):
        with patch("sys.argv", ["sessionflow", "recover"]), \
             patch("cli.main.cmd_recover") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_view_command(self):
        with patch("sys.argv", ["sessionflow", "view", "abc"]), \
             patch("cli.main.cmd_view") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_tasks_command(self):
        with patch("sys.argv", ["sessionflow", "tasks", "abc"]), \
             patch("cli.main.cmd_tasks") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_stats_command(self):
        with patch("sys.argv", ["sessionflow", "stats", "abc"]), \
             patch("cli.main.cmd_stats") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_note_command(self):
        with patch("sys.argv", ["sessionflow", "note", "abc"]), \
             patch("cli.main.cmd_note") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_task_command(self):
        with patch("sys.argv", ["sessionflow", "task", "list"]), \
             patch("cli.main.cmd_task") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_progress_command(self):
        with patch("sys.argv", ["sessionflow", "progress"]), \
             patch("cli.main.cmd_progress") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_bookmark_command(self):
        with patch("sys.argv", ["sessionflow", "bookmark", "list"]), \
             patch("cli.main.cmd_bookmark") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_host_command(self):
        with patch("sys.argv", ["sessionflow", "host", "list"]), \
             patch("cli.main.cmd_host") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_req_command(self):
        with patch("sys.argv", ["sessionflow", "req", "list"]), \
             patch("cli.main.cmd_req") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_link_command(self):
        with patch("sys.argv", ["sessionflow", "link", "s1", "r1"]), \
             patch("cli.main.cmd_link") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_unlink_command(self):
        with patch("sys.argv", ["sessionflow", "unlink", "s1"]), \
             patch("cli.main.cmd_unlink") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_which_req_command(self):
        with patch("sys.argv", ["sessionflow", "which-req", "s1"]), \
             patch("cli.main.cmd_which_req") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_archive_command(self):
        with patch("sys.argv", ["sessionflow", "archive", "s1"]), \
             patch("cli.main.cmd_archive") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_restore_command(self):
        with patch("sys.argv", ["sessionflow", "restore", "s1"]), \
             patch("cli.main.cmd_restore") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_trash_command(self):
        with patch("sys.argv", ["sessionflow", "trash", "s1"]), \
             patch("cli.main.cmd_trash") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()

    def test_delete_command(self):
        with patch("sys.argv", ["sessionflow", "delete", "s1"]), \
             patch("cli.main.cmd_delete") as mock_cmd:
            cli_main.main()
            mock_cmd.assert_called_once()
