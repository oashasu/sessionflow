"""Provider模块额外测试 - 覆盖base_provider和claude_provider的未测试方法"""

import sys
import json
import time
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open

from providers.protocol import ToolInfo, TmuxMapping, RemoteHost, SessionProvider
from providers.base_provider import BaseSessionProvider
from providers.claude_provider import ClaudeProvider


# ========== 具体测试子类 ==========

class ConcreteProvider(BaseSessionProvider):
    """用于测试BaseSessionProvider抽象方法的具体子类"""

    @property
    def tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="test-tool",
            display_name="Test Tool",
            version="1.0.0",
            executable="test-tool",
            session_dir="~/.test-tool/projects/",
            supports_resume=True,
            resume_arg_format="test-tool --resume {id}",
            schema_version="1.0"
        )

    def _scan_impl(self, host):
        return []

    def _attach_tmux(self, tmux_info, host):
        return True

    def _create_and_recover(self, session, host):
        return True


def _make_host(**kwargs) -> RemoteHost:
    """创建RemoteHost辅助函数"""
    defaults = {
        "id": "test-host",
        "name": "Test Host",
        "hostname": "192.168.1.100",
        "user": "testuser",
        "ssh_alias": None,
    }
    defaults.update(kwargs)
    return RemoteHost(**defaults)


def _make_session(session_id="abc123-def456", cwd="/Users/test/project"):
    """创建模拟session对象辅助函数"""
    session = MagicMock()
    session.meta.session_id = session_id
    session.meta.cwd = cwd
    session.tmux_info = None
    session.recovery_cmd = ""
    return session


# ========== BaseSessionProvider: _build_ssh_cmd ==========

class TestBuildSshCmd:
    """测试_build_ssh_cmd方法"""

    def test_build_ssh_cmd_with_none_host(self):
        """host=None时直接返回remote_cmd"""
        provider = ConcreteProvider()
        cmd = provider._build_ssh_cmd(None, ["claude", "--version"])
        assert cmd == ["claude", "--version"]

    def test_build_ssh_cmd_with_host_user_hostname(self):
        """host有user和hostname时构造SSH命令"""
        provider = ConcreteProvider()
        host = _make_host(user="ada", hostname="10.0.0.1", ssh_alias=None)
        cmd = provider._build_ssh_cmd(host, ["ls", "-la"])
        assert cmd == ["ssh", "-o", "RemoteCommand=none", "-o", "RequestTTY=no", "ada@10.0.0.1", "ls", "-la"]

    def test_build_ssh_cmd_with_ssh_alias(self):
        """host有ssh_alias时优先使用alias"""
        provider = ConcreteProvider()
        host = _make_host(user="ada", hostname="10.0.0.1", ssh_alias="my-server")
        cmd = provider._build_ssh_cmd(host, ["tmux", "list-sessions"])
        assert cmd[5] == "my-server"
        assert "ada@" not in cmd[5]

    def test_build_ssh_cmd_empty_remote_cmd(self):
        """remote_cmd为空列表"""
        provider = ConcreteProvider()
        cmd = provider._build_ssh_cmd(None, [])
        assert cmd == []

    def test_build_ssh_cmd_preserves_order(self):
        """remote_cmd元素顺序保持不变"""
        provider = ConcreteProvider()
        cmd = provider._build_ssh_cmd(None, ["a", "b", "c", "d"])
        assert cmd == ["a", "b", "c", "d"]


# ========== BaseSessionProvider: _exec_ssh_cmd ==========

class TestExecSshCmd:
    """测试_exec_ssh_cmd方法"""

    @patch("subprocess.run")
    def test_exec_ssh_cmd_local(self, mock_run):
        """本地执行(无host)"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="ok")
        result = provider._exec_ssh_cmd(None, ["echo", "ok"])
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["echo", "ok"]
        assert result.returncode == 0

    @patch("subprocess.run")
    def test_exec_ssh_cmd_remote(self, mock_run):
        """远程执行"""
        provider = ConcreteProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=0, stdout="remote-ok")
        result = provider._exec_ssh_cmd(host, ["ls"])
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "ssh"
        assert result.stdout == "remote-ok"

    @patch("subprocess.run")
    def test_exec_ssh_cmd_custom_timeout(self, mock_run):
        """自定义超时参数"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0)
        provider._exec_ssh_cmd(None, ["ls"], timeout=60)
        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 60

    @patch("subprocess.run")
    def test_exec_ssh_cmd_default_timeout(self, mock_run):
        """默认超时为30秒"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0)
        provider._exec_ssh_cmd(None, ["ls"])
        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 30

    @patch("subprocess.run")
    def test_exec_ssh_cmd_capture_output(self, mock_run):
        """验证capture_output=True, text=True"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0)
        provider._exec_ssh_cmd(None, ["ls"])
        call_args = mock_run.call_args
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True


# ========== BaseSessionProvider: _safe_quote ==========

class TestSafeQuote:
    """测试_safe_quote方法"""

    def test_safe_quote_normal_string(self):
        provider = ConcreteProvider()
        result = provider._safe_quote("hello")
        assert result == "hello"

    def test_safe_quote_with_spaces(self):
        provider = ConcreteProvider()
        result = provider._safe_quote("hello world")
        assert result == "'hello world'"

    def test_safe_quote_with_semicolon(self):
        """防止命令注入"""
        provider = ConcreteProvider()
        result = provider._safe_quote("/path; rm -rf /")
        assert ";" not in result or result.startswith("'")

    def test_safe_quote_with_backtick(self):
        """防止反引号注入"""
        provider = ConcreteProvider()
        result = provider._safe_quote("`malicious`")
        assert "`" not in result or result.startswith("'")

    def test_safe_quote_empty_string(self):
        provider = ConcreteProvider()
        result = provider._safe_quote("")
        assert result == "''"

    def test_safe_quote_with_dollar(self):
        """防止变量展开"""
        provider = ConcreteProvider()
        result = provider._safe_quote("$HOME/path")
        assert "$" not in result or result.startswith("'")


# ========== BaseSessionProvider: scan_tmux_mappings ==========

class TestScanTmuxMappings:
    """测试scan_tmux_mappings方法"""

    @patch("subprocess.run")
    def test_scan_tmux_mappings_no_sessions(self, mock_run):
        """没有tmux会话时返回空字典"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = provider.scan_tmux_mappings()
        assert result == {}

    @patch("subprocess.run")
    def test_scan_tmux_mappings_with_sessions(self, mock_run):
        """有tmux会话时调用_scan_tmux_session_panes"""
        provider = ConcreteProvider()
        # 第一次调用是tmux list-sessions
        mock_run.return_value = MagicMock(returncode=0, stdout="session1\nsession2\n")
        with patch.object(provider, '_scan_tmux_session_panes') as mock_panes:
            result = provider.scan_tmux_mappings()
            assert mock_panes.call_count == 2

    @patch("subprocess.run")
    def test_scan_tmux_mappings_skips_empty_names(self, mock_run):
        """跳过空的session名"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="session1\n\nsession2\n")
        with patch.object(provider, '_scan_tmux_session_panes') as mock_panes:
            provider.scan_tmux_mappings()
            assert mock_panes.call_count == 2

    @patch("subprocess.run")
    def test_scan_tmux_mappings_timeout(self, mock_run):
        """tmux命令超时时返回空字典"""
        import subprocess
        provider = ConcreteProvider()
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 10)
        result = provider.scan_tmux_mappings()
        assert result == {}

    @patch("subprocess.run")
    def test_scan_tmux_mappings_remote_host(self, mock_run):
        """远程host参数传递"""
        provider = ConcreteProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=0, stdout="s1\n")
        with patch.object(provider, '_scan_tmux_session_panes') as mock_panes:
            provider.scan_tmux_mappings(host=host)
            mock_panes.assert_called_once_with(host, "s1", {})


# ========== BaseSessionProvider: _scan_tmux_session_panes ==========

class TestScanTmuxSessionPanes:
    """测试_scan_tmux_session_panes方法"""

    @patch("subprocess.run")
    def test_scan_panes_success(self, mock_run):
        """成功扫描pane"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="1234\n5678\n")
        mappings = {}
        with patch.object(provider, '_scan_tmux_pane_process') as mock_process:
            provider._scan_tmux_session_panes(None, "test-session", mappings)
            assert mock_process.call_count == 2
            mock_process.assert_any_call(None, "test-session", 1234, mappings)
            mock_process.assert_any_call(None, "test-session", 5678, mappings)

    @patch("subprocess.run")
    def test_scan_panes_failure(self, mock_run):
        """tmux list-panes失败"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mappings = {}
        with patch.object(provider, '_scan_tmux_pane_process') as mock_process:
            provider._scan_tmux_session_panes(None, "test-session", mappings)
            mock_process.assert_not_called()

    @patch("subprocess.run")
    def test_scan_panes_skips_empty(self, mock_run):
        """跳过空行"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="1234\n\n5678\n")
        mappings = {}
        with patch.object(provider, '_scan_tmux_pane_process') as mock_process:
            provider._scan_tmux_session_panes(None, "test-session", mappings)
            assert mock_process.call_count == 2

    @patch("subprocess.run")
    def test_scan_panes_timeout(self, mock_run):
        """超时时静默处理"""
        import subprocess
        provider = ConcreteProvider()
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 10)
        mappings = {}
        provider._scan_tmux_session_panes(None, "test-session", mappings)
        assert mappings == {}

    @patch("subprocess.run")
    def test_scan_panes_invalid_pid(self, mock_run):
        """非数字PID时捕获ValueError"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="not-a-number\n")
        mappings = {}
        provider._scan_tmux_session_panes(None, "test-session", mappings)
        assert mappings == {}


# ========== BaseSessionProvider: _scan_tmux_pane_process ==========

class TestScanTmuxPaneProcess:
    """测试_scan_tmux_pane_process方法"""

    @patch("subprocess.run")
    def test_pane_process_matching_tool(self, mock_run):
        """pane运行的进程匹配当前工具"""
        provider = ConcreteProvider()
        # ps返回匹配的进程命令
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="test-tool --resume abc"),
            MagicMock(returncode=0, stdout="p1 p2 p3 p4 p5 p6 p7 p8 p9 cwd /home/test\n"),
        ]
        mappings = {}
        with patch.object(provider, '_find_session_id_by_cwd', return_value="session-123"):
            provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
            assert "session-123" in mappings
            assert mappings["session-123"].tmux_session_name == "my-session"
            assert mappings["session-123"].pane_pid == 9999

    @patch("subprocess.run")
    def test_pane_process_non_matching_tool(self, mock_run):
        """pane运行的进程不匹配当前工具"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="bash")
        mappings = {}
        provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
        assert mappings == {}

    @patch("subprocess.run")
    def test_pane_process_ps_failure(self, mock_run):
        """ps命令失败"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mappings = {}
        provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
        assert mappings == {}

    @patch("subprocess.run")
    def test_pane_process_lsof_failure(self, mock_run):
        """lsof命令失败"""
        provider = ConcreteProvider()
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="test-tool --version"),
            MagicMock(returncode=1, stdout=""),
        ]
        mappings = {}
        provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
        assert mappings == {}

    @patch("subprocess.run")
    def test_pane_process_no_cwd_in_lsof(self, mock_run):
        """lsof输出中没有cwd行"""
        provider = ConcreteProvider()
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="test-tool --version"),
            MagicMock(returncode=0, stdout="p1 p2 p3 txt /usr/bin/test-tool\n"),
        ]
        mappings = {}
        provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
        assert mappings == {}

    @patch("subprocess.run")
    def test_pane_process_no_session_id(self, mock_run):
        """找不到session_id时跳过"""
        provider = ConcreteProvider()
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="test-tool --version"),
            MagicMock(returncode=0, stdout="p1 p2 p3 p4 p5 p6 p7 p8 p9 cwd /home/test\n"),
        ]
        mappings = {}
        with patch.object(provider, '_find_session_id_by_cwd', return_value=None):
            provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
            assert mappings == {}

    @patch("subprocess.run")
    def test_pane_process_timeout(self, mock_run):
        """超时时静默处理"""
        import subprocess
        provider = ConcreteProvider()
        mock_run.side_effect = subprocess.TimeoutExpired("ps", 5)
        mappings = {}
        provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
        assert mappings == {}

    @patch("subprocess.run")
    def test_pane_process_matches_by_name(self, mock_run):
        """进程命令包含tool name时匹配"""
        provider = ConcreteProvider()
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="python run-test-tool serve"),
            MagicMock(returncode=0, stdout="p1 p2 p3 p4 p5 p6 p7 cwd /home/test\n"),
        ]
        mappings = {}
        with patch.object(provider, '_find_session_id_by_cwd', return_value="s1"):
            provider._scan_tmux_pane_process(None, "my-session", 9999, mappings)
            assert "s1" in mappings


# ========== BaseSessionProvider: _find_existing_tmux ==========

class TestFindExistingTmux:
    """测试_find_existing_tmux方法"""

    def test_find_existing_tmux_with_tmux_info(self):
        """session已有tmux_info时直接返回"""
        provider = ConcreteProvider()
        tmux = TmuxMapping(tmux_session_name="existing", tmux_window_id=0, pane_pid=123, is_attached=True)
        session = _make_session()
        session.tmux_info = tmux
        result = provider._find_existing_tmux(session, None)
        assert result is tmux

    def test_find_existing_tmux_scan_mappings(self):
        """tmux_info为None时扫描映射"""
        provider = ConcreteProvider()
        session = _make_session(session_id="target-id")
        mapping = TmuxMapping(tmux_session_name="found", tmux_window_id=0, pane_pid=456, is_attached=False)
        with patch.object(provider, 'scan_tmux_mappings', return_value={"target-id": mapping}):
            result = provider._find_existing_tmux(session, None)
            assert result is mapping

    def test_find_existing_tmux_not_found(self):
        """扫描后也找不到时返回None"""
        provider = ConcreteProvider()
        session = _make_session(session_id="missing-id")
        with patch.object(provider, 'scan_tmux_mappings', return_value={}):
            result = provider._find_existing_tmux(session, None)
            assert result is None

    def test_find_existing_tmux_no_meta(self):
        """session没有meta属性时返回None"""
        provider = ConcreteProvider()
        session = MagicMock(spec=[])  # 无任何属性
        session.tmux_info = None
        # hasattr(session, 'meta') 返回False
        with patch.object(provider, 'scan_tmux_mappings', return_value={"any": "val"}):
            result = provider._find_existing_tmux(session, None)
            assert result is None


# ========== BaseSessionProvider: _find_session_id_by_cwd (default) ==========

class TestFindSessionIdByCwd:
    """测试_find_session_id_by_cwd默认实现"""

    def test_default_returns_none(self):
        """基类默认实现返回None"""
        provider = ConcreteProvider()
        result = provider._find_session_id_by_cwd(None, "/some/path")
        assert result is None

    def test_default_returns_none_with_host(self):
        """带host时默认实现仍返回None"""
        provider = ConcreteProvider()
        host = _make_host()
        result = provider._find_session_id_by_cwd(host, "/some/path")
        assert result is None


# ========== BaseSessionProvider: get_session_stats / get_session_history ==========

class TestGetSessionDefaults:
    """测试get_session_stats和get_session_history默认实现"""

    def test_get_session_stats_default(self):
        provider = ConcreteProvider()
        result = provider.get_session_stats("any-id")
        assert result == {}

    def test_get_session_history_default(self):
        provider = ConcreteProvider()
        result = provider.get_session_history("any-id")
        assert result == []

    def test_get_session_history_custom_limit(self):
        provider = ConcreteProvider()
        result = provider.get_session_history("any-id", limit=100)
        assert result == []


# ========== BaseSessionProvider: _is_cache_valid ==========

class TestIsCacheValid:
    """测试_is_cache_valid边界条件"""

    def test_cache_none_returns_false(self):
        """缓存为None时返回False"""
        provider = ConcreteProvider()
        assert provider._is_cache_valid(None) is False

    def test_cache_time_none_returns_false(self):
        """缓存时间未设置时返回False"""
        provider = ConcreteProvider()
        provider._cache = []
        provider._cache_time = None
        assert provider._is_cache_valid(None) is False

    def test_cache_valid_within_ttl(self):
        """缓存在TTL内返回True"""
        provider = ConcreteProvider()
        provider._cache = [{"session": "data"}]
        provider._cache_time = time.time()
        provider._cache_ttl = 60
        assert provider._is_cache_valid(None) is True

    def test_cache_expired(self):
        """缓存过期返回False"""
        provider = ConcreteProvider()
        provider._cache = [{"session": "data"}]
        provider._cache_time = time.time() - 120
        provider._cache_ttl = 60
        assert provider._is_cache_valid(None) is False

    def test_cache_remote_host_returns_false(self):
        """远程host不使用缓存"""
        provider = ConcreteProvider()
        provider._cache = [{"session": "data"}]
        provider._cache_time = time.time()
        host = _make_host()
        assert provider._is_cache_valid(host) is False

    def test_cache_custom_ttl(self):
        """自定义TTL"""
        provider = ConcreteProvider(config={"cache_ttl": 10})
        provider._cache = [{"data": True}]
        provider._cache_time = time.time() - 15
        assert provider._is_cache_valid(None) is False

    def test_cache_at_exact_boundary(self):
        """缓存在TTL边界（刚好过期）"""
        provider = ConcreteProvider()
        provider._cache = [{"data": True}]
        provider._cache_time = time.time() - 60  # exactly TTL
        provider._cache_ttl = 60
        # time.time() - cache_time >= cache_ttl -> expired
        assert provider._is_cache_valid(None) is False


# ========== BaseSessionProvider: _update_cache ==========

class TestUpdateCache:
    """测试_update_cache方法"""

    def test_update_cache_local(self):
        """本地扫描更新缓存"""
        provider = ConcreteProvider()
        sessions = [{"id": "1"}, {"id": "2"}]
        provider._update_cache(sessions, None)
        assert provider._cache == sessions
        assert provider._cache_time is not None

    def test_update_cache_remote_no_cache(self):
        """远程扫描不更新缓存"""
        provider = ConcreteProvider()
        provider._cache = None
        provider._cache_time = None
        host = _make_host()
        provider._update_cache([{"id": "1"}], host)
        assert provider._cache is None
        assert provider._cache_time is None

    def test_update_cache_preserves_existing_remote(self):
        """远程扫描不覆盖已有本地缓存"""
        provider = ConcreteProvider()
        local_sessions = [{"id": "local"}]
        provider._cache = local_sessions
        provider._cache_time = 100.0
        host = _make_host()
        provider._update_cache([{"id": "remote"}], host)
        assert provider._cache == local_sessions
        assert provider._cache_time == 100.0


# ========== BaseSessionProvider: scan_sessions模板方法 ==========

class TestScanSessionsTemplate:
    """测试scan_sessions模板方法的缓存逻辑"""

    def test_scan_uses_cache_on_second_call(self):
        """第二次调用使用缓存"""
        provider = ConcreteProvider()
        with patch.object(provider, '_pre_scan_check', return_value=True):
            with patch.object(provider, '_scan_impl', return_value=[{"id": "1"}]):
                with patch.object(provider, '_post_scan_process', return_value=[{"id": "1"}]):
                    result1 = provider.scan_sessions()
                    result2 = provider.scan_sessions()
                    assert result1 == [{"id": "1"}]
                    assert result2 == [{"id": "1"}]
                    # _scan_impl只调用一次
                    provider._scan_impl.assert_called_once()

    def test_scan_force_refresh_ignores_cache(self):
        """force_refresh=True忽略缓存"""
        provider = ConcreteProvider()
        call_count = 0

        def mock_scan(host):
            nonlocal call_count
            call_count += 1
            return [{"call": call_count}]

        with patch.object(provider, '_pre_scan_check', return_value=True):
            with patch.object(provider, '_scan_impl', side_effect=mock_scan):
                with patch.object(provider, '_post_scan_process', side_effect=lambda s, h: s):
                    provider.scan_sessions()
                    provider.scan_sessions(force_refresh=True)
                    assert call_count == 2

    def test_scan_returns_empty_on_pre_check_fail(self):
        """前置检查失败时返回空列表"""
        provider = ConcreteProvider()
        with patch.object(provider, '_pre_scan_check', return_value=False):
            result = provider.scan_sessions()
            assert result == []

    def test_scan_remote_does_not_cache(self):
        """远程扫描不缓存结果"""
        provider = ConcreteProvider()
        host = _make_host()
        with patch.object(provider, '_pre_scan_check', return_value=True):
            with patch.object(provider, '_scan_impl', return_value=[{"id": "remote"}]):
                with patch.object(provider, '_post_scan_process', return_value=[{"id": "remote"}]):
                    provider.scan_sessions(host=host)
                    # 第二次调用不应使用缓存
                    provider.scan_sessions(host=host)
                    assert provider._scan_impl.call_count == 2


# ========== ClaudeProvider: _scan_remote_impl ==========

class TestClaudeScanRemoteImpl:
    """测试ClaudeProvider._scan_remote_impl"""

    @patch("subprocess.run")
    def test_scan_remote_empty_output(self, mock_run):
        """远程find无输出"""
        provider = ClaudeProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = provider._scan_remote_impl(host)
        assert result == []

    @patch("subprocess.run")
    def test_scan_remote_find_failure(self, mock_run):
        """远程find命令失败"""
        provider = ClaudeProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=1, stderr="permission denied")
        result = provider._scan_remote_impl(host)
        assert result == []

    @patch("subprocess.run")
    def test_scan_remote_parses_stat_output(self, mock_run):
        """解析stat输出格式: mtime|path"""
        provider = ClaudeProvider()
        host = _make_host()
        stat_output = "1700000000|/home/user/.claude/projects/-Users-test-project/abc123.jsonl"
        mock_run.return_value = MagicMock(returncode=0, stdout=stat_output)
        result = provider._scan_remote_impl(host)
        assert len(result) == 1
        assert result[0].meta.session_id == "abc123"
        assert result[0].meta.status == "remote"

    @patch("subprocess.run")
    def test_scan_remote_with_stats_script(self, mock_run):
        """有stats_script时获取统计"""
        provider = ClaudeProvider()
        host = _make_host(stats_script="~/stats.py")
        stat_output = "1700000000|/home/user/.claude/projects/-Users-test/abc.jsonl"
        stats_json = json.dumps({
            "abc": {"topic": "test topic", "stats": {"tokens": 100}, "cwd": "/home/user/test"}
        })
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=stat_output),
            MagicMock(returncode=0, stdout=stats_json),
        ]
        result = provider._scan_remote_impl(host)
        assert len(result) == 1
        assert result[0].topic == "test topic"

    @patch("subprocess.run")
    def test_scan_remote_without_stats_script(self, mock_run):
        """无stats_script时跳过统计"""
        provider = ClaudeProvider()
        host = _make_host(stats_script="")
        stat_output = "1700000000|/home/user/.claude/projects/-Users-test/abc.jsonl"
        mock_run.return_value = MagicMock(returncode=0, stdout=stat_output)
        result = provider._scan_remote_impl(host)
        assert len(result) == 1
        assert result[0].topic is None

    @patch("subprocess.run")
    def test_scan_remote_stats_script_failure(self, mock_run):
        """stats脚本失败时继续处理"""
        provider = ClaudeProvider()
        host = _make_host(stats_script="~/stats.py")
        stat_output = "1700000000|/home/user/.claude/projects/-Users-test/abc.jsonl"
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=stat_output),
            MagicMock(returncode=1, stderr="script error"),
        ]
        result = provider._scan_remote_impl(host)
        assert len(result) == 1

    @patch("subprocess.run")
    def test_scan_remote_stats_invalid_json(self, mock_run):
        """stats输出非法JSON时继续处理"""
        provider = ClaudeProvider()
        host = _make_host(stats_script="~/stats.py")
        stat_output = "1700000000|/home/user/.claude/projects/-Users-test/abc.jsonl"
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=stat_output),
            MagicMock(returncode=0, stdout="not-json"),
        ]
        result = provider._scan_remote_impl(host)
        assert len(result) == 1

    @patch("subprocess.run")
    def test_scan_remote_malformed_stat_line(self, mock_run):
        """stat输出格式错误时跳过该行"""
        provider = ClaudeProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=0, stdout="no-pipe-here\n")
        result = provider._scan_remote_impl(host)
        assert result == []

    @patch("subprocess.run")
    def test_scan_remote_skips_short_parts(self, mock_run):
        """stat输出parts少于2时跳过"""
        provider = ClaudeProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=0, stdout="single_value\n")
        result = provider._scan_remote_impl(host)
        assert result == []


# ========== ClaudeProvider: _find_session_id_by_cwd ==========

class TestClaudeFindSessionIdByCwd:
    """测试ClaudeProvider._find_session_id_by_cwd"""

    @patch("subprocess.run")
    def test_find_session_id_success(self, mock_run):
        """成功找到jsonl文件"""
        provider = ClaudeProvider()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="/home/user/.claude/projects/-Users-test/abc123.jsonl\n"
        )
        result = provider._find_session_id_by_cwd(None, "/Users/test")
        assert result == "abc123"

    @patch("subprocess.run")
    def test_find_session_id_not_found(self, mock_run):
        """没有找到jsonl文件"""
        provider = ClaudeProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = provider._find_session_id_by_cwd(None, "/Users/test")
        assert result is None

    @patch("subprocess.run")
    def test_find_session_id_command_failure(self, mock_run):
        """命令失败返回None"""
        provider = ClaudeProvider()
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = provider._find_session_id_by_cwd(None, "/Users/test")
        assert result is None

    @patch("subprocess.run")
    def test_find_session_id_with_remote_host(self, mock_run):
        """远程host传递"""
        provider = ClaudeProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="/path/to/session-id.jsonl\n"
        )
        result = provider._find_session_id_by_cwd(host, "/Users/test")
        assert result == "session-id"
        # 验证使用了SSH
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ssh"


# ========== ClaudeProvider: _find_jsonl_path ==========

class TestClaudeFindJsonlPath:
    """测试ClaudeProvider._find_jsonl_path"""

    def test_find_jsonl_project_dir_not_exists(self):
        """项目目录不存在时返回None"""
        provider = ClaudeProvider()
        result = provider._find_jsonl_path("test-id", "/completely/fake/path")
        assert result is None

    def test_find_jsonl_exact_match(self, tmp_path):
        """精确匹配session_id前缀"""
        provider = ClaudeProvider()
        encoded = provider._encode_path("/tmp/test-project")
        project_dir = tmp_path / encoded
        project_dir.mkdir(parents=True)

        # 创建匹配的文件
        jsonl_file = project_dir / "abc123def456.jsonl"
        jsonl_file.touch()

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            result = provider._find_jsonl_path("abc123def456", "/tmp/test-project")
            assert result is not None
            assert "abc123def456" in result

    def test_find_jsonl_prefix_match(self, tmp_path):
        """前8位匹配"""
        provider = ClaudeProvider()
        encoded = provider._encode_path("/tmp/test-project")
        project_dir = tmp_path / encoded
        project_dir.mkdir(parents=True)

        jsonl_file = project_dir / "abc123def.jsonl"
        jsonl_file.touch()

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            result = provider._find_jsonl_path("abc123def456-789", "/tmp/test-project")
            assert result is not None

    def test_find_jsonl_fallback_to_newest(self, tmp_path):
        """无精确匹配时返回最新文件"""
        provider = ClaudeProvider()
        encoded = provider._encode_path("/tmp/test-project")
        project_dir = tmp_path / encoded
        project_dir.mkdir(parents=True)

        old_file = project_dir / "old-session.jsonl"
        old_file.touch()
        import time
        time.sleep(0.05)
        new_file = project_dir / "new-session.jsonl"
        new_file.touch()

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            result = provider._find_jsonl_path("nonexistent-id", "/tmp/test-project")
            assert result is not None
            assert "new-session" in result

    def test_find_jsonl_empty_directory(self, tmp_path):
        """目录为空时返回None"""
        provider = ClaudeProvider()
        encoded = provider._encode_path("/tmp/empty-project")
        project_dir = tmp_path / encoded
        project_dir.mkdir(parents=True)

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            result = provider._find_jsonl_path("any-id", "/tmp/empty-project")
            assert result is None


# ========== ClaudeProvider: _encode_path ==========

class TestClaudeEncodePath:
    """测试ClaudeProvider._encode_path边界条件"""

    def test_encode_simple_path(self):
        provider = ClaudeProvider()
        result = provider._encode_path("/Users/test")
        assert result == "-Users-test"

    def test_encode_strips_leading_slash(self):
        provider = ClaudeProvider()
        result = provider._encode_path("/home/user/project")
        assert result == "-home-user-project"

    def test_encode_with_home_tilde(self):
        """路径含~时展开home目录"""
        provider = ClaudeProvider()
        result = provider._encode_path("~/project")
        home = str(Path.home()).lstrip("/")
        assert result == "-" + home.replace("/", "-") + "-project"

    def test_encode_trailing_slash(self):
        provider = ClaudeProvider()
        result = provider._encode_path("/Users/test/")
        assert result.endswith("-test-")

    def test_encode_root_path(self):
        provider = ClaudeProvider()
        result = provider._encode_path("/")
        assert result == "-"


# ========== ClaudeProvider: _decode_project_dir ==========

class TestClaudeDecodeProjectDir:
    """测试ClaudeProvider._decode_project_dir"""

    def test_decode_standard_encoded(self):
        provider = ClaudeProvider()
        result = provider._decode_project_dir("-Users-ada-project")
        assert result == "/Users/ada/project"

    def test_decode_no_leading_dash(self):
        """不以-开头时原样返回"""
        provider = ClaudeProvider()
        result = provider._decode_project_dir("some_dir")
        assert result == "some_dir"

    def test_decode_single_dash(self):
        provider = ClaudeProvider()
        result = provider._decode_project_dir("-")
        assert result == "/"

    def test_decode_roundtrip(self):
        """编码再解码应得到原始路径（不含尾部斜杠）"""
        provider = ClaudeProvider()
        original = "/Users/ada/bin/sessionflow"
        encoded = provider._encode_path(original)
        decoded = provider._decode_project_dir(encoded)
        assert decoded == original


# ========== ClaudeProvider: _detect_entrypoint ==========

class TestClaudeDetectEntrypoint:
    """测试ClaudeProvider._detect_entrypoint"""

    def test_detect_entrypoint_found(self, tmp_path):
        """找到entrypoint字段"""
        provider = ClaudeProvider()
        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"entrypoint": "sdk-cli", "other": "data"}) + "\n")
            f.write(json.dumps({"msg": "more data"}) + "\n")
        result = provider._detect_entrypoint(jsonl_file)
        assert result == "sdk-cli"

    def test_detect_entrypoint_cli(self, tmp_path):
        provider = ClaudeProvider()
        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"entrypoint": "cli"}) + "\n")
        result = provider._detect_entrypoint(jsonl_file)
        assert result == "cli"

    def test_detect_entrypoint_not_found(self, tmp_path):
        """没有entrypoint字段"""
        provider = ClaudeProvider()
        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"type": "message"}) + "\n")
        result = provider._detect_entrypoint(jsonl_file)
        assert result is None

    def test_detect_entrypoint_invalid_json_lines(self, tmp_path):
        """包含无效JSON行时跳过"""
        provider = ClaudeProvider()
        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write("not-json\n")
            f.write(json.dumps({"entrypoint": "cli"}) + "\n")
        result = provider._detect_entrypoint(jsonl_file)
        assert result == "cli"

    def test_detect_entrypoint_file_not_exists(self):
        """文件不存在时返回None"""
        provider = ClaudeProvider()
        result = provider._detect_entrypoint(Path("/nonexistent/file.jsonl"))
        assert result is None

    def test_detect_entrypoint_stops_after_5000_bytes(self, tmp_path):
        """超过5000字节后停止检查"""
        provider = ClaudeProvider()
        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            # 写入超过5000字节的数据（无entrypoint）
            for i in range(200):
                f.write(json.dumps({"line": i, "data": "x" * 30}) + "\n")
            # 最后一行有entrypoint（但不应被读取到）
            f.write(json.dumps({"entrypoint": "sdk-cli"}) + "\n")
        result = provider._detect_entrypoint(jsonl_file)
        # 由于前面数据超过5000字节，最后的entrypoint不会被发现
        assert result is None


# ========== ClaudeProvider: _parse_session_json ==========

class TestClaudeParseSessionJson:
    """测试ClaudeProvider._parse_session_json"""

    def test_parse_valid_json(self, tmp_path):
        """解析有效的session JSON"""
        provider = ClaudeProvider()
        json_file = tmp_path / "session.json"
        data = {
            "sessionId": "sess-001",
            "cwd": "/Users/test",
            "status": "busy",
            "startedAt": 1000,
            "updatedAt": 2000,
            "pid": 12345,
            "version": "1.0.0",
        }
        with open(json_file, "w") as f:
            json.dump(data, f)
        meta = provider._parse_session_json(json_file)
        assert meta.session_id == "sess-001"
        assert meta.cwd == "/Users/test"
        assert meta.status == "busy"
        assert meta.pid == 12345
        assert meta.version == "1.0.0"

    def test_parse_json_defaults(self, tmp_path):
        """缺失字段使用默认值"""
        provider = ClaudeProvider()
        json_file = tmp_path / "session.json"
        with open(json_file, "w") as f:
            json.dump({}, f)
        meta = provider._parse_session_json(json_file)
        assert meta.session_id == ""
        assert meta.cwd == ""
        assert meta.status == "idle"
        assert meta.started_at == 0
        assert meta.updated_at == 0
        assert meta.pid is None
        assert meta.version is None

    def test_parse_invalid_json_file(self, tmp_path):
        """无效JSON返回None"""
        provider = ClaudeProvider()
        json_file = tmp_path / "bad.json"
        with open(json_file, "w") as f:
            f.write("{invalid json}")
        result = provider._parse_session_json(json_file)
        assert result is None

    def test_parse_nonexistent_file(self):
        """不存在的文件返回None"""
        provider = ClaudeProvider()
        result = provider._parse_session_json(Path("/no/such/file.json"))
        assert result is None


# ========== ClaudeProvider: _attach_tmux ==========

class TestClaudeAttachTmux:
    """测试ClaudeProvider._attach_tmux"""

    def test_attach_tmux_host_none_returns_false(self):
        """host为None时返回False"""
        provider = ClaudeProvider()
        tmux = TmuxMapping(tmux_session_name="test", tmux_window_id=0, pane_pid=123, is_attached=False)
        result = provider._attach_tmux(tmux, None)
        assert result is False

    @patch("providers.terminals.iterm2.ITerm2Terminal.open_session", return_value=True)
    def test_attach_tmux_success(self, mock_open):
        """成功attach"""
        provider = ClaudeProvider()
        host = _make_host(user="ada", hostname="10.0.0.1", ssh_alias=None)
        tmux = TmuxMapping(tmux_session_name="claude-abc", tmux_window_id=0, pane_pid=123, is_attached=False)
        result = provider._attach_tmux(tmux, host)
        assert result is True
        call_args = mock_open.call_args[0]
        assert "ssh -t" in call_args[1]
        assert "tmux attach -t claude-abc" in call_args[1]

    @patch("providers.terminals.iterm2.ITerm2Terminal.open_session", return_value=True)
    def test_attach_tmux_with_ssh_alias(self, mock_open):
        """使用ssh_alias"""
        provider = ClaudeProvider()
        host = _make_host(ssh_alias="my-server")
        tmux = TmuxMapping(tmux_session_name="test-session", tmux_window_id=0, pane_pid=123, is_attached=False)
        provider._attach_tmux(tmux, host)
        call_args = mock_open.call_args[0]
        assert "my-server" in call_args[1]


# ========== ClaudeProvider: _create_and_recover ==========

class TestClaudeCreateAndRecover:
    """测试ClaudeProvider._create_and_recover"""

    def test_create_and_recover_host_none_calls_local(self):
        """host为None时调用recover_local_session"""
        provider = ClaudeProvider()
        session = _make_session()
        with patch.object(provider, 'recover_local_session', return_value=True) as mock_local:
            result = provider._create_and_recover(session, None)
            assert result is True
            mock_local.assert_called_once_with(session)

    @patch("providers.terminals.iterm2.ITerm2Terminal.open_session", return_value=True)
    def test_create_and_recover_with_host(self, mock_open):
        """有host时创建tmux并恢复"""
        provider = ClaudeProvider()
        host = _make_host(user="ada", hostname="10.0.0.1")
        session = _make_session(session_id="abc123def456", cwd="/home/ada/project")
        result = provider._create_and_recover(session, host)
        assert result is True
        call_args = mock_open.call_args[0]
        assert "ssh -t" in call_args[1]
        assert "tmux new-session" in call_args[1]
        assert "claude-abc123de" in call_args[1]  # short_id = first 8 chars

    @patch("providers.terminals.iterm2.ITerm2Terminal.open_session", return_value=True)
    def test_create_and_recover_includes_cwd(self, mock_open):
        """tmux创建包含正确的cwd"""
        provider = ClaudeProvider()
        host = _make_host()
        session = _make_session(cwd="/home/ada/myproject")
        provider._create_and_recover(session, host)
        call_args = mock_open.call_args[0]
        assert "/home/ada/myproject" in call_args[1]


# ========== ClaudeProvider: get_session_stats / get_session_history ==========

class TestClaudeSessionDetails:
    """测试ClaudeProvider的get_session_stats和get_session_history"""

    def test_get_session_stats_returns_empty(self):
        provider = ClaudeProvider()
        result = provider.get_session_stats("test-id")
        assert result == {}

    def test_get_session_history_returns_empty(self):
        provider = ClaudeProvider()
        result = provider.get_session_history("test-id")
        assert result == []

    def test_get_session_history_custom_limit(self):
        provider = ClaudeProvider()
        result = provider.get_session_history("test-id", limit=10)
        assert result == []


# ========== ClaudeProvider: _scan_impl路由 ==========

class TestClaudeScanImpl:
    """测试_scan_impl路由逻辑"""

    def test_scan_impl_local_when_no_host(self):
        """host=None时调用_scan_local_impl"""
        provider = ClaudeProvider()
        with patch.object(provider, '_scan_local_impl', return_value=[{"local": True}]) as mock_local:
            result = provider._scan_impl(None)
            assert result == [{"local": True}]
            mock_local.assert_called_once()

    def test_scan_impl_remote_when_host(self):
        """有host时调用_scan_remote_impl"""
        provider = ClaudeProvider()
        host = _make_host()
        with patch.object(provider, '_scan_remote_impl', return_value=[{"remote": True}]) as mock_remote:
            result = provider._scan_impl(host)
            assert result == [{"remote": True}]
            mock_remote.assert_called_once_with(host)


# ========== ClaudeProvider: _scan_history_sessions子agent检测 ==========

class TestClaudeScanHistorySubagent:
    """测试_scan_history_sessions中的子agent检测"""

    def test_detect_subagent_from_path(self, tmp_path):
        """路径包含subagents时标记为子agent"""
        from core.models import SessionMeta, SessionRecord

        provider = ClaudeProvider()
        project_dir = tmp_path / "-Users-test"
        subagent_dir = project_dir / "subagents"
        subagent_dir.mkdir(parents=True)

        jsonl_file = subagent_dir / "agent-session.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"type":"summary","cwd":"/test","topic":"sub task","stats":{}}\n')

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            with patch('core.parser.get_jsonl_summary', return_value={"cwd": "/test", "topic": "sub task", "stats": {}}):
                with patch('core.storage.update_stats_cache'):
                    sessions = provider._scan_history_sessions()
                    assert len(sessions) == 1
                    assert sessions[0].is_subagent is True
                    assert sessions[0].entrypoint == "sdk-cli"

    def test_detect_subagent_from_filename(self, tmp_path):
        """文件名以agent-开头时标记为子agent"""
        provider = ClaudeProvider()
        project_dir = tmp_path / "-Users-test"
        project_dir.mkdir(parents=True)

        jsonl_file = project_dir / "agent-session.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"type":"summary","cwd":"/test","stats":{}}\n')

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            with patch('core.parser.get_jsonl_summary', return_value={"cwd": "/test", "stats": {}}):
                with patch('core.storage.update_stats_cache'):
                    sessions = provider._scan_history_sessions()
                    assert len(sessions) == 1
                    assert sessions[0].is_subagent is True

    def test_normal_session_not_subagent(self, tmp_path):
        """普通session不是子agent"""
        provider = ClaudeProvider()
        project_dir = tmp_path / "-Users-test"
        project_dir.mkdir(parents=True)

        jsonl_file = project_dir / "normal-session.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"type":"summary","cwd":"/test","stats":{}}\n')

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            with patch('core.parser.get_jsonl_summary', return_value={"cwd": "/test", "stats": {}}):
                with patch('core.storage.update_stats_cache'):
                    sessions = provider._scan_history_sessions()
                    assert len(sessions) == 1
                    assert sessions[0].is_subagent is False
                    assert sessions[0].entrypoint == "cli"

    def test_skips_meta_json_files(self, tmp_path):
        """跳过.meta.json文件"""
        provider = ClaudeProvider()
        project_dir = tmp_path / "-Users-test"
        project_dir.mkdir(parents=True)

        meta_file = project_dir / "session.meta.json"
        meta_file.touch()
        real_file = project_dir / "session.jsonl"
        with open(real_file, "w") as f:
            f.write('{"type":"summary","cwd":"/test","stats":{}}\n')

        with patch.object(type(provider), 'PROJECTS_DIR', tmp_path):
            with patch('core.parser.get_jsonl_summary', return_value={"cwd": "/test", "stats": {}}):
                with patch('core.storage.update_stats_cache'):
                    sessions = provider._scan_history_sessions()
                    assert len(sessions) == 1


# ========== ClaudeProvider: recover_session路由 ==========

class TestClaudeRecoverSession:
    """测试ClaudeProvider.recover_session路由"""

    def test_recover_with_existing_tmux(self):
        """有tmux时调用_attach_tmux"""
        provider = ClaudeProvider()
        session = _make_session()
        host = _make_host()
        tmux = TmuxMapping(tmux_session_name="existing", tmux_window_id=0, pane_pid=123, is_attached=False)
        with patch.object(provider, '_find_existing_tmux', return_value=tmux):
            with patch.object(provider, '_attach_tmux', return_value=True) as mock_attach:
                result = provider.recover_session(session, host)
                assert result is True
                mock_attach.assert_called_once_with(tmux, host)

    def test_recover_without_tmux(self):
        """无tmux时调用_create_and_recover"""
        provider = ClaudeProvider()
        session = _make_session()
        host = _make_host()
        with patch.object(provider, '_find_existing_tmux', return_value=None):
            with patch.object(provider, '_create_and_recover', return_value=True) as mock_create:
                result = provider.recover_session(session, host)
                assert result is True
                mock_create.assert_called_once_with(session, host)


# ========== ClaudeProvider: tool_info属性 ==========

class TestClaudeToolInfo:
    """测试ClaudeProvider.tool_info属性"""

    def test_tool_info_properties(self):
        provider = ClaudeProvider()
        info = provider.tool_info
        assert info.name == "claude"
        assert info.display_name == "Claude Code"
        assert info.executable == "claude"
        assert info.supports_resume is True
        assert "{id}" in info.resume_arg_format
        assert "claude" in info.session_dir

    def test_tool_info_immutable_per_instance(self):
        """每次访问返回相同值"""
        provider = ClaudeProvider()
        info1 = provider.tool_info
        info2 = provider.tool_info
        assert info1.name == info2.name
        assert info1.version == info2.version


# ========== BaseSessionProvider: __init__ ==========

class TestBaseProviderInit:
    """测试BaseSessionProvider初始化"""

    def test_init_default_config(self):
        provider = ConcreteProvider()
        assert provider.config == {}
        assert provider._cache is None
        assert provider._cache_time is None
        assert provider._cache_ttl == 60

    def test_init_custom_config(self):
        provider = ConcreteProvider(config={"cache_ttl": 120, "key": "value"})
        assert provider.config["key"] == "value"
        assert provider._cache_ttl == 120

    def test_init_none_config(self):
        provider = ConcreteProvider(config=None)
        assert provider.config == {}


# ========== BaseSessionProvider: is_installed / get_version ==========

class TestBaseProviderInstalled:
    """测试is_installed和get_version"""

    @patch("subprocess.run")
    def test_is_installed_success(self, mock_run):
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0)
        assert provider.is_installed() is True

    @patch("subprocess.run")
    def test_is_installed_failure(self, mock_run):
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=1)
        assert provider.is_installed() is False

    @patch("subprocess.run")
    def test_is_installed_timeout(self, mock_run):
        import subprocess
        provider = ConcreteProvider()
        mock_run.side_effect = subprocess.TimeoutExpired("test", 10)
        assert provider.is_installed() is False

    @patch("subprocess.run")
    def test_is_installed_file_not_found(self, mock_run):
        provider = ConcreteProvider()
        mock_run.side_effect = FileNotFoundError
        assert provider.is_installed() is False

    @patch("subprocess.run")
    def test_get_version_success(self, mock_run):
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="1.2.3\n")
        assert provider.get_version() == "1.2.3"

    @patch("subprocess.run")
    def test_get_version_failure(self, mock_run):
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=1)
        assert provider.get_version() == "unknown"

    @patch("subprocess.run")
    def test_get_version_timeout(self, mock_run):
        import subprocess
        provider = ConcreteProvider()
        mock_run.side_effect = subprocess.TimeoutExpired("test", 10)
        assert provider.get_version() == "unknown"

    @patch("subprocess.run")
    def test_get_version_multiline(self, mock_run):
        """多行输出时只取第一行"""
        provider = ConcreteProvider()
        mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0\nCopyright notice\n")
        assert provider.get_version() == "1.0.0"

    @patch("subprocess.run")
    def test_is_installed_with_remote_host(self, mock_run):
        provider = ConcreteProvider()
        host = _make_host()
        mock_run.return_value = MagicMock(returncode=0)
        assert provider.is_installed(host=host) is True
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ssh"


# ========== BaseSessionProvider: generate_recovery_cmd ==========

class TestGenerateRecoveryCmd:
    """测试generate_recovery_cmd"""

    def test_generate_recovery_cmd_supported(self):
        provider = ConcreteProvider()
        result = provider.generate_recovery_cmd("abc123", "/test")
        assert result == "test-tool --resume abc123"

    def test_generate_recovery_cmd_unsupported(self):
        """supports_resume=False时返回空字符串"""
        class NoResumeProvider(ConcreteProvider):
            @property
            def tool_info(self):
                info = super().tool_info
                return ToolInfo(
                    name="test-tool",
                    display_name="Test Tool",
                    version="1.0.0",
                    executable="test-tool",
                    session_dir="/test",
                    supports_resume=False,
                    resume_arg_format="",
                    schema_version="1.0"
                )
        provider = NoResumeProvider()
        result = provider.generate_recovery_cmd("abc123", "/test")
        assert result == ""
