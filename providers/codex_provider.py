"""Codex Provider - OpenAI Codex CLI 会话管理"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base_provider import BaseSessionProvider
from .protocol import ToolInfo, TmuxMapping, RemoteHost

logger = logging.getLogger(__name__)


class CodexProvider(BaseSessionProvider):
    """Codex CLI Provider

    功能：
    - 扫描 ~/.codex/session_index.jsonl（会话索引）
    - 扫描 ~/.codex/sessions/YYYY/MM/DD/*.jsonl（详细日志）
    - 支持codex resume恢复会话
    """

    # Codex目录常量
    CODEX_DIR = Path.home() / ".codex"
    SESSION_INDEX = CODEX_DIR / "session_index.jsonl"
    SESSIONS_DIR = CODEX_DIR / "sessions"

    @property
    def tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="codex",
            display_name="Codex CLI",
            version="unknown",  # 避免循环依赖，不在此调用get_version
            executable="codex",
            session_dir="~/.codex/sessions/",
            supports_resume=True,
            resume_arg_format="codex resume {id}",
            schema_version="1.0"
        )

    def _scan_impl(self, host: Optional[RemoteHost]) -> List[Any]:
        """核心扫描实现"""
        if host:
            return self._scan_remote_impl(host)
        return self._scan_local_impl()

    def _scan_local_impl(self) -> List[Any]:
        """扫描本机Codex会话"""
        from core.models import SessionMeta, SessionRecord, extract_project_name

        sessions = []

        # 1. 扫描session_index.jsonl（最新会话索引）
        index_sessions = self._scan_session_index()
        sessions.extend(index_sessions)

        # 2. 扫描sessions目录下的所有会话日志（补充历史）
        history_sessions = self._scan_sessions_directory()
        index_ids = {s.meta.session_id for s in index_sessions}

        for s in history_sessions:
            if s.meta.session_id not in index_ids:
                sessions.append(s)

        return sessions

    def _scan_session_index(self) -> List[Any]:
        """扫描session_index.jsonl"""
        from core.models import SessionMeta, SessionRecord, extract_project_name

        sessions = []

        if not self.SESSION_INDEX.exists():
            return sessions

        try:
            with open(self.SESSION_INDEX, encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        session_id = data.get("id", "")
                        thread_name = data.get("thread_name", "")
                        updated_at_str = data.get("updated_at", "")

                        # 解析时间
                        updated_at = 0
                        if updated_at_str:
                            try:
                                dt = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                                updated_at = int(dt.timestamp() * 1000)
                            except ValueError:
                                pass

                        # 从session_id映射到cwd（需要扫描session文件）
                        cwd, log_path = self._find_cwd_for_session(session_id)

                        meta = SessionMeta(
                            session_id=session_id,
                            cwd=cwd,
                            status="active",  # index中的会话通常活跃
                            started_at=0,
                            updated_at=updated_at,
                        )

                        record = SessionRecord(
                            meta=meta,
                            project_name=extract_project_name(cwd) if cwd else "unknown",
                            log_path=log_path,
                            recovery_cmd=self.generate_recovery_cmd(session_id, cwd),
                            topic=thread_name,
                            tool_type="codex",
                        )
                        sessions.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to read session_index: {e}")

        return sessions

    def _scan_sessions_directory(self) -> List[Any]:
        """扫描sessions/YYYY/MM/DD/*.jsonl"""
        from core.models import SessionMeta, SessionRecord, extract_project_name

        sessions = []

        if not self.SESSIONS_DIR.exists():
            return sessions

        # 按日期目录扫描
        for year_dir in self.SESSIONS_DIR.iterdir():
            if not year_dir.is_dir():
                continue

            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue

                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue

                    for jsonl_file in day_dir.glob("*.jsonl"):
                        try:
                            session_data = self._parse_session_file(jsonl_file)
                            if session_data:
                                session_id = session_data.get("id", "")
                                cwd = session_data.get("cwd", "")
                                timestamp_str = session_data.get("timestamp", "")

                                # 解析时间
                                updated_at = 0
                                if timestamp_str:
                                    try:
                                        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                        updated_at = int(dt.timestamp() * 1000)
                                    except ValueError:
                                        pass

                                meta = SessionMeta(
                                    session_id=session_id,
                                    cwd=cwd,
                                    status="closed",
                                    started_at=updated_at,
                                    updated_at=int(jsonl_file.stat().st_mtime * 1000),
                                )

                                # 尝试获取thread_name
                                thread_name = self._extract_thread_name(jsonl_file)

                                record = SessionRecord(
                                    meta=meta,
                                    project_name=extract_project_name(cwd) if cwd else "unknown",
                                    log_path=str(jsonl_file),
                                    recovery_cmd=self.generate_recovery_cmd(session_id, cwd),
                                    topic=thread_name,
                                    tool_type="codex",
                                )
                                sessions.append(record)
                        except Exception:
                            continue

        return sessions

    def _parse_session_file(self, jsonl_path: Path) -> Optional[Dict]:
        """解析session文件的session_meta行"""
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                # 只读第一行获取session_meta
                first_line = f.readline()
                if first_line:
                    data = json.loads(first_line.strip())
                    if data.get("type") == "session_meta":
                        return data.get("payload", {})
        except Exception:
            pass
        return None

    def _extract_thread_name(self, jsonl_path: Path) -> Optional[str]:
        """从session文件提取thread_name（第一用户消息）"""
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        # 查找用户消息
                        if data.get("role") == "user":
                            content = data.get("content", "")
                            if isinstance(content, str) and content:
                                # 截取前50字符
                                return content[:50] if len(content) > 50 else content
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return None

    def _find_cwd_for_session(self, session_id: str) -> tuple[str, Optional[str]]:
        """根据session_id查找cwd"""
        # 从session_index的session_id格式推断文件路径
        # session_id格式: 019e6015-7f0c-7f20-927b-a584d31a55e5
        # 文件路径格式: rollout-2026-05-26T01-01-22-{session_id}.jsonl

        if not self.SESSIONS_DIR.exists():
            return "", None

        # 搜索匹配的文件
        for jsonl_file in self.SESSIONS_DIR.glob("**/*.jsonl"):
            if session_id in jsonl_file.name:
                session_data = self._parse_session_file(jsonl_file)
                if session_data:
                    cwd = session_data.get("cwd", "")
                    return cwd, str(jsonl_file)

        return "", None

    def _scan_remote_impl(self, host: RemoteHost) -> List[Any]:
        """SSH扫描远程Codex会话"""
        from core.models import SessionMeta, SessionRecord, extract_project_name

        sessions = []

        # 安全构建命令
        session_dir = self._safe_quote(self.tool_info.session_dir)
        find_cmd = f"find {session_dir} -name '*.jsonl' -type f"

        result = self._exec_ssh_cmd(host, ["sh", "-c", find_cmd], timeout=30)

        if result.returncode != 0:
            logger.warning(f"Remote scan failed: {result.stderr}")
            return sessions

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                jsonl_path = line.strip()
                session_id = self._extract_session_id_from_path(jsonl_path)

                # 远程扫描无法获取cwd，需要从session文件解析
                # 这里简化处理，返回基本信息
                meta = SessionMeta(
                    session_id=session_id,
                    cwd="",  # 远程需要额外获取
                    status="remote",
                    started_at=0,
                    updated_at=0,
                )

                record = SessionRecord(
                    meta=meta,
                    project_name="remote",
                    log_path=jsonl_path,
                    recovery_cmd=self.generate_recovery_cmd(session_id, ""),
                    topic=None,
                    tool_type="codex",
                )
                sessions.append(record)
            except Exception:
                continue

        return sessions

    def _extract_session_id_from_path(self, path: str) -> str:
        """从路径提取session_id"""
        # rollout-2026-05-26T01-01-22-{uuid}.jsonl
        filename = Path(path).stem
        parts = filename.split("-")
        if len(parts) >= 7:
            # UUID部分
            return parts[-1]
        return filename

    def _find_session_id_by_cwd(
        self,
        host: Optional[RemoteHost],
        cwd: str
    ) -> Optional[str]:
        """根据cwd找到对应的session_id"""
        # Codex不按cwd组织目录，需要扫描session文件内容
        # 简化实现：搜索最近包含cwd的session
        session_dir = self._safe_quote(self.tool_info.session_dir)
        grep_cmd = f"grep -l 'cwd.*{self._safe_quote(cwd)}' {session_dir}/**/*.jsonl 2>/dev/null | head -1"

        result = self._exec_ssh_cmd(host, ["sh", "-c", grep_cmd], timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            return self._extract_session_id_from_path(result.stdout.strip())

        return None

    # ========== 恢复逻辑 ==========

    def recover_local_session(self, session: Any) -> bool:
        """本机iTerm2打开Codex"""
        import sys
        from providers.terminals.iterm2 import ITerm2Terminal

        terminal = ITerm2Terminal()
        cmd = self.generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        print(f"[CodexProvider DEBUG] Generated command: {cmd}", flush=True)

        # Codex resume需要在cwd目录执行
        cwd = session.meta.cwd or str(Path.home())

        return terminal.open_session(cwd, cmd)

    def recover_remote_session(self, session: Any, host: RemoteHost) -> bool:
        """远程SSH + tmux恢复"""
        tmux_info = self._find_existing_tmux(session, host)

        if tmux_info:
            return self._attach_tmux(tmux_info, host)
        else:
            return self._create_and_recover(session, host)

    def _attach_tmux(
        self,
        tmux_info: TmuxMapping,
        host: Optional[RemoteHost]
    ) -> bool:
        """attach到已有tmux"""
        from providers.terminals.iterm2 import ITerm2Terminal

        if host is None:
            return False

        terminal = ITerm2Terminal()
        ssh_target = host.ssh_alias or f"{host.user}@{host.hostname}"
        cmd = f"ssh {ssh_target} && tmux attach -t '{tmux_info.tmux_session_name}'"

        return terminal.open_session(str(Path.home()), cmd)

    def _create_and_recover(
        self,
        session: Any,
        host: Optional[RemoteHost]
    ) -> bool:
        """创建新tmux并恢复"""
        from providers.terminals.iterm2 import ITerm2Terminal

        if host is None:
            return self.recover_local_session(session)

        terminal = ITerm2Terminal()
        ssh_target = host.ssh_alias or f"{host.user}@{host.hostname}"
        session_short_id = session.meta.session_id[:8]
        cwd = session.meta.cwd or str(Path.home())

        cmds = [
            f"ssh {ssh_target}",
            f"tmux new -s 'codex-{session_short_id}' -c '{cwd}'",
            self.generate_recovery_cmd(session.meta.session_id, cwd)
        ]

        return terminal.open_session_chain(cwd, cmds)

    # ========== 会话详情 ==========

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        # 简化实现
        return {}

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话对话历史"""
        cwd, log_path = self._find_cwd_for_session(session_id)

        if not log_path:
            return []

        history = []
        try:
            with open(log_path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    try:
                        data = json.loads(line.strip())
                        if data.get("role") in ["user", "assistant"]:
                            history.append({
                                "role": data.get("role"),
                                "content": data.get("content", ""),
                                "timestamp": data.get("timestamp", ""),
                            })
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return history