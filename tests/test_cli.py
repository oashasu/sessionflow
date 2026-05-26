"""SessionFlow CLI测试"""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

from sessionflow import find_session, print_table, cmd_scan, cmd_list, cmd_open
from core.models import SessionMeta, SessionRecord
from core.errors import SessionNotFoundError, MultipleMatchError


class TestCLIHelpers:
    """测试CLI辅助函数"""

    def test_find_session_exact_match(self):
        """测试精确匹配"""
        sessions = [
            SessionRecord(
                meta=SessionMeta(session_id="abc12345", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test",
            )
        ]
        result = find_session("abc12345", sessions)
        assert result.meta.session_id == "abc12345"

    def test_find_session_prefix_match(self):
        """测试前缀匹配"""
        sessions = [
            SessionRecord(
                meta=SessionMeta(session_id="abc12345", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test",
            )
        ]
        result = find_session("abc1", sessions)
        assert result.meta.session_id == "abc12345"

    def test_find_session_multiple_match_raises(self):
        """测试多个匹配抛出异常"""
        sessions = [
            SessionRecord(
                meta=SessionMeta(session_id="abc12345", cwd="/test1", status="idle", started_at=0, updated_at=0),
                project_name="test1",
            ),
            SessionRecord(
                meta=SessionMeta(session_id="abc12399", cwd="/test2", status="idle", started_at=0, updated_at=0),
                project_name="test2",
            )
        ]
        # abc1会匹配两个会话
        with pytest.raises(MultipleMatchError):
            find_session("abc1", sessions)

    def test_find_session_multiple_match_select_first(self):
        """测试多个匹配选择第一个"""
        sessions = [
            SessionRecord(
                meta=SessionMeta(session_id="abc12345", cwd="/test1", status="idle", started_at=0, updated_at=0),
                project_name="test1",
            ),
            SessionRecord(
                meta=SessionMeta(session_id="abc12399", cwd="/test2", status="idle", started_at=0, updated_at=0),
                project_name="test2",
            )
        ]
        # abc1会匹配两个会话，select_first选第一个
        result = find_session("abc1", sessions, select_first=True)
        assert result.meta.session_id == "abc12345"

    def test_find_session_not_found(self):
        """测试未找到会话"""
        sessions = [
            SessionRecord(
                meta=SessionMeta(session_id="abc12345", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test",
            )
        ]
        with pytest.raises(SessionNotFoundError):
            find_session("xyz", sessions)

    def test_print_table_no_rich(self):
        """测试无Rich库表格输出"""
        # 强制禁用Rich
        import sessionflow
        sessionflow.USE_RICH = False
        sessionflow.console = None

        rows = [["a", "b", "c"], ["1", "2", "3"]]
        headers = ["Col1", "Col2", "Col3"]
        # 不验证输出，只验证函数不崩溃
        print_table("Test", rows, headers)

    def test_find_session_short_prefix(self):
        """测试短前缀（少于4位）"""
        sessions = [
            SessionRecord(
                meta=SessionMeta(session_id="abc12345", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test",
            )
        ]
        # 少于4位应该失败
        with pytest.raises(SessionNotFoundError):
            find_session("abc", sessions)


class TestCLICommands:
    """测试CLI命令"""

    @patch('sessionflow.scan_sessions')
    def test_cmd_scan(self, mock_scan):
        """测试scan命令"""
        from argparse import Namespace
        mock_scan.return_value = [
            SessionRecord(
                meta=SessionMeta(session_id="test-id", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test/project",
                topic="Test topic",
            )
        ]

        args = Namespace(all=False, limit=10)
        result = cmd_scan(args)
        assert result is None or result == 0

    @patch('sessionflow.scan_sessions')
    def test_cmd_list(self, mock_scan):
        """测试list命令"""
        from argparse import Namespace
        mock_scan.return_value = [
            SessionRecord(
                meta=SessionMeta(session_id="test-id", cwd="/test", status="busy", started_at=0, updated_at=1000),
                project_name="test/project",
                topic="Test topic",
            )
        ]

        args = Namespace(all=False, project=None, status=None, limit=10, verbose=False, host_id=None, remote=False, tool="all")
        result = cmd_list(args)
        assert result is None or result == 0

    @patch('sessionflow.scan_sessions')
    @patch('sessionflow.generate_recovery_cmd')
    def test_cmd_open(self, mock_cmd, mock_scan):
        """测试open命令"""
        from argparse import Namespace
        mock_scan.return_value = [
            SessionRecord(
                meta=SessionMeta(session_id="test-id-123", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test/project",
                log_path="/tmp/test.jsonl",
                topic="Test topic",
            )
        ]
        mock_cmd.return_value = "claude --resume test-id-123"

        args = Namespace(session_id="test-id-123", copy=False, select_first=False, remote=False, host_id=None)
        result = cmd_open(args)
        assert result is None or result == 0

    @patch('sessionflow.scan_sessions')
    def test_cmd_status(self, mock_scan):
        """测试status命令"""
        from argparse import Namespace
        from sessionflow import cmd_status
        mock_scan.return_value = [
            SessionRecord(
                meta=SessionMeta(session_id="test-id", cwd="/test", status="busy", started_at=0, updated_at=0),
                project_name="test/project",
            )
        ]

        args = Namespace()
        result = cmd_status(args)
        assert result is None or result == 0

    @patch('sessionflow.scan_sessions')
    def test_cmd_status_no_active(self, mock_scan):
        """测试status命令无活跃会话"""
        from argparse import Namespace
        from sessionflow import cmd_status
        mock_scan.return_value = [
            SessionRecord(
                meta=SessionMeta(session_id="test-id", cwd="/test", status="idle", started_at=0, updated_at=0),
                project_name="test/project",
            )
        ]

        args = Namespace()
        result = cmd_status(args)
        assert result is None or result == 0


class TestCLIIntegration:
    """CLI集成测试"""

    def test_cli_help(self):
        """测试CLI帮助命令"""
        result = subprocess.run(
            ["python", "sessionflow.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )
        assert result.returncode == 0
        assert "SessionFlow" in result.stdout

    def test_cli_list(self):
        """测试CLI list命令"""
        result = subprocess.run(
            ["python", "sessionflow.py", "list", "--limit", "3"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )
        assert result.returncode == 0
        assert "会话" in result.stdout

    def test_cli_scan(self):
        """测试CLI scan命令"""
        result = subprocess.run(
            ["python", "sessionflow.py", "scan", "--limit", "3"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )
        assert result.returncode == 0

    def test_cli_status(self):
        """测试CLI status命令"""
        result = subprocess.run(
            ["python", "sessionflow.py", "status"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])