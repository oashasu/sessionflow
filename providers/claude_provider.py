"""Claude Code Provider - 迁移现有逻辑并加入SSH安全修复"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from .base_provider import BaseSessionProvider
from .protocol import ToolInfo, TmuxMapping, RemoteHost

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseSessionProvider):
    """Claude Code Provider

    功能：
    - 扫描 ~/.claude/projects/*.jsonl
    - 扫描 ~/.claude/sessions/*.json（活跃会话）
    - tmux映射扫描
    - iTerm2启动恢复
    """

    # Claude Code目录常量
    PROJECTS_DIR = Path.home() / ".claude" / "projects"
    SESSIONS_DIR = Path.home() / ".claude" / "sessions"

    @property
    def tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="claude",
            display_name="Claude Code",
            version="unknown",  # 避免循环依赖，不在此调用get_version
            executable="claude",
            session_dir="~/.claude/projects/",
            supports_resume=True,
            resume_arg_format="claude --resume {id}",
            schema_version="1.0"
        )

    def _scan_impl(self, host: Optional[RemoteHost]) -> List[Any]:
        """核心扫描实现"""
        if host:
            return self._scan_remote_impl(host)
        return self._scan_local_impl()

    def _scan_local_impl(self) -> List[Any]:
        """扫描本机Claude会话"""
        from core.models import SessionMeta, SessionRecord, extract_project_name
        from core.parser import find_ai_title, get_jsonl_summary

        sessions = []

        # 1. 扫描活跃会话
        active_sessions = self._scan_active_sessions()
        sessions.extend(active_sessions)

        # 2. 扫描历史会话（JSONL）
        history_sessions = self._scan_history_sessions()
        active_ids = {s.meta.session_id for s in active_sessions}

        for s in history_sessions:
            if s.meta.session_id not in active_ids:
                sessions.append(s)

        return sessions

    def _scan_active_sessions(self) -> List[Any]:
        """扫描活跃会话（sessions/*.json）"""
        from core.models import SessionMeta, SessionRecord, extract_project_name
        from core.parser import find_ai_title

        sessions = []

        if not self.SESSIONS_DIR.exists():
            return sessions

        for json_file in self.SESSIONS_DIR.glob("*.json"):
            try:
                meta = self._parse_session_json(json_file)
                if meta:
                    project_name = extract_project_name(meta.cwd)
                    log_path = self._find_jsonl_path(meta.session_id, meta.cwd)
                    recovery_cmd = self.generate_recovery_cmd(meta.session_id, meta.cwd)

                    topic = None
                    if log_path:
                        topic = find_ai_title(Path(log_path))

                    record = SessionRecord(
                        meta=meta,
                        project_name=project_name,
                        log_path=log_path,
                        recovery_cmd=recovery_cmd,
                        topic=topic,
                        tool_type="claude",
                    )
                    sessions.append(record)
            except Exception as e:
                logger.warning(f"Failed to parse {json_file}: {e}")
                continue

        return sessions

    def _scan_history_sessions(self) -> List[Any]:
        """扫描历史会话（projects目录JSONL）"""
        from core.models import SessionMeta, SessionRecord, extract_project_name
        from core.parser import get_jsonl_summary

        sessions = []

        if not self.PROJECTS_DIR.exists():
            return sessions

        for project_dir in self.PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            # 默认cwd（从目录名解码，可能不准确）
            default_cwd = self._decode_project_dir(project_dir.name)

            # 使用递归glob扫描所有JSONL文件（包括subagents目录）
            for jsonl_file in project_dir.glob("**/*.jsonl"):
                # 跳过.meta.json文件
                if jsonl_file.name.endswith(".meta.json"):
                    continue

                # 根据文件路径判断是否为子agent会话
                # 子agent文件路径包含 subagents/ 目录或文件名以 agent- 开头
                is_subagent = "subagents" in jsonl_file.parts or jsonl_file.name.startswith("agent-")
                entrypoint = "sdk-cli" if is_subagent else "cli"

                session_id = jsonl_file.stem

                try:
                    summary = get_jsonl_summary(jsonl_file)
                    topic = summary.get("topic") or summary.get("first_user_message")
                    stats = summary.get("stats", {})
                    # 使用JSONL中的真实cwd（如果有），否则使用解码的cwd
                    cwd = summary.get("cwd") or default_cwd

                    meta = SessionMeta(
                        session_id=session_id,
                        cwd=cwd,
                        status="closed",
                        started_at=0,
                        updated_at=int(jsonl_file.stat().st_mtime * 1000),
                    )

                    record = SessionRecord(
                        meta=meta,
                        project_name=extract_project_name(cwd),
                        log_path=str(jsonl_file),
                        recovery_cmd="",  # 已关闭会话无法恢复
                        topic=topic,
                        tool_type="claude",
                        is_subagent=is_subagent,
                        entrypoint=entrypoint,
                    )
                    record.stats = stats
                    sessions.append(record)
                except Exception:
                    continue

        return sessions

    def _scan_remote_impl(self, host: RemoteHost) -> List[Any]:
        """SSH扫描远程Claude会话（安全实现）"""
        from core.models import SessionMeta, SessionRecord, extract_project_name

        sessions = []

        # 直接传递完整命令字符串，让远程shell处理$HOME展开
        find_cmd = "find $HOME/.claude/projects/ -name '*.jsonl' -type f"
        result = self._exec_ssh_cmd(host, [find_cmd], timeout=30)

        if result.returncode != 0:
            logger.warning(f"Remote scan failed: {result.stderr}")
            return sessions

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                # 解析远程路径格式
                # ~/.claude/projects/-Users-xxx-project/session-id.jsonl
                jsonl_path = line.strip()
                parts = jsonl_path.split("/")

                # 找到session_id和目录编码
                session_id = Path(jsonl_path).stem
                dir_encoded = parts[-2] if len(parts) >= 2 else ""

                cwd = self._decode_project_dir(dir_encoded)

                meta = SessionMeta(
                    session_id=session_id,
                    cwd=cwd,
                    status="remote",
                    started_at=0,
                    updated_at=0,
                )

                record = SessionRecord(
                    meta=meta,
                    project_name=extract_project_name(cwd),
                    log_path=jsonl_path,
                    recovery_cmd=self.generate_recovery_cmd(session_id, cwd),
                    topic=None,
                    tool_type="claude",
                )
                sessions.append(record)
            except Exception:
                continue

        return sessions

    def _find_session_id_by_cwd(
        self,
        host: Optional[RemoteHost],
        cwd: str
    ) -> Optional[str]:
        """根据cwd找到对应的session_id"""
        encoded = self._encode_path(cwd)

        # 构建安全命令
        project_dir = self._safe_quote(f"{self.tool_info.session_dir}/{encoded}")
        find_cmd = f"ls -t {project_dir}/*.jsonl 2>/dev/null | head -1"

        result = self._exec_ssh_cmd(host, ["sh", "-c", find_cmd], timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).stem

        return None

    def _find_jsonl_path(self, session_id: str, cwd: str) -> Optional[str]:
        """从cwd映射到projects目录，找到JSONL文件"""
        encoded = self._encode_path(cwd)
        project_dir = self.PROJECTS_DIR / encoded

        if not project_dir.exists():
            return None

        # 精确匹配
        for jsonl_file in project_dir.glob("*.jsonl"):
            if session_id[:8] in jsonl_file.name or session_id in jsonl_file.name:
                return str(jsonl_file)

        # 返回最新文件
        jsonl_files = list(project_dir.glob("*.jsonl"))
        if jsonl_files:
            return str(max(jsonl_files, key=lambda f: f.stat().st_mtime))

        return None

    def _encode_path(self, path: str) -> str:
        """编码路径为Claude Code格式"""
        path = path.lstrip("/")
        encoded = "-" + path.replace("/", "-")

        if encoded.startswith("-~"):
            home = str(Path.home())
            actual_path = path.replace("~", home).lstrip("/")
            encoded = "-" + actual_path.replace("/", "-")

        return encoded

    def _detect_entrypoint(self, jsonl_path: Path) -> Optional[str]:
        """检测会话入口类型（cli/sdk-cli）"""
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if "entrypoint" in data:
                            return data.get("entrypoint")
                    except json.JSONDecodeError:
                        continue
                    # 只检查前几行，避免读取整个文件
                    if f.tell() > 5000:
                        break
        except Exception:
            pass
        return None

    def _decode_project_dir(self, encoded: str) -> str:
        """解码项目目录名回原始路径"""
        if encoded.startswith("-"):
            path = encoded[1:]
            path = path.replace("-", "/")
            return "/" + path
        return encoded

    def _parse_session_json(self, json_path: Path) -> Optional[Any]:
        """解析会话JSON文件"""
        from core.models import SessionMeta

        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

            return SessionMeta(
                session_id=data.get("sessionId", ""),
                cwd=data.get("cwd", ""),
                status=data.get("status", "idle"),
                started_at=data.get("startedAt", 0),
                updated_at=data.get("updatedAt", 0),
                pid=data.get("pid"),
                version=data.get("version"),
            )
        except Exception:
            return None

    # ========== 恢复逻辑 ==========

    def recover_local_session(self, session: Any) -> bool:
        """本机iTerm2打开"""
        from providers.terminals.iterm2 import ITerm2Terminal

        terminal = ITerm2Terminal()
        cmd = self.generate_recovery_cmd(session.meta.session_id, session.meta.cwd)

        return terminal.open_session(session.meta.cwd, cmd)

    def recover_remote_session(self, session: Any, host: RemoteHost) -> bool:
        """远程SSH + tmux恢复"""
        tmux_info = self._find_existing_tmux(session, host)

        if tmux_info:
            # attach到已有tmux
            return self._attach_tmux(tmux_info, host)
        else:
            # 创建新tmux并恢复
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

        # 使用命令链：先SSH连接，再在远程执行tmux attach
        # 这样确保tmux attach在远程shell内执行
        cmds = [
            f"ssh {ssh_target}",
            f"tmux attach -t {tmux_info.tmux_session_name}"
        ]

        return terminal.open_session_chain(str(Path.home()), cmds)

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

        # SSH连接 -> 创建tmux -> cd -> 恢复
        cmds = [
            f"ssh {ssh_target}",
            f"tmux new -s 'claude-{session_short_id}' -c '{session.meta.cwd}'",
            self.generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        ]

        return terminal.open_session_chain(session.meta.cwd, cmds)

    # ========== 会话详情 ==========

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        from core.parser import get_jsonl_summary

        # 查找jsonl文件
        # 这里简化实现，实际需要根据cwd查找
        return {}

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话对话历史"""
        from core.parser import parse_jsonl_file

        # 简化实现
        return []