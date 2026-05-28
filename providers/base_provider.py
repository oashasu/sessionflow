"""Provider基类 - 定义通用流程骨架（模板模式）"""

import subprocess
import shlex
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any

from .protocol import ToolInfo, TmuxMapping, RemoteHost, SessionProvider


class BaseSessionProvider(ABC, SessionProvider):
    """Provider基类 - 提供通用流程骨架

    子类继承此类可获得：
    - 模板方法scan_sessions（通用扫描流程）
    - 钩子方法可覆盖（_pre_scan_check, _post_scan_process）
    - 缓存机制
    - 安全的SSH命令执行

    Protocol用于接口契约，ABC用于代码复用。
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._cache: Optional[List[Any]] = None
        self._cache_time: Optional[float] = None
        self._cache_ttl: int = self.config.get("cache_ttl", 60)

    # ========== 工具信息（子类必须实现） ==========

    @property
    @abstractmethod
    def tool_info(self) -> ToolInfo:
        """返回工具基本信息（子类必须实现）"""
        pass

    # ========== 模板方法：扫描流程 ==========

    def scan_sessions(
        self,
        host: Optional[RemoteHost] = None,
        force_refresh: bool = False
    ) -> List[Any]:
        """扫描会话的通用流程（模板方法）

        流程：
        1. 前置检查（钩子）
        2. 核心扫描（子类实现）
        3. 后置处理（钩子）

        Args:
            host: 远程主机（None表示本机）
            force_refresh: 强制刷新缓存

        Returns:
            会话记录列表
        """
        # 缓存检查
        if not force_refresh and self._is_cache_valid(host):
            return self._cache or []

        # 钩子1：前置检查
        if not self._pre_scan_check(host):
            return []

        # 核心扫描（子类实现）
        sessions = self._scan_impl(host)

        # 钩子2：后置处理
        sessions = self._post_scan_process(sessions, host)

        # 更新缓存
        self._update_cache(sessions, host)

        return sessions

    def _is_cache_valid(self, host: Optional[RemoteHost]) -> bool:
        """检查缓存是否有效"""
        if self._cache is None or self._cache_time is None:
            return False
        # 远程扫描不使用缓存（网络状态可能变化）
        if host is not None:
            return False
        return time.time() - self._cache_time < self._cache_ttl

    def _update_cache(self, sessions: List[Any], host: Optional[RemoteHost]) -> None:
        """更新缓存"""
        if host is None:  # 仅缓存本机扫描
            self._cache = sessions
            self._cache_time = time.time()

    # ========== 钩子方法（子类可覆盖） ==========

    def _pre_scan_check(self, host: Optional[RemoteHost]) -> bool:
        """钩子：前置检查（子类可覆盖）

        默认检查工具是否安装。
        """
        return self.is_installed(host)

    def _post_scan_process(
        self,
        sessions: List[Any],
        host: Optional[RemoteHost]
    ) -> List[Any]:
        """钩子：后置处理（子类可覆盖）

        默认添加tmux映射和生成恢复命令。
        """
        # 扫描tmux映射
        tmux_mappings = self.scan_tmux_mappings(host)

        # 为每个session添加信息
        for session in sessions:
            # 添加tmux映射
            if hasattr(session, 'meta') and hasattr(session.meta, 'session_id'):
                session_id = session.meta.session_id
                if session_id in tmux_mappings:
                    session.tmux_info = tmux_mappings[session_id]

            # 生成恢复命令
            if hasattr(session, 'meta') and hasattr(session, 'recovery_cmd'):
                cwd = session.meta.cwd if hasattr(session.meta, 'cwd') else ""
                session.recovery_cmd = self.generate_recovery_cmd(
                    session.meta.session_id, cwd
                )

        return sessions

    # ========== 核心实现（子类必须实现） ==========

    @abstractmethod
    def _scan_impl(self, host: Optional[RemoteHost]) -> List[Any]:
        """核心扫描实现（子类必须实现）"""
        pass

    # ========== 默认实现 ==========

    def is_installed(self, host: Optional[RemoteHost] = None) -> bool:
        """检测工具是否已安装"""
        try:
            cmd = self._build_ssh_cmd(host, [self.tool_info.executable, "--version"])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_version(self, host: Optional[RemoteHost] = None) -> str:
        """获取工具版本"""
        try:
            cmd = self._build_ssh_cmd(host, [self.tool_info.executable, "--version"])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
            return "unknown"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return "unknown"

    def generate_recovery_cmd(self, session_id: str, cwd: str) -> str:
        """生成恢复命令"""
        if not self.tool_info.supports_resume:
            return ""
        return self.tool_info.resume_arg_format.format(id=session_id)

    # ========== SSH命令安全执行 ==========

    def _build_ssh_cmd(
        self,
        host: Optional[RemoteHost],
        remote_cmd: List[str]
    ) -> List[str]:
        """构建安全的SSH命令（避免命令注入）

        Args:
            host: 远程主机（None表示本机执行）
            remote_cmd: 远程命令列表

        Returns:
            完整命令列表（适合subprocess.run）
        """
        if host is None:
            return remote_cmd

        # 使用列表形式避免shell注入
        # 添加SSH选项绕过SSH配置中的限制
        ssh_target = host.ssh_alias or f"{host.user}@{host.hostname}"
        return [
            "ssh",
            "-o", "RemoteCommand=none",
            "-o", "RequestTTY=no",
            ssh_target
        ] + remote_cmd

    def _exec_ssh_cmd(
        self,
        host: Optional[RemoteHost],
        cmd_parts: List[str],
        timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """执行SSH命令（安全封装）

        Args:
            host: 远程主机
            cmd_parts: 命令部分列表（会被shlex.quote处理）
            timeout: 超时秒数

        Returns:
            subprocess结果
        """
        full_cmd = self._build_ssh_cmd(host, cmd_parts)
        return subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

    def _safe_quote(self, value: str) -> str:
        """安全转义字符串用于shell命令"""
        return shlex.quote(value)

    # ========== tmux映射扫描（默认实现） ==========

    def scan_tmux_mappings(self, host: Optional[RemoteHost] = None) -> Dict[str, TmuxMapping]:
        """扫描tmux会话映射（session_id -> tmux_info）

        算法：
        1. tmux list-sessions获取所有session
        2. 获取每个pane的PID
        3. lsof获取cwd
        4. 匹配工具进程名
        5. 根据cwd找到session目录
        """
        mappings: Dict[str, TmuxMapping] = {}

        try:
            # Step 1: 获取所有tmux会话
            result = self._exec_ssh_cmd(
                host,
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                timeout=10
            )

            if result.returncode != 0:
                return mappings

            session_names = result.stdout.strip().split("\n")

            for session_name in session_names:
                if not session_name:
                    continue

                self._scan_tmux_session_panes(host, session_name, mappings)

        except subprocess.TimeoutExpired:
            pass

        return mappings

    def _scan_tmux_session_panes(
        self,
        host: Optional[RemoteHost],
        session_name: str,
        mappings: Dict[str, TmuxMapping]
    ) -> None:
        """扫描单个tmux session的所有pane"""
        try:
            # 获取所有pane的PID
            result = self._exec_ssh_cmd(
                host,
                ["tmux", "list-panes", "-a", "-t", session_name, "-F", "#{pane_pid}"],
                timeout=10
            )

            if result.returncode != 0:
                return

            pane_pids = result.stdout.strip().split("\n")

            for pane_pid in pane_pids:
                if not pane_pid:
                    continue

                self._scan_tmux_pane_process(host, session_name, int(pane_pid), mappings)

        except (subprocess.TimeoutExpired, ValueError):
            pass

    def _scan_tmux_pane_process(
        self,
        host: Optional[RemoteHost],
        session_name: str,
        pane_pid: int,
        mappings: Dict[str, TmuxMapping]
    ) -> None:
        """扫描单个pane的进程"""
        try:
            # 检查是否是目标工具进程
            result = self._exec_ssh_cmd(
                host,
                ["ps", "-p", str(pane_pid), "-o", "command="],
                timeout=5
            )

            if result.returncode != 0:
                return

            cmd = result.stdout.strip()

            # 检查是否匹配当前工具
            if self.tool_info.executable not in cmd and self.tool_info.name not in cmd:
                return

            # 获取cwd
            cwd_result = self._exec_ssh_cmd(
                host,
                ["lsof", "-p", str(pane_pid)],
                timeout=5
            )

            if cwd_result.returncode != 0:
                return

            # 解析cwd
            for line in cwd_result.stdout.split("\n"):
                if "cwd" in line:
                    parts = line.split()
                    if len(parts) >= 9:
                        cwd = parts[-1]
                        session_id = self._find_session_id_by_cwd(host, cwd)
                        if session_id:
                            mappings[session_id] = TmuxMapping(
                                tmux_session_name=session_name,
                                tmux_window_id=0,
                                pane_pid=pane_pid,
                                is_attached=True  # 简化判断
                            )
                        break

        except subprocess.TimeoutExpired:
            pass

    def _find_session_id_by_cwd(
        self,
        host: Optional[RemoteHost],
        cwd: str
    ) -> Optional[str]:
        """根据cwd找到对应的session_id"""
        # 子类根据各自存储结构实现
        return None

    # ========== 恢复流程（模板方法） ==========

    def recover_session(
        self,
        session: Any,
        host: Optional[RemoteHost] = None
    ) -> bool:
        """恢复会话的通用流程（模板方法）

        流程：
        1. 检查是否有已有tmux连接
        2. 有 → attach
        3. 无 → 创建新tmux并恢复
        """
        tmux_info = self._find_existing_tmux(session, host)

        if tmux_info:
            return self._attach_tmux(tmux_info, host)
        else:
            return self._create_and_recover(session, host)

    def _find_existing_tmux(
        self,
        session: Any,
        host: Optional[RemoteHost]
    ) -> Optional[TmuxMapping]:
        """查找已有tmux连接"""
        if hasattr(session, 'tmux_info') and session.tmux_info:
            return session.tmux_info

        # 扫描最新映射
        mappings = self.scan_tmux_mappings(host)
        if hasattr(session, 'meta') and hasattr(session.meta, 'session_id'):
            return mappings.get(session.meta.session_id)
        return None

    @abstractmethod
    def _attach_tmux(
        self,
        tmux_info: TmuxMapping,
        host: Optional[RemoteHost]
    ) -> bool:
        """attach到已有tmux（子类实现）"""
        pass

    @abstractmethod
    def _create_and_recover(
        self,
        session: Any,
        host: Optional[RemoteHost]
    ) -> bool:
        """创建新tmux并恢复（子类实现）"""
        pass

    # ========== 会话详情（默认实现） ==========

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        return {}

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话对话历史"""
        return []